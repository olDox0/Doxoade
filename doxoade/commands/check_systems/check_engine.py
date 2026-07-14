# doxoade/doxoade/commands/check_systems/check_engine.py
"""Motor de Auditoria - Casa de Máquinas (PASC 8.5)."""
import os
import sys
import re
import ast
import json
import hashlib
# [DOX-UNUSED] import shutil
# [DOX-UNUSED] from typing import Any
from click import progressbar
from .check_state import CheckState
# [DOX-UNUSED] from .check_utils import _calculate_incident_stats
from doxoade.tools.analysis import _get_code_snippet
from doxoade.tools.filesystem import _find_project_root
from doxoade.tools.memory_pool import finding_arena
from doxoade.tools.telemetry_tools.logger import chief_heartbeat
# [DOX-UNUSED] from doxoade.tools.vulcan.indent_fixer import perform_indent_surgery

def _extract_archaeology_symbol(msg: str):
    """Extrai com alta precisão o símbolo (variável, função ou parâmetro) de mensagens de aviso."""
    # Normaliza aspas simples, duplas e backticks (crases) de linters
    msg_clean = msg.replace('`', "'").replace('"', "'")
    match = re.search(r"'(.*?)'", msg_clean)
    if match:
        sym = match.group(1).strip()
        # Remove prefixos descritivos comuns injetados por compiladores/linters
        for prefix in ['global ', 'variable ', 'local variable ', 'function ', 'parameter ', 'unused ']:
            if sym.startswith(prefix):
                sym = sym[len(prefix):].strip()
        if sym and ' ' not in sym:
            return sym
            
    # Heurística secundária para atribuições sintáticas sem aspas na mensagem
    if 'assigned' in msg.lower() or 'unused' in msg.lower():
        words = re.split(r"[\s'\"`]+", msg)
        for w in words:
            w_clean = w.strip().replace("'", "").replace('"', "").replace("`", "")
            if w_clean.isidentifier() and w_clean not in {
                'is', 'never', 'assigned', 'unused', 'variable', 'local', 'global', 'parameter', 'but', 'to'
            }:
                return w_clean
    return None

def _get_git_root(file_path: str) -> str:
    """Obtém o diretório raiz absoluto do repositório Git de forma precisa."""
    import subprocess
    try:
        res = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'], 
            cwd=os.path.dirname(os.path.abspath(file_path)), 
            capture_output=True, text=True, encoding='utf-8', errors='ignore'
        )
        if res.returncode == 0:
            return os.path.normpath(res.stdout.strip())
    except Exception:
        pass
    return None

def _get_git_commit_snippet(file_path: str, commit_hash: str, line_number: int, context_lines=2):
    """Recupera um trecho de código de um arquivo em um commit específico via 'git show'."""
    import subprocess
    
    project_root = _get_git_root(file_path) or _find_project_root(os.path.dirname(os.path.abspath(file_path)))
    if not project_root:
        chief_heartbeat("HORUS", "GIT_SNIPPET_ERROR", {
            "file": file_path,
            "error": "Incapaz de localizar a raiz do projeto Git."
        })
        return None
    
    # Normaliza ambos os caminhos de forma nativa para evitar falhas de os.path.relpath no Windows
    norm_file_path = os.path.normpath(os.path.abspath(file_path))
    norm_project_root = os.path.normpath(os.path.abspath(project_root))
    
    rel_path = os.path.relpath(norm_file_path, norm_project_root).replace('\\', '/')
    cmd = ['git', 'show', f'{commit_hash}:{rel_path}']
    try:
        res = subprocess.run(cmd, cwd=norm_project_root, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if res.returncode == 0:
            lines = res.stdout.splitlines()
            idx = line_number - 1
            # Evita estouro de índice caso o arquivo histórico possua tamanhos diferentes
            idx = min(max(0, idx), len(lines) - 1)
            
            snippet = {}
            start = max(0, idx - context_lines)
            end = min(len(lines), idx + context_lines + 1)
            for i in range(start, end):
                snippet[str(i + 1)] = lines[i]
            return snippet
        else:
            # Envia a falha do Git para a telemetria do Hades/Hórus para diagnóstico rápido
            chief_heartbeat("HORUS", "GIT_SNIPPET_ERROR", {
                "file": rel_path,
                "commit": commit_hash,
                "exit_code": res.returncode,
                "stderr": res.stderr.strip()
            })
    except Exception as e:
        chief_heartbeat("HORUS", "GIT_SNIPPET_ERROR", {
            "file": rel_path,
            "commit": commit_hash,
            "error": str(e)
        })
    return None

def _run_integrity_check(files, project_root):
    """Verifica se as chamadas de função em 'files' batem com as definições no projeto."""
    from ...probes.manager import ProbeManager
    from ..check import _get_probe_path
    manager = ProbeManager(sys.executable, project_root)
    res = manager.execute(_get_probe_path('xref_probe.py'), project_root, payload={'files': files})
    return json.loads(res['stdout']) if res['success'] else []

def run_audit_engine(state, io_manager, **kwargs):
    from doxoade.probes.manager import ProbeManager
    finding_arena.flush() 
    
    # Tratamento dual de parâmetros de cache para garantir compatibilidade com Click
    no_cache_active = kwargs.get('no_cache') or (kwargs.get('cache') is False)
    
    manager = ProbeManager(sys.executable, state.root)
    files = io_manager.resolve_files(kwargs.get('target_files'))
    cache = {} if no_cache_active else io_manager.load_cache()
    to_scan = _filter_by_cache(files, cache, io_manager, state, no_cache_active)
    finding_arena.recycled_count = 0
    
    if to_scan:
        with progressbar(to_scan, label='Auditando') as bar:
            for fp, cache_key, mtime, size in bar:
                finding_arena.flush() 
                results = _scan_single_file(fp, manager, kwargs)
                
                for res in results:
                    if kwargs.get('archaeology') and res.get('line', 0) > 0:
                        from doxoade.tools.git import _get_line_history, _find_symbol_crime_scene
                        from doxoade.tools.streamer import ufs
                        
                        norm_file = os.path.normpath(os.path.abspath(res['file']))
                        
                        symbol = _extract_archaeology_symbol(res['message'])
                        # Coleta Arqueológica de Nascimento
                        res['archaeology'] = _get_line_history(norm_file, res['line'])
                        if res['archaeology'] and res['archaeology'].get('hash'):
                            res['archaeology']['snippet'] = _get_git_commit_snippet(
                                norm_file, res['archaeology']['hash'], res['line']
                            )
                        
                        if symbol:
                            lines = ufs.get_lines(norm_file)
                            res['ghost_references'] = [
                                {'line': i+1, 'text': ln.strip()} 
                                for i, ln in enumerate(lines) 
                                if symbol in ln and (i+1) != res['line']
                            ]
                            # Rastro de Morte (Atrição)
                            res['attrition'] = _find_symbol_crime_scene(norm_file, symbol)
                            if res['attrition'] and res['attrition'].get('hash'):
                                attr_line = res['attrition'].get('line', res['line'])
                                res['attrition']['snippet'] = _get_git_commit_snippet(
                                    norm_file, res['attrition']['hash'], attr_line
                                )
                    
                    # --- SINCRONIA COM A ARENA ---
                    f_hash = hashlib.sha256(res['message'].encode('utf-8')).hexdigest()
                    arena_res = finding_arena.rent(
                        res['severity'], res['category'], res['message'], res['file'], res['line']
                    )
                    
                    if 'archaeology' in res: arena_res['archaeology'] = res['archaeology']
                    if 'ghost_references' in res: arena_res['ghost_references'] = res['ghost_references']
                    if 'attrition' in res: arena_res['attrition'] = res['attrition']
                    
                    arena_res['finding_hash'] = f_hash
                    arena_res['snippet'] = _get_code_snippet(res['file'], res.get('line', 0))
                    state.register_finding(arena_res)

                if mtime > 0 and (not any((f.get('category') == 'SYSTEM' for f in results))):
                    cache[cache_key] = {'mtime': mtime, 'size': size, 'findings': results}
    
    if kwargs.get('clones'):
        _run_clone_detection(files, manager, state) 
    if not no_cache_active:
        io_manager.save_cache(cache)

def _scan_single_file(fp, manager, kwargs):
    from doxoade.tools.governor import governor
    if governor.pace(file_path=fp, force=kwargs.get('full_power')):
        return [{'severity': 'INFO', 'category': 'SYSTEM', 'message': 'ALB_REDUCED', 'file': fp, 'line': 0}]
    if fp.endswith(('.c', '.cpp', '.h', '.hpp')): 
        return _run_c_cpp_checks(fp)
    findings = _run_syntax_check(fp, manager, kwargs)
    if findings is None: findings = []
    if any(f.get('severity') == 'CRITICAL' for f in findings):
        return findings
    findings.extend(_run_static_probes(fp, manager))
    if not kwargs.get('fast'):
        findings.extend(_run_style_check(fp))
    return findings

def _run_syntax_check(fp, manager, kwargs):
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as src:
            source = src.read()
        ast.parse(source)
        return []
    except (SyntaxError, IndentationError) as e:
        msg = str(e).lower()
        if "indent" in msg or "unindent" in msg or "expected an indented" in msg:
            cat = 'INDENT'
            action = 'INDENT_ERR'
        else:
            cat = 'SYNTAX'
            action = None
        
        return [{
            'severity': 'CRITICAL',
            'category': cat,
            'message': f"Erro de Sintaxe: {str(e)}",
            'file': fp,
            'line': getattr(e, 'lineno', 0),
            'suggestion_action': action
        }]

def _run_style_check(f):
    from radon.visitors import ComplexityVisitor
    from doxoade.tools.streamer import ufs
    try:
        lines = ufs.get_lines(f)
        v = ComplexityVisitor.from_ast(ast.parse(''.join(lines)))
        return [{'severity': 'WARNING', 'category': 'COMPLEXITY', 'message': f"Função '{func.name}' complexa (CC: {func.complexity}).", 'file': f, 'line': func.lineno} for func in v.functions if func.complexity > 12]
    except Exception:
        return []

def _run_static_probes(f, manager):
    from ..check import _get_probe_path
    results = []
    res_pf = manager.execute(_get_probe_path('static_probe.py'), f)
    if res_pf['stdout']:
        for line in res_pf['stdout'].splitlines():
            m = re.match('^(.+):(\\d+):(?:\\d+):? (.+)$', line)
            if m:
                results.append({'severity': 'WARNING', 'category': 'STYLE', 'message': m.group(3), 'file': f, 'line': int(m.group(2))})
    res_ht = manager.execute(_get_probe_path('hunter_probe.py'), f)
    try:
        data = json.loads(res_ht['stdout'])
        for d in data if isinstance(data, list) else [data]:
            d['file'] = f
            results.append(d)
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context=f'Static Probes (Hunter) -> {os.path.basename(f)}', debug=True)
    return results

def _filter_by_cache(files, cache, io_manager, state, force_no_cache):
    to_scan = []
    for fp in files:
        mtime, size = io_manager.get_file_metadata(fp)
        cache_key = fp.replace('\\', '/')
        c_entry = cache.get(cache_key)
        if not force_no_cache and c_entry and (c_entry.get('mtime') == mtime):
            if not any((f.get('category') == 'SYSTEM' for f in c_entry.get('findings', []))):
                for f in c_entry.get('findings', []):
                    state.register_finding(f)
                continue
        to_scan.append((fp, cache_key, mtime, size))
    return to_scan

def _run_clone_detection(files, manager, state):
    from ..check import _get_probe_path
    res = manager.execute(_get_probe_path('clone_probe.py'), payload={'files': files})
    if res['success'] and res['stdout']:
        try:
            clones = json.loads(res['stdout'])
            for c in clones:
                state.register_finding(c)
        except Exception as e:
            from doxoade.tools.error_info import handle_error
            handle_error(e, context='Clone Detection JSON Parse', debug=True)

def run_check_logic(path: str, state=None, *_args, **kwargs):
    from .check_io import CheckIO
    from .check_filters import apply_filters
    from .check_refactor import analyze_refactor_opportunities
    from doxoade.tools.genesis import _enrich_findings_with_solutions, _enrich_with_dependency_analysis
    
    # Consolida argumentos posicionais do Click e de compatibilidade em um dicionário único
    params = dict(kwargs)
    arg_keys = ['archaeology', 'full_power', 'fast', 'clones', 'no_cache']
    for i, val in enumerate(_args):
        if i < len(arg_keys):
            params[arg_keys[i]] = val
            
    # Sincroniza flag nativo de no_cache do Click
    if params.get('cache') is False:
        params['no_cache'] = True
    
    # [DIAG] Print de console para rastreamento em nível de Engine
    import click
    from doxoade.tools.doxcolors import Fore, Style
    click.echo(f"   {Fore.CYAN}[ ENGINE_DEBUG ] consolidated_params = {params}{Style.RESET_ALL}")
    
    chief_heartbeat("HORUS", "ENGINE_RUN_CHECK_LOGIC_ARGS", {
        "path": path,
        "state_is_none": state is None,
        "args": str(_args),
        "kwargs": str(params)
    })
    
    io = CheckIO(path)
    no_cache_active = params.get('no_cache') or (params.get('cache') is False)
    state = CheckState(root=io.project_root, target_path=io.target_abs, is_full_power=params.get('full_power', False))
    
    run_audit_engine(state, io, **params)
    _enrich_findings_with_solutions(state.findings, state.root)
    _enrich_with_dependency_analysis(state.findings, path)
    apply_filters(state, **params)
    analyze_refactor_opportunities(state)
    return {'summary': state.summary, 'findings': state.findings, 'alb_files': state.alb_files}

def _run_c_cpp_checks(fp):
    import subprocess
    import re
    import os
    findings = []
    is_cpp = fp.endswith(('.cpp', '.hpp'))
    compiler = 'g++' if is_cpp else 'gcc'
    file_dir = os.path.dirname(os.path.abspath(fp))
    project_root = _find_project_root(file_dir)
    includes = [f'-I{file_dir}']
    if project_root:
        includes.append(f'-I{project_root}')
        for folder in ['include', 'src', 'inc']:
            p = os.path.join(project_root, folder)
            if os.path.isdir(p):
                includes.append(f'-I{p}')
        parent_dir = os.path.dirname(file_dir)
        if parent_dir and parent_dir != project_root:
            includes.append(f'-I{parent_dir}')
            for folder in ['include', 'src', 'inc']:
                p = os.path.join(parent_dir, folder)
                if os.path.isdir(p):
                    includes.append(f'-I{p}')
    cmd = [compiler, '-fsyntax-only', '-Wall', '-Wextra', '-Wpedantic'] + includes + [fp]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
        output = result.stderr
        if output:
            gcc_pattern = re.compile('^(.+?):(\\d+):(?:\\d+:)?\\s*(error|warning|note|fatal error):\\s*(.*)$', re.MULTILINE)
            for match in gcc_pattern.finditer(output):
                file_path_gcc = match.group(1)
                line_n = int(match.group(2))
                sev_str = match.group(3).lower()
                msg = match.group(4).strip()
                
                msg_lower = msg.lower()
                if 'no such file' in msg_lower or 'not found' in msg_lower or 'diretório ou arquivo não encontrado' in msg_lower:
                    continue
                
                if 'error' in sev_str:
                    severity = 'CRITICAL'
                    category = 'C_SYNTAX'
                elif 'warning' in sev_str:
                    severity = 'WARNING'
                    category = 'C-LINT'
                else:
                    severity = 'INFO'
                    category = 'STYLE'
                findings.append({'severity': severity, 'category': category, 'message': f'[{compiler}] {msg}', 'file': fp, 'line': line_n})
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            logic_branches = re.findall('\\b(?:if|for|while|catch|case)\\b', content)
            complexity = len(logic_branches) + 1
            if complexity > 20:
                findings.append({'severity': 'WARNING', 'category': 'COMPLEXITY', 'message': f'Arquivo excede limite de complexidade (CC Estimado: {complexity}).', 'file': fp, 'line': 1})
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context='Ponte w64devkit C/C++', silent=True)
        findings.append({'severity': 'ERROR', 'category': 'SYSTEM', 'message': f'Falha ao executar {compiler}. w64devkit está ativo?', 'file': fp, 'line': 0})
    return findings
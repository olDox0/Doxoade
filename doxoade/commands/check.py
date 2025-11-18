# doxoade/commands/check.py
import sys
import os
import ast
import json
import subprocess
import re
import click
import shutil
import hashlib
from pathlib import Path
from colorama import Fore
from io import StringIO
from pyflakes import api as pyflakes_api
from importlib import resources

# Linha corrigida, que não causa o ciclo
from .._version import __version__ as DOXOADE_VERSION

from ..shared_tools import (
    ExecutionLogger,
    _present_results,
    _get_code_snippet,
    _get_venv_python_executable,
    _get_project_config,
    collect_files_to_analyze,
    analyze_file_structure,
    _run_git_command
)

# AS STRINGS DAS SONDAS FORAM REMOVIDAS DAQUI!
def _get_probe_path(probe_name):
    """Encontra o caminho para um arquivo de sonda de forma segura."""
    try:
        # Python 3.9+
        with resources.path('doxoade.probes', probe_name) as probe_path:
            return str(probe_path)
    except (AttributeError, ModuleNotFoundError):
        # Fallback para Python < 3.9
        from pkg_resources import resource_filename
        return resource_filename('doxoade', f'probes/{probe_name}')

def _run_syntax_probe(file_path, python_executable, debug=False):
    findings = []
    # ALTERADO: Chama o arquivo da sonda em vez da string
    probe_path = _get_probe_path('syntax_probe.py')
    syntax_cmd = [python_executable, probe_path, file_path]
    try:
        result = subprocess.run(syntax_cmd, capture_output=True, text=True, encoding='utf-8', errors='backslashreplace')
        # ... (o resto da função continua igual) ...
        if debug:
            click.echo(Fore.CYAN + "\n--- [DEBUG-SYNTAX PROBE] ---")
            click.echo(f"  > Alvo: {file_path}")
            click.echo(f"  > RC Sonda Sintaxe: {result.returncode}")
            click.echo(f"  > STDERR Sintaxe:\n---\n{result.stderr.strip()}\n---")
            click.echo("--- [FIM DEBUG-SYNTAX PROBE] ---\n")

        if result.returncode != 0:
            line_match = re.search(r':(\d+):', result.stderr)
            line_num = int(line_match.group(1)) if line_match else 1
            findings.append({'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f"Erro de sintaxe impede a análise: {result.stderr.strip()}", 'file': file_path, 'line': line_num})
    except Exception as e:
        findings.append({'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f"Falha catastrófica ao invocar a sonda de sintaxe: {e}", 'file': file_path, 'line': line_num})
    return findings

def _run_pyflakes_probe(file_path, python_executable, debug=False):
    findings = []
    # ALTERADO: Chama o arquivo da sonda em vez da string
    probe_path = _get_probe_path('static_probe.py')
    pyflakes_cmd = [python_executable, probe_path, file_path]
    try:
        result = subprocess.run(pyflakes_cmd, capture_output=True, text=True, encoding='utf-8', errors='backslashreplace')
        # ... (o resto da função continua igual) ...
        if debug:
            click.echo(Fore.CYAN + "\n--- [DEBUG-CHECK] ---")
            click.echo(f"  > Alvo: {file_path}")
            click.echo(f"  > RC Sonda: {result.returncode}")
            click.echo(f"  > STDOUT Sonda:\n---\n{result.stdout.strip()}\n---")
            click.echo(f"  > STDERR Sonda:\n---\n{result.stderr.strip()}\n---")
            click.echo("--- [FIM DEBUG] ---\n")

        if result.stderr:
            if 'invalid syntax' in result.stderr.lower() or 'indentation' in result.stderr.lower():
                line_match = re.search(r':(\d+):', result.stderr)
                line_num = int(line_match.group(1)) if line_match else 1
                findings.append({'severity': 'CRITICAL', 'message': f"Erro de sintaxe impede a análise: {result.stderr.strip()}", 'file': file_path, 'line': line_num})
            else:
                findings.append({'severity': 'WARNING', 'message': "Sonda de análise estática reportou um erro.", 'file': file_path, 'line': 1, 'details': result.stderr})

        for line_error in result.stdout.strip().splitlines():
            match = re.match(r'(.+?):(\d+):(\d+):\s(.+)', line_error)
            if match:
                _, line_num, _, message_text = match.groups()
    
                # --- LÓGICA DE CLASSIFICAÇÃO APRIMORADA ---
                if 'imported but unused' in message_text or 'redefinition' in message_text:
                    severity = 'ERROR'
                    category = 'DEADCODE'
                elif 'undefined name' in message_text:
                    severity = 'CRITICAL'
                    category = 'RUNTIME-RISK'
                # Adicione mais regras aqui se necessário, como para f-strings
                elif "f-string is missing placeholders" in message_text:
                    severity = 'WARNING'
                    category = 'STYLE'
                else:
                    severity = 'WARNING'
                    category = 'STYLE' # Padrão para outros avisos do Pyflakes
    
                findings.append({
                    'severity': severity,
                    'category': category,
                    'message': message_text,
                    'file': file_path,
                    'line': int(line_num)
                })
    except Exception as e:
        findings.append({'severity': 'CRITICAL', 'message': f"Falha catastrófica ao invocar a sonda Pyflakes: {e}", 'file': file_path})
    return findings

def _run_import_probe(all_imports, venv_python, logger, search_path):
    unique_module_names = sorted(list({imp['module'] for imp in all_imports}))
    if not unique_module_names: return []
    try:
        # ALTERADO: Chama o arquivo da sonda em vez da string
        probe_path = _get_probe_path('import_probe.py')
        process = subprocess.run([venv_python, probe_path], input=json.dumps(unique_module_names), capture_output=True, text=True, check=True, encoding='utf-8')
        missing_from_venv = set(json.loads(process.stdout))
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.add_finding('CRITICAL', "A Sonda de Ambiente falhou.", details=str(e))
        return []
    # ... (o resto da função continua igual) ...
    if not missing_from_venv: return []
    truly_missing_modules = set()
    for module_name in missing_from_venv:
        potential_file = os.path.join(search_path, f"{module_name}.py")
        potential_package = os.path.join(search_path, module_name)
        if not os.path.exists(potential_file) and not os.path.isdir(potential_package):
            truly_missing_modules.add(module_name)
    if not truly_missing_modules: return []
    import_findings = []
    IGNORE_MODULES = {'setuptools', 'kivy', 'ia_core'}
    for imp in all_imports:
        if imp['module'] in truly_missing_modules and imp['module'] not in IGNORE_MODULES:
            import_findings.append({'severity': 'CRITICAL', 'category': 'DEPENDENCY', 'message': f"Import não resolvido: Módulo '{imp['module']}' não foi encontrado.", 'file': imp['file'], 'line': imp['line'], 'snippet': _get_code_snippet(imp['file'], imp['line'])})
    return import_findings

def _extract_imports(file_path):
    imports = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        if content.strip():
            tree = ast.parse(content, filename=file_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names: imports.append({'module': alias.name.split('.')[0], 'line': node.lineno, 'file': file_path})
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module: imports.append({'module': node.module.split('.')[0], 'line': node.lineno, 'file': file_path})
    except (SyntaxError, IOError):
        pass
    return imports
    
def _analyze_single_file_statically(file_path, python_executable, debug=False):
    syntax_findings = _run_syntax_probe(file_path, python_executable, debug)
    if syntax_findings:
        return syntax_findings, []
    pyflakes_findings = _run_pyflakes_probe(file_path, python_executable, debug)
    imports = _extract_imports(file_path)
    return pyflakes_findings, imports
    
def _fix_unused_imports(file_path, logger):
    """Comenta linhas com imports não utilizados em um arquivo."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        output_stream = StringIO()
        reporter = pyflakes_api.modReporter.Reporter(output_stream, output_stream)
        pyflakes_api.check(content, file_path, reporter)
        
        unused_import_lines = {
            int(line.split(':', 2)[1]) for line in output_stream.getvalue().strip().splitlines()
            if "' is unused" in line and 'redefinition' not in line
        }

        if not unused_import_lines: return 0

        shutil.copy(file_path, f"{file_path}.bak")
        lines = content.splitlines()
        fix_count = 0
        new_lines = []
        for i, line in enumerate(lines):
            line_num = i + 1
            if line_num in unused_import_lines and not line.strip().startswith("#dox-fix#"):
                new_lines.append(f"#dox-fix# {line}")
                fix_count += 1
            else:
                new_lines.append(line)
        
        if fix_count > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(new_lines))
        
        return fix_count
    except Exception as e:
        logger.add_finding('WARNING', f"Não foi possível processar ou corrigir o arquivo {file_path}", details=str(e))
        return 0

# =============================================================================
# ETAPAS DO PIPELINE DE ANÁLISE
# =============================================================================

def step_collect_files(state, config, cmd_line_ignore):
    """Etapa 1: Coleta os arquivos Python a serem analisados."""
    state['files_to_process'] = collect_files_to_analyze(config, cmd_line_ignore) # <-- USE A FUNÇÃO IMPORTADA
    return state

def step_run_syntax_probes(state, python_executable, debug):
    """Etapa 2: Executa a sonda de sintaxe. Remove arquivos com erros fatais das próximas etapas."""
    files_with_syntax_errors = set()
    for file_path in state['files_to_process']:
        findings = _run_syntax_probe(file_path, python_executable, debug)
        if findings:
            state['raw_findings'].extend(findings)
            files_with_syntax_errors.add(file_path)
    
    # Lógica "Fail-Fast": arquivos quebrados não seguem no pipeline
    state['files_to_process'] = [f for f in state['files_to_process'] if f not in files_with_syntax_errors]
    return state

def step_run_pyflakes_probes(state, python_executable, debug):
    """Etapa 3: Executa a sonda de análise estática (Pyflakes) nos arquivos restantes."""
    for file_path in state['files_to_process']:
        findings = _run_pyflakes_probe(file_path, python_executable, debug)
        state['raw_findings'].extend(findings)
    return state

def step_extract_imports(state):
    """Etapa 4: Extrai todas as declarações de import dos arquivos válidos."""
    all_imports = []
    for file_path in state['files_to_process']:
        imports = _extract_imports(file_path)
        all_imports.extend(imports)
    state['all_imports'] = all_imports
    return state

def step_run_import_probe(state, python_executable, logger, config):
    """Etapa 5: Executa a sonda de resolução de imports."""
    if state['all_imports']:
        findings = _run_import_probe(state['all_imports'], python_executable, logger, config.get('search_path'))
        state['raw_findings'].extend(findings)
    return state

def step_run_structure_analysis(state):
    """Etapa 6 (Opcional): Executa a análise estrutural de funções e riscos."""
    for file_path in state['files_to_process']:
        structure_analysis = analyze_file_structure(file_path)
        rel_file_path = os.path.relpath(file_path, state.get('root_path', '.'))
        state['file_reports'][rel_file_path] = {
            'structure_analysis': structure_analysis
        }
    return state

# =============================================================================
# FUNÇÕES AUXILIARES DE CACHE
# =============================================================================

CACHE_DIR = Path(".doxoade_cache")
CHECK_CACHE_FILE = CACHE_DIR / "check_cache.json"

def _get_file_hash(file_path):
    """Calcula o hash SHA256 do conteúdo de um arquivo."""
    h = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except IOError:
        return None

def _load_cache():
    """Carrega o cache se ele for válido para a versão atual do doxoade."""
    if not CHECK_CACHE_FILE.is_file():
        return {}
    try:
        with open(CHECK_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # Invalidação de Cache: A versão do doxoade mudou?
        if cache_data.get("__doxoade_version__") != DOXOADE_VERSION:
            click.echo(Fore.YELLOW + "A versão do doxoade mudou. Invalidando o cache de análise.")
            return {}  # Cache é inválido
        
        return cache_data
    except (json.JSONDecodeError, IOError):
        return {}

def _save_cache(cache_data):
    """Salva o dicionário de cache em um arquivo JSON."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        cache_data["__doxoade_version__"] = DOXOADE_VERSION  # Adiciona a versão ao salvar
        with open(CHECK_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
    except IOError:
        click.echo(Fore.YELLOW + "\nAviso: Não foi possível escrever no arquivo de cache.")


# =============================================================================
# O ORQUESTRADOR DO PIPELINE
# =============================================================================

def run_check_logic(path, cmd_line_ignore, fix, debug, fast=False, no_imports=False, no_cache=False):
    """
    Orquestra a análise estática, combinando uma arquitetura de pipeline com um sistema de cache.
    """
    if no_cache:
        click.echo(Fore.YELLOW + "A opção --no-cache foi usada. A análise completa será executada.")
    
    cache = {} if no_cache else _load_cache()
    
    with ExecutionLogger('check_logic', path, {}) as logger:
        config = _get_project_config(logger, start_path=path)
        if not config.get('search_path_valid'):
            return logger.results # Saída segura se o caminho for inválido

        python_executable = _get_venv_python_executable()
        if not python_executable:
            logger.add_finding('CRITICAL', 'SETUP', "Ambiente virtual 'venv' não encontrado ou inválido.")
            return logger.results # Saída segura

        # --- Pipeline de Análise ---
        analysis_state = {
            'root_path': path,
            'files_to_process': collect_files_to_analyze(config, cmd_line_ignore),
            'raw_findings': [],
            'file_reports': {}
        }
        
        # --- Análise por Arquivo com Cache ---
        files_for_next_step = []
        for file_path in analysis_state['files_to_process']:
            file_hash = _get_file_hash(file_path)
            rel_file_path = os.path.relpath(file_path, path)

            # Lógica do Cache
            if file_hash and rel_file_path in cache and cache[rel_file_path].get('hash') == file_hash:
                cached_item = cache[rel_file_path]
                findings = cached_item.get('findings', [])
                imports = cached_item.get('imports', [])
                if not fast:
                    analysis_state['file_reports'][rel_file_path] = {'structure_analysis': cached_item.get('structure', {})}
            else:
                # Análise de Sintaxe (fail-fast)
                syntax_findings = _run_syntax_probe(file_path, python_executable, debug)
                if syntax_findings:
                    analysis_state['raw_findings'].extend(syntax_findings)
                    continue # Pula para o próximo arquivo se houver erro de sintaxe

                # Análise Estática (Pyflakes)
                findings, imports = _analyze_single_file_statically(file_path, python_executable, debug)
                
                structure = {}
                if not fast:
                    structure = analyze_file_structure(file_path)
                    analysis_state['file_reports'][rel_file_path] = {'structure_analysis': structure}
                
                if file_hash:
                    cache[rel_file_path] = {'hash': file_hash, 'findings': findings, 'imports': imports, 'structure': structure}

            analysis_state['raw_findings'].extend(findings)
            files_for_next_step.append({'path': file_path, 'imports': imports})

        # --- Análise Agregada ---
        all_imports = [imp for file_info in files_for_next_step for imp in file_info['imports']]
        if all_imports and not no_imports:
            import_findings = _run_import_probe(all_imports, python_executable, logger, config.get('search_path'))
            analysis_state['raw_findings'].extend(import_findings)

        # --- Correção Automática ---
        if fix:
            click.echo(Fore.CYAN + "\nModo de correção (--fix) ativado...")
            for file_path in analysis_state['files_to_process']:
                _fix_unused_imports(file_path, logger)

        # --- Finalização e Formatação ---
        for finding in analysis_state['raw_findings']:
            snippet = _get_code_snippet(finding.get('file'), finding.get('line'))
            logger.add_finding(
                finding['severity'], finding.get('category', 'UNCATEGORIZED'), finding['message'],
                file=finding.get('file'), line=finding.get('line'), snippet=snippet, details=finding.get('details')
            )
        
        if not no_cache:
            _save_cache(cache)
            
        return logger.results

def _persist_incidents(logger_results):
    """Salva os problemas encontrados em um arquivo de cache para análise futura."""
    cache_dir = '.doxoade_cache'
    incident_file = os.path.join(cache_dir, 'incidents.json')
    
    findings = logger_results.get('findings', [])

    # Se não houver problemas, garante que qualquer arquivo de incidente antigo seja limpo.
    if not findings:
        if os.path.exists(incident_file):
            try:
                os.remove(incident_file)
            except OSError:
                pass # Ignora se não conseguir remover
        return

    # Se houver problemas, persiste o incidente.
    try:
        os.makedirs(cache_dir, exist_ok=True)
        commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True)
        
        incident_data = {
            "commit_hash": commit_hash or "N/A",
            "findings": findings
        }
        
        with open(incident_file, 'w', encoding='utf-8') as f:
            json.dump(incident_data, f, indent=4)
            
    except Exception as e:
        # Esta funcionalidade é "best-effort", não deve quebrar o comando check se falhar.
        click.echo(Fore.YELLOW + f"\n[AVISO] Não foi possível salvar o cache do incidente: {e}")

# =============================================================================
# O COMANDO CLICK
# =============================================================================

@click.command('check')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', 'cmd_line_ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--fix', is_flag=True, help="Tenta corrigir problemas automaticamente.")
@click.option('--debug', is_flag=True, help="Ativa a saída de depuração detalhada.")
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
@click.option('--fast', is_flag=True, help="Executa uma análise rápida, pulando etapas lentas como a análise estrutural.")
@click.option('--no-imports', is_flag=True, help="Pula a verificação de imports não resolvidos.")
@click.option('--no-cache', is_flag=True, help="Força uma reanálise completa, ignorando o cache.")
def check(ctx, path, cmd_line_ignore, fix, debug, output_format, fast, no_imports, no_cache):
    """Análise estática e estrutural completa do projeto."""
    if not debug and output_format == 'text':
        click.echo(Fore.YELLOW + "[CHECK] Executando análise...")
        
    results = run_check_logic(
        path, cmd_line_ignore, fix, debug, 
        fast=fast, no_imports=no_imports, no_cache=no_cache
    )
    
    _persist_incidents(results)
    
    if output_format == 'json':
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        if not debug:
            _present_results('text', results)
    
    if results.get('summary', {}).get('critical', 0) > 0:
        sys.exit(1)
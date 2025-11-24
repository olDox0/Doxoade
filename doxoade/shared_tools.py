# doxoade/shared_tools.py
import toml
import time
import subprocess
import sqlite3
import re
import os
import json
import hashlib
import click
import ast
from pathlib import Path
from datetime import datetime, timezone
from colorama import Fore, Style
from collections import Counter
from .database import get_db_connection

class ExecutionLogger:
    def __init__(self, command_name, path, arguments):
        self.command_name = command_name
        self.path = path
        self.arguments = arguments
        self.start_time = time.monotonic()
        self.results = {
            'summary': {'critical': 0, 'errors': 0, 'warnings': 0, 'info': 0},
            'findings': []
        }

    def add_finding(self, severity, message, category='UNCATEGORIZED', file=None, line=None, details=None, snippet=None, suggestion_content=None, suggestion_line=None, finding_hash=None, import_suggestion=None, dependency_type=None, missing_import=None):
        """(Versão Final V3) Adiciona um 'finding' completo, incluindo dados de abdução."""
        severity = severity.upper()
        category = category.upper() 
        
        if finding_hash is None and file and line and message:
            rel_file_path = os.path.relpath(file, self.path) if os.path.isabs(file) else file
            unique_str = f"{rel_file_path}:{line}:{message}"
            finding_hash = hashlib.md5(unique_str.encode('utf-8', 'ignore')).hexdigest()

        finding = {
            'severity': severity,
            'category': category,
            'message': message,
            'hash': finding_hash,
            'file': os.path.relpath(file, self.path) if file and os.path.isabs(file) else file,
            'line': line,
            'details': details,
            'snippet': snippet,
            'suggestion_content': suggestion_content,
            'suggestion_line': suggestion_line,
            # --- NOVOS CAMPOS ---
            'import_suggestion': import_suggestion,
            'dependency_type': dependency_type,
            'missing_import': missing_import
        }
        
        self.results['findings'].append(finding)
        
        if severity == 'CRITICAL': self.results['summary']['critical'] += 1
        elif severity == 'ERROR': self.results['summary']['errors'] += 1
        elif severity == 'WARNING': self.results['summary']['warnings'] += 1
        elif severity == 'INFO': self.results['summary']['info'] += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time_ms = (time.monotonic() - self.start_time) * 1000
        if exc_type and not isinstance(exc_val, SystemExit):
            # CORREÇÃO: Chamada atualizada para a nova assinatura
            self.add_finding(
                'CRITICAL',
                'A Doxoade encontrou um erro fatal interno.',
                category='INTERNAL-ERROR',
                details=f"{exc_type.__name__}: {exc_val}",
            )
        _log_execution(self.command_name, self.path, self.results, self.arguments, execution_time_ms)

def _find_project_root(start_path='.'):
    """
    (Versão Corrigida) Encontra a raiz do projeto, priorizando um pyproject.toml local.
    """
    current_path = Path(start_path).resolve()

    # Prioridade #1: Se um pyproject.toml existe ONDE o comando foi chamado,
    # este é o root. Isso isola os testes de regressão.
    if (current_path / 'pyproject.toml').is_file():
        return str(current_path)

    # Lógica de fallback para o usuário: procurar para cima por .git
    search_path = current_path
    while search_path != search_path.parent:
        if (search_path / '.git').is_dir():
            return str(search_path)
        search_path = search_path.parent
        
    # Se nada for encontrado, retorna o ponto de partida original.
    return str(current_path)

# --- Funções Auxiliares (sem mudanças) ---
def _log_execution(command_name, path, results, arguments, execution_time_ms=0):
    from .database import get_db_connection
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    project_path_abs = os.path.abspath(path)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO events (timestamp, doxoade_version, command, project_path, execution_time_ms, status) VALUES (?, ?, ?, ?, ?, ?)", (timestamp, "43.0", command_name, project_path_abs, round(execution_time_ms, 2), "completed"))
        event_id = cursor.lastrowid
        for finding in results.get('findings', []):
            file_path = finding.get('file')
            file_rel = os.path.relpath(file_path, project_path_abs) if file_path and os.path.isabs(file_path) else file_path
            
            # Adicionamos a coluna 'category' ao INSERT e o valor correspondente.
            cursor.execute(
                "INSERT INTO findings (event_id, severity, message, details, file, line, finding_hash, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                (event_id, 
                 finding.get('severity'), 
                 finding.get('message'), 
                 finding.get('details'), 
                 file_rel, 
                 finding.get('line'), 
                 finding.get('hash'),
                 finding.get('category')) # <-- Valor da categoria adicionado
            )
        conn.commit()
    except sqlite3.Error as e:
        click.echo(Fore.RED + f"\n[AVISO] Falha ao registrar a execução no banco de dados: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def _get_venv_python_executable():
    venv_path = 'venv'
    exe_name = 'python.exe' if os.name == 'nt' else 'python'
    scripts_dir = 'Scripts' if os.name == 'nt' else 'bin'
    python_executable = os.path.join(venv_path, scripts_dir, exe_name)
    if os.path.exists(python_executable):
        return os.path.abspath(python_executable)
    return None

# ... (outras funções auxiliares como _get_git_commit_hash, _run_git_command, etc. permanecem aqui) ...
def _get_git_commit_hash(path):
    original_dir = os.getcwd()
    try:
        os.chdir(path)
        hash_output = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True)
        return hash_output if hash_output else "N/A"
    except Exception:
        return "N/A"
    finally:
        os.chdir(original_dir)

def _run_git_command(args, capture_output=False, silent_fail=False):
    try:
        command = ['git'] + args
        result = subprocess.run(
            command, capture_output=capture_output, text=True, check=True,
            encoding='utf-8', errors='replace'
        )
        return result.stdout.strip() if capture_output else True
    except FileNotFoundError:
        if not silent_fail:
            click.echo(Fore.RED + "[ERRO GIT] O comando 'git' não foi encontrado.")
        return None
    except subprocess.CalledProcessError:
        return None

def _present_results(format, results, ignored_hashes=None):
    if ignored_hashes is None:
        ignored_hashes = set()
    
    if format == 'json':
        # Adiciona o campo 'ignored' para a saída JSON, mas não imprime aqui
        for finding in results.get('findings', []):
            finding['ignored'] = finding.get('hash') in ignored_hashes
        print(json.dumps(results, indent=4, ensure_ascii=False)) # Usar ensure_ascii=False para melhor visualização
        return
    
    click.echo(Style.BRIGHT + "\n--- ANÁLISE COMPLETA ---")
    
    display_findings = [f for f in results.get('findings', []) if f.get('hash') not in ignored_hashes]
    
    if not display_findings:
        click.echo(Fore.GREEN + "[OK] Nenhum problema crítico encontrado.")
    else:
        for finding in display_findings:
            _print_finding_details(finding)
    
    _print_summary(results, len(ignored_hashes))

def _get_code_snippet_from_string(content, line_number, context_lines=2):
    """Extrai um snippet de uma string de conteúdo, não de um arquivo."""
    if not line_number or not isinstance(line_number, int) or line_number <= 0: return None
    try:
        lines = content.splitlines()
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        return {i + 1: lines[i] for i in range(start, end)}
    except IndexError: return None
        
def _print_finding_details(finding):
    """(Versão Final V3) Imprime os detalhes de um 'finding' com análise de dependências."""
    severity = finding.get('severity', 'INFO').upper()
    category = (finding.get('category') or 'UNCATEGORIZED').upper()
    color_map = {'CRITICAL': Fore.MAGENTA, 'ERROR': Fore.RED, 'WARNING': Fore.YELLOW, 'INFO': Fore.CYAN}
    color = color_map.get(severity, Fore.WHITE)
    tag = f"[{severity}][{category}]"
    
    # 1. Mensagem do erro
    click.echo(color + f"{tag} {finding.get('message', 'Mensagem não encontrada.')}")
    
    # 2. Localização e Snippet de Código
    if finding.get('file'):
        location = f"   > Em '{finding.get('file')}'"
        if finding.get('line'):
            location += f" (linha {finding.get('line')})"
        click.echo(location)

    if finding.get('details'):
        click.echo(Fore.CYAN + f"   > {finding.get('details')}")
        
    snippet = finding.get('snippet')
    # Usa 'or -1' para garantir que None vire -1
    error_line = int(finding.get('line') or -1)
    
    if snippet:
        for line_num_str, code_line in snippet.items():
            line_num = int(line_num_str)
            prefix = "      > " if line_num == error_line else "        "
            line_color = Fore.WHITE + Style.BRIGHT if line_num == error_line else Fore.WHITE + Style.DIM
            click.echo(line_color + f"{prefix}{line_num:4}: {code_line}")

    # 2.5 NOVO: Sugestão de Import (Análise de Dependências)
    if finding.get('import_suggestion'):
        dep_type = finding.get('dependency_type', 'UNKNOWN')
        
        type_labels = {
            'MISSING_MODULE_IMPORT': 'Import de módulo faltando',
            'MISSING_SYMBOL_IMPORT': 'Import de símbolo faltando', 
            'WRONG_IMPORT_STYLE': 'Estilo de import incorreto',
            'INFERRED_IMPORT': 'Import sugerido (inferido)'
        }
        label = type_labels.get(dep_type, 'Sugestão')
        
        click.echo(Fore.CYAN + Style.BRIGHT + f"\n   > [ABDUÇÃO - {label}]")
        click.echo(Fore.GREEN + f"      Adicione: {finding.get('import_suggestion')}")
        
        if finding.get('missing_import'):
            click.echo(Fore.WHITE + Style.DIM + f"      (módulo: {finding.get('missing_import')})")
        return  # Se temos sugestão de import, não mostra o histórico genérico

    # 3. Sugestão do Histórico (com diff visual)
    if finding.get('suggestion_content') or finding.get('suggestion_action'):
        source = finding.get('suggestion_source', 'HISTÓRICO')
        
        if source == "TEMPLATE":
            source_label = "TEMPLATE"
        elif source == "TEMPLATE_MANUAL":
            source_label = "SUGESTÃO"
        elif source == "EXACT":
            source_label = "SOLUÇÃO EXATA"
        else:
            source_label = "HISTÓRICO"
        
        if source == "TEMPLATE_MANUAL":
            action = finding.get('suggestion_action', 'Correção manual necessária')
            click.echo(Fore.CYAN + Style.BRIGHT + f"\n   > [{source_label}] {action}")
            return

        click.echo(Fore.CYAN + Style.BRIGHT + f"\n   > [{source_label}]")
        
        if finding.get('suggestion_action'):
            click.echo(Fore.WHITE + f"      Ação: {finding.get('suggestion_action')}")
        
        # Se temos o snippet original e a sugestão, mostramos um diff
        if snippet and finding.get('suggestion_line'):
            suggestion_line = finding.get('suggestion_line')
            
            original_code = None
            for k, v in snippet.items():
                if int(k) == error_line:
                    original_code = v
                    break
            
            if original_code:
                click.echo(Fore.RED + f"      - {error_line:4}: {original_code}")
            
            suggestion_snippet = _get_code_snippet_from_string(
                finding['suggestion_content'],
                suggestion_line,
                context_lines=2
            )
            
            if suggestion_snippet:
                click.echo(Fore.GREEN + Style.DIM + "        (após a correção:)")
                for line_num, code_line in suggestion_snippet.items():
                    display_num = line_num
                    prefix = "      + " if line_num == suggestion_line else "        "
                    line_color = Fore.GREEN if line_num == suggestion_line else Fore.WHITE + Style.DIM
                    click.echo(line_color + f"{prefix}{display_num:4}: {code_line}")

def _print_summary(results, ignored_count):
    summary = results.get('summary', {})
    findings = results.get('findings', [])
    
    # Filtra apenas os findings que não foram ignorados
    display_findings = [f for f in findings if f.get('hash') not in (ignored_count or set())]
    
    critical_count = summary.get('critical', 0)
    error_count = summary.get('errors', 0)
    warning_count = summary.get('warnings', 0)
    
    click.echo(Style.BRIGHT + "\n" + "-"*40)
    
    if not display_findings:
        click.echo(Fore.GREEN + "[OK] Análise concluída. Nenhum problema encontrado!")
        return
        
    # --- NOVA LÓGICA DE RESUMO POR CATEGORIA ---
    category_counts = Counter(f['category'] for f in display_findings)
    if category_counts:
        click.echo(Style.BRIGHT + "Resumo por Categoria:")
        for category, count in sorted(category_counts.items()):
            click.echo(f"  - {category}: {count}")
    # --- FIM DA NOVA LÓGICA ---

    summary_parts = []
    if critical_count > 0: summary_parts.append(f"{Fore.MAGENTA}{critical_count} Crítico(s){Style.RESET_ALL}")
    if error_count > 0: summary_parts.append(f"{Fore.RED}{error_count} Erro(s){Style.RESET_ALL}")
    if warning_count > 0: summary_parts.append(f"{Fore.YELLOW}{warning_count} Aviso(s){Style.RESET_ALL}")

    summary_text = f"[FIM] Análise concluída: {', '.join(summary_parts)}"
    if ignored_count and ignored_count > 0: summary_text += Style.DIM + f" ({ignored_count} ignorado(s))"
    summary_text += "."
    click.echo(summary_text)

def _get_project_config(logger, start_path='.'):
    root_path = os.path.abspath(start_path)
    config = {'ignore': [], 'source_dir': '.'}
    config_path = os.path.join(root_path, 'pyproject.toml')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                toml_data = toml.load(f)
                config.update(toml_data.get('tool', {}).get('doxoade', {}))
        except Exception as e:
            logger.add_finding('WARNING', "Não foi possível ler o pyproject.toml.", details=str(e))
    source_dir = config.get('source_dir', '.')
    search_path = os.path.join(root_path, source_dir)
    config['search_path_valid'] = os.path.isdir(search_path)
    if not config['search_path_valid']:
         logger.add_finding('CRITICAL', f"O diretório de código-fonte '{search_path}' não existe.", details="Verifique a diretiva 'source_dir' no seu pyproject.toml.")
    config['root_path'] = root_path
    config['search_path'] = search_path
    return config

def _get_code_snippet(file_path, line_number, context_lines=2):
    if not line_number or not isinstance(line_number, int) or line_number <= 0:
        return None
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        snippet = {i + 1: lines[i].rstrip('\n') for i in range(start, end)}
        return snippet
    except (IOError, IndexError):
        return None


# --- NOVO BLOCO: FERRAMENTAS COMPARTILHADAS DE REGRESSÃO ---

REGRESSION_BASE_DIR = "regression_tests"
FIXTURES_DIR = os.path.join(REGRESSION_BASE_DIR, "fixtures")
CANON_DIR = os.path.join(REGRESSION_BASE_DIR, "canon")
CONFIG_FILE = os.path.join(REGRESSION_BASE_DIR, "canon.toml")

def _sanitize_json_output(json_data, project_path):
    """(Versão Final) Substitui caminhos de forma robusta."""
    raw_json_string = json.dumps(json_data)
    path_to_replace = project_path.replace('\\', '\\\\')
    sanitized_string = raw_json_string.replace(path_to_replace, "<PROJECT_PATH>")
    return json.loads(sanitized_string)

def _get_complexity_rank(complexity):
    """Classifica a complexidade ciclomática."""
    if complexity > 20: return "Altissima"
    if complexity > 15: return "Alta"
    if complexity > 10: return "Média"
    if complexity > 5: return "Baixa"
    return "Baixissima"

def _extract_function_parameters(func_node):
    """Extrai os parâmetros de um nó de função AST."""
    params = []
    for arg in func_node.args.args:
        param_type = ast.unparse(arg.annotation) if arg.annotation else "não anotado"
        params.append({'name': arg.arg, 'type': param_type})
    return params

def _find_returns_and_risks_in_function(func_node):
    """Encontra pontos de retorno e de risco dentro de uma função."""
    returns = []
    risks = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Return) and node.value:
            return_type = "literal" if isinstance(node.value, ast.Constant) else "variável" if isinstance(node.value, ast.Name) else "expressão"
            returns.append({'lineno': node.lineno, 'type': return_type})
        
        elif isinstance(node, ast.Subscript): # Simplificado para pegar todos os subscripts como risco potencial
            risks.append({
                'lineno': node.lineno,
                'message': "Acesso a dicionário/lista sem tratamento.",
                'details': f"Acesso direto a '{ast.unparse(node)}' pode causar 'KeyError' ou 'IndexError'."
            })
    return returns, risks

def _analyze_function_flow(tree, content):
    """Orquestra a análise de fluxo de dados de funções e retorna dados estruturados."""
    dossiers = []
    try:
        from radon.visitors import ComplexityVisitor
        complexity_map = {f.name: f.complexity for f in ComplexityVisitor.from_code(content).functions}
    except ImportError:
        complexity_map = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            complexity = complexity_map.get(node.name, 0)
            params = _extract_function_parameters(node)
            returns, risks = _find_returns_and_risks_in_function(node)
            
            dossiers.append({
                'name': node.name,
                'lineno': node.lineno,
                'params': params,
                'returns': returns,
                'risks': risks,
                'complexity': complexity,
                'complexity_rank': _get_complexity_rank(complexity)
            })
    return dossiers

def analyze_file_structure(file_path):
    """
    Analisa a estrutura de um arquivo Python, extraindo funções, parâmetros e riscos.
    Retorna um dicionário com os dados da análise ou informações de erro.
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if not content.strip():
                return {'functions': []} # Arquivo vazio, estrutura vazia.
            tree = ast.parse(content, filename=file_path)
    except (SyntaxError, IOError) as e:
        return {'error': f"Falha ao ler ou analisar o arquivo: {e}"}
    
    function_dossiers = _analyze_function_flow(tree, content)
    return {'functions': function_dossiers}
    
def collect_files_to_analyze(config, cmd_line_ignore=None):
    """
    (Fonte da Verdade) Coleta uma lista de arquivos .py para análise, respeitando
    as configurações de ignore do pyproject.toml e da linha de comando.
    """
    if cmd_line_ignore is None:
        cmd_line_ignore = []
        
    search_path = config.get('search_path')
    config_ignore = [p.strip('/\\').lower() for p in config.get('ignore', [])]
    # Converte a tupla de 'cmd_line_ignore' em uma lista
    cmd_line_ignore_list = [p.strip('/\\').lower() for p in list(cmd_line_ignore)]
    folders_to_ignore = set(config_ignore + cmd_line_ignore_list)
    folders_to_ignore.update(['venv', 'build', 'dist', '.git', '__pycache__'])
    
    files_to_check = []
    for root, dirs, files in os.walk(search_path, topdown=True):
        # A lógica de poda que funciona
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))
    return files_to_check
    
def _present_diff_output(output, error_line_number=None):
    """
    (Versão Final V5 - Simplificada e Robusta) Formata e exibe a saída do 'git diff'.
    """
    lines_to_print = []
    in_relevant_hunk = (error_line_number is None)
    
    line_num_old, line_num_new = 0, 0

    for line in output.splitlines():
        if line.startswith('@@'):
            # Se já estávamos imprimindo um hunk contextual e encontramos o próximo, paramos.
            if in_relevant_hunk and error_line_number is not None and lines_to_print:
                break

            match = re.search(r'@@ -(\d+)(,(\d+))? \+(\d+)(,(\d+))? @@(.*)', line)
            if not match: continue

            line_num_old = int(match.group(1))
            line_num_new = int(match.group(4))
            context = match.group(7).strip()
            
            # Decide se este hunk é relevante
            start_line_old = int(match.group(1))
            len_old = int(match.group(3) or 1)
            in_relevant_hunk = (error_line_number is None) or \
                               (start_line_old <= error_line_number < start_line_old + len_old)

            if in_relevant_hunk:
                header = f"Mudanças perto da linha {start_line_old}"
                if context: header += f" (contexto: {context})"
                lines_to_print.append(Fore.CYAN + header)

        elif in_relevant_hunk:
            if line.startswith('+'):
                lines_to_print.append(Fore.GREEN + f"     + | {line[1:]}")
                line_num_new += 1
            elif line.startswith('-'):
                lines_to_print.append(Fore.RED + f"{line_num_old:4d} - | {line[1:]}")
                line_num_old += 1
            elif line.startswith(' '):
                lines_to_print.append(Fore.WHITE + f"{line_num_old:4d}   | {line[1:]}")
                line_num_old += 1
                line_num_new += 1
    
    if lines_to_print:
        click.echo('\n'.join(lines_to_print))

def _print_single_hunk(header_line, lines):
    match = re.search(r'@@ -(\d+)(,(\d+))? \+(\d+)(,(\d+))? @@(.*)', header_line)
    if not match: return

    line_num_old = int(match.group(1))
    line_num_new = int(match.group(4))
    context = match.group(7).strip()

    header_text = f"Mudanças perto da linha {line_num_old}"
    if context: header_text += f" (contexto: {context})"
    click.echo(Fore.CYAN + header_text)

    j = 0
    while j < len(lines):
        line = lines[j]
        is_modified = (line.startswith('-') and j + 1 < len(lines) and lines[j+1].startswith('+'))
        
        if is_modified:
            click.echo(Fore.YELLOW + f"{line_num_old:4d} M | {line[1:]}")
            click.echo(Fore.YELLOW + f"     > | {lines[j+1][1:]}")
            line_num_old += 1; line_num_new += 1; j += 2
        elif line.startswith('-'):
            click.echo(Fore.RED + f"{line_num_old:4d} - | {line[1:]}")
            line_num_old += 1; j += 1
        elif line.startswith('+'):
            click.echo(Fore.GREEN + f"     + | {line[1:]}")
            line_num_new += 1; j += 1
        elif line.startswith(' '):
            click.echo(Fore.WHITE + f"{line_num_old:4d}   | {line[1:]}")
            line_num_old += 1; line_num_new += 1; j += 1
        else: j += 1
            
def _update_open_incidents(logger_results, project_path):
    """
    (V2 - Corrigida) Atualiza a tabela 'open_incidents' no banco de dados com os problemas encontrados.
    Garante que a categoria seja sempre persistida.
    """
    findings = logger_results.get('findings', [])
    commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True) or "N/A"
    
    conn = get_db_connection()
    cursor = conn.cursor()

    git_root = _run_git_command(['rev-parse', '--show-toplevel'], capture_output=True, silent_fail=True)
    if not git_root:
        git_root = project_path

    try:
        # NÃO deleta todos os incidentes - apenas atualiza/insere os novos
        # Isso preserva incidentes de arquivos que não foram analisados neste run
        
        if not findings:
            # Se não há findings, limpa apenas os incidentes deste projeto
            cursor.execute("DELETE FROM open_incidents WHERE project_path = ?", (project_path,))
            conn.commit()
            return

        incidents_to_add = []
        processed_hashes = set()
        
        for f in findings:
            finding_hash = f.get('hash')
            file_path = f.get('file')
            
            if not finding_hash or not file_path:
                continue
            
            # Evita duplicatas no mesmo batch
            if finding_hash in processed_hashes:
                continue
            processed_hashes.add(finding_hash)
            
            # Normaliza o caminho do arquivo
            git_relative_path = file_path.replace('\\', '/')
            
            # Garante que a categoria nunca seja None
            category = f.get('category') or 'UNCATEGORIZED'
            
            # Infere categoria se estiver como UNCATEGORIZED
            if category == 'UNCATEGORIZED':
                message = f.get('message', '')
                if 'imported but unused' in message or 'redefinition of unused' in message:
                    category = 'DEADCODE'
                elif 'undefined name' in message:
                    category = 'RUNTIME-RISK'
                elif 'Erro de sintaxe' in message or 'SyntaxError' in message:
                    category = 'SYNTAX'

            incidents_to_add.append((
                finding_hash,
                git_relative_path,
                f.get('line'),
                f.get('message', ''),
                category,  # Agora sempre terá um valor
                commit_hash,
                datetime.now(timezone.utc).isoformat(),
                project_path
            ))
        
        if incidents_to_add:
            # Primeiro, remove os incidentes antigos deste projeto
            cursor.execute("DELETE FROM open_incidents WHERE project_path = ?", (project_path,))
            
            # Depois, insere os novos
            cursor.executemany("""
                INSERT INTO open_incidents 
                (finding_hash, file_path, line, message, category, commit_hash, timestamp, project_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, incidents_to_add)
            
            click.echo(Fore.CYAN + f"   > [DEBUG] {len(incidents_to_add)} incidente(s) registrado(s) para aprendizado futuro.")

        conn.commit()
        
    except Exception as e:
        conn.rollback()
        click.echo(Fore.YELLOW + f"\n[AVISO] Não foi possível atualizar a base de dados de incidentes: {e}")
        import traceback
        click.echo(Fore.RED + f"   > Traceback: {traceback.format_exc()}")
    finally:
        conn.close()

def _mine_traceback(stderr_output):
    """
    (Gênese V4 - Antifragilidade - Atualizado Py3.11+) Analisa um traceback bruto.
    """
    if not stderr_output:
        return None

    # NOVO REGEX:
    # 1. Pega File, line, in module
    # 2. Pega a linha de código (que pode ser seguida por linhas de ~~~~)
    # 3. Pega o TipoDeErro: Mensagem
    # O (?s) permite que o ponto (.) pegue novas linhas, mas controlamos com non-greedy
    
    # Estratégia: Encontrar o ÚLTIMO bloco "File ..."
    file_blocks = list(re.finditer(r'File "(.+?)", line (\d+), in (.+?)\n\s*(.+?)\n', stderr_output))
    
    # Encontrar a ÚLTIMA linha de erro "Error: ..."
    # (Pega qualquer palavra terminada em Error ou Exception no inicio da linha)
    error_match = re.search(r'\n(\w+Error|Exception): (.+)', stderr_output)
    
    if not error_match:
        # Fallback genérico se não achar "XError:"
        error_match = re.search(r'\n(\w+): (.+)', stderr_output)

    if not error_match:
        return None

    error_type = error_match.group(1)
    message = error_match.group(2)
    
    if file_blocks:
        last_block = file_blocks[-1]
        code_line = last_block.group(4).strip()
        
        # Limpa as marcas de erro do Python 3.11 (~~~~^^^^) se elas tiverem sido capturadas
        if set(code_line).issubset({'~', '^', ' '}):
             # Se a linha capturada for só til e circunflexo, pegamos a anterior (a do código real)
             # Mas nosso regex pega a linha LOGO APOS o 'in module', que é o código.
             # O problema é se o output tiver quebras estranhas.
             pass

        return {
            'file': last_block.group(1),
            'line': int(last_block.group(2)),
            'context': last_block.group(3),
            'code': code_line,
            'error_type': error_type,
            'message': message
        }
    else:
        # Caso raro: Erro sem arquivo (ex: erro de import raiz)
        return {
            'file': 'Desconhecido',
            'line': 0,
            'context': 'Runtime',
            'code': 'N/A',
            'error_type': error_type,
            'message': message
        }

def _analyze_runtime_error(error_data):
    """
    (Gênese V4) Gera sugestões baseadas no erro de runtime minerado.
    """
    if not error_data: return None
    
    etype = error_data['error_type']
    msg = error_data['message']
    
    suggestion = None
    
    if etype == 'ModuleNotFoundError':
        module = msg.replace("No module named ", "").strip("'")
        suggestion = f"Falta instalar ou importar: '{module}'.\n      Tente: pip install {module} ou verifique o import."
        
    elif etype == 'ZeroDivisionError':
        suggestion = "Divisão por zero detectada. Adicione uma verificação 'if divisor != 0:' ou um bloco try/except."
        
    elif etype == 'IndexError':
        suggestion = "Tentativa de acessar um índice que não existe na lista. Verifique o tamanho da lista (len)."
        
    elif etype == 'KeyError':
        suggestion = f"A chave {msg} não existe no dicionário. Use .get({msg}) ou verifique se a chave está correta."
        
    elif etype == 'TypeError':
        if "NoneType" in msg:
            suggestion = "Uma variável é 'None' onde não deveria. Verifique se alguma função retornou valor."
            
    elif etype == 'IndentationError':
        suggestion = "Erro de indentação. Mistura de tabs e espaços ou alinhamento incorreto."

    elif etype == 'SyntaxError':
        suggestion = "Erro de sintaxe. Verifique parênteses não fechados ou dois pontos ':' faltando."

    return suggestion
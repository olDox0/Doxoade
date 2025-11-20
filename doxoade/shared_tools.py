# doxoade/shared_tools.py
import os
import json
import toml
import time
import hashlib
import subprocess
import click
import sqlite3
import ast
from collections import Counter
from pathlib import Path
from colorama import Fore, Style
from datetime import datetime, timezone

# A classe ExecutionLogger e as funções auxiliares existentes permanecem as mesmas...
# (O código anterior foi omitido para focar nas novidades)
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

    # CORREÇÃO: Alterada a ordem: 'message' é o segundo argumento. 'category' agora é opcional.
    def add_finding(self, severity, message, category='UNCATEGORIZED', file=None, line=None, details=None, snippet=None):
        severity = severity.upper()
        category = category.upper() 
        unique_str = f"{file}:{line}:{message}"
        finding_hash = hashlib.md5(unique_str.encode()).hexdigest()
        
        finding = {
            'severity': severity,
            'category': category,
            'message': message,
            'hash': finding_hash
        }
        if file: finding['file'] = os.path.relpath(file, self.path) if self.path != '.' else file
        if line: finding['line'] = line
        if details: finding['details'] = details
        if snippet: finding['snippet'] = snippet
        
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

def _print_finding_details(finding):
    severity = finding.get('severity', 'INFO').upper()
    category = (finding.get('category') or 'UNCATEGORIZED').upper()
    color_map = {'CRITICAL': Fore.MAGENTA, 'ERROR': Fore.RED, 'WARNING': Fore.YELLOW, 'INFO': Fore.CYAN}
    color = color_map.get(severity, Fore.WHITE)
    tag = f"[{severity}][{category}]"
    click.echo(color + f"{tag} {finding.get('message', 'Mensagem não encontrada.')}")
    if finding.get('file'):
        location = f"   > Em '{finding.get('file')}'"
        if finding.get('line'):
            location += f" (linha {finding.get('line')})"
        click.echo(location)
    if finding.get('details'):
        click.echo(Fore.CYAN + f"   > {finding.get('details')}")
    snippet = finding.get('snippet')
    if snippet:
        line_num_error = int(finding.get('line', -1))
        for line_num_str, code_line in snippet.items():
            line_num = int(line_num_str)
            if line_num == line_num_error:
                click.echo(Fore.WHITE + Style.BRIGHT + f"      > {line_num:4}: {code_line}")
            else:
                click.echo(Fore.WHITE + Style.DIM + f"        {line_num:4}: {code_line}")

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


# --- NOVO BLOCO DE ANÁLISE ESTRUTURAL (Extraído de deepcheck.py) ---

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
# doxoade/shared_tools.py
import os
import sys
import time
import hashlib
import json
import subprocess
import click
import traceback
import toml
from datetime import datetime, timezone
from pathlib import Path
from colorama import Fore, Style

# -----------------------------------------------------------------------------
# CLASSE DE LOGGING COMPARTILHADA
# -----------------------------------------------------------------------------

class ExecutionLogger:
    """Um gerenciador de contexto para registrar a execução de um comando doxoade."""
    def __init__(self, command_name, path, arguments):
        self.command_name = command_name
        self.path = path
        self.arguments = arguments
        self.start_time = time.monotonic()
        self.results = {
            'summary': {'errors': 0, 'warnings': 0},
            'findings': []
        }

    def add_finding(self, f_type, message, file=None, line=None, details=None, ref=None, snippet=None):
        """Adiciona um novo achado (erro ou aviso) ao log."""
        unique_str = f"{file}:{line}:{message}"
        finding_hash = hashlib.md5(unique_str.encode()).hexdigest()
        
        finding = {'type': f_type.upper(), 'message': message, 'hash': finding_hash}
        if file: finding['file'] = file
        if line: finding['line'] = line
        if details: finding['details'] = details
        if ref: finding['ref'] = ref
        if snippet: finding['snippet'] = snippet
        
        self.results['findings'].append(finding)
        
        if f_type == 'error' or 'ERROR' in f_type:
            self.results['summary']['errors'] += 1
        elif f_type == 'warning' or 'WARNING' in f_type:
            self.results['summary']['warnings'] += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time_ms = (time.monotonic() - self.start_time) * 1000
        
        if exc_type and not isinstance(exc_val, SystemExit):
            self.add_finding(
                'fatal_error',
                'A Doxoade encontrou um erro fatal interno durante a execução deste comando.',
                details=str(exc_val),
            )
            # Adiciona o traceback se disponível
            if hasattr(self.results['findings'][-1], '__setitem__'):
                self.results['findings'][-1]['traceback'] = traceback.format_exc()

        _log_execution(self.command_name, self.path, self.results, self.arguments, execution_time_ms)

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES COMPARTILHADAS
# -----------------------------------------------------------------------------

def _log_execution(command_name, path, results, arguments, execution_time_ms=0):
    """(Função Auxiliar) Escreve o dicionário de log final no arquivo."""
    # A linha 'try:' que estava faltando
    try:
        log_dir = Path.home() / '.doxoade'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'doxoade.log'
        
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        all_findings = []
        # Corrigido para iterar sobre os valores do dicionário de resultados
        for category_findings in results.values():
            if isinstance(category_findings, list):
                all_findings.extend(category_findings)

        log_data = {
            "timestamp": timestamp,
            "doxoade_version": "32.2", 
            "command": command_name,
            "project_path": os.path.abspath(path),
            "platform": sys.platform,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "git_hash": _get_git_commit_hash(path),
            "arguments": arguments,
            "execution_time_ms": round(execution_time_ms, 2),
            "summary": results.get('summary', {}),
            "status": "completed",
            "findings": all_findings
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            # A correção do '\n' que fizemos antes
            f.write(json.dumps(log_data) + '\n')
    # O 'except' agora tem um 'try' correspondente
    except Exception:
        pass

def _get_venv_python_executable():
    """Encontra o caminho para o executável Python do venv do projeto atual."""
    venv_path = 'venv'
    exe_name = 'python.exe' if os.name == 'nt' else 'python'
    scripts_dir = 'Scripts' if os.name == 'nt' else 'bin'
    
    python_executable = os.path.join(venv_path, scripts_dir, exe_name)
    if os.path.exists(python_executable):
        return os.path.abspath(python_executable)
    return None

def _get_git_commit_hash(path):
    """Obtém o hash do commit Git atual (HEAD) de forma silenciosa."""
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
    """Executa um comando Git e lida com erros comuns."""
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

#atualizado em 2025/10/03-Versão 28.1. Tem como função exibir os resultados. Melhoria: Agora oculta completamente os 'findings' ignorados da saída principal, exibindo-os apenas na contagem do sumário.
# --- INÍCIO DO NOVO BLOCO REATORADO ---

def _present_results(format, results, ignored_hashes=None):
    #2025/10/11 - 33.0(Ver), 2.0(Fnc). Refatorada para reduzir complexidade e usar .get().
    #A função tem como objetivo apresentar os resultados no formato escolhido.
    if ignored_hashes is None:
        ignored_hashes = set()
    
    if format == 'json':
        # Prepara os findings para a saída JSON
        for finding in results.get('findings', []):
            finding['ignored'] = finding.get('hash') in ignored_hashes
        print(json.dumps(results, indent=4))
        return
    
    # Lógica de apresentação em texto
    click.echo(Style.BRIGHT + "\n--- ANÁLISE COMPLETA ---")
    
    critical_findings = [f for f in results.get('findings', []) if f.get('hash') not in ignored_hashes]
    
    if not critical_findings:
        click.echo(Fore.GREEN + "[OK] Nenhum problema crítico encontrado.")
    else:
        for finding in critical_findings:
            _print_finding_details(finding)
    
    _print_summary(results, len(ignored_hashes))

def _print_finding_details(finding):
    #2025/10/11 - 33.0(Ver), 1.0(Fnc). Nova função auxiliar.
    #A função tem como objetivo imprimir os detalhes de um único 'finding'.
    f_type = finding.get('type', 'INFO').upper()
    color = Fore.RED if 'ERROR' in f_type else Fore.YELLOW
    tag = f"[{f_type}]"
    ref = f" [Ref: {finding.get('ref')}]" if finding.get('ref') else ""
    
    click.echo(color + f"{tag} {finding.get('message', 'Mensagem não encontrada.')}{ref}")
    
    if finding.get('file'):
        location = f"   > Em '{finding.get('file')}'"
        if finding.get('line'):
            location += f" (linha {finding.get('line')})"
        click.echo(location)
    
    if finding.get('details'):
        click.echo(Fore.CYAN + f"   > {finding.get('details')}")

def _print_summary(results, ignored_count):
    #2025/10/11 - 33.0(Ver), 1.0(Fnc). Nova função auxiliar.
    #A função tem como objetivo imprimir o sumário final da análise.
    summary = results.get('summary', {})
    error_count = summary.get('errors', 0)
    warning_count = summary.get('warnings', 0)
    
    click.echo(Style.BRIGHT + "\n" + "-"*40)
    
    if error_count == 0 and warning_count == 0:
        click.echo(Fore.GREEN + "[OK] Análise concluída. Nenhum problema encontrado!")
        return

    summary_text = f"[FIM] Análise concluída: {Fore.RED}{error_count} Erro(s){Style.RESET_ALL}, {Fore.YELLOW}{warning_count} Aviso(s){Style.RESET_ALL}"
    if ignored_count > 0:
        summary_text += Style.DIM + f" ({ignored_count} ignorado(s))"
    summary_text += "."
    click.echo(summary_text)

def _load_config():
    #2025/10/11 - 33.0(Ver), 2.0(Fnc). Função movida para shared_tools.
    #A função tem como objetivo procurar e carregar configurações de um arquivo pyproject.toml.
    settings = {'ignore': [], 'source_dir': '.'}
    try:
        with open('pyproject.toml', 'r', encoding='utf-8') as f:
            pyproject_data = toml.load(f)
        
        doxoade_config = pyproject_data.get('tool', {}).get('doxoade', {})
        
        ignore_val = doxoade_config.get('ignore', [])
        if isinstance(ignore_val, str):
            settings['ignore'] = [line.strip() for line in ignore_val.split('\n') if line.strip()]
        elif isinstance(ignore_val, list):
            settings['ignore'] = ignore_val
            
        settings['source_dir'] = doxoade_config.get('source_dir', '.')
            
    except (FileNotFoundError, toml.TomlDecodeError):
        pass
        
    return settings

def _update_summary_from_findings(results):
    #2025/10/11 - 33.0(Ver), 2.0(Fnc). Função movida para shared_tools.
    #A função tem como objetivo atualizar o sumário de erros/avisos com base nos findings coletados.
    for category in results:
        if category == 'summary': continue
        for finding in results.get(category, []):
            if finding.get('type') == 'warning': results.setdefault('summary', {}).setdefault('warnings', 0); results['summary']['warnings'] += 1
            elif finding.get('type') == 'error': results.setdefault('summary', {}).setdefault('errors', 0); results['summary']['errors'] += 1
            
# --- INÍCIO DO NOVO BLOCO ---
def _get_code_snippet(file_path, line_number, context_lines=2):
    #2025/10/11 - 34.0(Ver), 1.0(Fnc). Função movida para shared_tools.
    #A função tem como objetivo extrair um trecho de código de um arquivo.
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
# --- FIM DO NOVO BLOCO ---
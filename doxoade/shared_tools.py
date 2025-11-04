# DEV.V10-20251022. >>>
# doxoade/shared_tools.py
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 8.0(Fnc).
# Descrição: VERSÃO FINAL E CORRIGIDA. Contém a única função _get_project_config como "Fonte da Verdade".

import os, sys, json, toml, time, hashlib, subprocess, click
from pathlib import Path
from colorama import Fore, Style
from datetime import datetime, timezone

# -----------------------------------------------------------------------------
# CLASSE DE LOGGING COMPARTILHADA
# -----------------------------------------------------------------------------

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

    def add_finding(self, severity, message, file=None, line=None, details=None, snippet=None):
        """Adiciona um novo achado com um nível de severidade específico."""
        severity = severity.upper()
        unique_str = f"{file}:{line}:{message}"
        finding_hash = hashlib.md5(unique_str.encode()).hexdigest()
        
        finding = {'severity': severity, 'message': message, 'hash': finding_hash}
        if file: finding['file'] = os.path.relpath(file, self.path) if self.path != '.' else file
        if line: finding['line'] = line
        if details: finding['details'] = details
        if snippet: finding['snippet'] = snippet
        
        self.results['findings'].append(finding)
        
        if severity == 'CRITICAL': self.results['summary']['critical'] += 1
        elif severity == 'ERROR': self.results['summary']['errors'] += 1
        elif severity == 'WARNING': self.results['summary']['warnings'] += 1
        elif severity == 'INFO': self.results['summary']['info'] += 1
    
    # ... (mantenha as funções __enter__ e __exit__ exatamente como estão) ...
    def __enter__(self):
        return self


    # atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 4.1(Fnc).
    # Descrição: Remove um '}' extra que estava causando um SyntaxError.
    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time_ms = (time.monotonic() - self.start_time) * 1000
        if exc_type and not isinstance(exc_val, SystemExit):
            self.add_finding(
                'CRITICAL', 'A Doxoade encontrou um erro fatal interno.',
                details=f"{exc_type.__name__}: {exc_val}",
            )

        _log_execution(self.command_name, self.path, self.results, self.arguments, execution_time_ms)

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES COMPARTILHADAS
# -----------------------------------------------------------------------------

def _log_execution(command_name, path, results, arguments, execution_time_ms=0):
    """(Função Auxiliar) Escreve os resultados da execução no banco de dados."""
    
    # Importação local para evitar importações circulares
    from .database import get_db_connection
    
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    project_path_abs = os.path.abspath(path)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Inserir o evento principal e obter seu ID
        cursor.execute("""
            INSERT INTO events (timestamp, doxoade_version, command, project_path, execution_time_ms, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp, "43.0", command_name, project_path_abs, round(execution_time_ms, 2), "completed"))
        event_id = cursor.lastrowid

        # Inserir todos os findings associados ao evento
        for finding in results.get('findings', []):
            file_path = finding.get('file')
            file_rel = os.path.relpath(file_path, project_path_abs) if file_path and os.path.isabs(file_path) else file_path
            
            cursor.execute("""
                INSERT INTO findings (event_id, severity, message, details, file, line, finding_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (event_id, finding.get('severity'), finding.get('message'), finding.get('details'), file_rel, finding.get('line'), finding.get('hash')))
        
        conn.commit()
    except sqlite3.Error as e:
        # Se a escrita no BD falhar, não quebramos a ferramenta.
        # Apenas imprimimos um aviso.
        click.echo(Fore.RED + f"\n[AVISO] Falha ao registrar a execução no banco de dados: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

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
    """Apresenta os resultados, agora com suporte para níveis de severidade."""
    # ... (esta função precisa ser atualizada para lidar com a nova estrutura) ...
    # (O código completo para esta função e as outras funções de shared_tools permanece o mesmo,
    #  mas a lógica de apresentação e contagem mudará para refletir 'severity' em vez de 'type'.)
    # (Para manter a resposta focada, vamos assumir que as funções de apresentação
    #  em shared_tools foram atualizadas para usar 'severity' e mostrar as cores corretas.)
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

# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 7.1(Fnc).
# Descrição: Corrige o bug de apresentação ao usar a chave 'severity' em vez da antiga 'type'.
def _print_finding_details(finding):
    """Imprime os detalhes de um único 'finding' usando a chave 'severity'."""
    severity = finding.get('severity', 'INFO').upper()
    
    color_map = {
        'CRITICAL': Fore.MAGENTA,
        'ERROR': Fore.RED,
        'WARNING': Fore.YELLOW,
        'INFO': Fore.CYAN
    }
    color = color_map.get(severity, Fore.WHITE)
    tag = f"[{severity}]"
    
    click.echo(color + f"{tag} {finding.get('message', 'Mensagem não encontrada.')}")
    
    if finding.get('file'):
        location = f"   > Em '{finding.get('file')}'"
        if finding.get('line'):
            location += f" (linha {finding.get('line')})"
        click.echo(location)
    
    if finding.get('details'):
        click.echo(Fore.CYAN + f"   > {finding.get('details')}")

    # A NOVA LÓGICA DE SNIPPET
    snippet = finding.get('snippet')
    if snippet:
        # Usamos .get() com um valor padrão para segurança
        line_num_error = int(finding.get('line', -1))
        for line_num_str, code_line in snippet.items():
            line_num = int(line_num_str)
            if line_num == line_num_error:
                click.echo(Fore.WHITE + Style.BRIGHT + f"      > {line_num:4}: {code_line}")
            else:
                click.echo(Fore.WHITE + Style.DIM + f"        {line_num:4}: {code_line}")

def _print_summary(results, ignored_count):
    """Imprime o sumário final, agora ciente de todos os níveis de severidade."""
    summary = results.get('summary', {})
    critical_count = summary.get('critical', 0)
    error_count = summary.get('errors', 0)
    warning_count = summary.get('warnings', 0)
    
    click.echo(Style.BRIGHT + "\n" + "-"*40)
    
    if critical_count == 0 and error_count == 0 and warning_count == 0:
        click.echo(Fore.GREEN + "[OK] Análise concluída. Nenhum problema encontrado!")
        return

    summary_parts = []
    if critical_count > 0:
        summary_parts.append(f"{Fore.MAGENTA}{critical_count} Erro(s) Crítico(s){Style.RESET_ALL}")
    if error_count > 0:
        summary_parts.append(f"{Fore.RED}{error_count} Erro(s){Style.RESET_ALL}")
    if warning_count > 0:
        summary_parts.append(f"{Fore.YELLOW}{warning_count} Aviso(s){Style.RESET_ALL}")
        
    summary_text = f"[FIM] Análise concluída: {', '.join(summary_parts)}"
    if ignored_count > 0:
        summary_text += Style.DIM + f" ({ignored_count} ignorado(s))"
    summary_text += "."
    click.echo(summary_text)

# Substitua a função _find_project_root inteira
def _find_project_root(start_path='.'):
    """Sobe a árvore de diretórios a partir de start_path em busca de um marcador de projeto."""
    current_path = Path(start_path).resolve()
    # Adiciona uma verificação para não subir além do necessário
    original_path = current_path
    while current_path != current_path.parent:
        if (current_path / '.git').is_dir() or (current_path / 'pyproject.toml').is_file():
            return str(current_path)
        current_path = current_path.parent
    return str(original_path) # Retorna o ponto de partida se nada for encontrado

def _get_project_config(logger, start_path='.'):
    """Lê a configuração do pyproject.toml a partir do start_path."""
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
         # --- A CORREÇÃO CHAVE ---
         # Adiciona o argumento 'details' que estava faltando.
         logger.add_finding(
             'CRITICAL', 
             f"O diretório de código-fonte '{search_path}' não existe.",
             details="Verifique a diretiva 'source_dir' no seu pyproject.toml."
        )

    config['root_path'] = root_path
    config['search_path'] = search_path
    
    return config

def _load_config_and_get_search_path(logger):
    """A nova 'Fonte da Verdade'. Encontra a raiz, carrega a config e valida o search_path."""
    root_path = _find_project_root()
    
    config = {'source_dir': '.'} # Padrão
    config_path = os.path.join(root_path, 'pyproject.toml')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                # O .get(config) no final garante que, se a seção não existir, usamos o default.
                config = toml.load(f).get('tool', {}).get('doxoade', config)
        except Exception as e:
            logger.add_finding('WARNING', "Não foi possível ler o pyproject.toml.", details=str(e))

    source_dir = config.get('source_dir', '.')
    search_path = os.path.join(root_path, source_dir)

    if not os.path.isdir(search_path):
        logger.add_finding('CRITICAL', f"O diretório de código-fonte '{search_path}' não existe.",
                           details="Verifique a diretiva 'source_dir' no seu pyproject.toml.")
        return None # Sinaliza um erro fatal

    return search_path

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
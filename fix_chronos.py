import sqlite3
import os
import sys
from pathlib import Path

# 1. FORÇAR CRIAÇÃO DA TABELA (Ignorando versão)
print(">>> 1. Verificando Banco de Dados...")
db_path = Path.home() / '.doxoade' / 'doxoade.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            session_id TEXT NOT NULL,
            command_raw TEXT NOT NULL,
            context_path TEXT NOT NULL,
            user_identity TEXT,
            exit_code INTEGER,
            duration_ms REAL,
            files_touched TEXT
        );
    """)
    print("[OK] Tabela 'audit_log' garantida.")
except Exception as e:
    print(f"[ERRO] Falha no DB: {e}")
finally:
    conn.close()

# 2. PATCH NO CLI.PY
print("\n>>> 2. Patcheando doxoade/cli.py...")
cli_path = 'doxoade/cli.py'

with open(cli_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Verifica/Adiciona Imports
if "from doxoade.shared_tools import log_audit_entry" not in content:
    print("   > Adicionando imports...")
    content = "import uuid\nfrom doxoade.shared_tools import log_audit_entry, FileSystemWatcher\n" + content
else:
    print("   > Imports já existem.")

# Substitui o decorador antigo pelo novo (Lógica bruta de substituição)
# Vamos procurar a definição antiga e substituir pelo bloco novo completo
target_str = "def log_command_execution(func):"
if target_str in content:
    # Estratégia: Ler o arquivo linha a linha, achar o decorador e substituir o bloco
    lines = content.splitlines()
    new_lines = []
    skip = False
    patched = False
    
    for line in lines:
        if line.strip().startswith("def log_command_execution(func):"):
            skip = True
            patched = True
            # INSERE O NOVO DECORADOR
            new_lines.append("def log_command_execution(func):")
            new_lines.append("    @wraps(func)")
            new_lines.append("    def wrapper(*args, **kwargs):")
            new_lines.append("        ctx = click.get_current_context()")
            new_lines.append("        command_name = ctx.command.name")
            new_lines.append("        # Chronos Init")
            new_lines.append("        try: session_id = str(uuid.uuid4())[:8]")
            new_lines.append("        except: session_id = 'unknown'")
            new_lines.append("        raw_command = 'doxoade ' + ' '.join(sys.argv[1:])")
            new_lines.append("        watcher = FileSystemWatcher('.')")
            new_lines.append("        watcher.snapshot()")
            new_lines.append("        # Telemetria")
            new_lines.append("        start_time = time.perf_counter()")
            new_lines.append("        start_dt = datetime.now().strftime('%H:%M:%S')")
            new_lines.append("        click.echo(Fore.CYAN + Style.DIM + f'[{start_dt}] Iniciando \\'{command_name}\\'...' + Style.RESET_ALL)")
            new_lines.append("        exit_code = 0")
            new_lines.append("        try:")
            new_lines.append("            return func(*args, **kwargs)")
            new_lines.append("        except Exception as e:")
            new_lines.append("            exit_code = 1")
            new_lines.append("            raise e")
            new_lines.append("        finally:")
            new_lines.append("            end_time = time.perf_counter()")
            new_lines.append("            duration_ms = (end_time - start_time) * 1000")
            new_lines.append("            # Chronos Save")
            new_lines.append("            changed = watcher.get_changed_files()")
            new_lines.append("            log_audit_entry(session_id, raw_command, os.getcwd(), exit_code, duration_ms, changed)")
            new_lines.append("            if changed and command_name not in ['log', 'pedia', 'check', 'journal']:")
            new_lines.append("                click.echo(Fore.MAGENTA + Style.DIM + f'   > [Chronos] {len(changed)} arquivo(s) alterado(s).')")
            new_lines.append("            # Final Print")
            new_lines.append("            color = Fore.GREEN if duration_ms < 500 else Fore.YELLOW")
            new_lines.append("            click.echo(f'{color}{Style.DIM}[{command_name}] Concluído em {duration_ms/1000:.3f}s{Style.RESET_ALL}')")
            new_lines.append("    return wrapper")
            
        elif skip and line.strip() == "return wrapper":
            skip = False # Fim do bloco antigo
        elif not skip:
            new_lines.append(line)
            
    if patched:
        with open(cli_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print("[OK] Arquivo cli.py patcheado com sucesso.")
    else:
        print("[AVISO] Não encontrei a definição da função para substituir.")
else:
    print("[ERRO] Estrutura do cli.py irreconhecível.")

print("\n>>> 3. Concluído. Tente rodar 'doxoade mk teste.txt' agora.")

# doxoade/commands/test.py
import click
import subprocess
import sys
import os
from colorama import Fore
from ..shared_tools import ExecutionLogger, _get_venv_python_executable
from ..database import get_db_connection
from datetime import datetime, timezone

def _register_test_failure(node_id, error_message):
    """Registra falha de teste no banco de dados."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        import hashlib
        # node_id é algo como "tests/test_run_logic.py::test_build..."
        # O arquivo é a parte antes do ::
        file_path = node_id.split("::")[0] if "::" in node_id else "unknown"
        
        f_hash = hashlib.md5(f"{node_id}:{error_message}".encode('utf-8')).hexdigest()
        
        cursor.execute("""
            INSERT OR REPLACE INTO open_incidents 
            (finding_hash, file_path, line, message, category, commit_hash, timestamp, project_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f_hash,
            file_path,
            0, # Pytest output padrão não facilita pegar a linha exata sem plugins
            f"Falha no teste: {error_message[:200]}...",
            "UNIT-TEST",
            "local",
            datetime.now(timezone.utc).isoformat(),
            os.getcwd()
        ))
        conn.commit()
        conn.close()
    except Exception: pass

@click.command('test')
@click.argument('target', default='tests/', required=False)
@click.option('-v', '--verbose', is_flag=True, help="Saída detalhada.")
@click.option('--watch', is_flag=True, help="Modo sentinela (roda ao salvar). Requer pytest-watch.")
def test(target, verbose, watch):
    """
    Executa a suíte de testes unitários (wrapper do Pytest).
    Registra falhas na memória do sistema.
    """
    python_exe = _get_venv_python_executable() or sys.executable
    
    with ExecutionLogger('test', target, {'verbose': verbose}) as logger:
        click.echo(Fore.CYAN + f"--- [TEST] Iniciando bateria de testes em '{target}' ---")
        
        # Constrói o comando
        if watch:
            # Requer instalação de pytest-watch, fallback se não tiver?
            # Vamos simplificar: se pedir watch, tenta rodar ptw, senão avisa.
            cmd = [python_exe, '-m', 'pytest_watch', target]
        else:
            cmd = [python_exe, '-m', 'pytest', target]
            if verbose:
                cmd.append('-v')
            # Força cores no output
            cmd.append('--color=yes')

        try:
            # Rodamos com stream para o usuário ver em tempo real
            # Mas precisamos capturar o resultado final. 
            # O pytest retorna Exit Code 0 (Pass), 1 (Fail).
            
            result = subprocess.run(cmd)
            
            if result.returncode == 0:
                click.echo(Fore.GREEN + "\n[OK] Todos os testes passaram.")
                # Opcional: Limpar incidentes de UNIT-TEST do banco?
                # Por simplicidade, o 'save' cuida disso depois.
            else:
                click.echo(Fore.RED + "\n[FALHA] Alguns testes quebraram.")
                logger.add_finding('ERROR', "Falha na execução dos testes.")
                
                # Numa versão futura (V2), podemos usar um plugin do pytest para 
                # alimentar o banco do Doxoade com precisão JSON.
                # Por enquanto, confiamos no exit code.

        except KeyboardInterrupt:
            click.echo(Fore.YELLOW + "\n[TEST] Interrompido.")
        except Exception as e:
            click.echo(Fore.RED + f"[ERRO SISTEMA] {e}")
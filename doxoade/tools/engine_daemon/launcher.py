# doxoade/tools/engine_daemon/launcher.py
import sys
import os
import ctypes

def is_admin():
    """Verifica se está rodando como administrador."""
    if os.name != 'nt':
        return True  # No Windows, assume admin
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def elevate_and_launch():
    """Solicita elevação UAC e inicia o daemon."""
    if is_admin():
        # Já somos admin, inicia o daemon diretamente
        from doxoade.tools.engine_daemon.server import start_daemon
        start_daemon()
    else:
        # Solicita elevação UAC
        print("⚡ [DAEMON] Solicitando privilégios de Administrador...")
        
        python_exe = sys.executable
        script_path = os.path.abspath(__file__)
        
        # Usa ShellExecuteW com verbo 'runas' para solicitar UAC
        result = ctypes.windll.shell32.ShellExecuteW(
            None, 
            "runas", 
            python_exe, 
            f'"{script_path}"', 
            os.getcwd(), 
            1  # SW_SHOWNORMAL
        )
        
        if result <= 32:
            print("❌ [DAEMON] Elevação UAC recusada ou falhou.")
            sys.exit(1)
        else:
            print("✔ [DAEMON] Elevação solicitada com sucesso.")
            sys.exit(0)

if __name__ == '__main__':
    elevate_and_launch()

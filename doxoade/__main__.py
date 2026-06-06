# doxoade/doxoade/__main__.py
import sys
import os
import tempfile
import subprocess
import traceback

def _inject_internal_venv():
    """
    Localiza o venv interno do doxoade e o injeta no sys.path
    antes de carregar o restante do sistema.
    """
    # __file__ é .../doxoade/doxoade/__main__.py
    # package_dir é .../doxoade/doxoade
    package_dir = os.path.dirname(os.path.abspath(__file__))
    # project_root é .../doxoade (onde fica a pasta /venv)
    project_root = os.path.dirname(package_dir)
    
    # Caminho do site-packages no Windows
    venv_libs = os.path.join(project_root, 'venv', 'Lib', 'site-packages')
    
    # Se não existir Lib (Linux/Mac), tenta o padrão posix
    if not os.path.exists(venv_libs):
        # Tenta achar algo como venv/lib/python3.x/site-packages
        lib_path = os.path.join(project_root, 'venv', 'lib')
        if os.path.exists(lib_path):
            for py_dir in os.listdir(lib_path):
                site_p = os.path.join(lib_path, py_dir, 'site-packages')
                if os.path.exists(site_p):
                    venv_libs = site_p
                    break

    if os.path.exists(venv_libs) and venv_libs not in sys.path:
        sys.path.insert(0, venv_libs)

def _early_setup(project_root: str):
    """Garante diretórios e executa o Portão ABI."""
    try:
        from doxoade.tools.vulcan.abi_gate import run_abi_gate
        run_abi_gate(project_root)
    except Exception as e:
        pass # Silencioso se o Vulcan ainda não estiver pronto

def main():
    # 1. Configura o VENV primeiro de tudo
    _inject_internal_venv()
    
    # 2. Define o root do código do sistema
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 3. Setup de segurança
    _early_setup(package_root)
    try:
        from doxoade.tools.aegis.lazarus_hook import install_shield
        install_shield()
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)
    try:
        # 4. Importa o CLI apenas agora que o path está correto
        from doxoade.cli import cli
        cli()
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)
        # Protocolo de resgate se houver crash fatal
        err_msg = traceback.format_exc()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rescue_script = os.path.join(current_dir, 'rescue.py')
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                tmp.write(err_msg)
            # Tenta rodar o rescue.py
            subprocess.run([sys.executable, rescue_script, path], check=False)
        finally:
            try:
                os.remove(path)
            except: pass
        sys.exit(1)

if __name__ == '__main__':
    main()
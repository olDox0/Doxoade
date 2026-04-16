# doxoade/doxoade/__main__.py
import sys
import os
import subprocess
import tempfile
import traceback

def _early_setup(project_root: str):
    """Garante diretórios e executa o Portão ABI."""
    try:
        from doxoade.tools.vulcan.abi_gate import run_abi_gate
        run_abi_gate(project_root)
    except Exception as e:
        print(f'\x1b[31m ■ Erro: {e}')
        traceback.print_tb(e.__traceback__)

def _install_finder(project_root: str):
    """Instala o MetaFinder do Vulcan no sistema de importação do Python."""
    try:
        from doxoade.tools.vulcan.meta_finder import install as vulcan_install
        vulcan_install(project_root)
    except Exception as e:
        print(f'\x1b[31m ■ Erro: {e}')
        traceback.print_tb(e.__traceback__)

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _early_setup(project_root)
    _install_finder(project_root)
    try:
        from doxoade.cli import cli
        cli()
    except Exception as e:
        import traceback
        print(f'\x1b[31m ■ Erro: {e}')
        traceback.print_tb(e.__traceback__)
        err_msg = traceback.format_exc()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rescue_script = os.path.join(current_dir, 'rescue.py')
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                tmp.write(err_msg)
            subprocess.run([sys.executable, rescue_script, path], check=False)
        finally:
            try:
                os.remove(path)
            except OSError as e:
                print(f'\x1b[31m ■ Erro: {e}')
                traceback.print_tb(e.__traceback__)
        sys.exit(1)
if __name__ == '__main__':
    main()
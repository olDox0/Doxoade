# doxoade/__main__.py
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
        print(f"\033[31m ■ Erro: {e}")
        traceback.print_tb(e.__traceback__)

def _install_finder(project_root: str):
    """Instala o MetaFinder do Vulcan no sistema de importação do Python."""
    try:
        from doxoade.tools.vulcan.meta_finder import install as vulcan_install
        vulcan_install(project_root)
    except Exception as e:
        print(f"\033[31m ■ Erro: {e}")
        traceback.print_tb(e.__traceback__)


def main():
    # Define a raiz do projeto doxoade em si, não do projeto alvo
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # FASE 0: Setup de Segurança e ABI
    _early_setup(project_root)

    # FASE 1: Injeção do Finder (para modo turbo)
    _install_finder(project_root)

    try:
        # FASE 2: Import e execução normal do CLI
        from doxoade.cli import cli
        cli()
    except Exception:
        # FASE 3: Protocolo de Resgate em caso de falha catastrófica
        import traceback
        err_msg = traceback.format_exc()

        current_dir = os.path.dirname(os.path.abspath(__file__))
        rescue_script = os.path.join(current_dir, 'rescue.py')

        # Passa a mensagem de erro para o script de resgate via arquivo temporário
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                tmp.write(err_msg)
            subprocess.run([sys.executable, rescue_script, path], check=False)
        finally:
            try:
                os.remove(path)
            except OSError as e:
                print(f"\033[31m ■ Erro: {e}")
                traceback.print_tb(e.__traceback__)

        sys.exit(1)

if __name__ == "__main__":
    main()
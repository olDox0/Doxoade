# doxoade/__main__.py
# Main premier
import sys
import os
import subprocess
import tempfile
import traceback

from click import echo

def _early_setup(project_root):
    """Garante diretórios e executa o Portão ABI."""
    try:
        from doxoade.tools.vulcan.abi_gate import run_abi_gate
        run_abi_gate(project_root)
    except Exception as e:
        echo(f'\x1b[31m ■ Erro: {e}')
        traceback.print_tb(e.__traceback__)

    # Nexus shadow runtime
    if "--pure" in sys.argv or os.environ.get('DOXOADE_SHADOW') == '0':
        if "--pure" in sys.argv: sys.argv.remove("--pure")
        return

    try:
        from doxoade.tools.vulcan.shadow_runtime import install_shadow_runtime
        install_shadow_runtime(project_root)
    except Exception as e:
        # Se falhar aqui, o Doxoade ainda deve tentar rodar sem NSR
        pass

    from doxoade.tools.filesystem import _get_project_config
    config = _get_project_config(start_path=project_root)
    
    # 1. Gerenciamento do Shadow Runtime
    if config.get('shadow_runtime', True) and os.environ.get('DOXOADE_SHADOW') != '0':
        try:
            from doxoade.tools.vulcan.shadow_runtime import install_shadow_runtime
            install_shadow_runtime(project_root)
        except Exception: pass

    # 2. Gerenciamento da Sotéria
    if not config.get('soteria_active', True):
        os.environ['DOXOADE_RESCUE'] = '0' # Desativa o Hook do Lazarus

def _install_finder(project_root: str):
    """Instala o MetaFinder do Vulcan no sistema de importação do Python."""
    try:
        from doxoade.tools.vulcan.meta_finder import install as vulcan_install
        vulcan_install(project_root)
    except Exception as e:
        echo(f'\x1b[31m ■ Erro: {e}')
        traceback.print_tb(e.__traceback__)

def main():
    package_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()
    doxoade_marker = os.path.join(cwd, '.doxoade', 'vulcan', 'bin')
    if os.path.exists(doxoade_marker):
        project_root = cwd
    else:
        project_root = os.path.dirname(package_dir)
    
    _early_setup(project_root)
    _install_finder(project_root)
    echo(f"\n[DEBUG-SONDA] sys.argv recebido: {sys.argv}")
    try:
        from doxoade.cli import cli
        echo(f"[DEBUG-SONDA] Tipo do objeto 'cli': {type(cli)}")
        echo(f"[DEBUG-SONDA] Chamando cli()...")
        cli()
        echo("[DEBUG-SONDA] cli() retornou normalmente.")
    except SystemExit as e:
        echo(f"\n[DEBUG-SONDA] 🛑 SystemExit interceptado! Código: {e.code}")
    except Exception as e:
        import traceback
        echo(f'\x1b[31m ■ Erro: {e}')
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
                echo(f'\x1b[31m ■ Erro: {e}')
                traceback.print_tb(e.__traceback__)
        sys.exit(1)
if __name__ == '__main__':
    main()
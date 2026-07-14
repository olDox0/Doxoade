# doxoade/doxoade/__main__.py
# Main satellite
import sys
import os
from pathlib import Path

def _find_project_root():
    current = Path.cwd().resolve()
    for node in [current, *current.parents]:
        if (node / ".doxoade" / "vulcan" / "bin").exists(): return str(node)
    return str(current)

def main():
    # 1. Silenciador de Banco de Dados
    os.environ["DOXOADE_QUIET_BOOT"] = "1"
    
    # 2. Ancoragem de Sistema
    package_dir = Path(__file__).resolve().parent
    project_root = str(package_dir.parent)

    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    cwd_root = _find_project_root()
    
    os.environ["DOXOADE_PROJECT_ROOT"] = cwd_root 
    
    pure_mode = "--pure" in sys.argv

    # 3. Chamar o Gerenciador Central (Background Systems)
    if pure_mode:
        sys.argv.remove("--pure")
    else:
        from doxoade.boot import ignite_background_systems
        ignite_background_systems(cwd_root)

    # 4. Entrega ao CLI
    os.environ["DOXOADE_QUIET_BOOT"] = "0"
    try:
        from doxoade.cli import cli
        cli()
    except Exception as e:
        if "Exit" in type(e).__name__ or "Abort" in type(e).__name__:
            sys.exit(getattr(e, 'exit_code', 0))
        
        import traceback
        print(f"\n\x1b[41;1m 🔥 CRASH NO SISTEMA \x1b[0m")
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
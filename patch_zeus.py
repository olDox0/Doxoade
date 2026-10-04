# doxoade/patch_zeus.py
from pathlib import Path

MAIN_FILE = Path("doxoade/__main__.py")

PATCH_CODE = """
    # ⚡ ZEUS: DELEGAÇÃO AO DAEMON (ZERO COLD-START)
    if '--no-daemon' not in sys.argv and os.environ.get('DOXOADE_NO_DAEMON') != '1':
        try:
            from doxoade.tools.engine_daemon.client import dispatch_to_daemon
            _exit_code = dispatch_to_daemon(sys.argv, os.getcwd())
            if _exit_code is not None:
                sys.exit(_exit_code)
        except Exception:
            pass
"""

def apply_patch():
    if not MAIN_FILE.exists():
        print(f"❌ Arquivo não encontrado: {MAIN_FILE}")
        return
        
    content = MAIN_FILE.read_text(encoding='utf-8')
    
    if "DELEGAÇÃO AO DAEMON" in content:
        print("✔ Patch já está aplicado.")
        return
        
    # Ponto de injeção: logo após _ensure_admin_elevation()
    target = "    _ensure_admin_elevation()\n"
    if target not in content:
        print("❌ Não encontrei o ponto de injeção (_ensure_admin_elevation).")
        return
        
    new_content = content.replace(target, target + PATCH_CODE, 1)
    MAIN_FILE.write_text(new_content, encoding='utf-8')
    print("✔ Patch de Zeus aplicado com sucesso!")
    print("  Execute 'doxoade --help' novamente para testar.")

if __name__ == "__main__":
    apply_patch()

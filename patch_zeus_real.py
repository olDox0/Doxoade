# patch_zeus_real.py
from pathlib import Path

MAIN_FILE = Path("doxoade/__main__.py")

PATCH_CODE = """    # ⚡ ZEUS: TENTATIVA DE DELEGAÇÃO AO DAEMON (ZERO COLD-START)
    if '--no-daemon' not in sys.argv and os.environ.get('DOXOADE_NO_DAEMON') != '1':
        try:
            from doxoade.tools.engine_daemon.client import dispatch_to_daemon
            exit_code = dispatch_to_daemon(sys.argv, os.getcwd())
            if exit_code is not None:
                sys.exit(exit_code)  # Sucesso! O daemon fez o trabalho.
        except Exception:
            pass  # Falha na comunicação, cai para o Plano B (Cold Start)

"""

def apply_patch():
    if not MAIN_FILE.exists():
        print(f"❌ Arquivo não encontrado: {MAIN_FILE}")
        return
        
    content = MAIN_FILE.read_text(encoding='utf-8')
    
    if "TENTATIVA DE DELEGAÇÃO AO DAEMON" in content:
        print("✔ Patch já está aplicado em doxoade/__main__.py")
        return
        
    target = "def main():\n"
    if target not in content:
        print("❌ Não encontrei 'def main():' no arquivo.")
        return
        
    new_content = content.replace(target, target + PATCH_CODE, 1)
    MAIN_FILE.write_text(new_content, encoding='utf-8')
    print("✔ Patch de Zeus aplicado com sucesso em doxoade/__main__.py!")
    print("  Agora execute 'doxoade --help' para testar.")

if __name__ == "__main__":
    apply_patch()

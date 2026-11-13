# doxoade/commands/lite_xl_systems/doxly_tray.py
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import pystray
    from PIL import Image
except ImportError:
    print("⚠ Dependência ausente. Instale com: pip install pystray Pillow")
    sys.exit(1)

from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

def run_command(cmd_args):
    """Executa o comando em background para não travar o Tray."""
    def _worker():
        subprocess.Popen([sys.executable, "-m", "doxoade"] + cmd_args, creationflags=0x00000010)
    threading.Thread(target=_worker, daemon=True).start()

def get_logo_path():
    """Busca a logo.ico convertida."""
    assets_dir = LiteXLEngine.get_template_dir().parent / "assets"
    ico_path = assets_dir / "logo.ico"
    if ico_path.exists():
        return ico_path
    # Fallback para o PNG
    png_path = assets_dir / "logo.png"
    if png_path.exists():
        return png_path
    return None

def create_tray_icon():
    logo_path = get_logo_path()
    if logo_path:
        image = Image.open(logo_path)
    else:
        # Fallback: quadrado preto se a logo não existir
        image = Image.new('RGB', (64, 64), color=(30, 30, 30))

    # Define o Menu (Clique Esquerdo/Direito)
    menu = pystray.Menu(
        pystray.MenuItem("🏛️ Abrir Canonical", lambda: run_command(["doxly", "canonical"]))
#        pystray.MenuItem("🏛️ Abrir Canonical", lambda: run_command(["doxly", "deploy", "launch", "-m", "production"])),
        pystray.MenuItem("🚀 Redeploy PRODUCTION", lambda: run_command(["doxly", "deploy", "production", "-f", "--legacy-direct"])),
        pystray.MenuItem("🧪 Redeploy TEST", lambda: run_command(["doxly", "deploy", "test", "-f"])),
        pystray.MenuItem("🎯 Redeploy STAGING", lambda: run_command(["doxly", "deploy", "staging", "-f", "--launch-test"])),
        pystray.MenuItem("⚡ PROMOTE", lambda: run_command(["doxly", "deploy", "promote", "-f"])),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("🖥️ Terminal Launcher", lambda: subprocess.Popen(["cmd.exe", "/c", "doxoade", "doxly", "deploy", "menu", "& pause"], creationflags=0x00000010)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("❌ Sair", lambda icon, item: icon.stop())
    )

    icon = pystray.Icon("Doxly", image, "Doxly Launcher", menu)
    return icon

def start_tray():
    """Inicia o ícone na bandeja do sistema (executa em thread separada)."""
    icon = create_tray_icon()
    
    # Roda em uma thread para não bloquear o terminal
    threading.Thread(target=icon.run, daemon=True).start()
    
    print("🐺 Doxly Tray Icon iniciado. Verifique ao lado do relógio do Windows.")
    print("   (Pressione Ctrl+C neste terminal para encerrar o Tray)")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        icon.stop()
        print("🛑 Doxly Tray encerrado.")

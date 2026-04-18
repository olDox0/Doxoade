@click.command()
def build_gui():
    """Compila a DXGUI nativa para o sistema atual."""
    if platform.system() == "Windows":
        # Comando para gerar a DLL
        subprocess.run(['gcc', '-shared', '-o', 'dxgui.dll', 'native/win/dxgui_win.c', '-lgdi32'])
    else:
        # Comando para gerar a .so no Linux
        subprocess.run(['gcc', '-shared', '-o', 'libdxgui.so', '-fPIC', 'native/linux/dxgui_x11.c', '-lX11'])
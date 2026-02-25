# Proxy de Cores
try:
    from .doxcolors import Fore, Back, Style, colors
except ImportError:
    # Fallback de segurança se o doxcolors não existir (Bootstrap)
    class Fore: RED = ""; GREEN = ""; YELLOW = ""; CYAN = ""; WHITE = ""; MAGENTA = ""; BLUE = ""; RESET = ""
    class Back: RESET = ""
    class Style: BRIGHT = ""; DIM = ""; RESET_ALL = ""
    colors = None
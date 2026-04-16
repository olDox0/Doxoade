# doxoade/doxoade/tools/__init__.py
try:
    from .doxcolors import Fore, Back, Style, colors
except ImportError:

    class Fore:
        RED = ''
        GREEN = ''
        YELLOW = ''
        CYAN = ''
        WHITE = ''
        MAGENTA = ''
        BLUE = ''
        RESET = ''

    class Back:
        RESET = ''

    class Style:
        BRIGHT = ''
        DIM = ''
        RESET_ALL = ''
    colors = None
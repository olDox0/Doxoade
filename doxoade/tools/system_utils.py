# doxoade/commands/mobile_ide_terms.py

import os

def is_termux():
    """Detecta se está rodando no Termux"""
    return os.path.exists('/data/data/com.termux')

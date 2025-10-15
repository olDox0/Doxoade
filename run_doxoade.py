#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Ponto de entrada inteligente e universal para a Doxoade.
"""

import sys
import os
import re

# --- LÓGICA DO BOOTSTRAPPER INTELIGENTE ---

# O caminho para o executável Python deste script
CURRENT_PYTHON = sys.executable

# Define o caminho esperado para o executável Python do venv local
VENV_PYTHON_WIN = os.path.join(os.getcwd(), 'venv', 'Scripts', 'python.exe')
VENV_PYTHON_UNIX = os.path.join(os.getcwd(), 'venv', 'bin', 'python')

# Verifica se um venv local existe e se NÃO estamos rodando dentro dele
if os.name == 'nt' and os.path.exists(VENV_PYTHON_WIN) and CURRENT_PYTHON.lower() != VENV_PYTHON_WIN.lower():
    # Re-lança a si mesmo com o Python do venv no Windows
    os.execv(VENV_PYTHON_WIN, [VENV_PYTHON_WIN, __file__] + sys.argv[1:])
elif os.name != 'nt' and os.path.exists(VENV_PYTHON_UNIX) and CURRENT_PYTHON != VENV_PYTHON_UNIX:
    # Re-lança a si mesmo com o Python do venv no Linux/macOS/Termux
    os.execv(VENV_PYTHON_UNIX, [VENV_PYTHON_UNIX, __file__] + sys.argv[1:])

# Se chegamos aqui, ou não há venv local, ou já estamos rodando no venv correto.
# Agora podemos importar e executar a doxoade com segurança.

from doxoade.doxoade import cli

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    cli()
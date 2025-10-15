#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import re

# --- LÓGICA DO BOOTSTRAPPER CONSCIENTE DE CONTEXTO ---

# O comando 'doctor' é especial - ele deve rodar no ambiente da doxoade,
# não no venv do projeto alvo, para poder consertá-lo.
IS_DOCTOR_COMMAND = len(sys.argv) > 1 and sys.argv[1] == 'doctor'

# O caminho para o executável Python deste script
CURRENT_PYTHON = sys.executable

# Caminhos esperados para o venv local
VENV_PYTHON_WIN = os.path.join(os.getcwd(), 'venv', 'Scripts', 'python.exe')
VENV_PYTHON_UNIX = os.path.join(os.getcwd(), 'venv', 'bin', 'python')

# Só fazemos o re-lançamento se o comando NÃO for 'doctor'
if not IS_DOCTOR_COMMAND:
    if os.name == 'nt' and os.path.exists(VENV_PYTHON_WIN) and CURRENT_PYTHON.lower() != VENV_PYTHON_WIN.lower():
        os.execv(VENV_PYTHON_WIN, [VENV_PYTHON_WIN, __file__] + sys.argv[1:])
    elif os.name != 'nt' and os.path.exists(VENV_PYTHON_UNIX) and CURRENT_PYTHON != VENV_PYTHON_UNIX:
        os.execv(VENV_PYTHON_UNIX, [VENV_PYTHON_UNIX, __file__] + sys.argv[1:])

# Se chegamos aqui, ou o comando é 'doctor', ou não há venv, ou já estamos no venv correto.
from doxoade.doxoade import cli

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    cli()
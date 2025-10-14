#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Ponto de entrada robusto para a Doxoade.
Este script garante que a ferramenta seja executada com o interpretador
correto e com o caminho do módulo devidamente configurado.
"""

# run_doxoade.py
import re
import sys
from doxoade.doxoade import cli

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    cli()
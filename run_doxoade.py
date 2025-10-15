# run_doxoade.py (Versão Final e Simples)
import sys
import re
from doxoade.doxoade import cli

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    cli()
# verify_tools.py
import ast, pathlib, sys
tree = ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
fns = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
from collections import Counter
dups = {n: c for n, c in Counter(fns).items() if c > 1}
if dups:
    print(f'❌ DUPLICADAS: {dups}')
    sys.exit(1)
print(f'✅ {len(fns)} funções, sem duplicatas: {fns}')

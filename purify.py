import re
import os
from pathlib import Path

# Padrões de corrupção gerados pelo erro anterior
# 1. f" ... ' (Abre com dupla, fecha com simples)
CORRUPT_1 = re.compile(r'(f")([^"\n]*?\{[^}\n]*?\}[^"\n]*?)(\')')
# 2. f' ... " (Abre com simples, fecha com dupla)
CORRUPT_2 = re.compile(r"(f')([^'\n]*?\{[^}\n]*?\}[^'\n]*?)(\")")

def purify():
    count = 0
    for root, dirs, files in os.walk("."):
        if any(x in root for x in ["venv", ".git", "__pycache__"]): continue
        for file in files:
            if file.endswith(".py"):
                path = Path(root) / file
                content = path.read_text(encoding="utf-8", errors="ignore")
                
                # Conserta f" ... ' -> f" ... "
                new_content = CORRUPT_1.sub(r'\1\2"', content)
                # Conserta f' ... " -> f" ... " (mais seguro para 3.11)
                new_content = CORRUPT_2.sub(r'f"\2"', new_content)
                
                if new_content != content:
                    path.write_text(new_content, encoding="utf-8")
                    print(f"[FIXED] {path}")
                    count += 1
    print(f"\nFim. {count} arquivos purificados.")

if __name__ == "__main__":
    purify()
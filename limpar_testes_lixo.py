import os
import shutil
from pathlib import Path

# Define as pastas de teste que são "espelhos" de pastas ignoradas
pastas_lixo = [
    r"tests\.dox_agent_workspace",
    r"tests\doxoade\neural\.dox_agent_workspace",
    r"tests\.dox_lab",
    r"tests\pytest_temp_dir",
    r"tests\regression_tests",
    r"tests\tmp",
    r"tests\Canone_Test",
    r"tests\commands_test"
]

print("🧹 Limpando testes gerados indevidamente...")

for pasta in pastas_lixo:
    p = Path(pasta)
    if p.exists():
        print(f"   REMOVENDO: {p}")
        shutil.rmtree(p)

# Remove arquivos soltos de teste para infraestrutura
arquivos_lixo = [
    r"tests\test_setup.py",
    r"tests\test_install.py",
    r"tests\doxoade\commands\test_install.py",
    r"tests\test_run_doxoade.py",
    r"tests\test_clean_db.py",
    r"tests\doxoade\test___init__.py" # Remove testes para __init__
]

for arq in arquivos_lixo:
    p = Path(arq)
    if p.exists():
        print(f"   REMOVENDO: {p}")
        os.remove(p)

print("✅ Limpeza concluída.")
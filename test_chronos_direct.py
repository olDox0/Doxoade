import sys
import os
# Garante que estamos importando do diretório local
sys.path.insert(0, os.getcwd())

from doxoade.cli import cli
from click.testing import CliRunner

print(">>> Testando Chronos Direto...")
runner = CliRunner()
result = runner.invoke(cli, ['mk', 'teste_direct.txt'])

print(f"Exit Code: {result.exit_code}")
print(f"Output:\n{result.output}")

if "[Chronos]" in result.output:
    print("\n[SUCESSO] Chronos detectado no output!")
else:
    print("\n[FALHA] Chronos NÃO detectado.")

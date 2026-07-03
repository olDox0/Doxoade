# test_hermes_redirect.py
import sys
import time
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style

print("=" * 70)
print("🔬 TESTE: Redirecionamento Vulcan Tier 3 → Hermes")
print("=" * 70)

# 1. Instala o HermesFinder ANTES de importar click
print("\n[1/4] Instalando HermesFinder...")
from doxoade.tools.hermes_systems.hermes_hook import install
install('.')
print("  ✔ HermesFinder instalado no sys.meta_path")

# 2. Importa click e verifica o caminho
print("\n[2/4] Importando click...")
t0 = time.perf_counter()
import click
t1 = time.perf_counter()
print(f"  ✔ click importado em {(t1-t0)*1000:.2f}ms")

# 3. Verifica se o __file__ aponta para .hermes
print("\n[3/4] Verificando origem do módulo...")
click_file = Path(click.__file__)
print(f"  📍 Caminho: {click_file}")

if click_file.suffix == '.hermes':
    print(f"  {Fore.GREEN}✔ REDIRECIONAMENTO ATIVO! Módulo carregado via Hermes{Style.RESET_ALL}")
    print(f"     Formato: {click_file.read_bytes()[:4]}")
else:
    print(f"  {Fore.YELLOW}⚠ Módulo carregado via Python puro (.py){Style.RESET_ALL}")
    print(f"     Possíveis causas:")
    print(f"     - HermesFinder não interceptou o import")
    print(f"     - Arquivo .hermes não existe para este módulo")
    print(f"     - Fallback para .py original")

# 4. Testa submódulos
print("\n[4/4] Testando submódulos do click...")
submodules = ['click.decorators', 'click.utils', 'click.parser']
for mod_name in submodules:
    try:
        mod = __import__(mod_name, fromlist=[''])
        mod_file = Path(mod.__file__)
        is_hermes = mod_file.suffix == '.hermes'
        status = f"{Fore.GREEN}✔ HERMES{Style.RESET_ALL}" if is_hermes else f"{Fore.YELLOW}⚠ PY{Style.RESET_ALL}"
        print(f"  {mod_name:30} {status} → {mod_file.name}")
    except Exception as e:
        print(f"  {mod_name:30} {Fore.RED}✘ ERRO{Style.RESET_ALL} → {e}")

print("\n" + "=" * 70)
print("✅ Teste concluído")
print("=" * 70)
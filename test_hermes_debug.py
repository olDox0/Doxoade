# test_hermes_debug.py
import sys
import os
from pathlib import Path

print("=" * 70)
print("🔬 DEBUG: Fluxo de Redirecionamento Hermes")
print("=" * 70)

# 1. Verifica se os .hermes existem
print("\n[1/5] Verificando arquivos .hermes...")
lib_dir = Path('.doxoade/hermes/lib/click')
if lib_dir.exists():
    hermes_files = list(lib_dir.glob('*.hermes'))
    print(f"  ✔ Encontrados {len(hermes_files)} arquivos .hermes")
    for f in hermes_files[:3]:
        print(f"     • {f.name}")
else:
    print(f"  ✘ Diretório não existe: {lib_dir}")

# 2. Instala o HermesFinder
print("\n[2/5] Instalando HermesFinder...")
from doxoade.tools.hermes_systems.hermes_hook import install, HermesFinder
install('.')

# 3. Verifica se o HermesFinder está no sys.meta_path
print("\n[3/5] Verificando sys.meta_path...")
hermes_finders = [f for f in sys.meta_path if isinstance(f, HermesFinder)]
print(f"  ✔ HermesFinder encontrado: {len(hermes_finders) > 0}")
print(f"  Posição no meta_path: {sys.meta_path.index(hermes_finders[0]) if hermes_finders else 'N/A'}")

# 4. Testa manualmente o find_spec
print("\n[4/5] Testando find_spec manualmente...")
if hermes_finders:
    finder = hermes_finders[0]
    
    # Testa click.__init__
    spec = finder.find_spec('click', None, None)
    print(f"  click.__init__: {'✔ ENCONTRADO' if spec else '✘ NÃO ENCONTRADO'}")
    if spec:
        print(f"     Origin: {spec.origin}")
    
    # Testa click.decorators
    spec = finder.find_spec('click.decorators', None, None)
    print(f"  click.decorators: {'✔ ENCONTRADO' if spec else '✘ NÃO ENCONTRADO'}")
    if spec:
        print(f"     Origin: {spec.origin}")

# 5. Testa o import real
print("\n[5/5] Testando import real...")
import click
print(f"  click.__file__: {click.__file__}")
print(f"  É .hermes? {click.__file__.endswith('.hermes')}")

print("\n" + "=" * 70)
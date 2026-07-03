# test_hermes_all_imports.py - Versão Corrigida
import sys
import os
import click

# Instala o HermesFinder ANTES de qualquer import
from doxoade.tools.hermes_systems.hermes_hook import install
install('.')

# Monkey-patch do importlib para rastrear todos os imports
_import_log = []

# Patcheia TODOS os finders, não apenas o primeiro
_original_find_specs = {}

for finder in sys.meta_path:
    if hasattr(finder, 'find_spec'):
        # Salva referência original de cada finder
        _original_find_specs[id(finder)] = finder.find_spec
        
        def _make_patched_find_spec(original_method, finder_ref):
            def _patched_find_spec(fullname, path=None, target=None):
                result = original_method(fullname, path, target)
                origin = getattr(result, 'origin', None) if result else None
                _import_log.append({
                    'module': fullname,
                    'origin': origin,
                    'is_hermes': origin and '.hermes' in str(origin) if origin else False
                })
                return result
            return _patched_find_spec
        
        # Aplica o patch
        finder.find_spec = _make_patched_find_spec(finder.find_spec, finder)

def _patched_find_spec(fullname, path=None, target=None):
    result = _original_find_spec(fullname, path, target)
    origin = getattr(result, 'origin', None) if result else None
    _import_log.append({
        'module': fullname,
        'origin': origin,
        'is_hermes': origin and '.hermes' in str(origin) if origin else False
    })
    return result

# Aplica o patch em todos os finders
for finder in sys.meta_path:
    if hasattr(finder, 'find_spec'):
        finder.find_spec = _patched_find_spec

# Agora importa o click
print("🔬 Importando click...")
import click
import click.decorators
import click.utils
import click.parser

# Mostra o log
print(f"\n{'='*70}")
print(f"📊 LOG DE IMPORTS ({len(_import_log)} módulos)")
print(f"{'='*70}\n")

hermes_count = 0
py_count = 0

for entry in _import_log:
    if entry['is_hermes']:
        status = f"{Fore.GREEN}✔ HERMES{Style.RESET_ALL}"
        hermes_count += 1
    else:
        status = f"{Fore.YELLOW}⚠ PY{Style.RESET_ALL}"
        py_count += 1
    
    print(f"  {entry['module']:40} {status}")

print(f"\n{'='*70}")
print(f"📊 RESUMO: {hermes_count} Hermes | {py_count} Python puro")
print(f"{'='*70}")
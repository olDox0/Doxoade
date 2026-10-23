# -*- coding: utf-8 -*-
# doxoade\commands\check_systems\check_cli_integrity.py
"""
Validador de Integridade do Mapa de Comandos (Lazy-Map Linter).
Garante que todas as strings de rota em cli.py são importáveis e existem.
"""
from importlib import import_module
import sys

def audit_cli_lazy_map():
    from doxoade.cli import DoxoadeCLI  # ou a classe que possui o _doxoade_commands
    cli_instance = DoxoadeCLI()
    routes = cli_instance._doxoade_commands

    print(f"\n🔍 [AUDIT] Verificando integridade de {len(routes)} comandos...")
    errors = []

    for cmd_name, route in routes.items():
        if ":" not in route:
            errors.append((cmd_name, route, "Formato inválido (ausência de ':')"))
            continue
        
        mod_path, attr_name = route.split(":")
        
        if "__init__" in mod_path:
            errors.append((cmd_name, route, "Sintaxe proibida: '__init__' no path do módulo"))
            continue

        try:
            mod = import_module(mod_path)
        except Exception as e:
            errors.append((cmd_name, route, f"Falha no import do módulo ({e})"))
            continue

        if not hasattr(mod, attr_name):
            errors.append((cmd_name, route, f"Atributo '{attr_name}' não existe no módulo"))

    if not errors:
        print("✅ [MA'AT] Todos os comandos do CLI estão 100% íntegros e roteáveis!\n")
        return True

    print(f"\n❌ [CRÍTICO] Encontradas {len(errors)} rotas corrompidas no CLI:\n")
    for cmd, route, reason in errors:
        print(f"  • Comando: '{cmd}'")
        print(f"    ↳ Rota:   {route}")
        print(f"    ↳ Motivo: {reason}\n")
    return False

if __name__ == "__main__":
    success = audit_cli_lazy_map()
    sys.exit(0 if success else 1)

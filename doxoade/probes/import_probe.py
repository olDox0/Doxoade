# doxoade/probes/import_probe.py
import sys
import json
import importlib.util

def check_modules(modules_to_check):
    missing = []
    for module_name in modules_to_check:
        try:
            if importlib.util.find_spec(module_name) is None:
                missing.append(module_name)
        except (ValueError, ImportError):
            pass
    return missing

if __name__ == "__main__":
    print(json.dumps(check_modules(json.loads(sys.stdin.read()))))
# doxoade/tools/hermes_systems/hermes_deadzone.py
"""
Hermes Deadzone - Previsão Estática e Quarentena Dinâmica.
Identifica módulos que usam padrões incompatíveis com o bytecode HBC6
(ex: introspecção de source, frame hacking) e os isola em Python Puro.
"""
import json
import re
from pathlib import Path
from typing import Set, List

# Gatilhos que quebram o Motor C ou a introspecção do HBC6
DEADZONE_TRIGGERS = {
    "inspect.getsource": re.compile(r'\binspect\.getsource\b'),
    "inspect.getsourcefile": re.compile(r'\binspect\.getsourcefile\b'),
    "inspect.findsource": re.compile(r'\binspect\.findsource\b'),
    "inspect.getframeinfo": re.compile(r'\binspect\.getframeinfo\b'),
    "sys._getframe": re.compile(r'\bsys\._getframe\b'),
    "sys._current_frames": re.compile(r'\bsys\._current_frames\b'),
    "ctypes.pythonapi": re.compile(r'\bctypes\.pythonapi\b'),
}

DEADZONE_FILE = Path(".doxoade/hermes/deadzone.json")

def scan_file_for_triggers(file_path: Path) -> List[str]:
    """Retorna a lista de triggers encontrados em um arquivo."""
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []
    
    found = []
    for trigger_name, pattern in DEADZONE_TRIGGERS.items():
        if pattern.search(content):
            found.append(trigger_name)
    return found

def scan_project(project_root: str) -> Set[str]:
    """Varre o projeto e retorna o set de módulos que devem ir para a Deadzone."""
    root = Path(project_root).resolve()
    deadzone_modules = set()
    ignore_dirs = {'venv', '.venv', '__pycache__', '.doxoade', 'build', 'dist', '.git', 'node_modules'}
    
    for py_file in root.rglob('*.py'):
        if any(part in py_file.parts for part in ignore_dirs):
            continue
            
        triggers = scan_file_for_triggers(py_file)
        if triggers:
            try:
                rel_path = py_file.relative_to(root.parent)
                module_name = '.'.join(rel_path.with_suffix('').parts)
                if module_name.startswith('doxoade.'):
                    deadzone_modules.add(module_name)
            except ValueError:
                pass
                
    return deadzone_modules

def update_deadzone_file(new_modules: Set[str]) -> int:
    """Atualiza o arquivo deadzone.json com novos módulos. Retorna a qtd total."""
    DEADZONE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    existing = set()
    if DEADZONE_FILE.exists():
        try:
            existing = set(json.loads(DEADZONE_FILE.read_text(encoding='utf-8')))
        except Exception:
            existing = set()
            
    combined = existing.union(new_modules)
    DEADZONE_FILE.write_text(
        json.dumps(sorted(list(combined)), indent=2), 
        encoding='utf-8'
    )
    return len(combined)

def load_deadzone() -> Set[str]:
    """Carrega a deadzone atual do disco."""
    if not DEADZONE_FILE.exists():
        return set()
    try:
        return set(json.loads(DEADZONE_FILE.read_text(encoding='utf-8')))
    except Exception:
        return set()
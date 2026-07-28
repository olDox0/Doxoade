# repair_vulcan_topology.py
import re
from pathlib import Path

def run_topology_sync():
    root = Path('.')
    fixes = 0
    
    print("🩹 [SOTERIA] Sincronizando topologia do silo vulcan_systems...")
    
    # 1. Substituições LITERAIS (Usa str.replace, zero risco de escape)
    literal_replacements = [
        ("doxoade/commands/vulcan_systems/vulcan_cmd.py", "doxoade/commands/vulcan_systems/vulcan_cmd.py"),
        ("doxoade\\commands\\vulcan_cmd.py", "doxoade\\commands\\vulcan_systems\\vulcan_cmd.py"),
    ]
    
    # 2. Substituições via REGEX (Usa re.compile com raw strings)
    regex_replacements = [
        (re.compile(r"\bdoxoade\.commands\.vulcan_cmd\b(?!\w)"), "doxoade.commands.vulcan_systems.vulcan_cmd"),
        (re.compile(r"\bfrom\s+\.vulcan_cmd\s+import\b"), "from .vulcan_systems.vulcan_cmd import"),
    ]
    
    for py_file in root.rglob('*.py'):
        if any(p in py_file.parts for p in ('venv', '.git', '__pycache__', '.doxoade')):
            continue
            
        try:
            text = py_file.read_text(encoding='utf-8')
        except Exception:
            continue
            
        original = text
        
        # Aplica substituições literais
        for old, new in literal_replacements:
            text = text.replace(old, new)
            
        # Aplica substituições via regex
        for pattern, repl in regex_replacements:
            text = pattern.sub(repl, text)
            
        if text != original:
            py_file.write_text(text, encoding='utf-8')
            print(f"  ✔ Cicatrizado: {py_file}")
            fixes += 1
            
    print(f"\n✅ [LÁZARO] Protocolo concluído. {fixes} arquivos reparados com sucesso.")

if __name__ == '__main__':
    run_topology_sync()
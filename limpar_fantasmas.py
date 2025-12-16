# limpar_fantasmas.py
import os
import sqlite3
from doxoade.database import get_db_connection
from doxoade.shared_tools import _get_project_config

def is_ignored(file_path, ignore_list):
    # Normaliza barras para comparação
    path = file_path.replace('\\', '/')
    for ignore in ignore_list:
        clean_ignore = ignore.replace('\\', '/').strip('/')
        if clean_ignore in path.split('/'):
            return True
    return False

conn = get_db_connection()
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("🔍 Iniciando Exorcismo de Fantasmas...")

# Carrega configuração de ignore do projeto atual
config = _get_project_config(None, start_path='.')
ignore_list = config.get('ignore', [])
# Adiciona padrões padrão que as vezes não estão no toml mas são implícitos
ignore_list.extend(['.dox_agent_workspace', 'venv', 'tests', 'check_tests']) 

print(f"📋 Lista de Ignore: {ignore_list}")

cursor.execute("SELECT finding_hash, file_path FROM open_incidents")
incidentes = cursor.fetchall()

removidos_inexistentes = 0
removidos_ignorados = 0

for row in incidentes:
    f_hash = row['finding_hash']
    rel_path = row['file_path']
    abs_path = os.path.abspath(rel_path)
    
    # 1. Checa se arquivo existe no disco
    if not os.path.exists(abs_path):
        cursor.execute("DELETE FROM open_incidents WHERE finding_hash = ?", (f_hash,))
        removidos_inexistentes += 1
        print(f"   👻 Fantasma removido (não existe): {rel_path}")
        continue
        
    # 2. Checa se arquivo deveria ser ignorado
    if is_ignored(rel_path, ignore_list):
        cursor.execute("DELETE FROM open_incidents WHERE finding_hash = ?", (f_hash,))
        removidos_ignorados += 1
        print(f"   🚫 Ignorado removido (config): {rel_path}")

conn.commit()
conn.close()

print("-" * 40)
print(f"✅ Total removidos: {removidos_inexistentes + removidos_ignorados}")
print(f"   - Inexistentes: {removidos_inexistentes}")
print(f"   - Ignorados: {removidos_ignorados}")
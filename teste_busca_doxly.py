# teste_busca_doxly.py
# -*- coding: utf-8 -*-
import sqlite3, re, sys
from pathlib import Path

# 1. Simular os caminhos que o Lite XL usa
home = Path.home()
db_path = home / ".doxoade" / "consult_docs_fts5.db"
out_path = home / ".doxoade" / "consult_search_test.lua"

print(f"🔍 [DIAG] Banco de dados esperado em: {db_path}")
print(f"💾 [DIAG] Arquivo de saída esperado em: {out_path}")

if not db_path.exists():
    print("❌ ERRO CRÍTICO: O banco de dados NÃO existe neste caminho!")
    sys.exit(1)

query = "json"
print(f"⚡ [DIAG] Iniciando busca por: '{query}'...")

try:
    # 2. Conexão direta (igual ao script injetado)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    
    clean_q = re.sub(r'[^\w\s]', ' ', query).strip()
    tokens = clean_q.split()
    fts_query = " OR ".join([f'"{tok}"*' for tok in tokens])
    print(f"📝 [DIAG] Query FTS5 gerada: {fts_query}")
    
    sql = """
        SELECT path, title, snippet(docs_fts, 3, '\x02', '\x03', '...', 18)
        FROM docs_fts
        WHERE docs_fts MATCH ?
        ORDER BY rank
        LIMIT 25;
    """
    
    results = conn.execute(sql, (fts_query,)).fetchall()
    conn.close()
    print(f"✅ [DIAG] Busca concluída! {len(results)} resultados encontrados.")
    
    # 3. Função de limpeza (igual ao Lua)
    def clean_lua_str(s):
        if not s: return ""
        clean = str(s).replace("\r", "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean)

    # 4. Gerar a tabela Lua
    lines = [
        "return {",
        f'  query = "{clean_lua_str(query)}",',
        f'  total = {len(results)},',
        '  results = {'
    ]
    
    for path, title, snippet in results:
        lines.append('    {')
        lines.append(f'      title = "{clean_lua_str(title)}",')
        lines.append(f'      path = "{clean_lua_str(path)}",')
        lines.append(f'      snippet = "{clean_lua_str(snippet or title)}"')
        lines.append('    },')
        
    lines.append('  }')
    lines.append('}')
    
    # 5. Gravar o arquivo
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text('\n'.join(lines), encoding="utf-8")
    print(f"✔ [DIAG] Arquivo Lua gerado com sucesso! ({out_path.stat().st_size} bytes)")
    
except Exception as e:
    print(f"❌ [DIAG] EXCEÇÃO DURANTE A EXECUÇÃO: {e}")
    import traceback
    traceback.print_exc()

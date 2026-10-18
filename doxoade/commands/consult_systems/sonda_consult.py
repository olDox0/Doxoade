# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/sonda_consult.py
"""
Sonda Forense Consult & Doxly (Pilar Hórus).
Diagnóstico profundo do pipeline IPC: Python -> SQLite FTS5 -> Disco -> Lua.
"""
from __future__ import annotations
import os
import sys
import time
import subprocess
import sqlite3
import datetime
from pathlib import Path

def hr(title=""):
    print(f"\n{'='*25} {title} {'='*25}")

def run_probe():
    print("🦅 [HÓRUS] INICIANDO SONDA FORENSE CONSULT & DOXLY\n")
    
    # ── 1. INSPEÇÃO DE PASTAS E PATHS ──
    hr("1. RASTREAMENTO DE DIRETÓRIOS")
    home_dir = Path.home()
    db_path = home_dir / ".doxoade" / "consult_docs_fts5.db"
    
    test_deploy_dir = home_dir / ".config" / "lite-xl" / ".doxoade" / "test_deploy" / ".doxoade"
    lite_user_dir = home_dir / ".config" / "lite-xl" / ".doxoade"
    
    print(f"• Banco FTS5:           {db_path} (Existe: {db_path.exists()})")
    print(f"• Pasta Test Deploy:    {test_deploy_dir} (Existe: {test_deploy_dir.exists()})")
    print(f"• Pasta Lite XL Padrão: {lite_user_dir} (Existe: {lite_user_dir.exists()})")
    
    # Inspeciona timestamps dos arquivos atuais
    if test_deploy_dir.exists():
        print("\nArquivos ativos em test_deploy/.doxoade:")
        for f in sorted(test_deploy_dir.glob("*consult*")):
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%H:%M:%S")
            print(f"  ↳ {f.name:<25} {f.stat().st_size:>8} bytes | Última escrita: {mtime}")

    # ── 2. AUDITORIA DO INTERPRETADOR PYTHON ──
    hr("2. SONDA DE INTERPRETADOR PYTHON")
    py_txt = test_deploy_dir / "python_path.txt"
    py_exe = sys.executable
    if py_txt.exists():
        try:
            candidate = py_txt.read_text(encoding="utf-8").strip()
            if candidate and Path(candidate).exists():
                py_exe = candidate
                print(f"• Python via python_path.txt: {py_exe}")
        except Exception as e:
            print(f"⚠ Erro ao ler python_path.txt: {e}")
    else:
        print(f"• Python ativo no venv: {py_exe}")

    t0_py = time.perf_counter()
    res_py = subprocess.run([py_exe, "-c", "import sys; print(f'Python OK: {sys.version.split()[0]}')"], capture_output=True, text=True)
    dt_py = (time.perf_counter() - t0_py) * 1000
    print(f"• Teste de inicialização do Python: {res_py.stdout.strip()} ({dt_py:.1f}ms)")
    if res_py.returncode != 0:
        print(f"❌ ERRO no Python: {res_py.stderr}")

    # ── 3. SONDA DE BANCO DE DADOS (SQLITE FTS5) ──
    hr("3. SONDA DE CONSULTA SQLITE FTS5")
    if not db_path.exists():
        print(f"❌ Banco não encontrado em: {db_path}")
        return

    t0_db = time.perf_counter()
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    cursor = conn.cursor()
    
    # Checa contagem
    cursor.execute("SELECT count(*) FROM docs;")
    total_docs = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM docs_fts;")
    total_fts = cursor.fetchone()[0]
    dt_conn = (time.perf_counter() - t0_db) * 1000
    print(f"• Conexão SQLite estabelecida em: {dt_conn:.2f}ms")
    print(f"• Registros em docs:     {total_docs}")
    print(f"• Registros em docs_fts: {total_fts}")

    # Testa busca de 'json'
    t0_search = time.perf_counter()
    sql_search = """
        SELECT path, title, snippet(docs_fts, 3, '\x02', '\x03', '...', 18)
        FROM docs_fts
        WHERE docs_fts MATCH '"json"*'
        ORDER BY rank
        LIMIT 25;
    """
    rows_json = cursor.execute(sql_search).fetchall()
    dt_search = (time.perf_counter() - t0_search) * 1000
    print(f"• Busca FTS5 por 'json': {len(rows_json)} resultados em {dt_search:.2f}ms!")

    # Testa busca de 'dataclass'
    t0_dc = time.perf_counter()
    rows_dc = cursor.execute("""
        SELECT path, title, snippet(docs_fts, 3, '\x02', '\x03', '...', 18)
        FROM docs_fts
        WHERE docs_fts MATCH '"dataclass"*'
        ORDER BY rank
        LIMIT 25;
    """).fetchall()
    dt_dc = (time.perf_counter() - t0_dc) * 1000
    print(f"• Busca FTS5 por 'dataclass': {len(rows_dc)} resultados em {dt_dc:.2f}ms!")
    conn.close()

    # ── 4. EMULAÇÃO COMPLETA DO SUBPROCESSO DO LITE XL ──
    hr("4. SIMULAÇÃO DO DISPARO DO SUBPROCESSO (LITE XL IPC)")
    target_dir = test_deploy_dir if test_deploy_dir.exists() else lite_user_dir
    probe_run_py = target_dir / "probe_runner.py"
    probe_out_lua = target_dir / "probe_output.lua"

    if probe_out_lua.exists():
        probe_out_lua.unlink()

    # Gera exatamente o script Python que o Lite XL gera
    script_content = f"""# -*- coding: utf-8 -*-
import sqlite3, re
from pathlib import Path

db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
conn = sqlite3.connect(str(db_path), timeout=5.0)

fts_query = '"json"*'
sql = '''
    SELECT path, title, snippet(docs_fts, 3, '\\x02', '\\x03', '...', 18)
    FROM docs_fts
    WHERE docs_fts MATCH ?
    ORDER BY rank
    LIMIT 25;
'''
try:
    results = conn.execute(sql, (fts_query,)).fetchall()
except Exception:
    results = []
finally:
    conn.close()

def clean_lua_str(s):
    if not s: return ""
    clean = str(s).replace("\\r", "").replace("\\\\", "\\\\\\\\").replace('"', '\\\\"').replace("\\n", " ")
    return re.sub(r'[\\x00-\\x1f\\x7f-\\x9f]', '', clean)

lines = [
    "return {{",
    '  query = "json",',
    f'  total = {{len(results)}},',
    '  results = {{'
]

for path, title, snippet in results:
    lines.append('    {{')
    lines.append(f'      title = "{{clean_lua_str(title)}}",')
    lines.append(f'      path = "{{clean_lua_str(path)}}",')
    lines.append(f'      snippet = "{{clean_lua_str(snippet or title)}}"')
    lines.append('    }},')

lines.append('  }}')
lines.append('}}')

out_path = Path(r"{probe_out_lua}")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text('\\n'.join(lines), encoding="utf-8")
"""
    probe_run_py.write_text(script_content, encoding="utf-8")
    print(f"• Script de teste gravado em: {probe_run_py}")

    # Dispara o subprocesso e cronometra
    print(f"• Disparando subprocesso via {Path(py_exe).name}...")
    t0_spawn = time.perf_counter()
    proc = subprocess.run([py_exe, str(probe_run_py)], capture_output=True, text=True)
    dt_spawn = (time.perf_counter() - t0_spawn) * 1000

    print(f"  ↳ Retorno do processo: Código {proc.returncode} em {dt_spawn:.1f}ms")
    if proc.stderr:
        print(f"  ❌ STDERR do Python: {proc.stderr}")

    # Verifica se o arquivo de saída surgiu
    if probe_out_lua.exists():
        size = probe_out_lua.stat().st_size
        print(f"  ✔ Arquivo probe_output.lua GERADO com sucesso ({size} bytes)!")
    else:
        print(f"  ❌ FALHA: probe_output.lua NÃO foi gerado!")

    # ── 5. VEREDICTO FORENSE ──
    hr("5. VEREDICTO FORENSE DA SONDA")
    if dt_spawn < 1000 and probe_out_lua.exists():
        print("✅ [DIAGNÓSTICO] O pipeline Python + SQLite está operando em ALTÍSSIMA VELOCIDADE!")
        print(f"   Tempo total de spawn + gravação: {dt_spawn:.1f}ms (MUITO abaixo do teto de 5000ms do Doxly).")
        print("   Isso indica que o gargalo NÃO é o Python nem o SQLite, mas sim como o Lite XL")
        print("   está disparando o processo ou qual pasta ele está monitorando.")
    else:
        print(f"⚠️ [DIAGNÓSTICO] O processo demorou {dt_spawn:.1f}ms ou falhou.")

    # Limpeza
    pcall_remove = lambda p: p.unlink() if p.exists() else None
    pcall_remove(probe_run_py)
    pcall_remove(probe_out_lua)
    print("\n🦅 [HÓRUS] Sonda concluída com sucesso.\n")

if __name__ == "__main__":
    run_probe()

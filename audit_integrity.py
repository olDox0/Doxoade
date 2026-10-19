# -*- coding: utf-8 -*-
# audit_integrity.py — ⚖️ [MA'AT] Auditoria de integridade do pipeline Consult
# Uso: python audit_integrity.py [path_doc_cpython] [uid_cheatsheet]
import json, sqlite3, sys, os, re, html as html_lib
from pathlib import Path

home = Path.home()
jsonl   = home / ".doxoade" / "consult" / "canonical" / "python_cheatsheet.jsonl"
db_path = home / ".doxoade" / "consult_docs_fts5.db"
md_path = home / ".config" / "lite-xl" / ".doxoade" / "test_deploy" / ".doxoade" / "consult_active_doc.md"
cpython_path = sys.argv[1] if len(sys.argv) > 1 else "library/dataclasses.html"

conn = sqlite3.connect(str(db_path))
q = lambda sql, *a: conn.execute(sql, a).fetchall()

print("=" * 62)
print("⚖️ [MA'AT] AUDITORIA DE INTEGRIDADE — PIPELINE CONSULT")
print("=" * 62)

# ── ETAPA 1: JSONL canônico vs SQLite (perda na ingestão?) ──
recs = [json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
lost, diff = [], []
for r in recs:
    row = q("SELECT content FROM docs WHERE path = ?", r["uid"])
    if not row: lost.append(r["uid"])
    elif row[0][0] != r["content"]: diff.append(r["uid"])
print(f"[1] JSONL CANÔNICO: {len(recs)} registros")
print(f"    ✔ Idênticos no banco: {len(recs) - len(lost) - len(diff)}")
print(f"    ❌ Ausentes no banco: {len(lost)} {lost[:5]}")
print(f"    ⚠ Conteúdo divergente: {len(diff)} {diff[:5]}")

# ── ETAPA 2: Fences de código truncados (``` ímpar = bloco cortado) ──
odd = [r["uid"] for r in recs if r["content"].count("```") % 2]
print(f"[2] FENCES: registros com bloco de código cortado: {len(odd)} {odd[:5]}")

# ── ETAPA 3: Arquivo que o leitor carregou vs banco (perda na transferência?) ──
if md_path.exists():
    md_txt = md_path.read_text(encoding="utf-8")
    row = q("SELECT path FROM docs WHERE content = ?", md_txt) or \
          q("SELECT path FROM docs WHERE content = ?", md_txt.strip())
    if row:
        print(f"[3] LEITOR ATIVO: md em disco == conteúdo integral de '{row[0][0]}' ✔ (zero perda)")
    else:
        title = md_txt.splitlines()[0].replace("#", "").strip() if md_txt else ""
        row2 = q("SELECT path, length(content) FROM docs WHERE title LIKE ?", f"%{title[:40]}%")
        if row2:
            print(f"[3] ⚠ PERDA NA TRANSFERÊNCIA: '{row2[0][0]}' tem {row2[0][1]} chars no banco, md tem {len(md_txt)}")
        else:
            print(f"[3] ⚠ md em disco não corresponde a nenhum registro completo")
else:
    print("[3] ⚠ consult_active_doc.md não encontrado")

# ── ETAPA 4: CPython — o corpo sobreviveu sob o lixo de navegação? ──
row = q("SELECT content FROM docs WHERE path = ?", cpython_path)
if row:
    c = row[0][0]
    print(f"[4] CPYTHON '{cpython_path}': {len(c)} chars no banco")
    print(f"    Poluição de navegação no topo: {'SIM (RIT-002)' if '### Navigation' in c else 'não'}")
    docs_root = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "Doc" / "html"
    raw_html = docs_root / cpython_path
    if raw_html.exists():
        ps = re.findall(r"<p>(.*?)</p>", raw_html.read_text(encoding="utf-8", errors="ignore"), re.DOTALL | re.IGNORECASE)
        if ps:
            tail = html_lib.unescape(re.sub(r"<[^>]+>", "", ps[-1])).strip()[:60]
            print(f"    Último <p> do HTML original: '{tail}'")
            print(f"    Cauda presente no banco: {'✔ CORPO INTEGRAL' if tail[:40] in c else '❌ PERDA DE CAUDA'}")
else:
    print(f"[4] ❌ '{cpython_path}' ausente no banco")

print("=" * 62)

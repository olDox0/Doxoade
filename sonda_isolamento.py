# -*- coding: utf-8 -*-
# sonda_isolamento.py — 🦅 [HÓRUS] Pré-voo do isolamento RIT-002 v2
import re, html as hl
from pathlib import Path

DOCS = Path(r"C:\Users\olDox222\AppData\Local\Programs\Python\Python312\Doc\html")
SAMPLES = ["library/dataclasses.html", "library/json.html",
           "library/asyncio-task.html", "reference/datamodel.html"]

def isolate(raw):
    m = re.search(r'<div[^>]*role="main"[^>]*>', raw, re.I) or \
        re.search(r'<div[^>]*class="body"[^>]*>', raw, re.I)
    if not m: return raw
    body = raw[m.end():]
    low = body.lower()
    cuts = [i for i in (low.find(x) for x in (
        '<div class="clearer"', '<div class="sphinxsidebar"',
        '<div role="navigation"', '<div class="footer"', '<footer')) if i > 0]
    return body[:min(cuts)] if cuts else body

clean = lambda s: hl.unescape(re.sub(r'<[^>]+>', ' ', s)).split()
for rel in SAMPLES:
    p = DOCS / rel
    if not p.exists(): print(f"⚠ {rel} ausente"); continue
    raw = p.read_text(encoding="utf-8", errors="ignore")
    body = isolate(raw)
    words = clean(body)
    print(f"• {rel}")
    print(f"    raw={len(raw):>7} | body={len(body):>7} ({len(body)*100//len(raw)}%) | {len(words)} palavras")
    print(f"    cabeça: {' '.join(words[:12])!r}")
    print(f"    cauda : {' '.join(words[-12:])!r}")
    print(f"    nav/sidebar no body: {'❌ FAIL' if ('sphinxsidebar' in body or 'class="related"' in body) else '✔ OK'}")

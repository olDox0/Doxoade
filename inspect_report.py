# inspect_report.py
# -*- coding: utf-8 -*-
"""Inspeciona mody_research.json com encoding correto (Windows-safe)."""
import json
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else 'mody_research.json')
if not path.exists():
    sys.exit(f'✘ Não encontrado: {path}')

# ── Leitura UTF-8 explícita ────────────────────────────────────────
data = json.loads(path.read_text(encoding='utf-8'))

# ── Resumo ─────────────────────────────────────────────────────────
rs = data['run_summary']
print(f"📄 Arquivo : {path} ({path.stat().st_size} bytes)")
print(f"🧪 Parser  : {data['parser']['name']} "
      f"(conf={data['parser']['confidence']:.2f})")
print(f"📊 Arquivos: {rs['total_files']}")
print(f"📊 Hunks   : {rs['total_hunks']} "
      f"(aplicáveis={rs['applicable']}, "
      f"idempotentes={rs['idempotent']}, "
      f"rejeitados={rs['rejected']}, "
      f"ambíguos={rs['ambiguous']})")

# ── Breakdown por arquivo ──────────────────────────────────────────
print("\n📁 Por arquivo:")
for f in data['files']:
    print(f"\n  {f['path']}")
    for h in f['hunks']:
        rule_ids = [r['rule_id'] for r in h['rule_trace']]
        warns = [r['rule_id'] for r in h['rule_trace'] if r['output'] == 'WARN']
        warn_str = f"  ⚠ {','.join(warns)}" if warns else ""
        print(f"    Hunk #{h['hunk_idx']:2d} "
              f"[{h['status']:12s}] "
              f"match={h['match_type'] or '—':24s} "
              f"trace={'→'.join(r.split('_')[0] for r in rule_ids)}"
              f"{warn_str}")

# ── Estatística de rule outputs (para sua rule table) ──────────────
print("\n🎯 Rule outcomes:")
from collections import Counter
cnt = Counter()
for f in data['files']:
    for h in f['hunks']:
        for r in h['rule_trace']:
            cnt[(r['rule_id'], r['output'])] += 1
for (rid, out), n in sorted(cnt.items()):
    print(f"  {rid:40s} {out:5s} × {n}")

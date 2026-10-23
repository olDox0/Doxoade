# analyze_h2.py
"""analyze_h2.py — Análise combinada de headroom + calls."""
import json
import sys
from collections import Counter
from pathlib import Path


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "vulcan_h2.json"
    data = json.load(open(path, encoding="utf-8"))

    agg = data["corpus"]
    calls = data.get("calls_analysis", {})

    print("=" * 70)
    print(f"  ANÁLISE: {path}")
    print("=" * 70)

    # 1. Distribuição de grades calibradas
    print("\n  DISTRIBUIÇÃO DE GRADES (calibrada)")
    print(f"  Total: {agg['total_functions']} funções")
    total = agg["total_functions"] or 1
    for g in ("ADAMANTIUM", "STEEL", "BRONZE", "SLAG"):
        c = agg["grade_distribution"].get(g, 0)
        pct = c / total * 100
        bar = "#" * int(pct / 2)
        print(f"    {g:<12} {c:>4} ({pct:>5.1f}%) {bar}")

    # 2. Calls por categoria
    if calls:
        print(f"\n  CALLS-IN-LOOP: {calls['total_calls']} chamadas")
        by_cat = calls["by_category"]
        order = ["HOIST", "SAFE", "BATCH", "BUFFER", "INLINE",
                 "NATIVE", "UNKNOWN", "BLOCKED"]
        ct = calls["total_calls"] or 1
        for cat in order:
            n = by_cat.get(cat, 0)
            if n == 0:
                continue
            pct = n / ct * 100
            bar = "#" * int(pct / 2)
            print(f"    {cat:<10} {n:>4} ({pct:>5.1f}%) {bar}")

        # Refatoráveis vs bloqueadas
        refactorable = sum(by_cat.get(c, 0) for c in
                           ("HOIST", "SAFE", "BATCH", "BUFFER", "NATIVE"))
        blocked = by_cat.get("BLOCKED", 0)
        unknown = by_cat.get("UNKNOWN", 0) + by_cat.get("INLINE", 0)
        print(f"\n  RESUMO:")
        print(f"    Refatoráveis: {refactorable} ({refactorable/ct*100:.1f}%)")
        print(f"    Bloqueadas  : {blocked} ({blocked/ct*100:.1f}%)")
        print(f"    Desconhecido: {unknown} ({unknown/ct*100:.1f}%)")

        # Top ROI
        print(f"\n  TOP 15 FUNÇÕES POR ROI:")
        for f in calls["roi_by_function"][:15]:
            print(f"    ref={f['refactorable']:>3} blk={f['blocked']:>3} "
                  f"unk={f['unknown']:>3}  {f['func_name']}")

        # Top targets bloqueados
        print(f"\n  TOP TARGETS BLOQUEADOS:")
        for target, count in list(calls["targets_per_category"].get("BLOCKED", {}).items())[:10]:
            print(f"    {target:<30} {count:>4}x")

        print(f"\n  TOP TARGETS HOIST (fácil refatorar):")
        for target, count in list(calls["targets_per_category"].get("HOIST", {}).items())[:10]:
            print(f"    {target:<30} {count:>4}x")

    print()


if __name__ == "__main__":
    main()

# analyze_headroom.py
"""Análise de corpus do Vulcan Headroom — W5H sobre padrões de otimização."""
import json
import sys
from collections import Counter
from pathlib import Path


def load(path: str) -> dict:
    return json.load(open(path, encoding="utf-8"))


def report_grades(data: dict) -> None:
    agg = data["corpus"]
    total = agg["total_functions"]
    print("=" * 70)
    print("  DISTRIBUICAO POR GRADE")
    print("=" * 70)
    print(f"  Total: {agg['total_files']} arquivos, {total} funcoes")
    print()
    for g in ("ADAMANTIUM", "STEEL", "BRONZE", "SLAG"):
        c = agg["grade_distribution"].get(g, 0)
        pct = (c / total * 100) if total else 0
        bar = "#" * int(pct / 2)
        print(f"  {g:<12} {c:>4} ({pct:>5.1f}%)  {bar}")


def report_score_histogram(data: dict) -> None:
    agg = data["corpus"]
    print()
    print("=" * 70)
    print("  HISTOGRAMA DE SCORES")
    print("=" * 70)
    for bucket, count in agg["score_histogram"].items():
        bar = "#" * min(count, 50)
        print(f"  {bucket:<8} {bar} {count}")


def report_top(data: dict, n: int = 20) -> None:
    all_funcs = []
    for file_report in data["files"]:
        for f in file_report["functions"]:
            all_funcs.append(f)

    all_funcs.sort(key=lambda f: -f["score"])

    print()
    print("=" * 70)
    print(f"  TOP {n} FUNCOES POR SCORE")
    print("=" * 70)
    for f in all_funcs[:n]:
        fname = Path(f["file"]).name
        print(
            f"  {f['score']:>3} {f['grade']:<11} "
            f"{f['name']:<35} ({fname}:L{f['lineno']})"
        )
        positives = []
        negatives = []
        for k in ("numeric_loops", "indexed_access", "local_arithmetic",
                  "branchless_candidates", "native_kernels_used"):
            if f.get(k, 0):
                positives.append(f"{k}={f[k]}")
        for k in ("python_calls_in_loop", "dict_lookups_in_loop",
                  "string_ops_in_loop", "io_calls", "dynamic_attrs",
                  "exceptions_in_loop"):
            if f.get(k, 0):
                negatives.append(f"{k}={f[k]}")
        if positives:
            print(f"      + {', '.join(positives)}")
        if negatives:
            print(f"      - {', '.join(negatives)}")


def report_patterns(data: dict) -> None:
    agg = data["corpus"]
    print()
    print("=" * 70)
    print("  PADROES EM ADAMANTIUM (top) vs SLAG (antipadroes)")
    print("=" * 70)

    high = agg["high_score_patterns"]
    low = agg["low_score_patterns"]

    print(f"\n  ADAMANTIUM: {high['count']} funcoes")
    if high["count"]:
        print("    Fatores positivos:")
        for k, v in sorted(high["positive_factors"].items(),
                            key=lambda x: -x[1]):
            pct = v / high["count"] * 100
            print(f"      {k:<25} {v:>3} ({pct:>5.1f}%)")
        if high["negative_factors"]:
            print("    Fatores negativos tolerados:")
            for k, v in sorted(high["negative_factors"].items(),
                                key=lambda x: -x[1]):
                pct = v / high["count"] * 100
                print(f"      {k:<25} {v:>3} ({pct:>5.1f}%)")

    print(f"\n  SLAG: {low['count']} funcoes")
    if low["count"]:
        print("    Fatores negativos dominantes:")
        for k, v in sorted(low["negative_factors"].items(),
                            key=lambda x: -x[1]):
            pct = v / low["count"] * 100
            print(f"      {k:<25} {v:>3} ({pct:>5.1f}%)")
        if low["positive_factors"]:
            print("    (positivos que nao salvaram a funcao)")
            for k, v in sorted(low["positive_factors"].items(),
                                key=lambda x: -x[1]):
                pct = v / low["count"] * 100
                print(f"      {k:<25} {v:>3} ({pct:>5.1f}%)")


def report_by_file(data: dict, n: int = 10) -> None:
    """Arquivos com maior media de score — candidatos prioritarios."""
    print()
    print("=" * 70)
    print(f"  TOP {n} ARQUIVOS POR MEDIA DE SCORE (min 3 funcoes)")
    print("=" * 70)
    files = [
        (Path(f["file"]).name, f["avg_score"], f["total_functions"])
        for f in data["files"]
        if f["total_functions"] >= 3
    ]
    files.sort(key=lambda x: -x[1])
    for name, avg, count in files[:n]:
        print(f"  avg={avg:>5.1f}  funcoes={count:>3}  {name}")


def report_factors_overall(data: dict) -> None:
    agg = data["corpus"]
    print()
    print("=" * 70)
    print("  FATORES AGREGADOS (todo o corpus)")
    print("=" * 70)
    print("\n  Positivos:")
    for k, v in sorted(agg["positive_totals"].items(), key=lambda x: -x[1]):
        print(f"    {k:<25} {v:>5}")
    print("\n  Negativos:")
    for k, v in sorted(agg["negative_totals"].items(), key=lambda x: -x[1]):
        print(f"    {k:<25} {v:>5}")


def dump_high_potential_functions(data: dict, threshold: int = 50) -> None:
    """Lista funcoes candidatas a virar template."""
    print()
    print("=" * 70)
    print(f"  CANDIDATAS A TEMPLATE (score >= {threshold})")
    print("=" * 70)
    candidates = [
        f
        for file_report in data["files"]
        for f in file_report["functions"]
        if f["score"] >= threshold
    ]
    if not candidates:
        print(f"  (nenhuma funcao com score >= {threshold})")
        return
    candidates.sort(key=lambda f: -f["score"])
    for f in candidates:
        print(
            f"  [{f['score']:>3}] {f['name']} "
            f"({Path(f['file']).name}:L{f['lineno']})"
        )


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "vulcan_headroom.json"
    if not Path(path).exists():
        print(f"Arquivo nao encontrado: {path}")
        return 1

    data = load(path)

    report_grades(data)
    report_score_histogram(data)
    report_top(data, n=20)
    report_patterns(data)
    report_by_file(data, n=10)
    report_factors_overall(data)
    dump_high_potential_functions(data, threshold=50)

    print()
    print("=" * 70)
    print("  ANALISE COMPLETA")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

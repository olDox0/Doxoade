# doxoade/commands/typhon_systems/typhon_consolidated.py
# -*- coding: utf-8 -*-
"""
TYPHON CONSOLIDATED — diagnóstico unificado para o Doxoade.
"""

import time
from pathlib import Path

try:
    import doxoade.tools.aegis.nexus_db as sqlite3
except Exception:
    import sqlite3

from doxoade.tools.core_locator import GLOBAL_DB_FILE
from doxoade.tools.doxcolors import Fore, Style

from .typhon_chaos import print_tree, run_chaos_suite
from .typhon_probes import run_all_probes


def check(db_path=None, verbose: bool = True):
    t0 = time.perf_counter()
    issues = []
    checks = 0

    db = Path(db_path).expanduser() if db_path else GLOBAL_DB_FILE

    if verbose:
        print(f"{Fore.CYAN}🌀 TYPHON CHECK — Doxoade{Style.RESET_ALL}")
        print(f"   DB: {db}")

    checks += 1

    if not db.exists():
        issues.append("locator: doxoade.db não localizado (doxoade.db ausente)")

        if verbose:
            print(f"   ❌ DB ausente: {db}")

        elapsed = (time.perf_counter() - t0) * 1000

        return {
            "db": str(db),
            "checks": checks,
            "issues": issues,
            "elapsed_ms": elapsed,
        }

    try:
        conn = sqlite3.connect(str(db), timeout=3)

    except Exception as e:
        issues.append(f"persistência: falha ao abrir DB: {e}")

        elapsed = (time.perf_counter() - t0) * 1000

        return {
            "db": str(db),
            "checks": checks,
            "issues": issues,
            "elapsed_ms": elapsed,
        }

    try:
        checks += 1

        tables = {
            r[0]
            for r in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                """
            ).fetchall()
        }

        if "operational_logs" not in tables:
            issues.append("tabela operational_logs ausente")

            if verbose:
                print("   ❌ operational_logs: ausente")

        else:
            if verbose:
                print("   ✅ operational_logs: presente")

            checks += 1

            count = conn.execute(
                "SELECT COUNT(*) FROM operational_logs"
            ).fetchone()[0]

            if verbose:
                print(f"   ✅ registros: {count}")

            checks += 1

            typhon_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM operational_logs
                WHERE subsystem = 'TYPHON'
                """
            ).fetchone()[0]

            if verbose:
                print(f"   ✅ heartbeats TYPHON: {typhon_count}")

        checks += 1

        result = conn.execute("PRAGMA integrity_check").fetchone()[0]

        if result != "ok":
            issues.append(f"SQLite integrity_check = {result}")

            if verbose:
                print(f"   ❌ SQLite integrity: {result}")

        else:
            if verbose:
                print("   ✅ SQLite integrity: ok")

    except Exception as e:
        issues.append(f"check: erro ao inspecionar DB: {e}")

    finally:
        try:
            conn.close()
        except Exception:
            pass

    elapsed = (time.perf_counter() - t0) * 1000

    if verbose:
        status = "❌" if issues else "✅"
        print(
            f"\n⏱️  {elapsed:.1f} ms | "
            f"checks={checks} | issues={len(issues)} {status}"
        )

    return {
        "db": str(db),
        "checks": checks,
        "issues": issues,
        "elapsed_ms": elapsed,
    }


def chaos(verbose: bool = True, soteria: bool = False, horus: bool = False):
    return run_chaos_suite(
        verbose=verbose,
        soteria=soteria,
        horus=horus,
    )


def probe(verbose: bool = True, db_path=None):
    return run_all_probes(verbose=verbose, db_path=db_path)


def tree():
    print_tree()


def report(
    db_path=None,
    verbose: bool = True,
    soteria: bool = False,
    horus: bool = False,
):
    if verbose:
        print("=" * 70)
        print("🌀 TYPHON REPORT — Doxoade")
        print("=" * 70)

    out = {}

    if verbose:
        print("\n--- CHECK ---")

    out["check"] = check(db_path=db_path, verbose=verbose)

    if verbose:
        print("\n--- CHAOS ---")

    out["chaos"] = chaos(verbose=verbose, soteria=soteria, horus=horus)

    if verbose:
        print("\n--- PROBES ---")

    out["probe"] = probe(verbose=verbose, db_path=db_path)

    if verbose:
        print("\n--- TREE ---")

    tree()

    return out

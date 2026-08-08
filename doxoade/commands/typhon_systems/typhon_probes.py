# doxoade/commands/typhon_systems/typhon_probes.py
# -*- coding: utf-8 -*-
"""
TYPHON PROBES — detectores vivos contra o Doxoade real.
"""

from pathlib import Path

try:
    import doxoade.tools.aegis.nexus_db as sqlite3
except Exception:
    import sqlite3

from doxoade.tools.core_locator import GLOBAL_DB_FILE


def _open_db(db_path=None):
    if db_path:
        path = Path(db_path).expanduser()
        return sqlite3.connect(str(path), timeout=3), str(path)

    try:
        from doxoade.core_database import get_db_connection

        return get_db_connection(), str(GLOBAL_DB_FILE)

    except Exception:
        return sqlite3.connect(str(GLOBAL_DB_FILE), timeout=3), str(GLOBAL_DB_FILE)


def run_all_probes(verbose: bool = True, db_path=None):
    achados = []

    try:
        conn, db_used = _open_db(db_path)

    except Exception as e:
        msg = f"persistência: falha ao abrir DB: {e}"
        achados.append(msg)

        if verbose:
            print(f"   🛑 {msg}")

        return achados

    if verbose:
        print(f"   🔬 DB alvo: {db_used}")

    try:
        table = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name='operational_logs'
            """
        ).fetchone()

        if not table:
            msg = "tabela operational_logs ausente"
            achados.append(msg)

            if verbose:
                print(f"   🛑 {msg}")

        else:
            count = conn.execute(
                "SELECT COUNT(*) FROM operational_logs"
            ).fetchone()[0]

            typhon_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM operational_logs
                WHERE subsystem = 'TYPHON'
                """
            ).fetchone()[0]

            if verbose:
                print(f"   ✅ operational_logs: {count} registros")
                print(f"   ✅ heartbeats TYPHON persistidos: {typhon_count}")

        result = conn.execute("PRAGMA integrity_check").fetchone()[0]

        if result != "ok":
            msg = f"SQLite integrity_check = {result}"
            achados.append(msg)

            if verbose:
                print(f"   🛑 {msg}")

        else:
            if verbose:
                print("   ✅ SQLite integrity: ok")

    except Exception as e:
        msg = f"probe: erro ao inspecionar DB: {e}"
        achados.append(msg)

        if verbose:
            print(f"   🛑 {msg}")

    finally:
        try:
            conn.close()
        except Exception:
            pass

    return achados

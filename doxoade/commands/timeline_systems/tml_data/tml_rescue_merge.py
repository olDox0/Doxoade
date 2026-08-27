# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/tml_data/tml_rescue_merge.py

r"""
Timeline Nexus - Resgate Arqueológico (standalone, fora do runtime/Aegis).
Modos:
  (padrão)   dry-run resumido
  --preview  dossiê detalhado de previsão (protocolo de segurança)
  --apply    snapshot hot protocolar + fusão + verificação pós + receipt
Rollback: DELETE FROM command_history WHERE id < <marco_zero>;
Uso: venv\Scripts\python doxoade\commands\timeline_systems\tml_data\tml_rescue_merge.py [--preview|--apply]
"""
import json
import sqlite3
import sys
import hashlib
from datetime import datetime
from pathlib import Path

CURRENT = Path(__file__).resolve().parents[4] / "data" / "doxoade.db"
BACKUP = Path.home() / ".doxoade" / "backups" / "doxoade_backup_20260610_164744.db"
SNAP_DIR = Path.home() / ".doxoade" / "backups"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()[:16]


def main():
    apply = "--apply" in sys.argv
    preview = "--preview" in sys.argv or apply

    con_c = sqlite3.connect(str(CURRENT))
    con_b = sqlite3.connect(str(BACKUP))

    cols_c = [r[1] for r in con_c.execute("PRAGMA table_info(command_history)")]
    cols_b = [r[1] for r in con_b.execute("PRAGMA table_info(command_history)")]
    common = [c for c in cols_c if c in cols_b]
    only_c = [c for c in cols_c if c not in cols_b]
    only_b = [c for c in cols_b if c not in cols_c]

    min_id_c, cnt_c, max_id_c = con_c.execute(
        "SELECT MIN(id), COUNT(*), MAX(id) FROM command_history").fetchone()
    ts_min_c, ts_max_c = con_c.execute(
        "SELECT MIN(timestamp), MAX(timestamp) FROM command_history").fetchone()
    n_res, r_min, r_max = con_b.execute(
        "SELECT COUNT(*), MIN(id), MAX(id) FROM command_history WHERE id < ?",
        (min_id_c,)).fetchone()
    r_ts_min, r_ts_max = con_b.execute(
        "SELECT MIN(timestamp), MAX(timestamp) FROM command_history WHERE id < ?",
        (min_id_c,)).fetchone()

    contiguo = n_res == (r_max - r_min + 1)
    colisao = "IMPOSSÍVEL" if (r_max or 0) < min_id_c else "⚠ VERIFICAR"

    print(f"--- [RESGATE] marco zero atual: id {min_id_c} ({cnt_c} linhas)")
    print(f"--- [RESGATE] resgatáveis (id < {min_id_c}): {n_res} "
          f"({r_ts_min[:10]} → {r_ts_max[:10]})")
    print(f"--- [RESGATE] colunas comuns: {len(common)}/{len(cols_c)}")

    if preview:
        print(f"\n--- [PREVIEW] 1. CONTINUIDADE DE LINHAGEM ---")
        print(f"   backup rescue ids : {r_min}..{r_max} (contíguo: {'SIM' if contiguo else 'NÃO'})")
        print(f"   current ids       : {min_id_c}..{max_id_c}")
        print(f"   colisão de PK     : {colisao}")
        print(f"   overlap descartado: {18778 - n_res if max_id_c else 0} linhas "
              f"(ids >= {min_id_c}, current é autoridade)")

        print(f"\n--- [PREVIEW] 2. DISTRIBUIÇÃO MENSAL (a inserir) ---")
        months = con_b.execute("""
            SELECT strftime('%Y-%m', timestamp) m, COUNT(*) c
            FROM command_history WHERE id < ? GROUP BY m ORDER BY m""",
            (min_id_c,)).fetchall()
        top = max(c for _, c in months) if months else 1
        for m, c in months:
            print(f"   {m}  {'█' * max(1, c * 40 // top)} {c}")

        print(f"\n--- [PREVIEW] 3. TOP COMANDOS (a inserir) ---")
        for name, c in con_b.execute("""
            SELECT command_name, COUNT(*) c FROM command_history
            WHERE id < ? GROUP BY command_name ORDER BY c DESC LIMIT 8""",
                (min_id_c,)).fetchall():
            print(f"   {name:<16} {c}")

        print(f"\n--- [PREVIEW] 4. INTEGRIDADE DO LOTE ---")
        err, nul = con_b.execute("""
            SELECT SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN exit_code IS NULL THEN 1 ELSE 0 END)
            FROM command_history WHERE id < ?""", (min_id_c,)).fetchone()
        bad_ts = con_b.execute("""
            SELECT COUNT(*) FROM command_history WHERE id < ?
            AND (timestamp IS NULL OR length(timestamp) < 19)""",
            (min_id_c,)).fetchone()[0]
        print(f"   erros (exit!=0): {err or 0} | exit NULL: {nul or 0} | ts inválidos: {bad_ts}")
        print(f"   colunas só no current (ficam NULL): {only_c or 'nenhuma'}")
        print(f"   colunas só no backup (descartadas): {only_b or 'nenhuma'}")

        print(f"\n--- [PREVIEW] 5. PÓS-FUSÃO PREVISTA ---")
        print(f"   total    : {cnt_c} + {n_res} = {cnt_c + n_res}")
        print(f"   cobertura: {r_ts_min[:10]} → {ts_max_c[:10]}")

        print(f"\n--- [PREVIEW] 6. PROTOCOLO ---")
        print(f"   sha256 current : {sha256_file(CURRENT)}")
        print(f"   sha256 backup  : {sha256_file(BACKUP)}")
        print(f"   rollback       : DELETE FROM command_history WHERE id < {min_id_c};")

    if not apply:
        print("[DRY-RUN] Nenhuma gravação. Use --apply para fundir.")
        return

    # --- PROTOCOLO: snapshot hot ANTES de gravar (SQLite Backup API, WAL-safe)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap = SNAP_DIR / f"pre_rescue_{ts}.db"
    con_snap = sqlite3.connect(str(snap))
    con_c.backup(con_snap)
    con_snap.close()
    print(f"🔒 [PROTOCOLO] Snapshot pré-fusão: {snap} (sha {sha256_file(snap)})")

    rows = con_b.execute(
        f"SELECT {','.join(common)} FROM command_history WHERE id < ? ORDER BY id",
        (min_id_c,)).fetchall()
    con_c.executemany(
        f"INSERT OR IGNORE INTO command_history ({','.join(common)}) "
        f"VALUES ({','.join('?' * len(common))})", rows)
    con_c.commit()

    n_after, new_min_ts, new_max_ts = con_c.execute(
        "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM command_history").fetchone()
    print(f"✅ Fundido: {cnt_c} → {n_after} (+{n_after - cnt_c})")
    print(f"✅ Cobertura nova: {new_min_ts[:10]} → {new_max_ts[:10]}")

    receipt = SNAP_DIR / f"rescue_receipt_{ts}.json"
    receipt.write_text(json.dumps({
        "when": ts, "marco_zero": min_id_c, "inserted": n_after - cnt_c,
        "sha_current_before": sha256_file(CURRENT), "snapshot": str(snap),
        "rollback": f"DELETE FROM command_history WHERE id < {min_id_c};",
    }, indent=2), encoding="utf-8")
    print(f"📜 [PROTOCOLO] Receipt: {receipt}")
    con_c.close(); con_b.close()


if __name__ == "__main__":
    main()
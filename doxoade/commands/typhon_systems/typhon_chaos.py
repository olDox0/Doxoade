# doxoade/doxoade/commands/typhon_systems/typhon_chaos.py
# -*- coding: utf-8 -*-
"""
TYPHON CHAOS — chaos engineering do diagnóstico no Doxoade.

Para cada modo de falha com injector: implanta a falha simulada, captura
o rastro (exceção + stderr + retorno) e verifica se algum symptom da
árvore casa.

• casa         → ✅ detectável
• não casa     → 🛑 injetada mas NÃO detectada
• sem symptoms → 🛑 SILENCIOSA por natureza → exige probe/censo
"""

import contextlib
import io
import re

from doxoade.commands.typhon_systems.typhon_tree import TREE


INJECTORS = {}


def injector(fmid):
    def deco(fn):
        INJECTORS[fmid] = fn
        return fn
    return deco


@injector("doxoade.db.missing")
def _inj_db_missing():
    raise FileNotFoundError("doxoade.db ausente (simulado)")


@injector("doxoade.env.invalid")
def _inj_env_invalid():
    raise FileNotFoundError("DOXOADE_GLOBAL_DB inválido: caminho não existe (simulado)")


@injector("doxoade.op_logs.missing")
def _inj_op_logs_missing():
    raise RuntimeError("tabela operational_logs ausente (simulado)")


@injector("doxoade.db.locked")
def _inj_db_locked():
    raise RuntimeError("database is locked (simulado)")


@injector("doxoade.sqlite.integrity")
def _inj_integrity():
    return "PRAGMA integrity_check falhou (simulado)"


@injector("doxoade.heartbeat.write_failed")
def _inj_hb_write_failed():
    raise RuntimeError("heartbeat write failed (simulado)")


@injector("soteria.envelope.malformed")
def _inj_envelope_malformed():
    return "envelope malformado: sem TAG_MOTIVO (simulado)"


@injector("doxoade.census.divergence")
def _inj_census_divergence():
    return "censo: 2 heartbeats evaporados (local=5, db=3)"


def print_tree():
    sev_mark = {
        "low": "·",
        "medium": "~",
        "high": "!",
        "critical": "☠",
    }

    def rec(nid, depth):
        n = TREE.nodes[nid]
        print(f"{'   ' * depth}├─ {n.name}")

        for fm in n.failures:
            print(
                f"{'   ' * depth}   [{sev_mark.get(fm.severity, '?')}] "
                f"{fm.id} — {fm.dev_comment[:70]}…"
            )

        for c in n.children:
            rec(c, depth + 1)

    for nid, n in TREE.nodes.items():
        if n.parent is None:
            rec(nid, 0)


def run_chaos_suite(verbose=True, soteria=False, horus=False):
    ok = silent = noinj = 0
    emit = None
    emit_hb = None

    if soteria:
        from .soteria_bridge import emit_envelope
        emit = emit_envelope

    if horus:
        from .horus_bridge import heartbeat
        emit_hb = heartbeat

    for fmid, fm in TREE.failures.items():
        inj = INJECTORS.get(fmid)

        if emit_hb:
            emit_hb("TYPHON", "CHAOS_INJECT", {"motivo": fmid})

        if inj is None:
            noinj += 1
            line = f"   ⚪ {fmid:<34} sem injector (só probe/censo)"
            detail = "sem injector registrado"
            status = "SEM_INJECTOR"

        else:
            buf = io.StringIO()
            out_parts = []

            try:
                with contextlib.redirect_stderr(buf):
                    ret = inj()
                    if ret is not None:
                        out_parts.append(str(ret))
            except Exception as e:
                out_parts.append(f"{type(e).__name__}: {e}")

            out = buf.getvalue() + " ".join(out_parts)
            detail = (out.strip().splitlines() or [""])[0][:120]

            hit = any(re.search(s, out) for s in fm.symptoms)

            if not fm.symptoms:
                silent += 1
                line = f"   🛑 {fmid:<34} SILENCIOSA — exige probe"
                status = "SILENCIOSA"

            elif hit:
                ok += 1
                line = f"   ✅ {fmid:<34} detectável"
                status = "DETECTAVEL"

            else:
                silent += 1
                line = f"   🛑 {fmid:<34} injetada mas NÃO detectada!"
                status = "SILENCIOSA"

        if verbose:
            print(line)

        if emit_hb:
            emit_hb("TYPHON", "CHAOS_VERDICT", {"motivo": fmid, "status": status})

        if emit:
            print(emit(fmid, detail, level="CHAOS"), end="")

    if verbose:
        print(f"\n📊 Typhon: {ok} detectáveis | {silent} silenciosas | {noinj} sem injector")

    return {
        "ok": ok,
        "silent": silent,
        "noinj": noinj,
    }

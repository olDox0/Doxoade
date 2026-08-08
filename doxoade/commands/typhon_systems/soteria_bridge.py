# doxoade/doxoade/commands/typhon_systems/soteria_bridge.py
# -*- coding: utf-8 -*-
"""
TYPHON ⇄ SOTERIA — ponte de envelopes.

Direção 1: Soteria -> Typhon
    Varre envelopes @SOTERIA_BEGIN@...@SOTERIA_END@ e casa contra a árvore.

Direção 2: Typhon -> Soteria
    O chaos emite envelopes válidos com TAG_MOTIVO=<failure id>.
"""

import re
import os

_ENV_RE = re.compile(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", re.DOTALL)
_TAG_RE = re.compile(r"TAG_(\w+):\s*(.*)")


def parse_envelopes(text):
    """Extrai dicts de tags de todos os envelopes Soteria no texto."""
    return [
        {k.upper(): v.strip() for k, v in _TAG_RE.findall(body)}
        for body in _ENV_RE.findall(text or "")
    ]


def diagnose_envelope(tags, tree):
    """Casa um envelope contra a árvore Typhon; retorna FailureMode ou None."""
    blob = " ".join(tags.values())

    for fm in tree.failures.values():
        if any(re.search(s, blob) for s in fm.symptoms):
            return fm

    return None


def _print_hit(fm):
    print(f"   🌀 [{fm.id}] {fm.name} (sev {fm.severity})")
    print(f"      💬 {fm.dev_comment}")
    if fm.mitigation:
        print(f"      🛠️  {fm.mitigation}")


def scan_log(text, tree, verbose=True):
    """Retrospectiva estruturada sobre um log."""

    # 🤫 DIRECT MODE: Pula a análise profunda de log se não for explicitamente verbose
    if os.environ.get('DOXOADE_MODE') == 'direct' and not verbose:
        return {"envelopes": 0, "matched": 0}
        
    envelopes = parse_envelopes(text)
    matched = 0

    if envelopes:
        for tags in envelopes:
            fm = diagnose_envelope(tags, tree)
            if fm:
                matched += 1
                if verbose:
                    _print_hit(fm)
            elif verbose:
                print(f"   ⚪ envelope não mapeado: MOTIVO={tags.get('MOTIVO', '?')}")

    else:
        seen = set()

        for line in (text or "").splitlines():
            if not line.strip():
                continue

            for fm in tree.failures.values():
                if any(re.search(s, line) for s in fm.symptoms):
                    key = (fm.id, line.strip()[:80])
                    if key in seen:
                        continue

                    seen.add(key)
                    matched += 1

                    if verbose:
                        _print_hit(fm)

        if verbose and not seen:
            print("   ⚪ nenhum sintoma conhecido no log.")

    return {
        "envelopes": len(envelopes),
        "matched": matched,
    }


def emit_envelope(fmid, detail, level="CHAOS"):
    """Typhon -> Soteria."""
    # 🤫 DIRECT MODE: Suprime envelopes verbosos
    if os.environ.get('DOXOADE_MODE') == 'direct':
        return "" 
        
    return (
        "@SOTERIA_BEGIN@\n"
        f"TAG_LEVEL: {level}\n"
        f"TAG_MOTIVO: {fmid}\n"
        f"TAG_DETAIL: {detail}\n"
        "TAG_SUBSIS: TYPHON_CHAOS\n"
        "@SOTERIA_END@\n"
    )

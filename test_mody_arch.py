# test_mody_arch.py
# -*- coding: utf-8 -*-
"""Testes das camadas 1-4 do mody patch arquitetural."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
FAIL = 0

def ok(m):
    print("  \033[92m\u2713\033[0m " + m)
def fail(m):
    global FAIL; FAIL += 1
    print("  \033[91m\u2717\033[0m " + m)
def section(t):
    print("\n" + "\u2550"*64 + "\n" + t + "\n" + "\u2550"*64)

# ────────────────────────────────────────────────────────────────
# L1 — Normalização. Usamos \u para não depender do encoding do arquivo.
# ────────────────────────────────────────────────────────────────
section("L1 \u00b7 mody_normalize.normalize_diff_text")
from doxoade.commands.moddify_sys.mody_normalize import normalize_diff_text

L1 = [
    # cp437/cp850: 'Mudanças' corrompido é \u251c \u00ba  (\u251c\u00ba)
    ("mojibake cp437 \u00e7",
     "Mudan\u251c\u00baas perto",
     "Mudan\u00e7as perto"),
    # cp1251: 'gestão' corrompido é \u0413 \u00a7  (\u0413\u00a7)
    ("mojibake cp1251 \u00e3",
     "gest\u0413\u00a7o",
     "gest\u00e3o"),
    # ANSI
    ("ANSI fg",   "\x1b[91m- linha\x1b[0m", "- linha"),
    ("ANSI reset","\x1b[0mtexto", "texto"),
    # CRLF
    ("CRLF", "a\r\nb", "a\nb"),
    # BOM
    ("BOM", "\ufeffhello", "hello"),
    # Estrutural (não deve tocar)
    ("pipe intacto",    "     - | -- a/f.py",
                        "     - | -- a/f.py"),
    ("unified intacto", "--- a/f.py\n+++ b/f.py",
                        "--- a/f.py\n+++ b/f.py"),
]

for name, inp, expected in L1:
    try:
        out = normalize_diff_text(inp)
    except Exception as e:
        fail(name + ": EXCEPTION " + repr(e))
        continue
    (ok if expected in out else fail)(
        name + ": in=" + repr(inp) + " out=" + repr(out)
    )

# ────────────────────────────────────────────────────────────────
# L2 — Registry
# ────────────────────────────────────────────────────────────────
section("L2 \u00b7 Registry de parsers")
from doxoade.commands.moddify_sys.mody_parsers import (
    _REGISTRY, detect_and_parse,
)

expected_parsers = {"unified", "decorated-pipe", "markdown-fence",
                    "numbered-padding", "loose-pairs"}
registered = {cls.name for cls in _REGISTRY}
for name in expected_parsers:
    (ok if name in registered else fail)("parser '" + name + "' registrado")

# ────────────────────────────────────────────────────────────────
# L3 — Confidence + parsing (concatenação, sem triple quotes)
# ────────────────────────────────────────────────────────────────
section("L3 \u00b7 Confidence scores + parsing")

sample_unified = (
    "--- a/x.py\n"
    "+++ b/x.py\n"
    "@@ -1,2 +1,2 @@\n"
    " alpha\n"
    "-old\n"
    "+new\n"
)

sample_decorated = (
    "     - | -- a/x.py\n"
    "     + | ++ b/x.py\n"
    "Mudan\u00e7as perto da linha 2\n"
    "       | alpha\n"
    "     - | old\n"
    "     + | new\n"
)

sample_markdown = (
    "Olha o fix:\n"
    "```diff\n"
    "--- a/x.py\n"
    "+++ b/x.py\n"
    "@@ -1,2 +1,2 @@\n"
    " alpha\n"
    "-old\n"
    "+new\n"
    "```\n"
)

sample_numbered = (
    "1 | --- a/x.py\n"
    "2 | +++ b/x.py\n"
    "3 | @@ -1,2 +1,2 @@\n"
    "4 |  alpha\n"
    "5 | -old\n"
    "6 | +new\n"
)

samples = [
    ("unified",   sample_unified,   "unified"),
    ("decorated", sample_decorated, "decorated-pipe"),
    ("markdown",  sample_markdown,  "markdown-fence"),
    ("numbered",  sample_numbered,  "numbered-padding"),
]

for label, text, expected in samples:
    try:
        patches, chosen, conf = detect_and_parse(text, ROOT)
    except Exception as e:
        fail(label + ": EXCEPTION " + repr(e))
        continue
    total_hunks = sum(len(p.hunks) for p in patches)
    match = chosen == expected
    msg = "%s: parser=%s (esperado %s) conf=%.2f hunks=%d" % (
        label, chosen, expected, conf, total_hunks
    )
    (ok if match else fail)(msg)

# ────────────────────────────────────────────────────────────────
# L4 — Idempotência
# ────────────────────────────────────────────────────────────────
section("L4 \u00b7 PatchSurgeon._is_idempotent_hunk")
from doxoade.commands.moddify_sys.mody_patch import (
    PatchSurgeon, Hunk, PatchLine,
)

if not hasattr(PatchSurgeon, "_is_idempotent_hunk"):
    fail("PatchSurgeon._is_idempotent_hunk AUSENTE — bug de indentação")
    sys.exit(1)

def mk_hunk(spec):
    return Hunk(
        old_start=1, old_count=1, new_start=1, new_count=1,
        header_ctx="test",
        lines=[PatchLine(kind=k, text=t) for k, t in spec],
    )

L4 = [
    ("dele\u00e7\u00e3o pura J\u00e1 aplicada",
     ["a", "b", "c"],    [('-', 'x'), ('-', 'y')],    True),
    ("dele\u00e7\u00e3o pura N\u00c3O aplicada",
     ["a", "x", "y"],    [('-', 'x'), ('-', 'y')],    False),
    ("adi\u00e7\u00e3o pura J\u00e1 aplicada",
     ["a", "novo"],      [('+', 'novo')],             True),
    ("adi\u00e7\u00e3o pura N\u00c3O aplicada",
     ["a", "b"],         [('+', 'novo')],             False),
    ("misto J\u00e1 aplicado",
     ["a", "novo", "c"], [('-', 'velho'), ('+', 'novo')], True),
    ("misto N\u00c3O aplicado",
     ["a", "velho"],     [('-', 'velho'), ('+', 'novo')], False),
    ("bloco ctx+adi\u00e7\u00e3o J\u00e1 presente",
     ["alpha", "beta"],  [(' ', 'alpha'), ('+', 'beta')], True),
]

for name, fc, spec, expected in L4:
    try:
        is_idem, why = PatchSurgeon._is_idempotent_hunk(fc, mk_hunk(spec))
    except Exception as e:
        fail(name + ": EXCEPTION " + repr(e))
        continue
    match = is_idem == expected
    (ok if match else fail)(
        "%s: is_idem=%s (%s)" % (name, is_idem, why or "\u2014")
    )

# ────────────────────────────────────────────────────────────────
section("RESUMO")
if FAIL == 0:
    print("  \033[92m\u2714 Todas as camadas L1-L4 passaram.\033[0m")
    sys.exit(0)
else:
    print("  \033[91m\u2718 %d falha(s).\033[0m" % FAIL)
    sys.exit(1)

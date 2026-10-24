# fix_versions.py
from pathlib import Path

fp = Path("doxoade/commands/moddify_sys/mody_patch.py")
content = fp.read_text(encoding="utf-8")

# 1. Docstring
content = content.replace(
    "Mody Patch Engine v6.2 — Motor de Cirurgia Atômica de Diff (Ma'at & Sotéria).",
    "Mody Patch Engine v6.5.1 — Motor de Cirurgia Atômica de Diff (Ma'at & Sotéria).",
)

# 2. Banner
content = content.replace(
    "🩹 [MODY PATCH v6.4.2] Cirurgia Atômica de Diff",
    "🩹 [MODY PATCH v6.5.1] Cirurgia Atômica de Diff",
)

fp.write_text(content, encoding="utf-8")
print("OK — versões atualizadas para v6.5.1")

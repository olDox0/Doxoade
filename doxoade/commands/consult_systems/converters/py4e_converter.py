# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/py4e_converter.py
"""
Conversor Canônico para Python for Everybody (Dr. Charles Severance).
Fonte: https://github.com/csev/py4e
Conformidade: ProDeNov 2.1 | Categoria 1 (Python Básico).
"""
from __future__ import annotations
import re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

_converters_dir = Path(__file__).resolve().parent
if str(_converters_dir) not in sys.path:
    sys.path.insert(0, str(_converters_dir))

try:
    from .base_converter import BaseCanonicalConverter
except (ImportError, ValueError):
    from base_converter import BaseCanonicalConverter


class Py4eConverter(BaseCanonicalConverter):
    category = "python_basic_py4e"
    canonical_filename = "py4e.jsonl"
    default_source_url = "https://raw.githubusercontent.com/csev/py4e/master/book3"

    CHAPTERS = [
        ("01-intro.mkd",        "Capítulo 01: Introdução à Programação"),
        ("02-variables.mkd",    "Capítulo 02: Variáveis, Expressões e Declarações"),
        ("03-conditional.mkd",  "Capítulo 03: Execução Condicional"),
        ("04-functions.mkd",    "Capítulo 04: Funções"),
        ("05-iterations.mkd",   "Capítulo 05: Iterações e Loops"),
        ("06-strings.mkd",      "Capítulo 06: Strings"),
        ("07-files.mkd",        "Capítulo 07: Arquivos e I/O"),
        ("08-lists.mkd",        "Capítulo 08: Listas"),
        ("09-dictionaries.mkd", "Capítulo 09: Dicionários"),
        ("10-tuples.mkd",       "Capítulo 10: Tuplas"),
        ("11-regex.mkd",        "Capítulo 11: Expressões Regulares"),
        ("12-network.mkd",      "Capítulo 12: Programas em Rede e HTTP"),
        ("13-web.mkd",          "Capítulo 13: Uso de Web Services (XML e JSON)"),
        ("14-objects.mkd",      "Capítulo 14: Programação Orientada a Objetos"),
        ("15-database.mkd",     "Capítulo 15: Bancos de Dados e SQLite"),
        ("16-viz.mkd",          "Capítulo 16: Visualização de Dados"),
    ]

    # ─── Sphinx reST → Markdown ────────────────────────────────────────
    @staticmethod
    def _dedent_block(block: str) -> str:
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if not lines:
            return ""
        min_indent = min(len(ln) - len(ln.lstrip()) for ln in lines)
        return "\n".join(ln[min_indent:] if len(ln) >= min_indent else "" for ln in lines)

    def _clean_markdown(self, raw_text: str, chapter_num: int, title: str) -> str:
        text = raw_text

        # 1) code-block directives: ``.. code-block:: python`` + bloco indentado
        def _repl_codeblock(m: re.Match) -> str:
            lang = m.group(1) or ""
            body = self._dedent_block(m.group(2))
            return f"```{lang}\n{body}\n```\n"

        text = re.sub(
            r'\.\.\s+code-block::\s*(\w+)\s*\n\n((?:[ \t]+.+\n?)+)',
            _repl_codeblock,
            text,
        )

        # 2) sourcecode directives (variante usada em alguns capítulos)
        def _repl_sourcecode(m: re.Match) -> str:
            body = self._dedent_block(m.group(1))
            return f"```python\n{body}\n```\n"

        text = re.sub(
            r'\.\.\s+sourcecode::\s*python\s*\n\n((?:[ \t]+.+\n?)+)',
            _repl_sourcecode,
            text,
        )

        # 3) Figure directives (``.. figure:: img.png``) → descarta
        text = re.sub(
            r'\.\.\s+figure::\s*\S+\s*\n(?:[ \t]+.*\n)*',
            "",
            text,
        )

        # 4) Admonitions (``.. note::``) → vira blockquote
        def _repl_admon(m: re.Match) -> str:
            kind = m.group(1).lower()
            body = self._dedent_block(m.group(2))
            quoted = "\n".join(f"> {ln}" if ln else ">" for ln in body.split("\n"))
            return f"\n**{kind.title()}:**\n\n{quoted}\n"

        text = re.sub(
            r'\.\.\s+(note|warning|tip|important)::\s*\n((?:[ \t]+.+\n?)+)',
            _repl_admon,
            text,
        )

        # 5) Links reST: ``\`text <url>\`_`` → ``[text](url)``
        text = re.sub(
            r'`([^`<]+?)\s*<([^>]+)>`_',
            r'[\1](\2)',
            text,
        )

        # 6) Negrito reST: ``**bold**`` já é compatível; ``*itálico*`` também.

        # 7) Comentários reST (``.. texto``) → remove
        text = re.sub(r'^\.\.\s+(?!code-block|sourcecode|figure|note|warning|tip|important).*$',
                      "", text, flags=re.MULTILINE)

        # 8) Colapsa linhas em branco
        text = re.sub(r'\n{3,}', '\n\n', text).strip()

        header = (
            f"# PY4E — {title}\n\n"
            f"> Fonte: Python for Everybody (Charles Severance) — Capítulo {chapter_num:02d}\n\n"
        )
        return header + text

    # ─── Download concorrente ─────────────────────────────────────────
    def _download_chapter(self, item: Tuple[int, str, str]) -> Tuple[int, str, str, Optional[str]]:
        idx, filename, title = item
        url = f"{self.default_source_url}/{filename}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Doxoade-Ingestor/1.0 (PY4E)"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status == 200:
                    raw = resp.read().decode("utf-8", errors="replace")
                    if len(raw) > 500:
                        return idx, filename, title, raw
        except Exception:
            pass
        return idx, filename, title, None

    def convert(self, source_url: Optional[str] = None) -> Path:
        print(f"\n[*] 📥 Baixando capítulos de PY4E ({len(self.CHAPTERS)} capítulos)...")
        records: List[Dict[str, Any]] = []

        items = [
            (i + 1, fn, title)
            for i, (fn, title) in enumerate(self.CHAPTERS)
        ]

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self._download_chapter, it) for it in items]
            for fut in as_completed(futures):
                idx, filename, title, raw_text = fut.result()
                if not raw_text:
                    print(f"  ✖ [FALHA] Não foi possível baixar: {filename}")
                    continue

                slug = f"ch{idx:02d}_{self.slugify(Path(filename).stem.replace('-', '_'))}"
                uid = f"python/basic/py4e/{slug}"
                clean = self._clean_markdown(raw_text, idx, title)
                keywords = self.extract_keywords(title, clean, max_words=45)

                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": self.category,
                    "title": f"PY4E — {title}",
                    "keywords": keywords,
                    "content": clean,
                    "_order": idx,
                })
                print(f"  ✔ [OK] Cap {idx:02d}: {title[:40]}... ({len(clean)} bytes)")

        records.sort(key=lambda r: r["_order"])
        for r in records:
            del r["_order"]

        print(f"\n[*] Concluído download de {len(records)}/{len(self.CHAPTERS)} capítulos.")
        return self.save_canonical(records)


def run_converter():
    converter = Py4eConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

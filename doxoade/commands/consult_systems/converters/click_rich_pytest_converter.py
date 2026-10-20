# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/click_rich_pytest_converter.py
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

try:
    from ..doc_indexer import DocIndexer
except (ImportError, ValueError):
    from doxoade.commands.consult_systems.doc_indexer import DocIndexer


class ClickRichPytestConverter(BaseCanonicalConverter):
    category = "python_automation"
    canonical_filename = "click_rich_pytest.jsonl"

    # Cada lib tem um índice + páginas
    LIBRARIES = {
        "click": {
            "base": "https://click.palletsprojects.com/en/stable/",
            "title": "Click (CLI framework)",
            "pages": [
                ("", "Quickstart"),
                ("why/", "Why Click?"),
                ("commands/", "Commands and Groups"),
                ("options/", "Options"),
                ("arguments/", "Arguments"),
                ("parameters/", "Parameters"),
                ("prompts/", "Prompts"),
                ("utils/", "Utilities"),
                ("testing/", "Testing Click Applications"),
                ("shell-completion/", "Shell Completion"),
                ("exceptions/", "Exceptions"),
                ("advanced/", "Advanced Patterns"),
                ("wincmd/", "Windows Support"),
                ("unicode-support/", "Unicode Support"),
            ],
        },
        "rich": {
            "base": "https://rich.readthedocs.io/en/stable/",
            "title": "Rich (terminal formatting)",
            "pages": [
                ("", "Introduction"),
                ("console.html", "Console API"),
                ("text.html", "Text and Style"),
                ("markup.html", "Console Markup"),
                ("pretty.html", "Pretty Printing"),
                ("logging.html", "Logging Handler"),
                ("progress.html", "Progress Display"),
                ("table.html", "Tables"),
                ("live.html", "Live Display"),
                ("layout.html", "Layout"),
                ("panel.html", "Panels"),
                ("syntax.html", "Syntax Highlighting"),
                ("json.html", "JSON Pretty Printing"),
                ("highlighter.html", "Highlighter"),
                ("traceback.html", "Tracebacks"),
                ("protocols.html", "Protocols (rich.console)"),
            ],
        },
        "pytest": {
            "base": "https://docs.pytest.org/en/stable/",
            "title": "pytest (testing)",
            "pages": [
                ("getting-started.html", "Get Started"),
                ("how-to/assert.html", "Assertions (assert)"),
                ("how-to/fixtures.html", "Fixtures"),
                ("how-to/parametrize.html", "Parametrization"),
                ("how-to/mark.html", "Markers"),
                ("how-to/skipping.html", "Skipping Tests"),
                ("how-to/tmp_path.html", "Temporary Paths (tmp_path)"),
                ("how-to/capture-stdout-stderr.html", "Capture stdout/stderr"),
                ("how-to/monkeypatch.html", "monkeypatch"),
                ("how-to/doctest.html", "Doctest Integration"),
                ("how-to/unittest.html", "unittest Compatibility"),
                ("reference.html", "API Reference"),
                ("fixture.html", "Fixture Reference"),
            ],
        },
    }

    def _download_page(self, lib: str, item: Tuple[str, str]) -> Tuple[str, str, str, Optional[str]]:
        slug, title = item
        base = self.LIBRARIES[lib]["base"]
        url = base + slug
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (AutomationDocs)"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                if resp.status == 200:
                    html = resp.read().decode("utf-8", errors="replace")
                    if len(html) > 1000:
                        return lib, slug or "index", title, html
        except Exception:
            pass
        return lib, slug or "index", title, None

    def convert(self, source_url: Optional[str] = None) -> Path:
        indexer = DocIndexer()
        records: List[Dict[str, Any]] = []

        total_pages = sum(len(v["pages"]) for v in self.LIBRARIES.values())
        print(f"\n[*] 📥 Baixando {total_pages} páginas de Click + Rich + Pytest...")

        # Dispara todos em paralelo (3 libs × ~14 páginas)
        tasks: List[Tuple[str, Tuple[str, str]]] = []
        for lib, cfg in self.LIBRARIES.items():
            for page in cfg["pages"]:
                tasks.append((lib, page))

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(self._download_page, lib, page) for lib, page in tasks]
            for fut in as_completed(futures):
                lib, slug, title, raw_html = fut.result()
                if not raw_html:
                    print(f"  ✖ [FALHA] {lib}/{slug}")
                    continue

                try:
                    md = indexer.html_to_markdown(
                        raw_html, title_fallback=f"{lib}: {title}"
                    )
                except Exception as e:
                    print(f"  ✖ [FALHA] Parser HTML ({lib}/{slug}): {e}")
                    continue

                lib_title = self.LIBRARIES[lib]["title"]
                slug_clean = slug.rstrip("/").replace("/", "_").replace(".html", "") or "index"
                uid = f"python/automation/{lib}/{slug_clean}"
                header = (
                    f"# {lib_title} — {title}\n\n"
                    f"> Fonte: {self.LIBRARIES[lib]['base']}{slug}\n\n"
                )
                content = header + md.strip()

                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": self.category,
                    "title": f"{lib_title}: {title}",
                    "keywords": self.extract_keywords(f"{lib} {title}", content, max_words=40),
                    "content": content,
                })
                print(f"  ✔ [OK] {lib}/{slug_clean[:25]}: {len(content)} bytes")

        print(f"\n[*] Concluído download de {len(records)}/{total_pages} páginas.")
        return self.save_canonical(records)


def run_converter():
    converter = ClickRichPytestConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

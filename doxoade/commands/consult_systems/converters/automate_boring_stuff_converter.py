# -*- coding: utf-8 -*-
# doxoade\commands\consult_systems\converters\automate_boring_stuff_converter.py
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

# Reusa o sanitizador HTML do indexer principal (já testado, zero risco)
try:
    from ..doc_indexer import DocIndexer
except (ImportError, ValueError):
    from doxoade.commands.consult_systems.doc_indexer import DocIndexer


class AutomateBoringStuffConverter(BaseCanonicalConverter):
    category = "python_basic_automate"
    canonical_filename = "automate_boring_stuff.jsonl"
    default_source_url = "https://automatetheboringstuff.com/2e"

    CHAPTERS = [
        ("chapter0",  "Chapter 0: Introduction"),
        ("chapter1",  "Chapter 1: Python Basics"),
        ("chapter2",  "Chapter 2: Flow Control"),
        ("chapter3",  "Chapter 3: Functions"),
        ("chapter4",  "Chapter 4: Lists"),
        ("chapter5",  "Chapter 5: Dictionaries and Structuring Data"),
        ("chapter6",  "Chapter 6: Manipulating Strings"),
        ("chapter7",  "Chapter 7: Pattern Matching with Regular Expressions"),
        ("chapter8",  "Chapter 8: Input Validation"),
        ("chapter9",  "Chapter 9: Reading and Writing Files"),
        ("chapter10", "Chapter 10: Organizing Files"),
        ("chapter11", "Chapter 11: Debugging"),
        ("chapter12", "Chapter 12: Web Scraping"),
        ("chapter13", "Chapter 13: Working with Excel Spreadsheets"),
        ("chapter14", "Chapter 14: Working with Google Sheets"),
        ("chapter15", "Chapter 15: Working with PDF and Word Documents"),
        ("chapter16", "Chapter 16: Working with CSV Files and JSON Data"),
        ("chapter17", "Chapter 17: Keeping Time, Scheduling Tasks, and Launching Programs"),
        ("chapter18", "Chapter 18: Sending Email and Text Messages"),
        ("chapter19", "Chapter 19: Manipulating Images"),
        ("chapter20", "Chapter 20: Controlling the Keyboard and Mouse with GUI Automation"),
    ]

    def _download_chapter(self, item: Tuple[int, str, str]) -> Tuple[int, str, str, Optional[str]]:
        idx, slug, title = item
        # URLs do 2e: /2e/chapterN/  (com barra no final)
        url = f"{self.default_source_url}/{slug}/"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Doxoade-Ingestor/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                if resp.status == 200:
                    html = resp.read().decode("utf-8", errors="replace")
                    if len(html) > 2000:
                        return idx, slug, title, html
        except Exception:
            pass
        return idx, slug, title, None

    def convert(self, source_url: Optional[str] = None) -> Path:
        print(f"\n[*] 📥 Baixando capítulos de Automate the Boring Stuff 2e "
              f"({len(self.CHAPTERS)} capítulos)...")

        indexer = DocIndexer()  # reusa html_to_markdown (não inicializa DB)
        records: List[Dict[str, Any]] = []

        items = [
            (i + 1, slug, title)
            for i, (slug, title) in enumerate(self.CHAPTERS)
        ]

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self._download_chapter, it) for it in items]
            for fut in as_completed(futures):
                idx, slug, title, raw_html = fut.result()
                if not raw_html:
                    print(f"  ✖ [FALHA] Não foi possível baixar: {slug}")
                    continue

                # html_to_markdown já remove nav/header/footer, preserva <pre><code>,
                # converte <h1..h3>, <p>, <li> para Markdown limpo.
                try:
                    md = indexer.html_to_markdown(raw_html, title_fallback=title)
                except Exception as e:
                    print(f"  ✖ [FALHA] Parser HTML ({slug}): {e}")
                    continue

                # Adiciona cabeçalho de origem
                header = (
                    f"# Automate the Boring Stuff — {title}\n\n"
                    f"> Fonte: Al Sweigart (2nd Edition) — {slug}\n\n"
                )
                content = header + md.strip()

                uid = f"python/basic/automate/{slug}"
                keywords = self.extract_keywords(title, content, max_words=45)

                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": self.category,
                    "title": f"Automate — {title}",
                    "keywords": keywords,
                    "content": content,
                    "_order": idx,
                })
                print(f"  ✔ [OK] Cap {idx:02d}: {title[:40]}... ({len(content)} bytes)")

        records.sort(key=lambda r: r["_order"])
        for r in records:
            del r["_order"]

        print(f"\n[*] Concluído download de {len(records)}/{len(self.CHAPTERS)} capítulos.")
        return self.save_canonical(records)


def run_converter():
    converter = AutomateBoringStuffConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

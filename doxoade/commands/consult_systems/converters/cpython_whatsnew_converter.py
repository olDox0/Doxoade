# -*- coding: utf-8 -*-
# doxoade\commands\consult_systems\converters\cpython_whatsnew_converter.py
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


class CpythonWhatsnewConverter(BaseCanonicalConverter):
    category = "python_whatsnew"
    canonical_filename = "cpython_whatsnew.jsonl"
    default_source_url = "https://docs.python.org"

    WHATSNEW = ["3.10", "3.11", "3.12", "3.13", "3.14"]

    DEPRECATIONS = [
        ("deprecations/index", "Deprecations — Índice Geral"),
        ("deprecations/pending-removal-in-3.10", "Pending removal in 3.10"),
        ("deprecations/pending-removal-in-3.11", "Pending removal in 3.11"),
        ("deprecations/pending-removal-in-3.12", "Pending removal in 3.12"),
        ("deprecations/pending-removal-in-3.13", "Pending removal in 3.13"),
        ("deprecations/pending-removal-in-3.14", "Pending removal in 3.14"),
        ("deprecations/pending-removal-in-3.15", "Pending removal in 3.15"),
    ]

    def _download_html(self, slug: str) -> Optional[str]:
        url = f"{self.default_source_url}/3/{slug}.html"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (CPythonWhatsnew)"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                if resp.status == 200:
                    html = resp.read().decode("utf-8", errors="replace")
                    if len(html) > 1000:
                        return html
        except Exception:
            pass
        return None

    def convert(self, source_url: Optional[str] = None) -> Path:
        print(f"\n[*] 📥 Baixando What's New + Deprecations do CPython...")
        indexer = DocIndexer()
        records: List[Dict[str, Any]] = []

        tasks: List[Tuple[str, str]] = []
        for v in self.WHATSNEW:
            tasks.append((f"whatsnew/{v}", f"What's New in Python {v}"))
        for slug, title in self.DEPRECATIONS:
            tasks.append((slug, title))

        print(f"[*] Alvo: {len(tasks)} páginas")

        def _fetch(task):
            slug, title = task
            return slug, title, self._download_html(slug)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(_fetch, t) for t in tasks]
            for fut in as_completed(futures):
                slug, title, html = fut.result()
                if not html:
                    print(f"  ✖ [FALHA] {slug}")
                    continue
                try:
                    md = indexer.html_to_markdown(html, title_fallback=title)
                except Exception as e:
                    print(f"  ✖ [FALHA] Parser HTML ({slug}): {e}")
                    continue

                final_cat = "python_deprecations" if slug.startswith("deprecations/") else "python_whatsnew"
                uid = slug
                header = f"\n> Fonte: https://docs.python.org/3/{slug}.html\n\n"
                content = header + md.strip()

                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": final_cat,
                    "title": title,
                    "keywords": self.extract_keywords(title, content, max_words=45),
                    "content": content,
                })
                print(f"  ✔ [OK] {slug[:50]}: {len(content)} bytes")

        print(f"\n[*] Concluído download de {len(records)}/{len(tasks)} páginas.")
        return self.save_canonical(records)


def run_converter():
    converter = CpythonWhatsnewConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

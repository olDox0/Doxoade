# -*- coding: utf-8 -*-
from __future__ import annotations
import sys, urllib.request
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


class SanitizersConverter(BaseCanonicalConverter):
    """ASan/UBSan/MSan/TSan — referência de runtime C."""
    category = "c_sanitizers"
    canonical_filename = "c_sanitizers.jsonl"
    base_url = "https://clang.llvm.org/docs/"

    PAGES = [
        ("AddressSanitizer",                    "ASan — Address Sanitizer"),
        ("UndefinedBehaviorSanitizer",          "UBSan — Undefined Behavior Sanitizer"),
        ("MemorySanitizer",                     "MSan — Memory Sanitizer"),
        ("ThreadSanitizer",                     "TSan — Thread Sanitizer"),
        ("LeakSanitizer",                       "LSan — Leak Sanitizer"),
        ("SanitizerSpecialCaseList",            "Sanitizer Special Case List"),
        ("AddressSanitizerAndStaticBinaries",   "ASan + Static Binaries"),
    ]

    def _download(self, page: str) -> Optional[str]:
        url = f"{self.base_url}{page}.html"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (Sanitizers)"}
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
        print(f"\n[*] 📥 Baixando Sanitizers LLVM/Clang ({len(self.PAGES)} páginas)...")
        indexer = DocIndexer()
        records: List[Dict[str, Any]] = []

        def _fetch(item: Tuple[str, str]):
            page, title = item
            return page, title, self._download(page)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(_fetch, item) for item in self.PAGES]
            for fut in as_completed(futures):
                page, title, html = fut.result()
                if not html:
                    print(f"  ✖ [SKIP] {page}")
                    continue
                try:
                    md = indexer.html_to_markdown(html, title_fallback=title)
                except Exception as e:
                    print(f"  ✖ [FALHA] {page}: {e}")
                    continue
                uid = f"c/sanitizer/{page.lower()}"
                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": self.category,
                    "title": title,
                    "keywords": self.extract_keywords(title, md, max_words=45),
                    "content": f"# {title}\n\n{md}",
                })
                print(f"  ✔ [OK] {page}: {len(md)} bytes")

        print(f"\n[*] Total: {len(records)} docs de sanitizers.")
        return self.save_canonical(records)


def run_converter():
    SanitizersConverter().convert()


if __name__ == "__main__":
    run_converter()

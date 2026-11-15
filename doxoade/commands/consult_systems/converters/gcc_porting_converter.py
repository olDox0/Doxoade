# -*- coding: utf-8 -*-
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


class GccPortingConverter(BaseCanonicalConverter):
    category = "c_gcc_porting"
    canonical_filename = "gcc_porting.jsonl"
    default_source_url = "https://gcc.gnu.org"
    VERSIONS = ["12", "13", "14", "15", "16"]

    def _download_html(self, version: str, page: str) -> Optional[str]:
        url = f"{self.default_source_url}/gcc-{version}/{page}.html"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (GCCPorting)"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status == 200:
                    html = resp.read().decode("utf-8", errors="replace")
                    if len(html) > 1000:
                        return html
        except Exception:
            pass
        return None

    def convert(self, source_url: Optional[str] = None) -> Path:
        print(f"\n[*] 📥 Baixando GCC Porting (versões {', '.join(self.VERSIONS)})...")
        indexer = DocIndexer()
        records: List[Dict[str, Any]] = []

        tasks: List[Tuple[str, str]] = []
        for v in self.VERSIONS:
            tasks.append((v, "porting_to"))
            tasks.append((v, "changes"))

        def _fetch(task):
            v, page = task
            return v, page, self._download_html(v, page)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(_fetch, t) for t in tasks]
            for fut in as_completed(futures):
                v, page, html = fut.result()
                if not html:
                    print(f"  ✖ [SKIP] gcc-{v}/{page}")
                    continue
                title = f"Porting to GCC {v}" if page == "porting_to" else f"GCC {v} Changes"
                slug = f"gcc-{v}-{page}"
                uid = f"c/gcc/porting/{slug}"
                try:
                    md = indexer.html_to_markdown(html, title_fallback=title)
                except Exception as e:
                    print(f"  ✖ [FALHA] Parser ({slug}): {e}")
                    continue
                header = f"\n> Fonte: https://gcc.gnu.org/gcc-{v}/{page}.html\n\n"
                content = header + md.strip()
                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": self.category,
                    "title": title,
                    "keywords": self.extract_keywords(title, content, max_words=45),
                    "content": content,
                })
                print(f"  ✔ [OK] gcc-{v}/{page}: {len(content)} bytes")

        print(f"\n[*] Total: {len(records)} páginas GCC.")
        return self.save_canonical(records)


def run_converter():
    converter = GccPortingConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

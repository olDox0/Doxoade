# -*- coding: utf-8 -*-

from __future__ import annotations
import re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Optional

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


class MypyConverter(BaseCanonicalConverter):
    """Ingere a referência de error codes do mypy, 1 doc por código."""
    category = "python_mypy_codes"
    canonical_filename = "mypy_codes.jsonl"
    PAGES = [
        "https://mypy.readthedocs.io/en/stable/error_code_list.html",
        "https://mypy.readthedocs.io/en/stable/error_code_list2.html",
    ]

    def _download(self, url: str) -> Optional[str]:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (Mypy)"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  ✖ Falha em {url}: {e}")
            return None

    def convert(self, source_url: Optional[str] = None) -> Path:
        print(f"\n[*] 📥 Ingerindo Mypy Error Codes...")
        indexer = DocIndexer()
        records: List[Dict[str, Any]] = []

        for url in self.PAGES:
            html = self._download(url)
            if not html:
                continue
            # Cada código é um <h2> com id tipo "check-name-defined"
            # ou <section id="..."><h2>[code-name]</h2>
            parts = re.split(r'<section[^>]*id="([^"]+)"', html)
            # parts: [preâmbulo, id1, corpo1, id2, corpo2, ...]
            for i in range(1, len(parts), 2):
                section_id = parts[i]
                body_html = parts[i + 1] if i + 1 < len(parts) else ""
                # Filtra seções que não são error codes
                if not re.match(r"^(?:check-|[a-z\-]+-)", section_id):
                    continue
                # Extrai o código do título (ex: "[attr-defined]")
                code_match = re.search(r"\[([a-z\-]+)\]", body_html)
                if not code_match:
                    continue
                code = code_match.group(1)
                title_match = re.search(r"<h\d[^>]*>(.*?)</h\d>", body_html, re.DOTALL)
                title = code
                if title_match:
                    clean = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
                    clean = re.sub(r"\[[a-z\-]+\]", "", clean).strip()
                    if clean:
                        title = clean
                md = indexer.html_to_markdown(
                    f"<div>{body_html}</div>",
                    title_fallback=f"mypy [{code}]",
                )
                md = re.sub(r"^# 📖[^\n]*\n+", "", md).strip()
                if len(md) < 80:
                    continue
                uid = f"python/mypy/codes/{code}"
                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": self.category,
                    "title": f"mypy [{code}]: {title}",
                    "keywords": self.extract_keywords(f"{code} {title} mypy", md, max_words=40),
                    "content": f"# mypy [{code}]\n\n{md}",
                })

        print(f"\n[*] Total: {len(records)} error codes do mypy.")
        return self.save_canonical(records)


def run_converter():
    MypyConverter().convert()


if __name__ == "__main__":
    run_converter()

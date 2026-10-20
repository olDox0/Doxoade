# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/peps_converter.py
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


class PepsConverter(BaseCanonicalConverter):
    category = "python_peps"
    canonical_filename = "peps.jsonl"
    default_source_url = "https://peps.python.org"

    # Curadoria cirúrgica — só as PEPs que definem arquitetura moderna
    PEPS = [
        (8,    "Style Guide for Python Code"),
        (20,   "The Zen of Python"),
        (257,  "Docstring Conventions"),
        (484,  "Type Hints"),
        (492,  "Decorators for Functions and Methods"),
        (526,  "Syntax for Variable Annotations"),
        (544,  "Protocols: Structural subtyping (static duck typing)"),
        (557,  "Data Classes"),
        (560,  "Core support for typing module and generic types"),
        (572,  "Assignment Expressions (walrus operator :=)"),
        (585,  "Type Hinting Generics In Standard Collections"),
        (604,  "Allow writing union types as X | Y"),
        (612,  "Parameter Specification Variables (ParamSpec)"),
        (634,  "Structural Pattern Matching: Specification"),
        (635,  "Structural Pattern Matching: Motivation and Rationale"),
        (636,  "Structural Pattern Matching: Tutorial"),
        (646,  "Variadic Generics (TypeVarTuple)"),
        (675,  "Arbitrary Literal String Type"),
    ]

    def _download_pep(self, item: Tuple[int, str]) -> Tuple[int, str, Optional[str]]:
        num, title = item
        url = f"{self.default_source_url}/pep-{num:04d}/"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (PEPs)"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                if resp.status == 200:
                    html = resp.read().decode("utf-8", errors="replace")
                    if len(html) > 1000:
                        return num, title, html
        except Exception:
            pass
        return num, title, None

    def convert(self, source_url: Optional[str] = None) -> Path:
        print(f"\n[*] 📥 Baixando {len(self.PEPS)} PEPs fundamentais...")

        indexer = DocIndexer()
        records: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self._download_pep, item) for item in self.PEPS]
            for fut in as_completed(futures):
                num, title, raw_html = fut.result()
                if not raw_html:
                    print(f"  ✖ [FALHA] PEP {num}")
                    continue

                # Isola o corpo da PEP (remove nav/header/footer do Sphinx)
                try:
                    md = indexer.html_to_markdown(raw_html, title_fallback=f"PEP {num}")
                except Exception as e:
                    print(f"  ✖ [FALHA] Parser HTML (PEP {num}): {e}")
                    continue

                uid = f"python/peps/pep_{num:04d}"
                header = f"# PEP {num} — {title}\n\n> Fonte: {self.default_source_url}/pep-{num:04d}/\n\n"
                content = header + md.strip()

                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": self.category,
                    "title": f"PEP {num}: {title}",
                    "keywords": self.extract_keywords(title, content, max_words=50),
                    "content": content,
                    "_order": num,
                })
                print(f"  ✔ [OK] PEP {num:04d}: {title[:45]}... ({len(content)} bytes)")

        records.sort(key=lambda r: r["_order"])
        for r in records:
            del r["_order"]

        print(f"\n[*] Concluído download de {len(records)}/{len(self.PEPS)} PEPs.")
        return self.save_canonical(records)


def run_converter():
    converter = PepsConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

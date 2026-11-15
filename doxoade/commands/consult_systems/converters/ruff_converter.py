# -*- coding: utf-8 -*-
from __future__ import annotations
import json, sys, urllib.request
from pathlib import Path
from typing import List, Dict, Any, Optional

_converters_dir = Path(__file__).resolve().parent
if str(_converters_dir) not in sys.path:
    sys.path.insert(0, str(_converters_dir))

try:
    from .base_converter import BaseCanonicalConverter
except (ImportError, ValueError):
    from base_converter import BaseCanonicalConverter

class RuffConverter(BaseCanonicalConverter):
    category = "python_ruff_rules"
    canonical_filename = "ruff_rules.jsonl"
    default_source_url = "https://docs.astral.sh/ruff/search/search_index.json"

    def convert(self, source_url: Optional[str] = None) -> Path:
        url = source_url or self.default_source_url
        print(f"\n[*] 📥 Baixando índice de busca do Ruff (MkDocs)...")
        req = urllib.request.Request(
            url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (Ruff)"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        records: List[Dict[str, Any]] = []
        for doc in data.get("docs", []):
            loc = doc.get("location", "")
            if not loc.startswith("rules/"):
                continue

            # Extrai o slug (ex: "f401")
            slug = loc.replace("rules/", "").strip("/")
            if not slug:
                continue

            title = doc.get("title", "").strip()
            text = doc.get("text", "").strip()
            if len(text) < 50:
                continue

            # Title geralmente é "unused-import (F401)"
            code_match = title.split("(")[-1].replace(")", "").strip() if "(" in title else slug.upper()
            
            uid = f"python/ruff/rules/{slug}"
            records.append({
                "uid": uid,
                "path": uid,
                "category": self.category,
                "title": f"Ruff {code_match}: {title}",
                "keywords": self.extract_keywords(f"{code_match} {slug} ruff", text, max_words=40),
                "content": f"# Ruff {code_match}\n\n**Regra:** `{title}`\n\n{text}",
            })

        print(f"\n[*] Total: {len(records)} regras Ruff válidas.")
        return self.save_canonical(records)

def run_converter():
    RuffConverter().convert()

if __name__ == "__main__":
    run_converter()

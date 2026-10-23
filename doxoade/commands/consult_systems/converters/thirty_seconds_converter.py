# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/thirty_seconds_converter.py
from __future__ import annotations
import io, re, sys, urllib.request, zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional

_converters_dir = Path(__file__).resolve().parent
if str(_converters_dir) not in sys.path:
    sys.path.insert(0, str(_converters_dir))

try:
    from .base_converter import BaseCanonicalConverter
except (ImportError, ValueError):
    from base_converter import BaseCanonicalConverter


class ThirtySecondsConverter(BaseCanonicalConverter):
    category = "python_snippets"
    canonical_filename = "30_seconds_python.jsonl"
    default_source_url = (
        "https://github.com/Chalarangelo/30-seconds-of-code/archive/refs/heads/master.zip"
    )

    def _clean_markdown(self, raw: str, title: str, tags: str) -> str:
        # Remove o frontmatter YAML do topo (já extraímos title/tags)
        text = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.DOTALL).strip()

        # Colapsa linhas vazias
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        header = (
            f"# 30 Seconds of Python — {title}\n\n"
            f"> Snippet rápido | Tags: {tags}\n\n"
        )
        return header + text

    def convert(self, source_url: Optional[str] = None) -> Path:
        url = source_url or self.default_source_url
        print(f"\n[*] 📥 Baixando ZIP do 30-seconds-of-code...")
        print(f"    {url}")

        req = urllib.request.Request(
            url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (30s)"}
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            zip_bytes = resp.read()
        print(f"[*] ZIP recebido ({len(zip_bytes) / (1024*1024):.2f} MB).")

        records: List[Dict[str, Any]] = []
        skipped = 0

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            all_names = zf.namelist()
            # Prefixo raiz: 30-seconds-of-code-master/
            root_prefix = ""
            for n in all_names:
                parts = n.split("/", 1)
                if len(parts) == 2 and parts[1]:
                    root_prefix = parts[0] + "/"
                    break
            print(f"[*] Prefixo raiz: {root_prefix!r}")

            for member in all_names:
                if not member.endswith(".md"):
                    continue
                if "content/snippets/python/" not in member:
                    continue
                if "snippet-template" in member.lower():
                    continue

                rel = member[len(root_prefix):] if member.startswith(root_prefix) else member
                try:
                    raw = zf.read(member).decode("utf-8", errors="replace")
                except Exception:
                    skipped += 1
                    continue

                # Extrai frontmatter YAML (simples, sem parser)
                title = Path(rel).stem.replace("-", " ").title()
                tags = "python"

                fm_match = re.search(r"^---\n(.*?)\n---\n", raw, flags=re.DOTALL)
                if fm_match:
                    fm = fm_match.group(1)
                    m_title = re.search(r"^title:\s*(.+)$", fm, re.MULTILINE)
                    if m_title:
                        title = m_title.group(1).strip().strip('"').strip("'")
                    m_tags = re.search(r"^tags:\s*\[(.+?)\]", fm, re.MULTILINE)
                    if m_tags:
                        tags = m_tags.group(1).strip()

                clean = self._clean_markdown(raw, title, tags)
                if len(clean) < 80:
                    skipped += 1
                    continue

                slug = Path(rel).stem
                uid = f"python/snippets/{slug}"
                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": self.category,
                    "title": f"30s Python: {title}",
                    "keywords": self.extract_keywords(f"{title} {tags} python snippet", clean, max_words=40),
                    "content": clean,
                })

        # Ordena alfabeticamente por title
        records.sort(key=lambda r: r["title"])
        print(f"\n[*] Total: {len(records)} snippets válidos ({skipped} ignorados).")
        return self.save_canonical(records)


def run_converter():
    converter = ThirtySecondsConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

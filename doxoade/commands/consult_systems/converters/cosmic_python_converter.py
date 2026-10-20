# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/cosmic_python_converter.py
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


class CosmicPythonConverter(BaseCanonicalConverter):
    category = "python_architecture"
    canonical_filename = "cosmic_python.jsonl"
    default_source_url = (
        "https://github.com/cosmicpython/book/archive/refs/heads/master.zip"
    )

    # Capítulos do livro, na ordem
    CHAPTERS = [
        ("chapter_01_domain_model",  "Chapter 1: Domain Modeling"),
        ("chapter_02_repository",    "Chapter 2: Repository Pattern"),
        ("chapter_03_abstractions",  "Chapter 3: Abstractions (Coupling and Abstractions)"),
        ("chapter_04_service_layer", "Chapter 4: Service Layer"),
        ("chapter_05_tdd",           "Chapter 5: TDD in High Gear and Low Gear"),
        ("chapter_06_uow",           "Chapter 6: Unit of Work Pattern"),
        ("chapter_07_aggregate",     "Chapter 7: Aggregates and Consistency Boundaries"),
        ("chapter_08_events",        "Chapter 8: Events and the Message Bus"),
        ("chapter_09_cqrs",          "Chapter 9: Going to Town on the Message Bus (CQRS)"),
        ("chapter_10_commands",      "Chapter 10: Commands and Command Handler"),
        ("chapter_11_eventsourcing", "Chapter 11: Event-Driven Architecture (Eventsourcing)"),
        ("chapter_12_cqrs",          "Chapter 12: CQRS"),
        ("chapter_13_dependency",    "Chapter 13: Dependency Injection (and Bootstrapping)"),
        ("epilogue",                 "Epilogue: Footguns"),
        ("appendix_dip",             "Appendix: Dependency Inversion Principle"),
    ]

    def _detect_root_prefix(self, names: List[str]) -> str:
        for n in names:
            parts = n.split("/", 1)
            if len(parts) == 2 and parts[1]:
                return parts[0] + "/"
        return ""

    def _clean_markdown(self, raw: str, title: str) -> str:
        text = raw
        # Remove diretivas Jekyll (o livro usa _config.yml com includes)
        text = re.sub(r'\{%\s*include\s+[^%]+\s*%\}', '', text)
        # Remove badges
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        # Colapsa linhas em branco
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        header = f"# Cosmic Python — {title}\n\n> Fonte: Architecture Patterns with Python (Percival & Gregory)\n\n"
        return header + text

    def convert(self, source_url: Optional[str] = None) -> Path:
        url = source_url or self.default_source_url
        print(f"\n[*] 📥 Baixando Cosmic Python...")
        print(f"    {url}")

        req = urllib.request.Request(
            url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (CosmicPython)"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            zip_bytes = resp.read()
        print(f"[*] ZIP recebido ({len(zip_bytes) / (1024*1024):.2f} MB).")

        records: List[Dict[str, Any]] = []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            all_names = zf.namelist()
            root = self._detect_root_prefix(all_names)
            print(f"[*] Prefixo raiz: {root!r}")

            # Mapeia capítulos por basename do .md dentro de chapters/
            for member in all_names:
                if not member.endswith(".md"):
                    continue
                rel = member[len(root):] if member.startswith(root) else member
                if not rel.startswith("chapters/"):
                    continue
                stem = Path(rel).stem
                # Match por capítulo
                title = None
                order = 999
                for idx, (slug, t) in enumerate(self.CHAPTERS):
                    if stem.startswith(slug) or slug.startswith(stem):
                        title = t
                        order = idx
                        break
                if not title:
                    continue

                try:
                    raw = zf.read(member).decode("utf-8", errors="replace")
                except Exception:
                    continue
                if len(raw) < 500:
                    continue

                clean = self._clean_markdown(raw, title)
                uid = f"python/architecture/cosmic/{stem}"
                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": self.category,
                    "title": f"Cosmic Python — {title}",
                    "keywords": self.extract_keywords(title, clean, max_words=50),
                    "content": clean,
                    "_order": order,
                })
                print(f"  ✔ [OK] {title[:45]}... ({len(clean)} bytes)")

        records.sort(key=lambda r: r["_order"])
        for r in records:
            del r["_order"]

        print(f"\n[*] Concluído download de {len(records)} capítulos.")
        return self.save_canonical(records)


def run_converter():
    converter = CosmicPythonConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

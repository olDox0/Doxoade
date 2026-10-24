# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/devdocs_bridge_converter.py
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

try:
    from ..doc_indexer import DocIndexer
except (ImportError, ValueError):
    from doxoade.commands.consult_systems.doc_indexer import DocIndexer


class DevDocsBridgeConverter(BaseCanonicalConverter):
    category = "python_ecosystem"
    canonical_filename = "devdocs_bridge.jsonl"

    # Cada lib tem: nome, URL do ZIP, prefixo interno (para filtrar)
    LIBRARIES = {
        "requests": {
            "url": "https://requests.readthedocs.io/_/downloads/en/latest/htmlzip/",  # ← 404
            # Usar o pacote do GitHub (stable, sempre disponível)
            "url": "https://github.com/psf/requests/archive/refs/heads/main.zip",
            "title": "Requests (HTTP library)",
            "include_prefix": "requests-main/docs/",  # filtra só docs/
        },    
        "numpy": {
            "url": "https://numpy.org/doc/stable/numpy-html.zip",
            "title": "NumPy (numerical computing)",
            "include_prefix": "",
        },
        "pandas": {
            "url": "https://pandas.pydata.org/pandas-docs/version/2.3/pandas.zip",
            "title": "pandas (data analysis)",
            "include_prefix": "",
        },
    }

    def _download_zip(self, url: str, timeout: int = 180) -> Optional[bytes]:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (Ecosystem)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            print(f"    ✖ Falha no download: {e}")
            return None

    def _process_zip(self, lib: str, zip_bytes: bytes, indexer: DocIndexer) -> List[Dict[str, Any]]:
        cfg = self.LIBRARIES[lib]
        records: List[Dict[str, Any]] = []
        skipped = 0

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            all_names = zf.namelist()
            # Detecta prefixo raiz (ex: numpy-html/)
            root_prefix = ""
            for n in all_names:
                parts = n.split("/", 1)
                if len(parts) == 2 and parts[1]:
                    root_prefix = parts[0] + "/"
                    break
            print(f"    [*] Prefixo raiz: {root_prefix!r}")

            for member in all_names:
                if not member.endswith(".html"):
                    continue
                if cfg.get("include_prefix") and cfg["include_prefix"] not in member:
                    continue
                # Ignora índices, genindex, search, etc.
                base = Path(member).name.lower()
                if any(x in base for x in ["genindex", "search", "py-modindex", "contents"]):
                    continue

                rel = member[len(root_prefix):] if member.startswith(root_prefix) else member
                try:
                    raw_html = zf.read(member).decode("utf-8", errors="replace")
                except Exception:
                    skipped += 1
                    continue

                if len(raw_html) < 500:
                    skipped += 1
                    continue

                try:
                    md = indexer.html_to_markdown(
                        raw_html, title_fallback=f"{cfg['title']} — {base}"
                    )
                except Exception:
                    skipped += 1
                    continue

                if len(md) < 100:
                    skipped += 1
                    continue

                # Path: python/ecosystem/<lib>/<rel_sem_html>
                slug = rel.replace(".html", "").replace("/", "_")
                uid = f"python/ecosystem/{lib}/{slug}"
                header = f"# {cfg['title']} — {base.replace('.html', '')}\n\n> Fonte: {cfg['url']}\n\n"
                content = header + md.strip()

                records.append({
                    "uid": uid,
                    "path": uid,
                    "category": self.category,
                    "title": f"{cfg['title']}: {base.replace('.html', '')}",
                    "keywords": self.extract_keywords(f"{lib} {base}", content, max_words=40),
                    "content": content,
                })

        print(f"    [*] {lib}: {len(records)} páginas válidas ({skipped} ignoradas).")
        return records

    def convert(self, source_url: Optional[str] = None) -> Path:
        indexer = DocIndexer()
        all_records: List[Dict[str, Any]] = []

        for lib, cfg in self.LIBRARIES.items():
            print(f"\n[*] 📥 Baixando {lib} ({cfg['title']})...")
            print(f"    {cfg['url']}")
            zip_bytes = self._download_zip(cfg["url"])
            if not zip_bytes:
                print(f"  ✖ [FALHA] {lib} — pulando.")
                continue
            print(f"[*] ZIP recebido ({len(zip_bytes) / (1024*1024):.2f} MB).")
            records = self._process_zip(lib, zip_bytes, indexer)
            all_records.extend(records)

        print(f"\n[*] Total: {len(all_records)} páginas de ecossistema Python.")
        return self.save_canonical(all_records)


def run_converter():
    converter = DevDocsBridgeConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

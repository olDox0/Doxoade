# -*- coding: utf-8 -*-
# doxoade\commands\consult_systems\converters\clang_diag_converter.py
from __future__ import annotations
import re, sys, urllib.request
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


class ClangDiagConverter(BaseCanonicalConverter):
    category = "c_clang_diag"
    canonical_filename = "clang_diagnostics.jsonl"
    default_source_url = "https://clang.llvm.org/docs/DiagnosticsReference.html"
    MAX_CHUNKS = 1200

    def _slugify_flag(self, flag: str) -> str:
        return flag.lstrip("-").replace("-", "_")

    def _is_c_relevant(self, text: str) -> bool:
        low = text.lower()
        if re.search(r"\bonly\s+(in\s+)?c\+\+", low):
            return False
        if re.search(r"\bc\+\+[\s\-]+only", low):
            return False
        return True

    def convert(self, source_url: Optional[str] = None) -> Path:
        import html as html_lib
        
        url = source_url or self.default_source_url
        print(f"\n[*] 📥 Baixando Clang DiagnosticsReference (HTML)...")
        req = urllib.request.Request(
            url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (ClangDiag)"}
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw_html = resp.read().decode("utf-8", errors="replace")
        print(f"[*] HTML recebido ({len(raw_html)/1024:.1f} KB).")

        # Encontra todos os H3 (cada um é uma flag)
        matches = list(re.finditer(r"<h3[^>]*>(.*?)</h3>", raw_html, re.DOTALL))
        print(f"[*] {len(matches)} flags <h3> detectadas")

        records: List[Dict[str, Any]] = []
        CHUNK_SIZE = 8  # Agrupa 8 flags por documento

        for i in range(0, len(matches), CHUNK_SIZE):
            chunk_matches = matches[i:i+CHUNK_SIZE]
            chunk_content = []
            chunk_path_slug = []

            for j, m in enumerate(chunk_matches):
                flag_title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                flag_title = html_lib.unescape(flag_title)
                
                start_pos = m.end()
                end_pos = matches[i + j + 1].start() if (i + j + 1 < len(matches)) else len(raw_html)
                body_html = raw_html[start_pos:end_pos]
                
                # 🎯 PRESERVA BLOCOS DE CÓDIGO: Substitui <pre>...</pre> por ```...```
                def _replace_pre(match):
                    code = re.sub(r'<[^>]+>', '', match.group(1))
                    return f"\n```c\n{html_lib.unescape(code).strip()}\n```\n"
                
                body_html = re.sub(r"<pre[^>]*>(.*?)</pre>", _replace_pre, body_html, flags=re.DOTALL)
                
                # Limpa o resto do HTML
                clean_text = re.sub(r'<[^>]+>', ' ', body_html)
                clean_text = html_lib.unescape(clean_text)
                clean_text = re.sub(r'[ \t]+', ' ', clean_text)
                clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()

                if len(clean_text) > 20:
                    chunk_content.append(f"### {flag_title}\n{clean_text}")
                    chunk_path_slug.append(flag_title.lstrip("-").replace("-", "_"))

            if not chunk_content:
                continue

            full_md = "\n\n".join(chunk_content)
            first_flag = re.sub(r"<[^>]+>", "", chunk_matches[0].group(1)).strip()
            last_flag = re.sub(r"<[^>]+>", "", chunk_matches[-1].group(1)).strip()
            title = f"Clang Diagnósticos: {first_flag} até {last_flag}"
            
            slug = f"lote_{i//CHUNK_SIZE + 1}"
            uid = f"c/clang/diag/{slug}"

            content = f"# {title}\n\n{full_md}"

            records.append({
                "uid": uid,
                "path": uid,
                "category": self.category,
                "title": title,
                "keywords": self.extract_keywords(" ".join(chunk_path_slug), content, max_words=40),
                "content": content,
            })

        print(f"\n[*] Total: {len(records)} lotes de diagnóstico Clang.")
        return self.save_canonical(records)

def run_converter():
    converter = ClangDiagConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

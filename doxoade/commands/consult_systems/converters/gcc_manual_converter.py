# -*- coding: utf-8 -*-
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

class GccManualConverter(BaseCanonicalConverter):
    category = "c_gcc_manual"
    canonical_filename = "gcc_manual.jsonl"
    default_source_url = "https://gcc.gnu.org/onlinedocs/gcc-14.2.0/gcc/Warning-Options.html"

    def convert(self, source_url: Optional[str] = None) -> Path:
        url = source_url or self.default_source_url
        print(f"\n[*] 📥 Baixando GCC Warning-Options...")
        req = urllib.request.Request(url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (GCC)"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            
        print(f"[*] HTML recebido ({len(html)/1024:.1f} KB).")
        indexer = DocIndexer()
        records: List[Dict[str, Any]] = []
        
        # No manual GCC, cada flag está num <dt><span><code>-Wflag</code></span></dt> seguido de <dd>explicação</dd>
        # Vamos usar regex para pegar os blocos
        pattern = re.compile(r"<dt[^>]*>.*?<code>(-W[\w\-=]+)</code>.*?</dt>\s*<dd>(.*?)</dd>", re.DOTALL | re.IGNORECASE)
        
        matches = pattern.findall(html)
        print(f"[*] {len(matches)} opções de warning encontradas.")

        seen = set()
        for flag, body_html in matches:
            flag = flag.strip()
            if flag in seen:
                continue
            seen.add(flag)

            try:
                md = indexer.html_to_markdown(f"<div>{body_html}</div>", title_fallback=f"GCC {flag}")
                md = re.sub(r"^# 📖[^\n]*\n+", "", md).strip()
            except Exception:
                continue

            if len(md) < 80:
                continue

            slug = flag.lstrip("-").replace("=", "_").replace("-", "_")
            uid = f"c/gcc/manual/{slug}"
            title = f"GCC Manual: {flag}"
            
            records.append({
                "uid": uid,
                "path": uid,
                "category": self.category,
                "title": title,
                "keywords": self.extract_keywords(f"{flag} gcc manual", md, max_words=40),
                "content": f"# {title}\n\n{md}",
            })

        print(f"\n[*] Total: {len(records)} opções do manual GCC.")
        return self.save_canonical(records)

def run_converter():
    GccManualConverter().convert()

if __name__ == "__main__":
    run_converter()

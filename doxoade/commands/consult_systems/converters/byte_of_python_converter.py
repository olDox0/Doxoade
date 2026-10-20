# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/byte_of_python_converter.py
"""
Conversor Canônico para A Byte of Python (Swaroop C H).
Fonte: https://github.com/swaroopch/byte-of-python
Conformidade: ProDeNov 2.1 | Categoria 1 (Python Básico).
"""
from __future__ import annotations
import sys
import re
import urllib.request
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


class ByteOfPythonConverter(BaseCanonicalConverter):
    category = "python_basic_byteofpython"
    canonical_filename = "byte_of_python.jsonl"
    default_source_url = "https://raw.githubusercontent.com/swaroopch/byte-of-python/master"

    # Mapeamento oficial dos capítulos conforme o SUMMARY.md do livro
    CHAPTERS = [
        ("about_python.md", "Sobre o Python e Recursos"),
        ("installation.md", "Instalação e Setup"),
        ("first_steps.md", "Primeiros Passos no Prompt e Arquivos"),
        ("basics.md", "Conceitos Básicos, Literais e Variáveis"),
        ("op_exp.md", "Operadores e Expressões"),
        ("control_flow.md", "Controle de Fluxo (if, for, while)"),
        ("functions.md", "Funções, Parâmetros e Escopos"),
        ("modules.md", "Módulos, Pacotes e Bytecode"),
        ("data_structures.md", "Estruturas de Dados (Listas, Tuplas, Dicionários, Sets)"),
        ("problem_solving.md", "Resolução de Problemas Práticos (Script de Backup)"),
        ("oop.md", "Programação Orientada a Objetos (Classes, self e herança)"),
        ("io.md", "Entrada e Saída, Arquivos e Pickle"),
        ("exceptions.md", "Tratamento de Exceções (try/except/finally)"),
        ("stdlib.md", "Biblioteca Padrão Essencial (sys, os, logging)"),
        ("more.md", "Tópicos Avançados (lambda, list comprehension, assert, repr)"),
        ("what_next.md", "Próximos Passos e Recursos Recomendados"),
    ]

    def _clean_markdown(self, raw_text: str, title: str) -> str:
        """Remove links de navegação e resolve tags de include externas."""
        text = re.sub(r'\[(?:Previous|Next|Table of Contents)\]\(.*?\)', '', raw_text, flags=re.IGNORECASE)
        text = re.sub(r'^\s*\|\s*$', '', text, flags=re.MULTILINE)

        # Converte tags {% include "./programs/xyz.py" %} para blocos markdown reais
        def _resolve_include(m):
            prog_rel = m.group(1).lstrip('./')
            prog_url = f"{self.default_source_url}/{prog_rel}"
            try:
                req = urllib.request.Request(prog_url, headers={'User-Agent': 'Doxoade-Ingestor/1.0'})
                with urllib.request.urlopen(req, timeout=8) as r:
                    code_bytes = r.read().decode('utf-8', errors='replace')
                    lang = "python" if prog_rel.endswith('.py') else ""
                    return f"\n```{lang}\n{code_bytes.strip()}\n```\n"
            except Exception:
                return f"\n```python\n# Arquivo: {prog_rel}\n```\n"

        text = re.sub(r'<pre><code[^>]*>\{%\s*include\s*["\'](.*?)["\']\s*%\}</code></pre>', _resolve_include, text)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        header = f"# 📖 A Byte of Python — {title}\n\n"
        return header + text

    def _download_chapter(self, item: Tuple[str, str]) -> Tuple[str, str, Optional[str]]:
        filename, title = item
        url = f"{self.default_source_url}/{filename}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Doxoade-Ingestor/1.0 (ByteOfPython)'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    raw_text = resp.read().decode('utf-8', errors='replace')
                    if len(raw_text) > 100:
                        return filename, title, raw_text
        except Exception:
            pass
        return filename, title, None

    def convert(self, source_url: Optional[str] = None) -> Path:
        print(f"\n[*] 📥 Baixando capítulos de A Byte of Python ({len(self.CHAPTERS)} capítulos)...")
        records: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self._download_chapter, item) for item in self.CHAPTERS]
            for future in as_completed(futures):
                filename, title, raw_text = future.result()
                if raw_text:
                    slug = self.slugify(Path(filename).stem)
                    uid = f"python/basic/byte_of_python/{slug}"
                    clean_content = self._clean_markdown(raw_text, title)
                    keywords = self.extract_keywords(title, clean_content, max_words=45)

                    records.append({
                        "uid": uid,
                        "path": uid,
                        "category": self.category,
                        "title": f"A Byte of Python — {title}",
                        "keywords": keywords,
                        "content": clean_content,
                        "_order": [f[0] for f in self.CHAPTERS].index(filename)
                    })
                    print(f"  ✔ [OK] {title[:35]}... ({len(clean_content)} bytes)")
                else:
                    print(f"  ✖ [FALHA] Não foi possível baixar: {filename}")

        # Ordena de acordo com o índice do livro
        records.sort(key=lambda r: r["_order"])
        for r in records:
            del r["_order"]

        print(f"\n[*] Concluído download de {len(records)}/{len(self.CHAPTERS)} capítulos integrais.")
        return self.save_canonical(records)


def run_converter():
    converter = ByteOfPythonConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

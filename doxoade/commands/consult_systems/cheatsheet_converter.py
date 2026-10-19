# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/cheatsheet_converter.py
"""
Conversor Canônico para Python Cheatsheet v4.0 (Capítulos Completos sem Fragmentação).
Preserva todos os subtópicos (###) no mesmo artigo para manter a dinâmica de estudo contínua.
"""
from __future__ import annotations
import os
import sys
import json
import re
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_URL = "https://raw.githubusercontent.com/gto76/python-cheatsheet/main/README.md"


class CheatsheetConverter:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or (Path.home() / ".doxoade" / "consult" / "canonical")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = self.output_dir / "python_cheatsheet.jsonl"

    @staticmethod
    def _slugify(text: str) -> str:
        text = re.sub(r'^\d+[\.\)]\s*', '', text)
        text = re.sub(r'[^\w\s-]', '', text).strip().lower()
        return re.sub(r'[-\s]+', '_', text)

    @staticmethod
    def _extract_keywords(title: str, content: str) -> str:
        raw_words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', title)
        code_blocks = re.findall(r'```(?:python|py)?(.*?)```', content, re.DOTALL)
        for block in code_blocks:
            identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', block)
            raw_words.extend(identifiers[:40])

        ignore = {'def', 'class', 'import', 'from', 'return', 'self', 'true', 'false', 'none', 'and', 'for', 'in', 'with', 'open'}
        unique = []
        for w in raw_words:
            wl = w.lower()
            if wl not in ignore and wl not in unique:
                unique.append(wl)
        return " ".join(unique[:50])

    def convert_text(self, markdown_text: str) -> List[Dict[str, Any]]:
        lines = markdown_text.splitlines()
        records: List[Dict[str, Any]] = []

        in_code_block = False
        current_h1 = "Python Cheatsheet"
        current_chapter = ""
        buffer: List[str] = []

        def flush_buffer():
            if not buffer:
                return
            body = "\n".join(buffer).strip()
            buffer.clear()

            # Descarta sumários de links (TOC) e blocos vazios
            if len(body) < 50 or (body.count('[') > 15 and body.count('](#') > 8):
                return

            chapter_name = current_chapter or "Geral"
            title = f"{current_h1} — {chapter_name}"
            slug = self._slugify(chapter_name)

            uid = f"python/cheatsheet/{slug}"
            keywords = self._extract_keywords(title, body)

            # Cabeçalho único e elegante no topo do capítulo
            full_content = f"# 📖 {title}\n\n{body}\n"

            records.append({
                "uid": uid,
                "path": uid,
                "category": "python_cheatsheet",
                "title": title,
                "keywords": keywords,
                "content": full_content
            })

        i = 0
        total_lines = len(lines)

        while i < total_lines:
            line = lines[i]
            stripped = line.strip()

            # Preserva blocos de código com comentários
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                buffer.append(line)
                i += 1
                continue

            if in_code_block:
                buffer.append(line)
                i += 1
                continue

            # 1. Detecção de Cabeçalho Setext (ex: 'JSON\n----' ou 'Class\n-----')
            if i + 1 < total_lines and stripped and not stripped.startswith('#') and not stripped.startswith('`'):
                next_line = lines[i + 1].strip()
                if re.match(r'^={3,}\s*$', next_line):
                    flush_buffer()
                    current_h1 = stripped
                    current_chapter = ""
                    i += 2
                    continue
                elif re.match(r'^-{3,}\s*$', next_line):
                    flush_buffer()
                    current_chapter = stripped
                    i += 2
                    continue

            # 2. Detecção de Cabeçalho ATX (# e ##).
            # ATENÇÃO: Os '###' NÃO sofrem flush! Eles viram subseções no mesmo artigo!
            if stripped.startswith('# ') or stripped.startswith('## '):
                m = re.match(r'^(#{1,2})\s+(.+)$', stripped)
                if m:
                    level = len(m.group(1))
                    header_text = re.sub(r'^\d+[\.\)]\s*', '', m.group(2).strip())
                    flush_buffer()
                    if level == 1:
                        current_h1 = header_text or "Python Cheatsheet"
                        current_chapter = ""
                    elif level == 2:
                        current_chapter = header_text
                    i += 1
                    continue

            buffer.append(line)
            i += 1

        flush_buffer()
        return records

    def process_url(self, url: str = DEFAULT_URL) -> Path:
        print(f"[*] Baixando fonte bruta: {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Doxoade-Converter/4.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_text = resp.read().decode('utf-8', errors='replace')

        print(f"[*] Convertendo em capítulos completos ({len(raw_text) / 1024:.1f} KB)...")
        records = self.convert_text(raw_text)

        print(f"[*] Gravando {len(records)} capítulos integrais em: {self.output_file}")
        with open(self.output_file, 'w', encoding='utf-8') as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')

        print(f"✔ Conversão concluída: {self.output_file.name}")
        return self.output_file


def run_converter():
    converter = CheatsheetConverter()
    converter.process_url()


if __name__ == "__main__":
    run_converter()

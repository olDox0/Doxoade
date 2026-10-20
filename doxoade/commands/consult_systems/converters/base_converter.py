# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/base_converter.py
"""
Base Canonical Converter (Thoth Engine).
Contrato e infraestrutura comum para ingestores de documentação técnica.
Conformidade: ProDeNov 2.1 | Zero dependências externas (stdlib pura).
"""
from __future__ import annotations
import os
import sys
import json
import re
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional


class BaseCanonicalConverter(ABC):
    """Classe base abstrata para todos os conversores de fontes canônicas."""

    category: str = "general"
    default_source_url: str = ""
    canonical_filename: str = ""

    def __init__(self, output_dir: Optional[Path] = None):
        self.canonical_dir = output_dir or (Path.home() / ".doxoade" / "consult" / "canonical")
        self.cache_dir = Path.home() / ".doxoade" / "consult" / "cache" / "raw_downloads"
        
        self.canonical_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.output_file = self.canonical_dir / (self.canonical_filename or f"{self.category}.jsonl")

    @staticmethod
    def slugify(text: str) -> str:
        """Converte títulos e nomes em slugs normalizados para o URI path."""
        text = re.sub(r'^\d+[\.\)]\s*', '', text)
        text = re.sub(r'[^\w\s-]', '', text).strip().lower()
        return re.sub(r'[-\s]+', '_', text)

    @staticmethod
    def extract_keywords(title: str, content: str, max_words: int = 40) -> str:
        """Extrai palavras-chave de alta densidade técnica do título e dos blocos de código."""
        raw_words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', title)
        code_blocks = re.findall(r'```(?:python|py)?(.*?)```', content, re.DOTALL)
        for block in code_blocks:
            identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', block)
            raw_words.extend(identifiers[:30])

        stopwords = {
            'def', 'class', 'import', 'from', 'return', 'self', 'true', 'false',
            'none', 'and', 'for', 'in', 'with', 'open', 'try', 'except', 'pass'
        }
        unique: List[str] = []
        for w in raw_words:
            wl = w.lower()
            if wl not in stopwords and wl not in unique:
                unique.append(wl)
        return " ".join(unique[:max_words])

    def download_text(self, url: str) -> str:
        """Executa download defensivo com User-Agent e timeout seguro."""
        print(f"[*] Baixando fonte bruta: {url}")
        req = urllib.request.Request(
            url,
            headers={'User-Agent': f'Doxoade-Ingestor/1.0 ({self.category})'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_bytes = resp.read()
        return raw_bytes.decode('utf-8', errors='replace')

    def validate_record(self, record: Dict[str, Any]) -> bool:
        """Valida a conformidade estrita do registro contra o contrato canônico."""
        required_keys = {"uid", "path", "category", "title", "keywords", "content"}
        if not required_keys.issubset(record.keys()):
            return False
        if not record["uid"] or not record["title"] or not record["content"]:
            return False
        return True

    def save_canonical(self, records: List[Dict[str, Any]]) -> Path:
        """Grava os registros em arquivo .jsonl com validação atômica."""
        valid_records = [r for r in records if self.validate_record(r)]
        print(f"[*] Validando e gravando {len(valid_records)} capítulos canônicos em: {self.output_file}")
        
        temp_file = self.output_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            for rec in valid_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        
        temp_file.replace(self.output_file)
        print(f"✔ [THOTH] Dataset canônico salvo com integridade: {self.output_file.name}")
        return self.output_file

    @abstractmethod
    def convert(self, source_url: Optional[str] = None) -> Path:
        """Método mestre de orquestração a ser implementado por cada conversor."""
        pass

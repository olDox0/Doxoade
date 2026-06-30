# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_compress.py
"""
Hermes Compressor v4.1 - Motor de Compressão Lossless.
CORREÇÃO: Apenas substituição de linhas inteiras (sem substrings).
"""
import os
from pathlib import Path
from .hermes_dict.hermes_builder import HermesDictionaryBuilder


class HermesCompressor:
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.builder = HermesDictionaryBuilder(project_root)
        self.dictionary = self.builder.load_dictionary()
        self.hermes_output_dir = self.root / '.doxoade' / 'hermes' / 'build'
        self.hermes_output_dir.mkdir(parents=True, exist_ok=True)

    def compress_file(self, py_file_path: Path, optimized_content: str = None,
                      use_dynamic_scan: bool = False):  # ← Desabilitado por padrão
        """
        Compressão linha-a-linha (sem substrings para evitar corrupção).
        """
        if not self.dictionary:
            raise RuntimeError("Dicionário Hermes não encontrado.")

        encoder = dict(self.dictionary['encoder'])
        
        if optimized_content is not None:
            source = optimized_content
        else:
            source = py_file_path.read_text(encoding='utf-8', errors='ignore')
        
        original_size = len(source.encode('utf-8'))

        # Compressão LINHA A LINHA (apenas match exato)
        lines = source.split('\n')
        compressed_lines = []

        for line in lines:
            stripped = line.strip()
            # APENAS match exato da linha inteira
            if stripped and stripped in encoder:
                token = encoder[stripped]
                indent = line[:len(line) - len(line.lstrip())]
                compressed_lines.append(indent + self._token_to_chr(token))
            else:
                compressed_lines.append(line)

        compressed_data = '\n'.join(compressed_lines).encode('utf-8')
        final_size = len(compressed_data)

        # Salva no formato FLAT
        py_file_abs = py_file_path.resolve()
        relative_path = py_file_abs.relative_to(self.root)
        module_name = str(relative_path.with_suffix('')).replace(os.sep, '.')
        hermes_file = self.hermes_output_dir / f"{module_name}.hermes"
        
        hermes_file.write_bytes(compressed_data)

        return original_size, final_size, hermes_file, 0

    def _compress_single_line(self, line: str, sorted_patterns: list) -> str:
        """
        Comprime UMA ÚNICA LINHA.
        1. Tenta match exato da linha inteira (stripped).
        2. Se falhar, tenta substituir substrings dentro da linha.
        NUNCA cruza limites de linha.
        """
        stripped = line.strip()

        # 1. Match exato da linha inteira
        if stripped and stripped in dict(sorted_patterns):
            token = dict(sorted_patterns)[stripped]
            indent = line[:len(line) - len(line.lstrip())]
            return indent + self._token_to_chr(token)

        # 2. Substituição de substrings dentro da linha
        compressed = line
        for pattern, token in sorted_patterns:
            if len(pattern) < 4:
                continue
            if pattern in compressed:
                token_chr = self._token_to_chr(token)
                compressed = compressed.replace(pattern, token_chr)

        return compressed

    def _token_to_chr(self, token) -> str:
        """Converte um token para string de caracteres binários."""
        if isinstance(token, int):
            return chr(token)
        elif isinstance(token, (list, tuple)) and len(token) == 2:
            return chr(token[0]) + chr(token[1])
        return ""
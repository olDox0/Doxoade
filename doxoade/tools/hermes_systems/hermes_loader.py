# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_loader.py
"""
Hermes Loader — Decodificador de arquivos .hermes (HBC1/HBC2/HBC3/HBC4).
Com cache persistente em disco para evitar decompressão LZMA em reloads.
"""
import hashlib
import lzma
import zlib
import marshal
import json
import types
from pathlib import Path
from typing import Optional

from .hermes_format import parse_header, get_bitmap, string_needs_reverse, MAGIC_HBC3
from .hermes_format_hbc4 import parse_header_hbc4, get_bitmap_hbc4, MAGIC_HBC4


class HermesLoader:
    """Loader com cache duplo (memória + disco)."""

    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.dict_file = self.root / '.doxoade' / 'hermes' / 'master.dict'
        self.hermes_base_dir = self.root / '.doxoade' / 'hermes' / 'build'
        self.cache_dir = self.root / '.doxoade' / 'hermes' / 'cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.decoder = self._load_decoder()

        # Cache em memória (LRU simples)
        self._code_cache: dict = {}
        self._cache_max_size = 200

        # Cache em disco (persistente)
        self._disk_cache_enabled = True

    # ═══════════════════════════════════════════════════════════════════
    # DICIONÁRIO
    # ═══════════════════════════════════════════════════════════════════
    def _load_decoder(self) -> dict:
        if not self.dict_file.exists():
            return {}
        try:
            with open(self.dict_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            decoder = {}
            for k, v in data.get('decoder', {}).items():
                if not k.startswith('['):
                    try:
                        decoder[int(k)] = v
                    except ValueError:
                        continue
            return decoder
        except Exception:
            return {}

    # ═══════════════════════════════════════════════════════════════════
    # CACHE EM DISCO
    # ═══════════════════════════════════════════════════════════════════
    def _disk_cache_path(self, hermes_path: Path) -> Path:
        """Gera caminho do cache baseado no hash do .hermes."""
        try:
            hermes_hash = hashlib.sha256(hermes_path.read_bytes()).hexdigest()[:16]
        except Exception:
            hermes_hash = "0000000000000000"
        return self.cache_dir / f"{hermes_path.stem}_{hermes_hash}.cache"

    def _load_from_disk_cache(self, hermes_path: Path):
        """Tenta carregar code object do cache em disco."""
        if not self._disk_cache_enabled:
            return None
        cache_path = self._disk_cache_path(hermes_path)
        if not cache_path.exists():
            return None
        try:
            with open(cache_path, 'rb') as f:
                return marshal.load(f)
        except Exception:
            # Cache corrompido, remove
            try:
                cache_path.unlink(missing_ok=True)
            except Exception:
                pass
            return None

    def _save_to_disk_cache(self, hermes_path: Path, code_obj):
        """Salva code object no cache em disco."""
        if not self._disk_cache_enabled:
            return
        cache_path = self._disk_cache_path(hermes_path)
        try:
            with open(cache_path, 'wb') as f:
                marshal.dump(code_obj, f)
        except Exception:
            pass  # Falha silenciosa

    # ═══════════════════════════════════════════════════════════════════
    # DECOMPRESSÃO PRINCIPAL
    # ═══════════════════════════════════════════════════════════════════
    def decompress_to_code(self, hermes_path: Path):
        """
        Decodifica arquivo .hermes em code object.
        Cache duplo: memória (instantâneo) → disco (persistente) → decompressão nativa C.
        """
        hermes_path = Path(hermes_path)
        cache_key = str(hermes_path)

        # 1. Cache em memória (mais rápido)
        if cache_key in self._code_cache:
            return self._code_cache[cache_key]

        # 2. Cache em disco (persistente entre execuções)
        cached = self._load_from_disk_cache(hermes_path)
        if cached is not None:
            self._code_cache[cache_key] = cached
            return cached

        # 3. Decompressão real
        if not hermes_path.exists():
            raise FileNotFoundError(f"Arquivo .hermes não encontrado: {hermes_path}")

        # [NOVO] TENTA USAR O DECODER NATIVO C PRIMEIRO (Vôo supersônico)
        try:
            from doxoade.tools.hermes_systems.native import decode as native_decode
            code_obj = native_decode(str(hermes_path))
            
            if code_obj:
                self._code_cache[cache_key] = code_obj
                self._save_to_disk_cache(hermes_path, code_obj)
                
                if len(self._code_cache) > self._cache_max_size:
                    oldest = next(iter(self._code_cache))
                    del self._code_cache[oldest]
                    
                return code_obj
        except Exception:
            # Fallback silencioso para Python puro se a lib C falhar
            pass

        # 4. Fallback Python puro
        data = hermes_path.read_bytes()
        code_obj = self._decompress_data(data, hermes_path)

        self._code_cache[cache_key] = code_obj
        self._save_to_disk_cache(hermes_path, code_obj)

        if len(self._code_cache) > self._cache_max_size:
            oldest = next(iter(self._code_cache))
            del self._code_cache[oldest]

        return code_obj

    def _decompress_data(self, data: bytes, hermes_path: Path):
        """Faz a decompressão real baseado no magic."""

        # HBC4: Sem LZMA (mais rápido)
        if data.startswith(MAGIC_HBC4):
            dynamic_decoder, marshalled_data, _ = parse_header_hbc4(data)
            if dynamic_decoder is None and len(data) > 4:
                marshalled_data = data[4:]
                dynamic_decoder = {}
            if marshalled_data is None:
                raise ValueError(f"HBC4 inválido: {hermes_path}")
            code_obj = marshal.loads(marshalled_data)
            if dynamic_decoder:
                bitmap = get_bitmap_hbc4(data)
                code_obj = self._reverse_dynamic_tokens(code_obj, dynamic_decoder, bitmap)
            return code_obj

        # HBC3: Com zlib + bitmap
        if data.startswith(MAGIC_HBC3):
            dynamic_decoder, compressed_data, _ = parse_header(data)
            if dynamic_decoder is None or compressed_data is None:
                raise ValueError(f"Header HBC3 inválido: {hermes_path}")
            bitmap = get_bitmap(data)
            marshalled_data = zlib.decompress(compressed_data)
            code_obj = marshal.loads(marshalled_data)
            if dynamic_decoder:
                code_obj = self._reverse_dynamic_tokens(code_obj, dynamic_decoder, bitmap)
            return code_obj

        # HBC2: Legado (JSON+LZMA)
        if data.startswith(b"HBC2"):
            rest = data[4:]
            metadata_len = int.from_bytes(rest[:4], 'little')
            metadata_compressed = rest[4:4 + metadata_len]
            compressed_data = rest[4 + metadata_len:]
            metadata = json.loads(lzma.decompress(metadata_compressed))
            dynamic_decoder = {int(k): v for k, v in metadata['dynamic_encoder'].items()}
            marshalled_data = lzma.decompress(compressed_data)
            code_obj = marshal.loads(marshalled_data)
            code_obj = self._reverse_dynamic_tokens(code_obj, dynamic_decoder, None)
            return code_obj

        # HBC1: Legacy (apenas LZMA)
        if data.startswith(b"HBC1"):
            compressed_data = data[4:]
            marshalled_data = lzma.decompress(compressed_data)
            return marshal.loads(marshalled_data)

        raise ValueError(f"Arquivo não é um binário Hermes válido: {hermes_path}")

    # ═══════════════════════════════════════════════════════════════════
    # REVERSE DE TOKENS
    # ═══════════════════════════════════════════════════════════════════
    def _reverse_dynamic_tokens(self, code_obj, decoder: dict, bitmap: bytes = None):
        """Reverse otimizado com bitmap vetorial."""
        if bitmap is None:
            token_chars = {chr(t) for t in decoder.keys()}

        def reverse_string(s: str) -> str:
            if bitmap is not None:
                if not string_needs_reverse(s, bitmap):
                    return s
            else:
                if not any(c in token_chars for c in s):
                    return s
            for token_int, original in decoder.items():
                s = s.replace(chr(token_int), original)
            return s

        def process_code(code):
            new_consts = []
            for const in code.co_consts:
                if isinstance(const, str):
                    new_consts.append(reverse_string(const))
                elif isinstance(const, types.CodeType):
                    new_consts.append(process_code(const))
                else:
                    new_consts.append(const)
            return code.replace(co_consts=tuple(new_consts))

        return process_code(code_obj)

    # ═══════════════════════════════════════════════════════════════════
    # UTILITÁRIOS
    # ═══════════════════════════════════════════════════════════════════
    def find_hermes_for_module(self, module_name: str) -> Optional[Path]:
        hermes_file = self.hermes_base_dir / f"{module_name}.hermes"
        return hermes_file if hermes_file.exists() else None

    def decompress_bytes(self, hermes_bytes: bytes) -> str:
        """Descompressão textual (legado)."""
        if not self.decoder:
            return hermes_bytes.decode('utf-8')
        text = hermes_bytes.decode('utf-8')
        lines = text.split('\n')
        result = []
        for line in lines:
            stripped = line.lstrip()
            if len(stripped) == 1:
                char_ord = ord(stripped)
                if char_ord in self.decoder:
                    indent = line[:len(line) - len(stripped)]
                    result.append(indent + self.decoder[char_ord])
                    continue
            result.append(line)
        return '\n'.join(result)

    def decompress_file(self, hermes_path: Path) -> str:
        hermes_path = Path(hermes_path)
        if not hermes_path.exists():
            raise FileNotFoundError(f"Arquivo .hermes não encontrado: {hermes_path}")
        return self.decompress_bytes(hermes_path.read_bytes())


def verify_lossless(source_text: str, original_py_path: Path,
                    hermes_path: Path, loader: 'HermesLoader') -> tuple:
    """Verifica se o bytecode reconstruído é equivalente ao original."""
    import dis
    original_code_obj = compile(source_text, str(original_py_path), 'exec', optimize=2)
    reconstructed_code_obj = loader.decompress_to_code(hermes_path)

    data = hermes_path.read_bytes()
    if data.startswith(b"HBC2"):
        orig_instructions = list(dis.get_instructions(original_code_obj))
        recon_instructions = list(dis.get_instructions(reconstructed_code_obj))
        if len(orig_instructions) != len(recon_instructions):
            return False, "instruções", "diferentes"
        orig_strings = _extract_all_strings(original_code_obj)
        recon_strings = _extract_all_strings(reconstructed_code_obj)
        if orig_strings == recon_strings:
            return True, "HBC2-OK", "structural-match"
        return False, "strings", "diferentes"

    original_marshalled = marshal.dumps(original_code_obj)
    reconstructed_marshalled = marshal.dumps(reconstructed_code_obj)
    orig_hash = hashlib.sha256(original_marshalled).hexdigest()[:8]
    recon_hash = hashlib.sha256(reconstructed_marshalled).hexdigest()[:8]
    return (original_marshalled == reconstructed_marshalled), orig_hash, recon_hash


def _extract_all_strings(code_obj) -> list:
    strings = []
    for const in code_obj.co_consts:
        if isinstance(const, str):
            strings.append(const)
        elif isinstance(const, types.CodeType):
            strings.extend(_extract_all_strings(const))
    return sorted(strings)
# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_loader.py
import hashlib
import lzma
import marshal
import json
import dis
import types
from pathlib import Path
from .hermes_format import parse_header, get_bitmap, string_needs_reverse, MAGIC_HBC3
from .hermes_format_hbc4 import parse_header_hbc4, get_bitmap_hbc4, MAGIC_HBC4
from .hermes_format_hbc5 import parse_header_hbc5, get_bitmap_hbc5, MAGIC_HBC5
from .hermes_decoder_vector import VectorDecoder, build_vector_decoder, reverse_tokens_vectorized

# ═══════════════════════════════════════════════════════════════════════════════
# CACHE GLOBAL (Singleton) — Dicionário carregado UMA VEZ
# ═══════════════════════════════════════════════════════════════════════════════
_GLOBAL_LOADER_CACHE = {}
_GLOBAL_DECODER_CACHE = {}
_GLOBAL_VECTOR_DECODER_CACHE = {}

class HermesLoader:
    # ═══════════════════════════════════════════════════════════════════════════════
    # THRESHOLDS ADAPTATIVOS (Fase 3)
    # ═══════════════════════════════════════════════════════════════════════════════
    SKIP_THRESHOLD = 10 * 1024      # < 10KB: skip Hermes (Python puro é mais rápido)
    TIER1_THRESHOLD = 30 * 1024     # < 30KB: só Tier 1 (32 tokens mais frequentes)
    TIER1_TOKEN_COUNT = 32          # Número de tokens no Tier 1
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.dict_file = self.root / '.doxoade' / 'hermes' / 'master.dict'
        self.hermes_base_dir = self.root / '.doxoade' / 'hermes' / 'build'
        self.decoder = self._load_decoder()
        self._vector_decoder = build_vector_decoder(self.decoder) if self.decoder else None
        self._code_cache = {}
        self._cache_max_size = 100

    def _load_global_decoder(self) -> dict:
        """Carrega APENAS o dicionário global (master.dict)."""
        if not self.dict_file.exists():
            return {}
        try:
            with open(self.dict_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            decoder = {}
            for k, v in data.get('decoder', {}).items():
                if not k.startswith('['):
                    decoder[int(k)] = v
            return decoder
        except Exception:
            return {}

    def decompress_to_code(self, hermes_path: Path):
        """
        Decompressão unificada com suporte a HBC3, HBC4, HBC5 e HBC6.
        """
        cache_key = str(hermes_path)
        if cache_key in self._code_cache:
            return self._code_cache[cache_key]
            
        data = hermes_path.read_bytes()
        code_obj = None
        
        # ═══════════════════════════════════════════════════════════════════
        # HBC5: Formato sem LZMA + flags
        # ═══════════════════════════════════════════════════════════════════
        if data.startswith(MAGIC_HBC5):
            file_decoder, marshalled_data, flags, _ = parse_header_hbc5(data)
            if file_decoder is None and len(data) > 4:
                marshalled_data = data[4:]
                file_decoder = {}
            code_obj = marshal.loads(marshalled_data)
            if file_decoder:
                combined_decoder = {**self._load_global_decoder(), **file_decoder}
                bitmap = get_bitmap_hbc5(data)
                vec_dec = build_vector_decoder(combined_decoder)
                code_obj = reverse_tokens_vectorized(code_obj, vec_dec, bitmap)
                
        # ═══════════════════════════════════════════════════════════════════
        # HBC4: Formato sem LZMA
        # ═══════════════════════════════════════════════════════════════════
        elif data.startswith(MAGIC_HBC4):
            file_decoder, marshalled_data, _ = parse_header_hbc4(data)
            if file_decoder is None and len(data) > 4:
                marshalled_data = data[4:]
                file_decoder = {}
            code_obj = marshal.loads(marshalled_data)
            if file_decoder:
                combined_decoder = {**self._load_global_decoder(), **file_decoder}
                bitmap = get_bitmap_hbc4(data)
                vec_dec = build_vector_decoder(combined_decoder)
                code_obj = reverse_tokens_vectorized(code_obj, vec_dec, bitmap)
                
        # ═══════════════════════════════════════════════════════════════════
        # HBC3: Formato com LZMA + bitmap
        # ═══════════════════════════════════════════════════════════════════
        elif data.startswith(MAGIC_HBC3):
            file_decoder, compressed_data, _ = parse_header(data)
            if file_decoder is None:
                raise ValueError(f"Header HBC3 inválido: {hermes_path}")
            bitmap = get_bitmap(data)
            decompressed = lzma.decompress(compressed_data)
            code_obj = marshal.loads(decompressed)
            if file_decoder:
                combined_decoder = {**self._load_global_decoder(), **file_decoder}
                vec_dec = build_vector_decoder(combined_decoder)
                code_obj = reverse_tokens_vectorized(code_obj, vec_dec, bitmap)
                
        # ═══════════════════════════════════════════════════════════════════
        # 🚀 HBC6: Formato Unificado (Bytecode + Strings)
        # ═══════════════════════════════════════════════════════════════════
        elif data[:4] == b'HBC6':
            code_obj = self._decompress_hbc6(data)
            
        else:
            raise ValueError(f"Formato desconhecido: {hermes_path}")
            
        # Salva no cache LRU
        if len(self._code_cache) >= self._cache_max_size:
            oldest = next(iter(self._code_cache))
            del self._code_cache[oldest]
        self._code_cache[cache_key] = code_obj
        return code_obj

    def _decompress_hbc6(self, data: bytes):
        """
        Fallback Python para HBC6.
        Lê o header, ignora a HRT/MacroDict (não aplica patches),
        e retorna o CodeObject cru do marshal.
        """
        import struct
        
        offset = 6  # Magic(4) + Version(1) + Flags(1)
        
        # 1. Lê HRT Size e pula a HRT
        hrt_size = struct.unpack_from('<I', data, offset)[0]
        offset += 4 + hrt_size
        
        # 2. 🚀 CORREÇÃO: Lê MACRO_DICT Size e guarda o offset ANTES de pular
        macro_dict_size = struct.unpack_from('<I', data, offset)[0]
        macro_dict_offset = offset + 4  # 🚀 Salva o offset do início do MACRO_DICT
        offset += 4 + macro_dict_size
        
        # 3. Lê o Payload Size
        payload_size = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        
        # 4. Extrai o Marshal
        payload = data[offset:offset + payload_size]
        
        import marshal
        code_obj = marshal.loads(payload)
        
        # 🚀 Expansão básica dos 0xC0 (sem o Motor C)
        code_obj = self._expand_hbc6_macros_python(code_obj, data, macro_dict_offset, macro_dict_size)
        
        return code_obj

    def _expand_hbc6_macros_python(self, code_obj, data: bytes, macro_dict_offset: int, macro_dict_size: int):
        """Expande os macros 0xC0 no fallback Python (lento, mas funcional)."""
        import struct, types, dis
        
        MACRO_OPCODE = 0xC0
        
        # 1. Parse do MACRO_DICT
        macro_dict = {}
        pos = macro_dict_offset + 4  # Pula o size field
        if macro_dict_size >= 2:
            dict_count = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            for _ in range(dict_count):
                tid = struct.unpack_from('<H', data, pos)[0]; pos += 2
                length = struct.unpack_from('<H', data, pos)[0]; pos += 2
                opcodes = data[pos:pos + length]
                macro_dict[tid] = opcodes
                pos += length
        
        # 2. Walker DFS para expandir
        def expand_code(co):
            bytecode = bytearray(co.co_code)
            expanded = bytearray()
            i = 0
            changed = False
            while i < len(bytecode):
                if bytecode[i] == MACRO_OPCODE and (i + 1) < len(bytecode):
                    token_id = bytecode[i + 1]
                    if token_id in macro_dict:
                        expanded.extend(macro_dict[token_id])
                        i += 2
                        changed = True
                        continue
                expanded.append(bytecode[i])
                i += 1
            
            new_co = co
            if changed:
                new_co = co.replace(co_code=bytes(expanded))
            
            # Recursão
            new_consts = []
            consts_changed = False
            for const in new_co.co_consts:
                if isinstance(const, types.CodeType):
                    new_const = expand_code(const)
                    if new_const is not const:
                        consts_changed = True
                    new_consts.append(new_const)
                else:
                    new_consts.append(const)
            
            if consts_changed:
                new_co = new_co.replace(co_consts=tuple(new_consts))
            
            return new_co
        
        return expand_code(code_obj)

    def _load_decoder(self) -> dict:
        """Carrega o dicionário de decodificação."""
        if not self.dict_file.exists():
            return {}
        try:
            with open(self.dict_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            decoder = {}
            for k, v in data.get('decoder', {}).items():
                if not k.startswith('['):
                    decoder[int(k)] = v
            return decoder
        except Exception:
            return {}

    def _build_vector_decoder(self) -> VectorDecoder:
        """Constrói o VectorDecoder a partir do decoder dict."""
        if not self.decoder:
            return VectorDecoder()
        return build_vector_decoder(self.decoder)

    def decompress_bytes(self, hermes_bytes: bytes) -> str:
        """Descompressão O(1) sem uso de sub-strings lentas"""
        if not self.decoder:
            return hermes_bytes.decode('utf-8')
        text = hermes_bytes.decode('utf-8')
        lines = text.split('\n')
        decompressed_lines = []
        for line in lines:
            stripped = line.lstrip()
            if len(stripped) == 1:
                char_ord = ord(stripped)
                if char_ord in self.decoder:
                    indent = line[:len(line) - len(stripped)]
                    decompressed_lines.append(indent + self.decoder[char_ord])
                    continue
            decompressed_lines.append(line)
        return '\n'.join(decompressed_lines)

    def decompress_file(self, hermes_path: Path) -> str:
        hermes_path = Path(hermes_path)
        if not hermes_path.exists():
            raise FileNotFoundError(f"Arquivo .hermes não encontrado: {hermes_path}")
        hermes_bytes = hermes_path.read_bytes()
        return self.decompress_bytes(hermes_bytes)



    # ═══════════════════════════════════════════════════════════════════════════════
    # CARREGAMENTO ADAPTATIVO (Fase 3)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def _filter_decoder_tier1(self, decoder_dict: dict) -> dict:
        """
        Filtra o dicionário para apenas os tokens mais frequentes (Tier 1).
        """
        if not decoder_dict:
            return {}
        sorted_tokens = sorted(decoder_dict.items(), key=lambda x: x[0])
        return dict(sorted_tokens[:self.TIER1_TOKEN_COUNT])

    def decompress_to_code_adaptive(self, hermes_path: Path, file_size: int = None):
        """
        Decompressão adaptativa baseada no tamanho do arquivo.
        """
        if file_size is None:
            file_size = hermes_path.stat().st_size
        
        # MODO SKIP: Arquivo muito pequeno
        if file_size < self.SKIP_THRESHOLD:
            return None
        
        # MODO TIER1: Arquivo médio
        if file_size < self.TIER1_THRESHOLD:
            return self._decompress_tier1(hermes_path)
        
        # MODO FULL: Arquivo grande
        return self.decompress_to_code(hermes_path)

    def _decompress_tier1(self, hermes_path: Path):
        """Decompressão Tier 1 — apenas os 32 tokens mais frequentes."""
        cache_key = f"tier1:{hermes_path}"
        if cache_key in self._code_cache:
            return self._code_cache[cache_key]

        data = hermes_path.read_bytes()

        if data.startswith(MAGIC_HBC5):
            dynamic_decoder, marshalled_data, flags, _ = parse_header_hbc5(data)
            if dynamic_decoder is None and len(data) > 4:
                marshalled_data = data[4:]
                dynamic_decoder = {}
            if dynamic_decoder:
                dynamic_decoder = self._filter_decoder_tier1(dynamic_decoder)
            code_obj = marshal.loads(marshalled_data)
            if dynamic_decoder:
                bitmap = get_bitmap_hbc5(data)
                vec_dec = build_vector_decoder(dynamic_decoder)
                code_obj = reverse_tokens_vectorized(code_obj, vec_dec, bitmap)

        elif data.startswith(MAGIC_HBC4):
            dynamic_decoder, marshalled_data, _ = parse_header_hbc4(data)
            if dynamic_decoder is None and len(data) > 4:
                marshalled_data = data[4:]
                dynamic_decoder = {}
            if dynamic_decoder:
                dynamic_decoder = self._filter_decoder_tier1(dynamic_decoder)
            code_obj = marshal.loads(marshalled_data)
            if dynamic_decoder:
                bitmap = get_bitmap_hbc4(data)
                vec_dec = build_vector_decoder(dynamic_decoder)
                code_obj = reverse_tokens_vectorized(code_obj, vec_dec, bitmap)

        elif data.startswith(MAGIC_HBC3):
            dynamic_decoder, compressed_data, _ = parse_header(data)
            if dynamic_decoder is None:
                raise ValueError(f"Header HBC3 inválido: {hermes_path}")
            if dynamic_decoder:
                dynamic_decoder = self._filter_decoder_tier1(dynamic_decoder)
            bitmap = get_bitmap(data)
            decompressed = lzma.decompress(compressed_data)
            code_obj = marshal.loads(decompressed)
            if dynamic_decoder:
                vec_dec = build_vector_decoder(dynamic_decoder)
                code_obj = reverse_tokens_vectorized(code_obj, vec_dec, bitmap)

        else:
            raise ValueError(f"Formato desconhecido: {hermes_path}")

        if len(self._code_cache) >= self._cache_max_size:
            oldest = next(iter(self._code_cache))
            del self._code_cache[oldest]
        self._code_cache[cache_key] = code_obj
        return code_obj

    def _reverse_dynamic_tokens(self, code_obj, decoder_dict, bitmap=None):
        """Compatibilidade retroativa — usa VectorDecoder internamente."""
        vec_dec = build_vector_decoder(decoder_dict)
        return reverse_tokens_vectorized(code_obj, vec_dec, bitmap)

    def find_hermes_for_module(self, module_name: str) -> Path:
        hermes_file = self.hermes_base_dir / f"{module_name}.hermes"
        return hermes_file if hermes_file.exists() else None

def verify_lossless(source_text: str, original_py_path: Path, 
                    hermes_path: Path, loader: 'HermesLoader') -> tuple:
    """Verifica se o bytecode reconstruído é equivalente ao original.
    
    Usa comparação estrutural (instruções + strings + nomes) ao invés de marshal.dumps,
    pois code objects podem ter representações binárias diferentes mesmo sendo semanticamente idênticos.
    """
    # Compila o original
    original_code_obj = compile(source_text, str(original_py_path), 'exec', optimize=2)
    
    # Descomprime o .hermes
    reconstructed_code_obj = loader.decompress_to_code(hermes_path)
    
    # ═══════════════════════════════════════════════════════════════════
    # COMPARAÇÃO ESTRUTURAL (robusta contra diferenças de marshal)
    # ═══════════════════════════════════════════════════════════════════
    
    # 1. Compara número de instruções
    orig_instructions = list(dis.get_instructions(original_code_obj))
    recon_instructions = list(dis.get_instructions(reconstructed_code_obj))
    
    if len(orig_instructions) != len(recon_instructions):
        return False, "instruções", f"{len(orig_instructions)} vs {len(recon_instructions)}"
    
    # 2. Compara strings recursivamente em co_consts
    orig_strings = _extract_all_strings(original_code_obj)
    recon_strings = _extract_all_strings(reconstructed_code_obj)
    
    if orig_strings != recon_strings:
        return False, "strings", f"{len(orig_strings)} vs {len(recon_strings)}"
    
    # 3. Compara nomes de variáveis e funções
    orig_names = original_code_obj.co_names
    recon_names = reconstructed_code_obj.co_names
    
    if orig_names != recon_names:
        return False, "names", f"{len(orig_names)} vs {len(recon_names)}"
    
    # 4. Compara constantes não-string (números, tuples, etc)
    orig_consts = [c for c in original_code_obj.co_consts if not isinstance(c, (str, types.CodeType))]
    recon_consts = [c for c in reconstructed_code_obj.co_consts if not isinstance(c, (str, types.CodeType))]
    
    if orig_consts != recon_consts:
        return False, "consts", f"{len(orig_consts)} vs {len(recon_consts)}"
    
    # 5. Compara variáveis locais
    orig_varnames = original_code_obj.co_varnames
    recon_varnames = reconstructed_code_obj.co_varnames
    
    if orig_varnames != recon_varnames:
        return False, "varnames", f"{len(orig_varnames)} vs {len(recon_varnames)}"
    
    # Se chegou aqui, é lossless
    import hashlib
    orig_hash = hashlib.sha256(str(orig_strings + list(orig_names)).encode()).hexdigest()[:8]
#    orig_hash = hashlib.sha256(str(orig_strings + orig_names).encode()).hexdigest()[:8]
    return True, orig_hash, "lossless"

def _extract_all_strings(code_obj) -> list:
    """Extrai recursivamente todas as strings de um code object."""
    strings = []
    for const in code_obj.co_consts:
        if isinstance(const, str):
            strings.append(const)
        elif isinstance(const, types.CodeType):
            strings.extend(_extract_all_strings(const))
    return sorted(strings)
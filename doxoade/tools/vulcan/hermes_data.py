# doxoade/tools/vulcan/hermes_data.py
import re
import struct
from pathlib import Path
from doxoade.tools.hermes_systems.hermes_dynamic_scanner import build_dynamic_dictionary

def compress_to_hbd1(source_file: str, dest_file: str) -> dict:
    source_path = Path(source_file)
    text = source_path.read_text(encoding='utf-8')
    orig_bytes = text.encode('utf-8')
    orig_sz = len(orig_bytes)

    dynamic_encoder = build_dynamic_dictionary(source_path, existing_encoder={}, max_new_tokens=254)
    sorted_patterns = sorted(dynamic_encoder.keys(), key=len, reverse=True)
    
    payload = orig_bytes
    
    # 🚀 PATCH: Pipeline de Substituição Single-Pass (Zero-Alloc de Memória)
    valid_patterns = []
    for pattern in sorted_patterns:
        pat_bytes = pattern.encode('utf-8')
        if len(pat_bytes) <= 2: continue
        valid_patterns.append(pat_bytes)
        if len(valid_patterns) >= 254: break

    # Mapeamento de Tokens e Construção do Header de Tokens
    replace_map = {}
    tokens_data = bytearray()
    for i, pat_bytes in enumerate(valid_patterns):
        replace_map[pat_bytes] = bytes([0xFF, i])
        tokens_data += struct.pack('<H', len(pat_bytes))
        tokens_data += pat_bytes

    # Substituição em UMA ÚNICA PASSADA (Nível C do Python via re.sub)
    if valid_patterns:
        # Escapa os padrões e cria uma regex do tipo: b'pat1|pat2|pat3'
        # Como já estão ordenados por tamanho (maior primeiro), a regex respeita a precedência
        combined_re = re.compile(b'|'.join(re.escape(p) for p in valid_patterns))
        payload = combined_re.sub(lambda m: replace_map[m.group(0)], payload)

    token_count = len(valid_patterns)

    # NOVO CABEÇALHO: HBD1(4) + Ver(1) + Count(2) + ORIG_SZ(4) + TokensData(N) + PayloadSize(4) + Payload
    header = (
        b"HBD1" +
        struct.pack('<B', 1) +
        struct.pack('<H', token_count) +
        struct.pack('<I', orig_sz) +
        tokens_data +
        struct.pack('<I', len(payload))
    )
    final_data = header + payload
    Path(dest_file).write_bytes(final_data)

    return {
        'original_bytes': orig_sz,
        'compressed_bytes': len(final_data),
        'tokens': token_count,
        'ratio': 1 - (len(final_data) / orig_sz) if orig_sz > 0 else 0
    }
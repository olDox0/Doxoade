# doxoade/tools/vulcan/hermes_data.py
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
    tokens_data = bytearray()
    token_count = 0
    
    for pattern in sorted_patterns:
        if token_count >= 254: break
        pat_bytes = pattern.encode('utf-8')
        if len(pat_bytes) <= 2: continue
            
        tok_bytes = bytes([0xFF, token_count])
        payload = payload.replace(pat_bytes, tok_bytes)
        
        tokens_data += struct.pack('<H', len(pat_bytes))
        tokens_data += pat_bytes
        token_count += 1

    # NOVO CABEÇALHO: HBD1(4) + Ver(1) + Count(2) + ORIG_SZ(4) + TokensData(N) + PayloadSize(4) + Payload
    header = (
        b"HBD1" +
        struct.pack('<B', 1) +
        struct.pack('<H', token_count) +
        struct.pack('<I', orig_sz) +         # <--- SALVANDO O TAMANHO DESCOMPACTADO!
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
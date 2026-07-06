# doxoade/tools/hermes_systems/native/hermes_gd_builder.py
import json
import struct
from pathlib import Path

def build_global_bin(project_root: str) -> bool:
    """Converte o master.dict (JSON) em master.bin (HGD1 mmap-ready)."""
    root = Path(project_root)
    json_path = root / '.doxoade' / 'hermes' / 'master.dict'
    bin_path = root / '.doxoade' / 'hermes' / 'master.bin'
    
    if not json_path.exists():
        print("  ✘ [GD-BUILDER] master.dict não encontrado. Rode o Hermes Scanner primeiro.")
        return False
        
    data = json.loads(json_path.read_text(encoding='utf-8'))
    decoder = data.get('decoder', {})
    
    # Filtra e ordena tokens (ex: {"57344": "doxoade.tools", ...})
    tokens = []
    for k, v in decoder.items():
        if not k.startswith('['):
            try:
                tokens.append((int(k), v.encode('utf-8')))
            except ValueError:
                continue
                
    tokens.sort(key=lambda x: x[0])
    if not tokens:
        print("  ✘ [GD-BUILDER] Dicionário vazio.")
        return False
        
    base_token = tokens[0][0]
    count = len(tokens)
    
    # Layout HGD1: Header (32B) + Entries (N * 8B) + Payload
    header_size = 32 + (count * 8)
    current_offset = header_size
    entries_data = bytearray()
    payload_data = bytearray()
    
    for token_int, pattern_bytes in tokens:
        entries_data += struct.pack('<II', current_offset, len(pattern_bytes))
        payload_data += pattern_bytes
        current_offset += len(pattern_bytes)
        
    # Monta o Header (32 bytes)
    header = bytearray(32)
    header[0:4] = b"HGD1"
    struct.pack_into('<I', header, 4, 1)       # Version
    struct.pack_into('<H', header, 8, count)   # Token Count
    struct.pack_into('<H', header, 10, base_token) # Base Token
    
    final_bin = header + entries_data + payload_data
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    bin_path.write_bytes(final_bin)
    
    size_kb = bin_path.stat().st_size / 1024
    print(f"  ✔ [GD-BUILDER] master.bin forjado: {size_kb:.1f} KB ({count} tokens)")
    return True

if __name__ == '__main__':
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    build_global_bin(root)
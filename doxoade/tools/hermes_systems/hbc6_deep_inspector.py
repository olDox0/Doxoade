# doxoade/tools/hermes_systems/hbc6_deep_inspector.py
"""
HBC6 Deep Bytecode Inspector
=============================
Analisa recursivamente TODOS os code objects (incluindo funções e classes).
"""
import struct
import marshal
import dis
import types
from pathlib import Path

def analyze_code_object_recursive(co, depth=0, path="module"):
    """Analisa um code object e todos os seus filhos recursivamente."""
    indent = "  " * depth
    bytecode = co.co_code
    
    print(f"{indent}📦 {path} ({co.co_name})")
    print(f"{indent}   Bytecode: {len(bytecode)} bytes")
    
    # Procura por 0xC0 no bytecode
    c0_count = 0
    nop_after_c0 = 0
    i = 0
    c0_locations = []
    
    while i < len(bytecode):
        if bytecode[i] == 0xC0 and (i + 1) < len(bytecode):
            c0_count += 1
            token_id = bytecode[i + 1]
            c0_locations.append((i, token_id))
            
            # Conta NOPs após o 0xC0
            j = i + 2
            nops = 0
            while j + 1 < len(bytecode) and bytecode[j] == 0x09 and bytecode[j+1] == 0x00:
                nops += 1
                j += 2
            nop_after_c0 += nops
            i = j
        else:
            i += 1
    
    if c0_count > 0:
        print(f"{indent}   🚨 Macros 0xC0 encontradas: {c0_count}")
        print(f"{indent}   🚨 NOPs de preenchimento: {nop_after_c0} ({nop_after_c0*2} bytes)")
        print(f"{indent}   📍 Localizações (primeiras 5):")
        for offset, tid in c0_locations[:5]:
            print(f"{indent}      Offset {offset}: 0xC0 0x{tid:02X}")
    
    # Valida o bytecode
    try:
        list(dis.get_instructions(co))
        print(f"{indent}   ✅ Bytecode VÁLIDO")
    except Exception as e:
        print(f"{indent}   ❌ Bytecode INVÁLIDO: {e}")
        return False
    
    # Recursa para code objects aninhados
    all_valid = True
    for idx, const in enumerate(co.co_consts):
        if isinstance(const, types.CodeType):
            child_path = f"{path}.{const.co_name}"
            if not analyze_code_object_recursive(const, depth + 1, child_path):
                all_valid = False
    
    return all_valid

def inspect_hbc6_deep(hbc6_path: Path):
    """Inspeciona profundamente um arquivo HBC6."""
    data = hbc6_path.read_bytes()
    
    if data[:4] != b'HBC6':
        print(f"❌ {hbc6_path.name}: Não é HBC6")
        return
    
    flags = data[5]
    offset = 6
    
    hrt_size = struct.unpack_from('<I', data, offset)[0]
    offset += 4 + hrt_size
    
    macro_dict_size = struct.unpack_from('<I', data, offset)[0]
    offset += 4 + macro_dict_size
    
    payload_size = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    
    payload = data[offset:offset + payload_size]
    code_obj = marshal.loads(payload)
    
    print(f"\n{'='*70}")
    print(f"🔬 ANÁLISE PROFUNDA: {hbc6_path.name}")
    print(f"{'='*70}")
    print(f"  Flags: 0x{flags:02X}")
    print(f"  Payload Size: {payload_size} bytes")
    print(f"\n🔍 ANÁLISE RECURSIVA DE TODOS OS CODE OBJECTS:")
    
    is_valid = analyze_code_object_recursive(code_obj, 0, "module")
    
    if is_valid:
        print(f"\n✅ TODOS os code objects têm bytecode válido")
    else:
        print(f"\n❌ ALGUNS code objects têm bytecode inválido")
    
    return is_valid

def main():
    project_root = Path.cwd()
    build_dir = project_root / '.doxoade' / 'hermes' / 'build'
    
    # Analisa os 5 primeiros arquivos
    hbc6_files = list(build_dir.glob('*.hbc6'))[:5]
    
    for hbc6 in hbc6_files:
        inspect_hbc6_deep(hbc6)
        print()

if __name__ == '__main__':
    main()
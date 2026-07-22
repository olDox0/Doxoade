#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hbc6_bytecode_inspector.py
"""
HBC6 Bytecode Inspector
=======================
Mostra o bytecode ANTES e DEPOIS da expansão de macros.
Prova que os NOPs de preenchimento são o problema.
"""
import struct
import marshal
import dis
import types
from pathlib import Path

def inspect_hbc6(hbc6_path: Path):
    """Inspeciona o bytecode de um arquivo HBC6."""
    data = hbc6_path.read_bytes()
    
    if data[:4] != b'HBC6':
        print(f"❌ {hbc6_path.name}: Não é HBC6")
        return
    
    flags = data[5]
    offset = 6
    
    hrt_size = struct.unpack_from('<I', data, offset)[0]
    offset += 4 + hrt_size
    
    macro_dict_size = struct.unpack_from('<I', data, offset)[0]
    macro_dict_offset = offset + 4
    offset += 4 + macro_dict_size
    
    payload_size = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    
    payload = data[offset:offset + payload_size]
    code_obj = marshal.loads(payload)
    
    print(f"\n{'='*70}")
    print(f"🔬 {hbc6_path.name}")
    print(f"{'='*70}")
    print(f"  Flags: 0x{flags:02X}")
    print(f"  HRT Size: {hrt_size} bytes")
    print(f"  Macro Dict Size: {macro_dict_size} bytes")
    print(f"  Payload Size: {payload_size} bytes")
    
    # Mostra o bytecode do primeiro code object (módulo principal)
    bytecode = code_obj.co_code
    print(f"\n  📋 BYTECODE DO MÓDULO PRINCIPAL ({len(bytecode)} bytes):")
    
    # Procura por 0xC0 no bytecode
    c0_count = 0
    nop_after_c0 = 0
    i = 0
    while i < len(bytecode):
        if bytecode[i] == 0xC0 and (i + 1) < len(bytecode):
            c0_count += 1
            token_id = bytecode[i + 1]
            # Conta NOPs após o 0xC0
            j = i + 2
            nops = 0
            while j + 1 < len(bytecode) and bytecode[j] == 0x09 and bytecode[j+1] == 0x00:
                nops += 1
                j += 2
            nop_after_c0 += nops
            if c0_count <= 5:  # Mostra os 5 primeiros
                print(f"    Offset {i:4d}: 0xC0 0x{token_id:02X} + {nops} NOPs ({nops*2} bytes)")
            i = j
        else:
            i += 1
    
    print(f"\n  📊 ESTATÍSTICAS:")
    print(f"    Macros 0xC0 encontradas: {c0_count}")
    print(f"    NOPs de preenchimento: {nop_after_c0} ({nop_after_c0*2} bytes)")
    print(f"    Bytecode ANTES da expansão: {len(bytecode)} bytes")
    print(f"    Bytecode DEPOIS (estimado): {len(bytecode) - nop_after_c0*2 - c0_count*2} bytes")
    
    if c0_count > 0 and nop_after_c0 == 0:
        print(f"\n  ✅ Sem NOPs de preenchimento - expansão segura")
    elif c0_count > 0 and nop_after_c0 > 0:
        print(f"\n  ⚠️  {nop_after_c0} NOPs de preenchimento detectados!")
        print(f"     Se o loader fizer i+=2, esses NOPs ficam no bytecode → SegFault")
        print(f"     O loader DEVE pular os NOPs após cada 0xC0")
    
    # Tenta expandir e validar
    print(f"\n  🧪 TESTE DE EXPANSÃO:")
    try:
        expanded = _expand_with_nop_skip(code_obj, data, macro_dict_offset, macro_dict_size)
        expanded_bytecode = expanded.co_code
        print(f"    Bytecode expandido: {len(expanded_bytecode)} bytes")
        
        # Valida com dis
        list(dis.get_instructions(expanded))
        print(f"    ✅ Bytecode expandido é VÁLIDO (dis.get_instructions passou)")
    except Exception as e:
        print(f"    ❌ Falha na expansão: {e}")

def _expand_with_nop_skip(code_obj, data, macro_dict_offset, macro_dict_size):
    """Expande macros pulando NOPs (versão de teste)."""
    macro_dict = {}
    pos = macro_dict_offset
    end_pos = macro_dict_offset + macro_dict_size
    if macro_dict_size >= 2:
        dict_count = data[pos]; pos += 1  # uint8!
        for _ in range(dict_count):
            if pos + 4 > end_pos: break
            tid = data[pos]; pos += 1       # uint8!
            length = data[pos]; pos += 1    # uint8!
            if pos + length > end_pos: break
            macro_dict[tid] = data[pos:pos + length]
            pos += length
    
    def expand_code(co):
        bytecode = bytearray(co.co_code)
        expanded = bytearray()
        i = 0
        changed = False
        while i < len(bytecode):
            if bytecode[i] == 0xC0 and (i + 1) < len(bytecode):
                token_id = bytecode[i + 1]
                if token_id in macro_dict:
                    expanded.extend(macro_dict[token_id])
                    i += 2
                    while i + 1 < len(bytecode) and bytecode[i] == 0x09 and bytecode[i+1] == 0x00:
                        i += 2
                    changed = True
                    continue
            expanded.append(bytecode[i])
            i += 1
        new_co = co
        if changed:
            new_co = co.replace(co_code=bytes(expanded))
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

def main():
    project_root = Path.cwd()
    build_dir = project_root / '.doxoade' / 'hermes' / 'build'
    
    # Inspeciona o cli.py (o que está crashando)
    cli_files = list(build_dir.glob('cli_*.hbc6'))
    if cli_files:
        inspect_hbc6(cli_files[0])
    
    # Inspeciona mais 2 arquivos
    for hbc6 in list(build_dir.glob('*.hbc6'))[:3]:
        if 'cli_' not in hbc6.name:
            inspect_hbc6(hbc6)

if __name__ == '__main__':
    main()
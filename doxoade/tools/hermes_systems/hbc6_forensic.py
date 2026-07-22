#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hbc6_forensic.py
"""
HBC6 Forensic Analyzer
======================
Investiga access violations no HBC6 analisando byte a byte.
"""
import struct
import marshal
import dis
import types
from pathlib import Path
from typing import Optional

class HBC6Forensic:
    """Analisador forense de arquivos HBC6."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.build_dir = self.root / '.doxoade' / 'hermes' / 'build'
    
    def analyze_file(self, hbc6_path: Path, py_path: Optional[Path] = None) -> dict:
        """
        Análise completa de um arquivo HBC6.
        Retorna dict com diagnóstico detalhado.
        """
        report = {
            'file': str(hbc6_path),
            'exists': hbc6_path.exists(),
            'valid_magic': False,
            'flags': 0,
            'flag_names': [],
            'hrt_size': 0,
            'macro_dict_size': 0,
            'payload_size': 0,
            'payload_valid': False,
            'code_obj_loaded': False,
            'macros_expanded': False,
            'bytecode_valid': False,
            'comparison': None,
            'errors': []
        }
        
        if not hbc6_path.exists():
            report['errors'].append(f"Arquivo não encontrado: {hbc6_path}")
            return report
        
        try:
            data = hbc6_path.read_bytes()
        except Exception as e:
            report['errors'].append(f"Erro ao ler arquivo: {e}")
            return report
        
        # 1. Valida Magic
        if len(data) < 6:
            report['errors'].append("Arquivo muito pequeno (< 6 bytes)")
            return report
        
        if data[:4] != b'HBC6':
            report['errors'].append(f"Magic inválido: {data[:4]}")
            return report
        
        report['valid_magic'] = True
        
        # 2. Lê flags
        flags = data[5]
        report['flags'] = flags
        
        # Decodifica flags
        flag_names = []
        if flags & 0x01:
            flag_names.append("TOKENIZED_CONSTS")
        if flags & 0x02:
            flag_names.append("BYTECODE_PATCHED")
        if flags & 0x10:
            flag_names.append("CUSTOM_PAYLOAD")  # 🚨 PERIGO
        if flags & 0x20:
            flag_names.append("LZ4_PAYLOAD")
        
        report['flag_names'] = flag_names
        
        # 3. Parse do header
        offset = 6
        
        # HRT Size
        hrt_size = struct.unpack_from('<I', data, offset)[0]
        report['hrt_size'] = hrt_size
        offset += 4 + hrt_size
        
        # Macro Dict Size
        macro_dict_size = struct.unpack_from('<I', data, offset)[0]
        report['macro_dict_size'] = macro_dict_size
        macro_dict_offset = offset + 4
        offset += 4 + macro_dict_size
        
        # Payload Size
        payload_size = struct.unpack_from('<I', data, offset)[0]
        report['payload_size'] = payload_size
        offset += 4
        
        # 4. Extrai payload
        payload = data[offset:offset + payload_size]
        
        # 5. 🚨 VERIFICAÇÃO CRÍTICA: Flag CUSTOM_PAYLOAD
        if flags & 0x10:
            report['errors'].append("🚨 FLAG_CUSTOM_PAYLOAD (0x10) está ativa! Isso causa SegFault.")
            report['errors'].append("   O compressor está usando hermes_payload.py (em quarentena).")
            report['errors'].append("   SOLUÇÃO: Recompile sem a flag 0x10.")
            return report
        
        # 6. Tenta deserializar o payload
        try:
            code_obj = marshal.loads(payload)
            report['payload_valid'] = True
            report['code_obj_loaded'] = True
        except Exception as e:
            report['errors'].append(f"Falha ao deserializar payload: {e}")
            return report
        
        # 7. Expande macros (se houver)
        if macro_dict_size > 0:
            try:
                expanded_code = self._expand_macros(code_obj, data, macro_dict_offset, macro_dict_size)
                report['macros_expanded'] = True
                code_obj = expanded_code
            except Exception as e:
                report['errors'].append(f"Falha ao expandir macros: {e}")
                return report
        
        # 8. Valida bytecode
        try:
            # Tenta disassemblar
            list(dis.get_instructions(code_obj))
            report['bytecode_valid'] = True
        except Exception as e:
            report['errors'].append(f"Bytecode inválido: {e}")
            report['errors'].append("   Isso causa o access violation no exec().")
            return report
        
        # 9. Compara com original (se disponível)
        if py_path and py_path.exists():
            try:
                comparison = self._compare_with_original(py_path, code_obj)
                report['comparison'] = comparison
            except Exception as e:
                report['errors'].append(f"Erro na comparação: {e}")
        
        return report
    
    def _expand_macros(self, code_obj, data: bytes, macro_dict_offset: int, macro_dict_size: int):
        """Expande macros 0xC0 usando a HRT."""
        MACRO_OPCODE = 0xC0
        
        # Parse do MACRO_DICT
        macro_dict = {}
        pos = macro_dict_offset
        end_pos = macro_dict_offset + macro_dict_size
        
        if macro_dict_size >= 2:
            dict_count = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            for _ in range(dict_count):
                if pos + 4 > end_pos:
                    break
                tid = struct.unpack_from('<H', data, pos)[0]; pos += 2
                length = struct.unpack_from('<H', data, pos)[0]; pos += 2
                if pos + length > end_pos:
                    break
                opcodes = data[pos:pos + length]
                macro_dict[tid] = opcodes
                pos += length
        
        if not macro_dict:
            return code_obj
        
        # Parse da HRT
        hrt_map = {}
        hrt_offset = 6 + 4  # Magic(4) + Ver(1) + Flags(1) + HRT_Size(4)
        hrt_size = struct.unpack_from('<I', data, 6)[0]
        pos = hrt_offset
        end_hrt = hrt_offset + hrt_size
        
        while pos + 12 <= end_hrt:
            co_index = struct.unpack_from('<I', data, pos)[0]; pos += 4
            offset_val = struct.unpack_from('<I', data, pos)[0]; pos += 4
            token_id = struct.unpack_from('<H', data, pos)[0]; pos += 2
            orig_len = struct.unpack_from('<H', data, pos)[0]; pos += 2
            hrt_map[(co_index, offset_val)] = orig_len
        
        # Mapeia id -> co_index
        dfs_index_map = {}
        def assign_indices(co, idx=0):
            dfs_index_map[id(co)] = idx
            idx += 1
            for c in co.co_consts:
                if isinstance(c, types.CodeType):
                    idx = assign_indices(c, idx)
            return idx
        assign_indices(code_obj)
        
        # Expande
        def expand_code(co):
            my_index = dfs_index_map.get(id(co), -1)
            bytecode = bytearray(co.co_code)
            expanded = bytearray()
            i = 0
            changed = False
            
            while i < len(bytecode):
                if bytecode[i] == MACRO_OPCODE and (i + 1) < len(bytecode):
                    token_id = bytecode[i + 1]
                    if token_id in macro_dict:
                        expanded.extend(macro_dict[token_id])
                        orig_len = hrt_map.get((my_index, i), 2)
                        i += orig_len
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
    
    def _compare_with_original(self, py_path: Path, hbc6_code: types.CodeType) -> dict:
        """Compara o bytecode HBC6 com o original."""
        source = py_path.read_text(encoding='utf-8')
        orig_code = compile(source, str(py_path), 'exec', optimize=2)
        
        comparison = {
            'instructions_match': False,
            'strings_match': False,
            'names_match': False,
            'details': []
        }
        
        # Compara instruções
        orig_instr = list(dis.get_instructions(orig_code))
        hbc6_instr = list(dis.get_instructions(hbc6_code))
        
        if len(orig_instr) == len(hbc6_instr):
            comparison['instructions_match'] = True
        else:
            comparison['details'].append(
                f"Instruções: {len(orig_instr)} vs {len(hbc6_instr)}"
            )
        
        # Compara strings
        orig_strings = sorted(self._extract_strings(orig_code))
        hbc6_strings = sorted(self._extract_strings(hbc6_code))
        
        if orig_strings == hbc6_strings:
            comparison['strings_match'] = True
        else:
            comparison['details'].append(
                f"Strings: {len(orig_strings)} vs {len(hbc6_strings)}"
            )
        
        # Compara nomes
        if orig_code.co_names == hbc6_code.co_names:
            comparison['names_match'] = True
        else:
            comparison['details'].append(
                f"Names: {len(orig_code.co_names)} vs {len(hbc6_code.co_names)}"
            )
        
        return comparison
    
    def _extract_strings(self, code_obj) -> list:
        """Extrai recursivamente todas as strings."""
        strings = []
        for const in code_obj.co_consts:
            if isinstance(const, str):
                strings.append(const)
            elif isinstance(const, types.CodeType):
                strings.extend(self._extract_strings(const))
        return strings
    
    def print_report(self, report: dict):
        """Imprime relatório formatado."""
        print("\n" + "=" * 80)
        print("🔬 HBC6 FORENSIC REPORT")
        print("=" * 80)
        print(f"Arquivo: {report['file']}")
        print(f"Existe: {report['exists']}")
        
        if not report['exists']:
            print("\n❌ Arquivo não encontrado")
            return
        
        print(f"\n📋 HEADER:")
        print(f"  Magic válido: {report['valid_magic']}")
        print(f"  Flags: 0x{report['flags']:02X} ({', '.join(report['flag_names'])})")
        print(f"  HRT Size: {report['hrt_size']} bytes")
        print(f"  Macro Dict Size: {report['macro_dict_size']} bytes")
        print(f"  Payload Size: {report['payload_size']} bytes")
        
        print(f"\n🔍 VALIDAÇÃO:")
        print(f"  Payload válido: {report['payload_valid']}")
        print(f"  Code object carregado: {report['code_obj_loaded']}")
        print(f"  Macros expandidos: {report['macros_expanded']}")
        print(f"  Bytecode válido: {report['bytecode_valid']}")
        
        if report['comparison']:
            print(f"\n📊 COMPARAÇÃO COM ORIGINAL:")
            comp = report['comparison']
            print(f"  Instruções: {'✅' if comp['instructions_match'] else '❌'}")
            print(f"  Strings: {'✅' if comp['strings_match'] else '❌'}")
            print(f"  Names: {'✅' if comp['names_match'] else '❌'}")
            if comp['details']:
                for detail in comp['details']:
                    print(f"    - {detail}")
        
        if report['errors']:
            print(f"\n🚨 ERROS:")
            for error in report['errors']:
                print(f"  {error}")
        
        print("=" * 80)


def main():
    """CLI para análise forense."""
    import sys
    
    project_root = Path.cwd()
    forensic = HBC6Forensic(str(project_root))
    
    # Analisa cli.py (o arquivo que está crashando)
    cli_hbc6 = forensic.build_dir / 'cli_*.hbc6'
    hbc6_files = list(forensic.build_dir.glob('cli_*.hbc6'))
    
    if not hbc6_files:
        print("❌ Nenhum arquivo cli_*.hbc6 encontrado")
        sys.exit(1)
    
    hbc6_file = hbc6_files[0]
    py_file = project_root / 'doxoade' / 'cli.py'
    
    print(f"🔬 Analisando: {hbc6_file.name}")
    report = forensic.analyze_file(hbc6_file, py_file)
    forensic.print_report(report)
    
    # Se há erros críticos, sugere correção
    if any("FLAG_CUSTOM_PAYLOAD" in err for err in report.get('errors', [])):
        print("\n💡 CORREÇÃO NECESSÁRIA:")
        print("   1. Abra doxoade/tools/hermes_systems/hermes_compress_hbc6.py")
        print("   2. Localize a Etapa 5 (por volta da linha 80)")
        print("   3. Substitua por este bloco limpo:")
        print()
        print("   # 5. Serialização do Payload (Marshal padrão - Estável)")
        print("   marshalled_payload = marshal.dumps(code_obj)")
        print()
        print("   # 6. Montagem do Arquivo HBC6")
        print("   header = MAGIC_HBC6 + struct.pack('<B', VERSION_HBC6) + struct.pack('<B', flags)")
        print("   final_data = (")
        print("       header +")
        print("       struct.pack('<I', len(hrt_bytes)) + hrt_bytes +")
        print("       struct.pack('<I', len(macro_dict_bytes)) + macro_dict_bytes +")
        print("       struct.pack('<I', len(marshalled_payload)) + marshalled_payload")
        print("   )")
        print()
        print("   4. Recompile: python doxoade/tools/hermes_systems/build_hbc6.py --all")


if __name__ == '__main__':
    main()
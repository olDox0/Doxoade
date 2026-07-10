# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_compress_hbc6.py
"""
Hermes Compressor HBC6 — O Linker de Bytecode (Patch-in-RAM)
Arquitetura: Compressão Semântica de Opcodes (Caminho A).
Estratégia: Gera a HRT (Tabela de Patches) e salva o marshal 100% INTACTO.
A cirurgia ocorre na RAM, executada pelo Motor C (Mercury Bridge) no boot.
"""
import dis
import types
import marshal
import struct
from pathlib import Path
from typing import Dict, List

MAGIC_HBC6 = b"HBC6"
VERSION_HBC6 = 6

class HBC6Compressor:
    """Motor de Análise e Geração de Patches HBC6."""
    
    def __init__(self, global_macros: Dict[str, List[str]], token_map: Dict[str, int]):
        self.global_macros = global_macros
        self.token_map = token_map
        self.patches = []
        self.stats = {'patches_found': 0, 'bytes_to_save': 0, 'code_objects_scanned': 0}

    def compress_file(self, py_file: Path, output_path: Path) -> dict:
        source = py_file.read_text(encoding='utf-8')
        orig_size = len(source.encode('utf-8'))
        
        # 1. Compilação Padrão (Intacta)
        code_obj = compile(source, str(py_file), 'exec', optimize=2)
        
        # 2. Mapeamento DFS (Atribui um ID único para cada CodeObject aninhado)
        dfs_index_map = {}
        self._assign_dfs_indices(code_obj, dfs_index_map)
        
        # 3. Varredura Cirúrgica (Encontra os Blocos Atômicos Isolados)
        self.patches = []
        self._scan_code_obj(code_obj, dfs_index_map)
        
        # 4. Serialização da Tabela de Patches (HRT)
        hrt_bytes = self._serialize_hrt()
        
        # 5. 🚀 CORREÇÃO: Serialização do Payload (Marshal 100% INTACTO)
        # A cirurgia ocorre na RAM, executada pelo Motor C no boot.
        # Se comprimirmos aqui, a HRT ficará dessincronizada com o bytecode.
        marshalled_payload = marshal.dumps(code_obj)
        
        # 6. Montagem do Arquivo HBC6
        header = MAGIC_HBC6 + struct.pack('<B', VERSION_HBC6)
        payload_size = struct.pack('<I', len(marshalled_payload))
        final_data = (
            header + 
            struct.pack('<I', len(hrt_bytes)) + hrt_bytes + 
            payload_size + marshalled_payload
        )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(final_data)
        
        return {
            'original_bytes': orig_size,
            'hbc6_bytes': len(final_data),
            'marshalled_bytes': len(marshalled_payload),
            'patches_applied': self.stats['patches_found'],
            'code_objects_scanned': self.stats['code_objects_scanned'],
            'bytes_to_save_in_ram': self.stats['bytes_to_save']
        }

    def _apply_compression_to_code_obj(self, code_obj: types.CodeType, dfs_index_map: dict) -> types.CodeType:
        """
        Aplica a compressão no co_code: substitui N-grams por NOP (0x09) + token_id.
        Retorna um novo CodeObject com o co_code comprimido.
        """
        co_index = dfs_index_map[id(code_obj)]
        co_code = code_obj.co_code
        
        # Cria um buffer mutável
        new_buf = bytearray(co_code)
        
        # Aplica os patches para este CodeObject
        for patch in self.patches:
            if patch['co_index'] == co_index:
                # 🚀 CORREÇÃO: As chaves corretas geradas pelo _scan_code_obj
                off = patch['offset']             # Era 'start'
                tok = patch['token_id']          
                orig_ng_len = patch['orig_ngram_len'] # Era 'original_size'
                
                # Injeta NOP + token_id
                new_buf[off] = 0x09  # NOP opcode
                if orig_ng_len > 1:
                    new_buf[off + 1] = tok  # Arg = token_id
                # Preenche o restante do N-gram com NOPs
                for j in range(2, orig_ng_len):
                    new_buf[off + j] = 0x09  # NOP opcode
        
        # Cria o novo CodeObject com o co_code comprimido
        new_code_obj = code_obj.replace(co_code=bytes(new_buf))
        
        # Recursão para os CodeObjects aninhados
        new_consts = []
        for const in code_obj.co_consts:
            if isinstance(const, types.CodeType):
                new_consts.append(self._apply_compression_to_code_obj(const, dfs_index_map))
            else:
                new_consts.append(const)
        
        if new_consts != list(code_obj.co_consts):
            new_code_obj = new_code_obj.replace(co_consts=tuple(new_consts))
        
        return new_code_obj

    def _assign_dfs_indices(self, code_obj: types.CodeType, index_map: dict, current_index: int = 0) -> int:
        index_map[id(code_obj)] = current_index
        current_index += 1
        for const in code_obj.co_consts:
            if isinstance(const, types.CodeType):
                current_index = self._assign_dfs_indices(const, index_map, current_index)
        return current_index

    def _scan_code_obj(self, code_obj: types.CodeType, dfs_index_map: dict):
        self.stats['code_objects_scanned'] += 1
        co_index = dfs_index_map[id(code_obj)]
        instructions = list(dis.get_instructions(code_obj))
        
        if not instructions:
            return

        # 1. MAPEAMENTO DO CAMPO MINADO (Jump Targets & Sources)
        jump_targets = set()
        jump_sources = {} 
        
        for instr in instructions:
            if instr.opcode in dis.hasjrel or instr.opcode in dis.hasjabs:
                if isinstance(instr.argval, int):
                    jump_targets.add(instr.argval)
                    jump_sources[instr.offset] = instr.argval

        # 2. CAÇA AOS BLOCOS ATÔMICOS ISOLADOS
        for mac_hash, mac_opnames in self.global_macros.items():
            if mac_hash not in self.token_map:
                continue
            token_id = self.token_map[mac_hash]
            n_len = len(mac_opnames)
            
            for i in range(len(instructions) - n_len + 1):
                window = [instructions[i+j].opname for j in range(n_len)]
                if window == mac_opnames:
                    start_offset = instructions[i].offset
                    end_instr = instructions[i + n_len - 1]
                    end_offset = end_instr.offset + getattr(end_instr, '_length', 2)
                    
                    is_isolated = True
                    for target in jump_targets:
                        if start_offset < target < end_offset:
                            is_isolated = False; break
                    if not is_isolated: continue
                    
                    for source in jump_sources:
                        if start_offset <= source < end_offset:
                            is_isolated = False; break
                    if not is_isolated: continue
                    
                    for source, target in jump_sources.items():
                        if (source < start_offset and target >= end_offset) or \
                           (source >= end_offset and target < start_offset):
                            is_isolated = False; break
                    if not is_isolated: continue
                    
                    self.patches.append({
                        'co_index': co_index,
                        'offset': start_offset,
                        'token_id': token_id,
                        'orig_size': end_offset - start_offset
                    })
                    self.stats['patches_found'] += 1
                    self.stats['bytes_to_save'] += (end_offset - start_offset - 2)

        # 3. RECURSÃO (Mantém a ordem DFS)
        for const in code_obj.co_consts:
            if isinstance(const, types.CodeType):
                self._scan_code_obj(const, dfs_index_map)

    def _serialize_hrt(self) -> bytes:
        # Ordena os patches por co_index e depois por offset para o Motor C
        self.patches.sort(key=lambda x: (x['co_index'], x['offset']))
        data = bytearray()
        for p in self.patches:
            data += struct.pack('<IIHH', p['co_index'], p['offset'], p['token_id'], p['orig_size'])
        return bytes(data)
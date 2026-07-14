# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_compress_hbc6.py
"""
Hermes Compressor HBC6 Unificado — O Linker de Bytecode & Strings
==================================================================
Arquitetura: HBC5 (Strings) + HBC6 (Bytecode/Telemetria) + HGD1 (Global Dict).

Estratégia de Expansão Pré-Marshal (Anti Py_FatalError):
  1. O compressor Python injeta macros (0xC0 + token_id) no co_code cru.
  2. O Motor C lê o payload, faz o PyMarshal (que não valida stack effect).
  3. O Motor C faz um Walker DFS, encontra os 0xC0 e expande em um buffer RAM 
     usando o MACRO_DICT embutido no header.
  4. O Motor C injeta o co_code JÁ EXPANDIDO de volta no PyCodeObject.
  5. O CPython recebe um bytecode 100% válido e stack-neutral.
"""
import dis
import types
import marshal
import struct
import json
from pathlib import Path
from typing import Dict, List

MAGIC_HBC6 = b"HBC6"
VERSION_HBC6 = 6
FLAG_TOKENIZED_CONSTS = 0x01
FLAG_BYTECODE_PATCHED = 0x02  # 🚀 Nova flag: Indica que o co_code contém macros 0xC0

# Opcode customizado para MACRO. 
# O Marshal aceita qualquer byte, mas o Motor C interceptará antes da execução.
MACRO_OPCODE = 0xC0

class HBC6Compressor:
    """Motor de Compressão Unificada (Strings + Bytecode)."""
    
    def __init__(self, project_root: Path, global_macros: Dict[str, List[str]], token_map: Dict[str, int]):
        self.root = project_root
        self.global_macros = global_macros  # {hash: [opname1, opname2, ...]}
        self.token_map = token_map          # {hash: token_id}
        self.patches = []                   # Lista de patches aplicados (HRT)
        self.macro_dict = {}                # {token_id: raw_bytes} para o Motor C
        self.stats = {
            'patches_found': 0, 
            'bytes_to_save': 0, 
            'code_objects_scanned': 0, 
            'tokens_applied': 0
        }
        
        # Carrega o Encoder Global (master.dict) para tokenizar strings (HBC5)
        self.global_encoder = self._load_global_encoder()
        
        # Mapeamento reverso: opname -> opcode byte (para reconstruir o bytecode cru)
        self.opcode_map = {dis.opname[i]: i for i in range(len(dis.opname))}
        
    def _load_global_encoder(self) -> dict:
        dict_path = self.root / '.doxoade' / 'hermes' / 'master.dict'
        if not dict_path.exists(): return {}
        try:
            data = json.loads(dict_path.read_text(encoding='utf-8'))
            return {k: int(v) for k, v in data.get('encoder', {}).items() if not k.startswith('[')}
        except Exception:
            return {}

    def compress_file(self, py_file: Path, output_path: Path) -> dict:
        source = py_file.read_text(encoding='utf-8')
        orig_size = len(source.encode('utf-8'))
        
        # 1. Compilação Padrão
        code_obj = compile(source, str(py_file), 'exec', optimize=2)
        
        # 2. FASE HBC5: Tokenização de Strings (co_consts)
        flags = 0
        if self.global_encoder:
            code_obj = self._tokenize_code_consts(code_obj)
            if self.stats['tokens_applied'] > 0:
                flags |= FLAG_TOKENIZED_CONSTS
                
        # 3. FASE HBC6: Mapeamento DFS e Varredura Cirúrgica (HRT)
        dfs_index_map = {}
        self._assign_dfs_indices(code_obj, dfs_index_map)
        self.patches = []
        self.macro_dict = {}
        self._scan_code_obj(code_obj, dfs_index_map)
        
        # 4. 🚀 APLICA A CIRURGIA NO BYTECODE (Injeção de 0xC0)
        if self.patches:
            code_obj = self._apply_patches_to_bytecode(code_obj, dfs_index_map)
            flags |= FLAG_BYTECODE_PATCHED
            
        hrt_bytes = self._serialize_hrt()
        macro_dict_bytes = self._serialize_macro_dict()
        
        # 5. Serialização do Payload (Marshal com co_code patcheado)
        marshalled_payload = marshal.dumps(code_obj)
        
        # 6. Montagem do Arquivo HBC6 Unificado
        # Layout: Magic(4) + Ver(1) + Flags(1) + HRT_Size(4) + HRT + MacroDict_Size(4) + MacroDict + Payload_Size(4) + Marshal
        header = MAGIC_HBC6 + struct.pack('<B', VERSION_HBC6) + struct.pack('<B', flags)
        
        final_data = (
            header + 
            struct.pack('<I', len(hrt_bytes)) + hrt_bytes + 
            struct.pack('<I', len(macro_dict_bytes)) + macro_dict_bytes +
            struct.pack('<I', len(marshalled_payload)) + marshalled_payload
        )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(final_data)
        
        return {
            'original_bytes': orig_size,
            'hbc6_bytes': len(final_data),
            'marshalled_bytes': len(marshalled_payload),
            'patches_applied': self.stats['patches_found'],
            'tokens_applied': self.stats['tokens_applied'],
            'code_objects_scanned': self.stats['code_objects_scanned']
        }

    def _apply_patches_to_bytecode(self, code_obj: types.CodeType, dfs_index_map: dict) -> types.CodeType:
        """Injeta 0xC0 + token_id no co_code cru e preenche o resto com NOPs."""
        my_index = dfs_index_map.get(id(code_obj), -1)
        my_patches = [p for p in self.patches if p['co_index'] == my_index]
        
        current_code_obj = code_obj
        if my_patches:
            bytecode = bytearray(code_obj.co_code)
            for patch in my_patches:
                offset = patch['offset']
                orig_len = patch['orig_ngram_len']
                token_id = patch['token_id']
                
                bytecode[offset] = MACRO_OPCODE  
                bytecode[offset + 1] = token_id & 0xFF
                
                # Preenche o resto com NOPs (Wordcode: 2 bytes por instrução)
                for i in range(2, orig_len, 2):
                    if offset + i + 1 < len(bytecode):
                        bytecode[offset + i] = 0x09     # NOP
                        bytecode[offset + i + 1] = 0x00 
                        
            current_code_obj = code_obj.replace(co_code=bytes(bytecode))

        new_consts = []
        changed = False
        for const in current_code_obj.co_consts:
            if isinstance(const, types.CodeType):
                new_const = self._apply_patches_to_bytecode(const, dfs_index_map)
                if new_const is not const:
                    changed = True
                new_consts.append(new_const)
            else:
                new_consts.append(const)
                
        if changed:
            current_code_obj = current_code_obj.replace(co_consts=tuple(new_consts))
            
        return current_code_obj

    def _serialize_macro_dict(self) -> bytes:
        """
        Serializa o dicionário de macros com tamanho DINÂMICO.
        Layout: [Count(2)] + [ (TokenID(2), Len(2), RawOpcodes(Len)) ... ]
        
        🚀 OTIMIZAÇÃO: Só serializa tokens realmente usados (não 256 fixos)
        """
        macro_dict_bytes = bytearray()
        used_tokens = set(p['token_id'] for p in self.patches)
        
        # 🚀 DINÂMICO: Count = tokens usados (não 256)
        macro_dict_bytes += struct.pack('<H', len(used_tokens))
        
        for token_id in sorted(used_tokens):
            ng_hash = next((h for h, tid in self.token_map.items() if tid == token_id), None)
            if not ng_hash or ng_hash not in self.global_macros:
                continue
                
            opnames = self.global_macros[ng_hash]
            raw_bytes = bytearray()
            for op in opnames:
                opcode = self.opcode_map.get(op, 0x09)
                raw_bytes.append(opcode)
                raw_bytes.append(0x00)
            
            macro_dict_bytes += struct.pack('<HH', token_id, len(raw_bytes))
            macro_dict_bytes += raw_bytes
            
        return bytes(macro_dict_bytes)


    def _tokenize_code_consts(self, code_obj: types.CodeType) -> types.CodeType:
        """Percorre recursivamente o code object e substitui strings em co_consts."""
        new_consts = []
        changed = False
        sorted_patterns = sorted(self.global_encoder.items(), key=lambda x: len(x[0]), reverse=True)
        
        for const in code_obj.co_consts:
            if isinstance(const, str) and len(const) > 4:
                result = const
                for pattern, token_int in sorted_patterns:
                    if pattern in result:
                        result = result.replace(pattern, chr(token_int))
                        self.stats['tokens_applied'] += 1
                if result != const:
                    new_consts.append(result)
                    changed = True
                else:
                    new_consts.append(const)
            elif isinstance(const, types.CodeType):
                new_consts.append(self._tokenize_code_consts(const))
            else:
                new_consts.append(const)
                
        if changed:
            return code_obj.replace(co_consts=tuple(new_consts))
        return code_obj

    def _assign_dfs_indices(self, code_obj: types.CodeType, index_map: dict, current_index: int = 0) -> int:
        index_map[id(code_obj)] = current_index
        current_index += 1
        for const in code_obj.co_consts:
            if isinstance(const, types.CodeType):
                current_index = self._assign_dfs_indices(const, index_map, current_index)
        return current_index

    def _scan_code_obj(self, code_obj: types.CodeType, dfs_index_map: dict):
        """Varre o bytecode em busca dos N-grams globais (greedy, sem sobreposição)."""
        self.stats['code_objects_scanned'] += 1
        my_index = dfs_index_map[id(code_obj)]
        
        instructions = list(dis.get_instructions(code_obj))
        clean_ops = []
        op_offsets = []
        
        _NOISE = {'RESUME', 'NOP', 'PRECALL', 'CACHE', 'PUSH_NULL', 'COPY', 'EXTENDED_ARG'}
        
        for instr in instructions:
            if instr.opname in _NOISE:
                continue
            clean_ops.append(instr.opname)
            op_offsets.append(instr.offset)
        
        # 🚀 ORDENA N-GRAMS POR TAMANHO (maior primeiro = greedy matching)
        sorted_ngrams = sorted(
            self.global_macros.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        # 🚀 TRACK DE REGIÕES JÁ COBERTAS (evita sobreposição)
        covered_ranges = []  # Lista de (start_idx, end_idx) já cobertos
        
        def is_covered(start_idx, end_idx):
            for cs, ce in covered_ranges:
                if start_idx < ce and end_idx > cs:
                    return True
            return False
        
        # Janela Deslizante (greedy: maior N-gram primeiro)
        for ng_hash, ng_ops in sorted_ngrams:
            n_len = len(ng_ops)
            if n_len < 2:
                continue
            
            for i in range(len(clean_ops) - n_len + 1):
                window = tuple(clean_ops[i:i+n_len])
                if window == tuple(ng_ops):
                    # Verifica se esta região já está coberta por um N-gram maior
                    if is_covered(i, i + n_len):
                        continue
                    
                    token_id = self.token_map.get(ng_hash, 0)
                    orig_len = n_len * 2  # Wordcode: 2 bytes por instrução
                    
                    # Verifica stack-neutral
                    stack = 0
                    stack_neutral = True
                    for opname in ng_ops:
                        opcode = dis.opmap.get(opname, 0)
                        try:
                            effect = dis.stack_effect(opcode, 0)
                        except Exception:
                            effect = 0
                        stack += effect
                        if stack < 0:
                            stack_neutral = False
                            break
                    if stack != 0:
                        stack_neutral = False
                    
                    if not stack_neutral:
                        continue
                    
                    self.patches.append({
                        'co_index': my_index,
                        'offset': op_offsets[i],
                        'token_id': token_id,
                        'orig_ngram_len': orig_len,
                        'hash': ng_hash
                    })
                    self.stats['patches_found'] += 1
                    self.stats['bytes_to_save'] += (orig_len - 2)
                    
                    # Marca esta região como coberta
                    covered_ranges.append((i, i + n_len))
        
        # Recursão
        for const in code_obj.co_consts:
            if isinstance(const, types.CodeType):
                self._scan_code_obj(const, dfs_index_map)

    def _serialize_hrt(self) -> bytes:
        """Serializa a Hermes Relocation Table."""
        hrt_bytes = bytearray()
        for p in self.patches:
            hrt_bytes += struct.pack('<I', p['co_index'])
            hrt_bytes += struct.pack('<I', p['offset'])
            hrt_bytes += struct.pack('<H', p['token_id'])
            hrt_bytes += struct.pack('<H', p['orig_ngram_len'])
        return bytes(hrt_bytes)
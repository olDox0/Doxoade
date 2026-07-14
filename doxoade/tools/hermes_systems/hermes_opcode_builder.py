# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_opcode_builder.py
"""
HBC6 Opcode Builder — O Linker de Bytecode do Hermes
====================================================
Arquitetura de Compressão Semântica (Caminho A).
Fase 1: Safe Zone (Atomic Blocks) & Relocation Table (HRT).

O "Campo Minado":
  Se um JUMP aponta para o MEIO de um N-gram, o N-gram é intocável (Zona Neutra).
  Se um JUMP aponta para DEPOIS de um N-gram, o N-gram é comprimido, e o JUMP 
  entra na Tabela de Relocação (HRT) para que o Motor C ajuste o offset no boot.
"""
import dis
import ast
import struct
import hashlib
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Set
from doxoade.tools.doxcolors import Fore, Style

# Opcodes que não geram lógica real (Ruído do CPython 3.11+)
_NOISE_OPCODES = frozenset({'RESUME', 'NOP', 'PRECALL', 'CACHE', 'PUSH_NULL', 'COPY', 'EXTENDED_ARG'})

class OpcodeInstruction:
    """Representa uma instrução Wordcode (2 bytes) limpa."""
    __slots__ = ('offset', 'opname', 'arg', 'is_jump', 'jump_target')
    def __init__(self, offset: int, opname: str, arg: int, is_jump: bool, jump_target: int):
        self.offset = offset
        self.opname = opname
        self.arg = arg
        self.is_jump = is_jump
        self.jump_target = jump_target # Offset absoluto em bytes (ou -1)

class HBC6Builder:
    """Motor de Cirurgia de Bytecode com Filtro de Campo Minado."""
    
    def __init__(self, project_root: str, global_ngrams: Dict[str, List[str]]):
        """
        Args:
            project_root: Raiz do projeto.
            global_ngrams: Dicionário {hash: [lista_de_opcodes]}. 
                           Ex: {'abc123': ['LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME']}
        """
        self.root = Path(project_root).resolve()
        self.global_ngrams = global_ngrams
        self.metrics = {
            'files_scanned': 0,
            'total_bytes_saved': 0,
            'macros_applied': 0,
            'hrt_entries': 0,
            'blocked_by_minefield': 0
        }

    def analyze_file(self, py_file: Path) -> Dict:
        """Analisa um arquivo e calcula o potencial de compressão HBC6."""
        self.metrics['files_scanned'] += 1
        try:
            source = py_file.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source, filename=str(py_file))
            code_obj = compile(tree, str(py_file), 'exec', optimize=2)
        except Exception as e:
            return {'error': str(e)}

        return self._walk_and_surgery(code_obj, py_file)

    def _is_stack_neutral(self, opcodes: list[str]) -> bool:
        """
        Verifica se o N-gram é stack-neutral (início e fim com stack = 0).
        Stack-neutral = seguro para injeção sem quebrar o CPython 3.11+
        """
        import dis
        if not opcodes:
            return False
        
        stack = 0
        for opname in opcodes:
            opcode = dis.opmap.get(opname)
            if opcode is None:
                return False # Opcode desconhecido, assume não seguro
            
            # Usamos 0 como oparg padrão. Para a PoC, isso cobre a maioria dos casos,
            # pois o efeito de pilha de opcodes como LOAD_CONST é +1 independente do arg.
            try:
                effect = dis.stack_effect(opcode, 0)
            except Exception:
                effect = 0
                
            stack += effect
            if stack < 0:
                return False # Underflow de pilha, não é seguro
                
        return stack == 0

    def _walk_and_surgery(self, code_obj, py_file: Path) -> Dict:
        """Extrai o DNA, mapeia o campo minado e calcula a HRT."""
        instructions = self._extract_instructions(code_obj)
        if not instructions:
            return {'saved_bytes': 0, 'hrt': []}

        minefield: Set[int] = set()
        for instr in instructions:
            if instr.is_jump and instr.jump_target != -1:
                minefield.add(instr.jump_target)

        safe_macros = []
        clean_instructions = [i for i in instructions if i.opname not in _NOISE_OPCODES]
        opnames = [i.opname for i in clean_instructions]
        
        # 🚀 ORDENA N-GRAMS POR TAMANHO (maior primeiro)
        sorted_ngrams = sorted(
            self.global_ngrams.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        # 🚀 TRACK DE REGIÕES COBERTAS
        covered_ranges = []
        
        def is_covered(start_idx, end_idx):
            for cs, ce in covered_ranges:
                if start_idx < ce and end_idx > cs:
                    return True
            return False
        
        for ng_hash, ng_ops in sorted_ngrams:
            n_len = len(ng_ops)
            if n_len < 2: continue
            
            if not self._is_stack_neutral(ng_ops):
                continue
            
            for i in range(len(opnames) - n_len + 1):
                if is_covered(i, i + n_len):
                    continue
                    
                window = tuple(opnames[i:i+n_len])
                if window == tuple(ng_ops):
                    start_offset = clean_instructions[i].offset 
                    end_offset = clean_instructions[i + n_len - 1].offset + 2 
                    
                    is_safe = True
                    for target in minefield:
                        if start_offset < target < end_offset:
                            is_safe = False
                            self.metrics['blocked_by_minefield'] += 1
                            break
                    
                    if is_safe:
                        safe_macros.append({
                            'hash': ng_hash,
                            'start': start_offset,
                            'end': end_offset,
                            'original_size': end_offset - start_offset,
                            'compressed_size': 2,
                            'stack_neutral': True
                        })
                        covered_ranges.append((i, i + n_len))

        hrt_entries = []
        total_saved = 0
        safe_macros.sort(key=lambda x: x['start'])
        
        for macro in safe_macros:
            delta = macro['compressed_size'] - macro['original_size']
            total_saved += -delta
            self.metrics['macros_applied'] += 1
            
            for instr in instructions:
                if instr.is_jump and instr.jump_target > macro['end']:
                    hrt_entries.append({
                        'jump_offset': instr.offset,
                        'delta': delta
                    })
                    self.metrics['hrt_entries'] += 1

        self.metrics['total_bytes_saved'] += total_saved
        
        return {
            'saved_bytes': total_saved,
            'macros_found': len(safe_macros),
            'hrt_entries': len(hrt_entries),
            'hrt_sample': hrt_entries[:3]
        }

    def _extract_instructions(self, code_obj) -> List[OpcodeInstruction]:
        """Converte o co_code em uma lista de instruções limpas e mapeadas."""
        instructions = []
        try:
            for instr in dis.get_instructions(code_obj):
                if instr.opname in _NOISE_OPCODES:
                    continue
                
                is_jump = 'JUMP' in instr.opname or 'FOR_ITER' in instr.opname
                # O argval do dis já é o offset absoluto em bytes (ou label)
                jump_target = instr.argval if is_jump and isinstance(instr.argval, int) else -1
                
                instructions.append(OpcodeInstruction(
                    offset=instr.offset,
                    opname=instr.opname,
                    arg=instr.arg,
                    is_jump=is_jump,
                    jump_target=jump_target
                ))
        except Exception:
            pass
        return instructions

    def print_report(self):
        """Imprime o relatório de engenharia do Builder."""
        print(f"\n{Fore.GREEN}{'═' * 70}")
        print(f"  🏗️  RELATÓRIO DE ENGENHARIA HBC6 (Fase 1: Safe Zone)")
        print(f"{'═' * 70}{Style.RESET_ALL}")
        print(f"  Arquivos Analisados       : {self.metrics['files_scanned']}")
        print(f"  Macros Atômicas Aplicadas : {Fore.CYAN}{self.metrics['macros_applied']}{Style.RESET_ALL}")
        print(f"  Bloqueadas (Campo Minado) : {Fore.YELLOW}{self.metrics['blocked_by_minefield']}{Style.RESET_ALL}")
        print(f"  Entradas na HRT (Saltos)  : {Fore.MAGENTA}{self.metrics['hrt_entries']}{Style.RESET_ALL}")
        print(f"  Economia Total de co_code : {Fore.GREEN}{self.metrics['total_bytes_saved'] / 1024:.2f} KB{Style.RESET_ALL}")
        print(f"{'═' * 70}\n")
        
    def _calculate_stack_effect(self, opcodes: list[str]) -> int:
        """Calcula o stack effect líquido de uma sequência de opcodes."""
        stack_delta = 0
        for opname in opcodes:
            opcode = dis.opmap.get(opname)
            if opcode is None:
                continue
            # Stack effect do opcode (1 = push, -1 = pop, 0 = neutro)
            effect = dis.stack_effect(opcode, 0)  # 0 = sem arg
            stack_delta += effect
        return stack_delta

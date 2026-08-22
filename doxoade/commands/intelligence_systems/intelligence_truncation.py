# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/intelligence_truncation.py
"""
Motor de Auditoria de Integridade Sintática e de Arquivo (Anúbis Protocol).
Garante que nem o código-fonte nem o dossiê de saída estejam truncados.
"""
import os
import re
import ast
import json

class TruncationChecker:
    """Verifica se arquivos de código estão sintaticamente incompletos."""
    
    @staticmethod
    def check_python(code: str) -> dict:
        try:
            ast.parse(code)
            return {"status": "intact", "reason": None}
        except SyntaxError as e:
            msg = str(e).lower()
            if "unexpected eof" in msg or "unmatched" in msg or "was never closed" in msg:
                return {"status": "truncated", "reason": f"SyntaxError: {e.msg} at L{e.lineno}"}
            return {"status": "corrupt", "reason": f"SyntaxError: {e.msg} at L{e.lineno}"}

    @staticmethod
    def check_lua(code: str) -> dict:
        # Remove comentários para não falsificar a contagem
        clean = re.sub(r'--\[\[.*?\]\]', '', code, flags=re.DOTALL)
        clean = re.sub(r'--.*', '', clean)
        
        # Conta blocos que exigem 'end' (function, if, for, while)
        openers = len(re.findall(r'\b(function|if|for|while)\b', clean))
        ends = len(re.findall(r'\bend\b', clean))
        
        if openers > ends:
            return {"status": "truncated", "reason": f"Missing {openers - ends} 'end' statement(s)"}
        return {"status": "intact", "reason": None}

    @staticmethod
    def check_c_cpp(code: str) -> dict:
        clean = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        clean = re.sub(r'//.*', '', clean)
        
        opens = clean.count('{')
        closes = clean.count('}')
        if opens > closes:
            return {"status": "truncated", "reason": f"Missing {opens - closes} closing brace(s) '}}'"}
        return {"status": "intact", "reason": None}

    @classmethod
    def analyze(cls, file_path: str, code: str) -> dict:
        ext = file_path.lower()
        if ext.endswith('.py'): return cls.check_python(code)
        elif ext.endswith('.lua'): return cls.check_lua(code)
        elif ext.endswith(('.c', '.cpp', '.h', '.hpp')): return cls.check_c_cpp(code)
        
        # Fallback genérico (balanceamento de parênteses/colchetes)
        stack = []
        mapping = {')': '(', ']': '[', '}': '{'}
        for char in code:
            if char in "([{": stack.append(char)
            elif char in ")]}":
                if not stack or stack[-1] != mapping[char]:
                    return {"status": "corrupt", "reason": f"Unmatched '{char}'"}
                stack.pop()
        if stack:
            return {"status": "truncated", "reason": f"Unclosed {len(stack)} bracket(s)"}
        return {"status": "intact", "reason": None}


def verify_dossier_integrity(output_path: str) -> tuple[bool, str]:
    """Verifica se o XML/JSON gerado não foi truncado no disco."""
    if not os.path.exists(output_path):
        return False, "Arquivo de saída não encontrado."
    
    with open(output_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if output_path.endswith('.xml'):
        if not content.strip().endswith('</doxoade_nexus_report>'):
            return False, "XML TRUNCADO: Falta a tag de fechamento </doxoade_nexus_report>."
    elif output_path.endswith('.json'):
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return False, f"JSON TRUNCADO/CORROMPIDO: {e}"
            
    return True, "Integridade validada (Ma'at)."

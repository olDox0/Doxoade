# doxoade/doxoade/commands/audit_systems/maat_weights.py
"""
WeightGuard - Vigilante PASC 1.3 & OSL 16.
Monitora o crescimento físico dos arquivos para evitar 'Overflat'.
"""
import os

class WeightGuard:

    def __init__(self, root):
        self.root = root
        self.MAX_KB = 50
        self.MAX_LINES = 1000

    def audit(self, files: list):
        findings = []
        for f in files:
            if not f.endswith('.py') or not os.path.exists(f):
                continue
            size_kb = os.path.getsize(f) / 1024
            if size_kb > self.MAX_KB:
                findings.append({'severity': 'ERROR', 'category': 'PASC-1.3', 'message': f'Arquivo obeso: {os.path.basename(f)} ({size_kb:.1f}KB)', 'file': f, 'line': 1})
            illegal = self._check_illegal_imports(f)
            if illegal:
                findings.append(illegal)
        return findings

    def _check_illegal_imports(self, file_path):
        """Verifica imports proibidos, respeitando o silenciador # noqa."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f, 1):
                    if 'import sqlite3' in line:
                        if '# noqa' in line.lower():
                            continue
                        if 'commands/' in file_path.replace('\\', '/'):
                            return {'severity': 'ERROR', 'category': 'PASC-8.6', 'message': 'Violação de Arquitetura: Comandos não podem importar sqlite3 diretamente. Use # noqa para ignorar.', 'file': file_path, 'line': i}
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_number = exc_tb.tb_lineno
            print(f'\x1b[31m ■ Archibe: {fname} - line: {line_number}  \n ■ Exception type: {e} . . .\n  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n')
            exc_trace(exc_tb)
        return None
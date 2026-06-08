# -*- coding: utf-8 -*-
# doxoade/commands/macrothon_systems/macrothon_translator.py
import re
from doxoade.tools.doxcolors import Fore, Style

class MacrothonTranslator:
    """Especialista em Transformação Semântica (Córtex do Macrothon)."""
    
    def __init__(self, raw_content):
        self.raw = raw_content.replace('\r\n', '\n')
        self.translated_blocks = 0
        self.orphaned_blocks = []

    def _find_line(self, name):
        for i, line in enumerate(self.raw.splitlines(), 1):
            if name + ":" in line: return i
        return 0

    def translate(self, context_keys):
        """Pipeline de tradução completo."""
        # 1. Limpa blocos de metadados
        code = re.sub(r"IMPORT\s*\{[^}]*\}", "", self.raw, flags=re.DOTALL)
        code = re.sub(r"TREE\s*\{[^}]*\}", "", code, flags=re.DOTALL)
        
        # 2. Injeta Debug: 'debug: var' -> print
        code = re.sub(r"([ \t]*)debug:\s*([\w\d_]+)", 
                      r"\n\1print(f'{Fore.MAGENTA}   🔍 [DEBUG] \2 = {\2}{Style.RESET_ALL}'); sys.stdout.flush()", code)

        # 3. Tradutor de Blocos Funcionais
        def replacer(match):
            indent, name, body = match.group(1), match.group(2), match.group(3)
            if name not in context_keys:
                self.orphaned_blocks.append((name, self._find_line(name)))
                return match.group(0)
            
            try:
                in_v = re.search(r"input\s*=\s*(.*)", body).group(1).strip()
                out_v = re.search(r"output\s*=\s*(.*)", body).group(1).strip()
                # NOTA: Não usamos 'await' aqui pois o _CALL já resolve o loop
                return (f"\n{indent}_t0 = time.perf_counter()\n"
                        f"{indent}{out_v} = _CALL({name}, {in_v})\n"
                        f"{indent}if {out_v} is None: {out_v} = {in_v}\n"
                        f"{indent}_dur = (time.perf_counter() - _t0)*1000\n"
                        f"{indent}_MACRO_METRICS.append({{'block': '{name}', 'ms': _dur}})\n"
                        f"{indent}sys.stdout.flush()\n")
            except:
                return f"\n{indent}print('{Fore.RED}   ✘ Erro de sintaxe no bloco {name}{Style.RESET_ALL}')\n"

        code = re.sub(r"(?m)^([ \t]*)(\w+):\s*\n((?:\1[ \t]+.*\n?)+)", replacer, code)
        return code.strip()
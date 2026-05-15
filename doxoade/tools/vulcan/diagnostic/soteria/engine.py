# -*- coding: utf-8 -*-
import os, sys, re, datetime

class SoteriaForensic:
    def __init__(self):
        self.reset = "\033[0m"; self.red = "\033[1;31m"; self.cyan = "\033[1;36m"
        self.ylw = "\033[1;33m"; self.gray = "\033[90m"; self.grn = "\033[1;32m"

    def shorten_path(self, path):
        if not path or path == "N/A": return "N/A"
        clean = path.replace("\\\\", "\\").replace("/", "\\")
        if "shadow" in clean: clean = os.path.join("src", clean.split("shadow")[-1].lstrip("\\/"))
        return clean

    def find_dna_mapping(self, c_file, start_line):
        """Busca profunda pelo mapeamento original do Cython (PASC 8.19)."""
        if not os.path.exists(c_file): return None, None
        try:
            with open(c_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            base_idx = int(start_line) - 1
            # PASC 6.9: Varredura de Proximidade (Busca 100 linhas a frente e 20 atras)
            # O Cython costuma colocar o comentário logo apos as declaracoes de variaveis
            for i in range(max(0, base_idx - 20), min(len(lines), base_idx + 100)):
                match = re.search(r'/\* "(.*\.pyx)":(\d+) \*/', lines[i])
                if match:
                    return match.group(1), match.group(2)
        except: pass
        return None, None

    def get_code_context(self, file_path, line, window=3, title="CONTEXTO"):
        if not os.path.exists(file_path): return f"   [!] Arquivo nao localizado: {file_path}"
        try:
            line = int(line); lines = open(file_path, 'r', encoding='utf-8', errors='ignore').readlines()
            output = f"   \033[1;37m[{title}]: {os.path.basename(file_path)}:{line}\033[0m\n"
            for i in range(max(0, line-window), min(len(lines), line+window)):
                marker = " >> " if i == line-1 else "    "
                color = self.red if i == line-1 else self.gray
                output += f"{color}{marker}{i+1:4} | {lines[i].rstrip()}{self.reset}\n"
            return output
        except: return ""

    def process_pipe(self, text):
        match = re.search(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", text, re.DOTALL)
        if not match: return False
        nx = match.group(1)
        def get_tag(t): return (re.findall(rf"TAG_{t}:\s*(.*)", nx, re.IGNORECASE) or ["N/A"])[0].strip()

        print(f"\n{self.red}" + "!" * 65 + f"\n SOTÉRIA: TRACEBACK CYTHON REAL (ALFA-GOLD)\n" + "!" * 65 + self.reset)
        
        # ÚLTIMO MARCO (A linha real do .pyx)
        r_msg = get_tag('RASTRO_MSG') # Ex: TRACEBACK: provocar_falha
        r_loc = get_tag('RASTRO_LOC') # Ex: kamikaze.pyx:9
        
        print(f"{self.cyan}■ ÚLTIMO PONTO DE CONTATO (CÓDIGO FONTE):{self.reset}")
        if ":" in r_loc:
            file, line = r_loc.rsplit(':', 1)
            print(f"  ARQUIVO: \033[1;32m{file}\033[0m | LINHA: \033[1;32m{line}\033[0m")
            print(f"  RASTRO:  {self.ylw}{r_msg}{self.reset}\n")
            print(self.get_code_context(file, line))

        print(f"{self.cyan}■ CAUSA TÉCNICA (NÍVEL C):{self.reset}")
        print(f"  {get_tag('DETAIL')} | PID: {get_tag('PID')}")
        print(f"{self.red}" + "─" * 65 + self.reset + "\n")
        return True
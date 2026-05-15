# -*- coding: utf-8 -*-
import os, sys, re

class SoteriaForensic:
    def __init__(self):
        self.reset = "\033[0m"; self.red = "\033[1;31m"; self.cyan = "\033[1;36m"
        self.ylw = "\033[1;33m"; self.gray = "\033[90m"; self.grn = "\033[1;32m"; self.white = "\033[1;37m"

    def shorten_path(self, path):
        if not path or path == "N/A": return "N/A"
        clean = path.replace("\\\\", "\\").replace("/", "\\")
        if "shadow" in clean: clean = os.path.join("src", clean.split("shadow")[-1].lstrip("\\/"))
        for root in ['oldox222-lab', 'doxoade', 'Projeto OADE']:
            if root in clean: return clean.split(root)[-1].lstrip('\\/')
        return clean

    def get_code_context(self, file_path, line, window=3, title="CONTEXTO"):
        if not os.path.exists(file_path): return f"   \033[1;31m[!] Fonte inacessível: {file_path}\033[0m"
        try:
            line = int(line); lines = open(file_path, 'r', encoding='utf-8', errors='ignore').readlines()
            output = f"   {self.white}[{title}]: {self.shorten_path(file_path)}:{line}{self.reset}\n"
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

        level = get_tag('LEVEL')
        color = self.red if level == "FATAL" else self.ylw
        
        print(f"{color}!" * 65 + f"\n SOTÉRIA: RELATÓRIO SUPREMO DE EVIDÊNCIAS ({level})\n" + "!" * 65 + self.reset)
        
        # 1. IDENTIDADE DO PROCESSO
        print(f"{self.cyan}■ INCIDENTE TÉCNICO:{self.reset}")
        print(f"  DETALHE: {self.white}{get_tag('DETAIL')}{self.reset}")
        print(f"  PID: {self.white}{get_tag('PID')}{self.reset} | COMANDO: {self.gray}{get_tag('COMMAND')}{self.reset}")

        # 2. PONTO DE RUPTURA / TRIANGULAÇÃO
        loc = get_tag('LOCAL')
        print(f"\n{self.red}■ PONTO DE RUPTURA (ONDE O SISTEMA PAROU):{self.reset}")
        if "N/A" in loc or "0x" in loc:
            r_loc = get_tag('RASTRO_LOC')
            print(f"  {self.ylw}💡 TRIANGULAÇÃO: Falha detectada logo após:{self.reset}")
            if ":" in r_loc:
                f, l = r_loc.rsplit(':', 1); print(self.get_code_context(f, l, window=4, title="ULTIMO MARCO"))
        else:
            print(f"  LOCALIZAÇÃO: {self.grn}{self.shorten_path(loc)}{self.reset}\n")
            f, l = loc.rsplit(':', 1); print(self.get_code_context(f, l, window=2, title="LOCAL DO CRIME"))

        # 3. LEAKS (SE HOUVER)
        leaks = re.findall(r"TAG_LEAK:\s*(.*)", nx)
        if leaks:
            print(f"\n{self.ylw}■ VAZAMENTOS DE MEMÓRIA (LEAKS):{self.reset}")
            for l in leaks:
                print(f"   ⚠️ {l}")
                pts = re.findall(r"em (.*):(\d+)", l)
                if pts: print(self.get_code_context(pts[0][0], pts[0][1], window=0, title="ORIGEM"))

        # 4. ÁRVORE DE CHAMADAS
        frames = re.findall(r"TAG_FRAME:\s*(.*)", nx)
        if frames:
            print(f"\n{self.cyan}■ CADEIA DE ENVOLVIMENTO (COMO CHEGAMOS AQUI):{self.reset}")
            for f in frames:
                pts = f.split('|')
                name, loc = pts[1].strip(), pts[2].strip()
                color_f = self.grn if "src" in loc.lower() or "test" in loc.lower() else self.gray
                print(f"   {color_f}↳ {name}{self.reset} {self.gray}({self.shorten_path(loc)}){self.reset}")

        print(f"\n{color}" + "─" * 65 + self.reset + "\n")
        return True

if __name__ == "__main__":
    if sys.platform == 'win32':
        import io; sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
        os.system('')
    raw = sys.stdin.read()
    if raw:
        f = SoteriaForensic()
        if not f.process_pipe(raw): sys.stdout.write(raw)
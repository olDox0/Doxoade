# -*- coding: utf-8 -*-
# doxoade\tools\vulcan\diagnostic\soteria\soteria_analysis.py
import os, sys, re

def archive_crash_to_hades(nx_data):
    """Salva a evidência do crash nativo para o motor Gênese aprender."""
    try:
        from doxoade.database import get_db_connection
        import json
        
        conn = get_db_connection()
        # Registra na tabela de incidentes para que a IA analise a causa raiz no futuro
        conn.execute('''
            INSERT INTO open_incidents (finding_hash, file_path, line, message, category, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            nx_data.get('hash'),
            nx_data.get('LOCAL'),
            nx_data.get('LINE', 0),
            f"[NATIVE_CRASH] {nx_data.get('DETAIL')}",
            "VULCAN-MEMORY-PROBE",
            datetime.datetime.now().isoformat()
        ))
        conn.commit()
    except:
        pass

class SoteriaForensic:
    """Analisador Forense Alfa-Gold do Doxoade."""
    def __init__(self):
        self.reset = "\033[0m"; self.red = "\033[1;31m"; self.cyan = "\033[1;36m"
        self.ylw = "\033[1;33m"; self.gray = "\033[90m"; self.grn = "\033[1;32m"; self.white = "\033[1;37m"

    def shorten_path(self, path):
        if not path or path == "N/A": return "N/A"
        clean = path.replace("\\\\", "/").replace("\\", "/")
        
        # Filtro seletivo: Só encurta se for um marcador conhecido
        for marker in ['doxoade', 'experiments', 'TNSE']:
            if marker in clean:
                return clean.split(marker)[-1].lstrip('/')
        return clean # Se não tiver marcador, mantém o caminho completo para não virar "A"

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
        """Analisa o fluxo de saída em busca de assinaturas Sotéria."""
        match = re.search(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", text, re.DOTALL)
        
        if "@NEXUS_END@" in text:
            text = text.replace("@NEXUS_END@", "@SOTERIA_END@")
        if "@NEXUS_BEGIN@" in text:
            text = text.replace("@NEXUS_BEGIN@", "@SOTERIA_BEGIN@")

        match = re.search(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", text, re.DOTALL)
        text = text.replace("@NEXUS_END@", "@SOTERIA_END@").replace("@NEXUS_BEGIN@", "@SOTERIA_BEGIN@")
        if "@SOTERIA_BEGIN@" not in text and "TAG_" in text:
            nx = text
        else:
            match = re.search(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", text, re.DOTALL)
            if not match: return False
            nx = match.group(1)
        else: nx = text.split("@SOTERIA_BEGIN@")[-1].split("@SOTERIA_END@")[0]
        if not match: return False
        parts = text.split("@SOTERIA_BEGIN@")
        nx = parts[-1].split("@SOTERIA_END@")[0]
#        nx = match.group(1)
        pyx_file = None; pyx_line = 0; pyx_path = None
        frames = re.findall(r"TAG_FRAME:\s*(.*)", nx)
        def get_tag(t): return (re.findall(rf"TAG_{t}:\s*(.*)", nx, re.IGNORECASE) or ["N/A"])[0].strip()
        
        # 1. Coleta de Tags Brutas
        level = get_tag('LEVEL')
        motivo = get_tag('MOTIVO')
        detail = get_tag('DETAIL').replace('@NEXUS_END@', '').strip()
        pid = get_tag('PID')
        comando = get_tag('COMMAND')
        
        if os.environ.get('VULCAN_DEBUG') == '1':
             print(f"{color}!" * 65 + f"\n SOTÉRIA: RESGATE DE EXECUÇÃO ATIVO\n" + "!" * 65 + self.reset)
        
        # --- FIX 2: NEXUS HADES MAPPING (Tradução de Causa Raiz) ---
        if detail == "N/A":
            if "0xc0000005" in motivo.lower():
                detail = "Access Violation: Tentativa de leitura/escrita em endereço inválido (NULL Pointer)."
            elif "0xc0000094" in motivo.lower():
                detail = "Integer Division by Zero: O hardware detectou uma divisão por zero."
            elif "0xc0000374" in motivo.lower():
                detail = "Heap Corruption: O banco de memória nativo foi violado (Double Free detectado)."
            else:
                detail = f"Falha Nativa: {motivo}"

        if detail == "N/A" and "OOM" in text:
            detail = "Internal Arena Overflow: O TNSE esgotou sua memoria reservada."

        # 2. Renderização do Cabeçalho
        if level == "EXIT_AUDIT":
            color = self.cyan
            print(f"{color}?" * 65 + f"\n SOTÉRIA: RASTREIO DE ENCERRAMENTO LÓGICO\n" + "?" * 65 + self.reset)
        else:
            color = self.red if level == "FATAL" else self.ylw
        print(f"{color}!" * 65 + f"\n SOTÉRIA: RELATÓRIO SUPREMO DE EVIDÊNCIAS ({level})\n" + "!" * 65 + self.reset)
        
        print(f"{self.cyan}■ INCIDENTE TÉCNICO:{self.reset}")
        print(f"  DETALHE: {self.white}{detail}{self.reset}")
        print(f"  PID: {self.white}{pid}{self.reset} | COMANDO: {self.gray}{comando}{self.reset}")

        # 3. PONTO DE RUPTURA / TRIANGULAÇÃO
        loc = get_tag('LOCAL')
        r_loc = get_tag('RASTRO_LOC')
        
        if get_tag('MOTIVO') == "N/A" and "Vocabulario" in text:
            detail = "Falha de Inicialização do Motor TNSE (Possível falta de arquivo de Cristal ou Regra)."
        
        # --- FIX 3: FALLBACK DE TRIANGULAÇÃO (Triangula via Pilha se necessário) ---
        if ("N/A" in r_loc or not r_loc) and frames:
            try:
                # Pega o local do primeiro frame (mais recente)
                last_frame = frames[0]
                r_loc = last_frame.split('|')[-1].strip()
            except: pass

        print(f"\n{self.red}■ PONTO DE RUPTURA (ONDE O SISTEMA PAROU):{self.reset}")
        if "N/A" in loc or "0x" in loc:
            print(f"  {self.ylw}💡 TRIANGULAÇÃO: Falha detectada logo após:{self.reset}")
            if ":" in r_loc:
                f, l = r_loc.rsplit(':', 1)
                print(self.get_code_context(f, l, window=4, title="ULTIMO MARCO"))
        else:
            print(f"  LOCALIZAÇÃO: {self.grn}{self.shorten_path(loc)}{self.reset}\n")
            f, l = loc.rsplit(':', 1)
            print(self.get_code_context(f, l, window=2, title="LOCAL DO CRIME"))

        # 4. LEAKS E CADEIA DE CHAMADAS (O resto permanece o mesmo)
        leaks = re.findall(r"TAG_LEAK:\s*(.*)", nx)
        if leaks:
            print(f"\n{self.ylw}■ VAZAMENTOS DE MEMÓRIA (LEAKS):{self.reset}")
            for l in leaks:
                print(f"   ⚠️ {l}")
        
        if frames:
            print(f"\n{self.cyan}■ CADEIA DE ENVOLVIMENTO (COMO CHEGAMOS AQUI):{self.reset}")
            for f in frames:
                pts = f.split('|')
                name, frame_loc = pts[1].strip(), pts[2].strip()
                color_f = self.grn if "src" in frame_loc.lower() else self.gray
                print(f"   {color_f}↳ {name}{self.reset} {self.gray}({self.shorten_path(frame_loc)}){self.reset}")

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
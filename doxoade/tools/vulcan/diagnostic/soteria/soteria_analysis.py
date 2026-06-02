# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/soteria_analysis.py
import os, sys, re
import datetime

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
        if not text: return False

        # 1. Normalização
        normalized = text.replace("@NEXUS_BEGIN@", "@SOTERIA_BEGIN@").replace("@NEXUS_END@", "@SOTERIA_END@")
        normalized_text = text.replace("@NEXUS_BEGIN@", "@SOTERIA_BEGIN@").replace("@NEXUS_END@", "@SOTERIA_END@")
#        normalized_text = text.replace("@NEXUS_BEGIN@", "@SOTERIA_BEGIN@") # <--- ADICIONE ESTA LINHA
        blocks = re.findall(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", normalized_text, re.DOTALL)
#        blocks = re.findall(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", normalized, re.DOTALL)
        
        if blocks: nx = blocks[-1]
        elif "TAG_" in normalized_text: nx = normalized_text
        else: return False

        # 2. Extração Atômica de Tags
        tags = {m.group(1).upper(): m.group(2).strip() for m in re.finditer(r"TAG_(\w+):\s*(.*)", nx)}

        def get_tag(t, default="N/A"):
            return tags.get(t.upper(), default)

        # 4. Oráculo de Causa Raiz (Tradução de NTSTATUS e Sinais)
        level = get_tag('LEVEL', 'FATAL')
        detail = tags.get('DETAIL', 'N/A').replace('@SOTERIA_END@', '').strip()
        motivo = tags.get('MOTIVO', 'N/A')
        
        if detail == "N/A":
            if "0xc0000005" in motivo.lower(): detail = "Access Violation (Ponteiro Inválido)"
            elif "0xc0000094" in motivo.lower(): detail = "Integer Division by Zero"
            else: detail = f"Falha Nativa: {motivo}"
            
            hex_map = {
                "0xc0000005": "Access Violation: Tentativa ilegal de acessar a RAM (NULL Pointer).",
                "0xc0000094": "Integer Division by Zero: Divisão aritmética inválida detectada.",
                "0xc0000374": "Heap Corruption: Banco de memória violado (Double Free ou Overflow).",
                "0xc00000fd": "Stack Overflow: A pilha de recursão explodiu."
            }
            for code, msg in hex_map.items():
                if code in motivo.lower():
                    detail = msg
                    break
            
            if detail == "N/A":
                if "OOM" in normalized_text: detail = "Internal Arena Overflow: Memória Vulcan exaurida."
                elif "Vocabulario" in normalized_text: detail = "Erro de Carga: Arquivo de regras ou cristal ausente."
                else: detail = f"Falha Nativa Não Mapeada: {motivo}"
        # 5. Renderização da Interface Tática
        color = self.cyan if level == "EXIT_AUDIT" else (self.red if level == "FATAL" else self.ylw)
        header_msg = "RASTREIO DE ENCERRAMENTO" if level == "EXIT_AUDIT" else f"RELATÓRIO SUPREMO DE EVIDÊNCIAS ({level})"
        
        print(f"\n{color}" + "!" * 80)
        print(f" SOTÉRIA: {header_msg} ".center(80))
        print("!" * 80 + self.reset)

        print(f"\n{self.cyan}■ INCIDENTE TÉCNICO:{self.reset}")
#        print(f"  {self.white}LAUDO   :{self.reset} {self.white}{detail}{self.reset}")
#        print(f"  {self.white}CONTEXTO:{self.reset} PID {get_tag('PID')} | CMD: {self.gray}{get_tag('COMMAND')}{self.reset}")
        print(f"  {self.cyan}LAUDO   :{self.reset} {self.white}{detail}{self.reset}")
        print(f"  {self.cyan}CONTEXTO:{self.reset} PID {tags.get('PID', '?')} | {tags.get('COMMAND', '?')}")

        # 6. Triangulação de Precisão (Onde o sistema parou)
        loc = get_tag('LOCAL')
        r_loc = get_tag('RASTRO_LOC')
        frames = re.findall(r"TAG_FRAME: \d+ \| (.*?) \| (.*)", nx)

        # Fallback: Se o local exato sumiu no crash, tenta o topo da pilha (Frame 0)
        if ("N/A" in r_loc or not r_loc) and frames:
            r_loc = frames[0][1]

        print(f"\n{self.red}■ PONTO DE RUPTURA:{self.reset}")
        
        # Resolve se mostra local exato ou último marco conhecido
        target_loc = loc if loc != "N/A" and "0x" not in loc else r_loc
        label = "LOCAL DO CRIME" if loc == target_loc else "ÚLTIMO MARCO CONHECIDO"

        if ":" in target_loc:
            try:
                f_path, l_num = target_loc.rsplit(':', 1)
                # get_code_context deve ser o método que busca o arquivo e a linha
                print(self.get_code_context(f_path, l_num, window=3, title=label))
            except:
                print(f"  {self.ylw}⚠️  Falha na leitura física de: {target_loc}{self.reset}")
        else:
            print(f"  {self.gray}Ponto de ruptura puramente nativo (sem rastro de código disponível).{self.reset}")

        # 7. Cadeia de Envolvimento (Stack Trace)
        if frames:
            print(f"\n{self.cyan}■ CADEIA DE ENVOLVIMENTO (ANATOMIA DA QUEDA):{self.reset}")
            for idx, (func_name, frame_loc) in enumerate(frames):
                # Destaque verde para código do projeto, cinza para sistema
                f_color = self.grn if any(x in frame_loc.lower() for x in ["src", "doxoade", self.root.lower()]) else self.gray
                print(f"    {self.gray}[{idx}]{self.reset} {f_color}↳ {func_name:<25}{self.reset} {self.gray}({os.path.basename(frame_loc)}){self.reset}")

        # 8. Vazamentos (Leaks)
        leaks = re.findall(r"TAG_LEAK:\s*(.*)", nx)
        if leaks:
            print(f"\n{self.ylw}■ VAZAMENTOS DE MEMÓRIA (DETECTOR HADES):{self.reset}")
            for l in leaks:
                print(f"   ⚠️ {l}")

        print(f"\n{color}" + "─" * 80 + self.reset + "\n")
        return True

if __name__ == "__main__":
    if sys.platform == 'win32':
        import io; sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
        os.system('')
    raw = sys.stdin.read()
    if raw:
        f = SoteriaForensic()
        if not f.process_pipe(raw): sys.stdout.write(raw)
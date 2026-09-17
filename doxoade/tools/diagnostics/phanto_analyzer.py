# doxoade/tools/diagnostics/phanto_analyzer.py
"""
👻 PHANTO_CRISIS ANALYZER — Leitor e Formatador de Laudos Forenses.
Lê o arquivo phanto_crisis.ndjson e gera um relatório estruturado (W5).
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore: RED = GREEN = YELLOW = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style: BRIGHT = DIM = RESET_ALL = ""

def get_ndjson_path() -> Path:
    user_dir = Path.home() / ".config" / "lite-xl"
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            user_dir = Path(appdata) / "lite-xl"
    
    return user_dir / ".doxoade" / "diagnostics" / "phanto_crisis.ndjson"

def analyze_and_report() -> None:
    ndjson_path = get_ndjson_path()
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
    print("👻 PHANTO_CRISIS — LAUDO FORENSE DE ERROS ISOLADOS")
    print(f"{'═' * 75}{Style.RESET_ALL}\n")
    
    if not ndjson_path.exists():
        print(f"  {Fore.GREEN}✔ Nenhum erro crítico capturado no buffer NDJSON.{Fore.RESET}")
        print(f"  {Fore.LIGHTBLACK_EX}Caminho verificado: {ndjson_path}{Fore.RESET}\n")
        return

    print(f"  {Fore.WHITE}Arquivo Alvo:{Fore.RESET} {ndjson_path}")
    
    errors_by_module: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    total_errors = 0

    try:
        with open(ndjson_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    errors_by_module[entry.get("module", "unknown")].append(entry)
                    total_errors += 1
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"  {Fore.RED}✖ Falha ao ler o arquivo NDJSON: {e}{Fore.RESET}\n")
        return

    print(f"  {Fore.WHITE}Total de Eventos Capturados:{Fore.RESET} {Style.BRIGHT}{total_errors}{Style.RESET_ALL}\n")

    # Ordena módulos por quantidade de erros (maior primeiro)
    sorted_modules = sorted(errors_by_module.items(), key=lambda x: len(x[1]), reverse=True)

    for module, entries in sorted_modules:
        print(f"{Fore.MAGENTA}{Style.BRIGHT}📌 MÓDULO: {module}{Style.RESET_ALL} ({len(entries)} ocorrências)")
        
        # Pega o erro mais recente para detalhar
        latest = entries[-1]
        print(f"  {Fore.YELLOW}• O QUE? (Erro):{Fore.RESET} {latest.get('error', 'Desconhecido')}")
        print(f"  {Fore.YELLOW}• ONDE? (Arquivo Ativo):{Fore.RESET} {latest.get('context', {}).get('active_file', 'N/A')}")
        print(f"  {Fore.YELLOW}• QUANDO? (Timestamp):{Fore.RESET} {latest.get('ts_iso', 'N/A')}")
        
        # Exibe um snippet do traceback (últimas 3 linhas relevantes)
        tb = latest.get("traceback", "")
        tb_lines = [l.strip() for l in tb.split("\n") if l.strip() and not l.startswith("stack traceback:")]
        if tb_lines:
            print(f"  {Fore.YELLOW}• POR QUÊ? (Snippet do Traceback):{Fore.RESET}")
            for line in tb_lines[-3:]:
                print(f"      {Fore.LIGHTBLACK_EX}↳ {line}{Fore.RESET}")
        print(f"  {Fore.LIGHTBLACK_EX}{'─' * 70}{Fore.RESET}\n")

    print(f"{Fore.CYAN}💡 DICA: Para limpar o histórico de erros, delete o arquivo phanto_crisis.ndjson{Fore.RESET}\n")

if __name__ == "__main__":
    analyze_and_report()

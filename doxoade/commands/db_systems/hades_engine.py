# doxoade/doxoade/commands/db_systems/hades_engine.py
import sqlite3
import os
from doxoade.tools.doxcolors import Fore, Style

class HadesEngine:
    def __init__(self, db_path):
        self.db_path = os.path.abspath(db_path)

    def run_full_diagnosis(self, logger):
        click_echo = __import__('click').echo
        click_echo(f"{Fore.YELLOW}🔬 [HADES] Iniciando Autópsia em: {os.path.basename(self.db_path)}{Style.RESET_ALL}")
        
        try:
            # Conexão direta para diagnóstico físico
            conn = sqlite3.connect(self.db_path)
            curr = conn.cursor()

            # 1. Integridade Física (Crucial para quedas de energia no N2808)
            curr.execute("PRAGMA integrity_check;")
            status = curr.fetchone()[0]
            if status == "ok":
                click_echo(f"   {Fore.GREEN}✔ Integridade de Disco: OK{Style.RESET_ALL}")
            else:
                logger.add_finding('CRITICAL', f"Banco Corrompido: {status}", category='DATABASE', file=self.db_path)
                click_echo(f"   {Fore.RED}✘ Falha Crítica: {status}{Style.RESET_ALL}")

            # 2. Análise de Tabelas e Bloat (Inchaço)
            curr.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [t[0] for t in curr.fetchall() if t[0] != 'sqlite_sequence']
            
            click_echo(f"\n   {Fore.WHITE}{Style.BRIGHT}Topologia detectada:{Style.RESET_ALL}")
            for table in tables:
                curr.execute(f"SELECT count(*) FROM {table}")
                rows = curr.fetchone()[0]
                
                # Checa se há índices para essa tabela
                curr.execute(f"PRAGMA index_list({table});")
                has_index = len(curr.fetchall()) > 0
                idx_status = f"{Fore.GREEN}[INDEXED]" if has_index else f"{Fore.RED}[NO INDEX]"
                
                click_echo(f"   • {table:<15} : {rows:>6} registros {idx_status}{Style.RESET_ALL}")
                
                # Validação específica Doxarchive: Tabela 'articles' sem índice é fatal para o Searcher
                if table == 'articles' and not has_index:
                    logger.add_finding('ERROR', "Tabela 'articles' sem índices. Buscas por ID serão lentas.", category='PERFORMANCE', file=self.db_path)

            # 3. Amostragem Semântica (Check de Corrupção de BLOB)
            if 'articles' in tables:
                click_echo(f"\n   {Fore.CYAN}🧪 Validando integridade dos BLOBs (Zstd)...{Style.RESET_ALL}")
                curr.execute("SELECT prose FROM articles LIMIT 1")
                sample = curr.fetchone()
                if sample and isinstance(sample[0], bytes):
                    click_echo(f"   {Fore.GREEN}✔ Amostra de BLOB: OK ({len(sample[0])} bytes binários){Style.RESET_ALL}")
                else:
                    logger.add_finding('WARNING', "Tabela 'articles' contém dados nulos ou em formato inesperado.", category='DATA-INTEGRITY')

            conn.close()
        except Exception as e:
            click_echo(f"{Fore.RED}🚨 ERRO NO MOTOR HADES: {e}{Style.RESET_ALL}")
            logger.add_finding('CRITICAL', f"Hades Engine Crash: {e}", category='SYSTEM')
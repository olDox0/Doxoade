"""
NEURAL PROFILER v2.0 (Deep Scan).
Gera relatórios detalhados de performance com visualização de gargalos.
"""
import cProfile
import pstats
import io
import os
from pstats import SortKey
from colorama import Fore, Style

class NeuralProfiler:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.pr = cProfile.Profile() if enabled else None

    def __enter__(self):
        if self.enabled:
            self.pr.enable()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.enabled:
            self.pr.disable()
            self._gerar_relatorio_detalhado()

    def _gerar_relatorio_detalhado(self):
        s = io.StringIO()
        # Ordena por tempo cumulativo para ver o fluxo
        ps = pstats.Stats(self.pr, stream=s).sort_stats(SortKey.CUMULATIVE)
        
        print(Fore.CYAN + "\n" + "="*60)
        print(f"📊 RELATÓRIO DE PERFORMANCE (CRONOS v2.0)")
        print("="*60 + Style.RESET_ALL)
        
        # Pega os dados brutos
        ps.print_stats(20) # Top 20 funções
        
        # Parse manual para criar tabela bonita
        print(f"\n{Fore.YELLOW}{'CHAMADAS':<10} | {'TOTAL (s)':<10} | {'POR CHAMADA':<12} | {'FUNÇÃO'}{Style.RESET_ALL}")
        print("-" * 80)
        
        # Uma heurística para pegar as estatísticas internas
        # (O pstats não facilita acesso direto aos dados, então filtramos a string ou usamos func_list)
        # Vamos focar na análise heurística que é mais útil:
        
        total_calls = ps.total_calls
        total_time = ps.total_tt
        
        print(f"Total de Chamadas: {total_calls}")
        print(f"Tempo Total de CPU: {total_time:.4f}s")
        
        print(Fore.CYAN + "\n🔍 DIAGNÓSTICO DE GARGALOS:" + Style.RESET_ALL)
        
        output = s.getvalue()
        
        # Detectores de Padrão
        gargalos = []
        
        if "dot" in output or "matmul" in output:
            gargalos.append((Fore.RED + "[CRÍTICO] Álgebra Linear", "O processador está saturado com multiplicações de matrizes. (Normal para IA)"))
        
        if "method 'reduce' of 'numpy.ufunc'" in output:
            gargalos.append((Fore.YELLOW + "[ALTO] Reduções NumPy", "Muitas operações de soma/max (Softmax/Loss)."))
            
        if "built-in method io.open" in output:
             gargalos.append((Fore.MAGENTA + "[I/O] Acesso a Disco", "Leitura/Escrita de arquivos lenta."))
             
        if "method 'append' of 'list'" in output:
             gargalos.append((Fore.YELLOW + "[MÉDIO] Listas Python", "Uso excessivo de listas dinâmicas. Tente pré-alocar com NumPy."))

        if "get_state" in output or "quantize" in output:
             gargalos.append((Fore.BLUE + "[INFO] Overhead de Compressão", "A quantização 8-bit está consumindo tempo."))

        if not gargalos:
            print("   ✅ Nenhum gargalo óbvio detectado (Distribuição equilibrada).")
        else:
            for titulo, desc in gargalos:
                print(f"   {titulo}: {desc}")

        print(Fore.CYAN + "="*60 + Style.RESET_ALL)
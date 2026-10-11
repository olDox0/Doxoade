# boot_forensic.py
import sys
import os
import tracemalloc
import cProfile
import pstats
import io
import runpy

def main():
    print("🔬 Iniciando Forense de Boot do Doxoade (runpy)...")
    
    # 1. Inicia o tracemalloc rastreando até 25 frames de profundidade 
    # (isso nos dá a linha exata e a cadeia de imports que alocou a memória)
    tracemalloc.start(25)
    snap0 = tracemalloc.take_snapshot()
    
    # 2. Inicia o profiler de CPU
    pr = cProfile.Profile()
    pr.enable()
    
    # 3. Executa o Doxoade exatamente como `python -m doxoade --help`
    # Isso garante que o __main__.py, o bootstrap do Vulcan e o Click sejam carregados.
    sys.argv = ['doxoade', '--help']
    try:
        runpy.run_module('doxoade', run_name='__main__', alter_sys=True)
    except SystemExit:
        pass # O Click faz sys.exit(0) após exibir o --help
    except Exception as e:
        print(f"❌ Erro durante execução: {e}")
        
    pr.disable()
    snap1 = tracemalloc.take_snapshot()
    
    # ==========================================
    # 🧠 ANÁLISE DE MEMÓRIA (Heap Python)
    # ==========================================
    print("\n" + "="*80)
    print("🧠 TOP 20 LINHAS QUE MAIS ALOCARAM MEMÓRIA (Heap Python)")
    print("="*80)
    stats_mem = snap1.compare_to(snap0, 'lineno')
    for stat in stats_mem[:20]:
        print(stat)
        
    # ==========================================
    # ⏱️ ANÁLISE DE CPU (Tempo de Execução)
    # ==========================================
    print("\n" + "="*80)
    print("⏱️ TOP 25 FUNÇÕES MAIS LENTAS NO BOOT (CPU Cumulativo)")
    print("="*80)
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(25)
    print(s.getvalue())
    
    # ==========================================
    # 💾 EXPORTAÇÃO PARA VISUALIZAÇÃO GRÁFICA
    # ==========================================
    pr.dump_stats("boot_forensic.prof")
    print("\n💾 Dossiê cProfile salvo em: boot_forensic.prof")
    print("   👉 Dica: Instale 'snakeviz' (pip install snakeviz) e rode:")
    print("      snakeviz boot_forensic.prof")

if __name__ == "__main__":
    main()

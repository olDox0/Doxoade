# doxoade/diagnostic/telemetry_trace.py
import os
import sys
import sqlite3
from doxoade.database import get_db_connection
from doxoade.chronos import chronos_recorder

def trace_telemetry_flow():
    print("🔬 [DIAGNOSTICO] Iniciando rastreio de fluxo de telemetria...")
    
    # 1. Verificar conexão
    conn = get_db_connection()
    try:
        res = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_history'").fetchone()
        if res:
            print("   [OK] Tabela command_history existe.")
        else:
            print("   [FALHA] Tabela command_history NÃO encontrada!")
            return
            
        # 2. Verificar contagem atual
        count_before = conn.execute("SELECT COUNT(*) FROM command_history").fetchone()[0]
        print(f"   [INFO] Registros antes do teste: {count_before}")

        # 3. Simular ciclo de vida do Chronos
        print("   [DEBUG] Simulando start_command...")
        class MockCtx:
            invoked_subcommand = "test_diag"
        chronos_recorder.start_command(MockCtx())
        
        import time
        time.sleep(0.1)
        
        print("   [DEBUG] Simulando end_command (Commit forçado)...")
        chronos_recorder.end_command(0, 100.0)
        
        # 4. Verificar se gravou
        count_after = conn.execute("SELECT COUNT(*) FROM command_history").fetchone()[0]
        if count_after > count_before:
            print(f"   [SUCESSO] O Chronos consegue gravar no banco. Atual: {count_after}")
        else:
            print("   [ERRO] O comando end_command rodou mas o registro NÃO apareceu no banco.")
            
    except Exception as e:
        print(f"   [ERRO CRITICO] Falha no rastreio: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    trace_telemetry_flow()
# clean_db.py
import sqlite3
import os

DB_PATH = os.path.expanduser("~/.doxoade/doxoade.db")

def limpar():
    if not os.path.exists(DB_PATH):
        print("Banco não encontrado.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print("🔍 Buscando memórias tóxicas...")
    
    # Deleta entradas com tokens de sistema ou vazias
    c.execute("""
        DELETE FROM solutions 
        WHERE stable_content LIKE '%<UNK>%' 
           OR stable_content LIKE '%ENDMARKER%'
           OR stable_content LIKE '%:%' AND length(stable_content) < 15
    """)
    
    removidos = c.rowcount
    conn.commit()
    conn.close()
    
    if removidos > 0:
        print(f"✅ Exorcismo completo: {removidos} memórias ruins deletadas.")
    else:
        print("✨ O banco de dados já está limpo.")

if __name__ == "__main__":
    limpar()
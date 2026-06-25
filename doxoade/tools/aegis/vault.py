import hashlib
import os
from datetime import datetime, timedelta
from doxoade.core_database import get_db_connection
import doxoade.tools.aegis.nexus_db as sqlite3

from doxoade.tools.alexandria.engine import alexandria_write
class NexusVault:
    @staticmethod
    def set_password(password):
        salt = os.urandom(16).hex()
        # PBKDF2 para segurança industrial
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
        
        conn = get_db_connection()
        alexandria_write("INSERT OR REPLACE INTO vault_config (key, value, salt) VALUES ('master_pwd', ?, ?)", (pwd_hash, salt))
        conn.commit()

    @staticmethod
    def unlock(password, hours=24):
        """Abre o sistema por um período determinado."""
        conn = get_db_connection()
        res = conn.execute("SELECT value, salt FROM vault_config WHERE key='master_pwd'").fetchone()
        if not res: return False
        
        # Verifica a senha
        check_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), res['salt'].encode(), 100000).hex()
        if check_hash == res['value']:
            # Define a expiração (None = Sempre Aberto)
            expiry = (datetime.now() + timedelta(hours=hours)).isoformat() if hours > 0 else "NEVER"
            alexandria_write("DELETE FROM vault_session")
            alexandria_write("INSERT INTO vault_session (unlocked_until) VALUES (?)", (expiry,))
            conn.commit()
            return True
        return False

    @staticmethod
    def is_unlocked():
        """Verifica se o cofre está aberto no momento."""
        try:
            conn = get_db_connection()
            # Se não houver senha definida, está sempre "aberto"
            has_pwd = conn.execute("SELECT 1 FROM vault_config WHERE key='master_pwd'").fetchone()
            if not has_pwd: return True
            
            session = conn.execute("SELECT unlocked_until FROM vault_session").fetchone()
            if not session: return False
            
            if session['unlocked_until'] == "NEVER": return True
            
            # Verifica se expirou
            expiry = datetime.fromisoformat(session['unlocked_until'])
            return datetime.now() < expiry
        except sqlite3.OperationalError:
            # Se a tabela não existe, o sistema ainda não foi protegido.
            return True

    @staticmethod
    def lock():
        """Fecha o cofre imediatamente."""
        conn = get_db_connection()
        alexandria_write("DELETE FROM vault_session")
        conn.commit()

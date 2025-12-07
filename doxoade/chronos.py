import sys
import os
import uuid
import json
import difflib
from datetime import datetime, timezone
from .database import get_db_connection

class Chronos:
    """O Guardião do Tempo: Registra ações e mutações."""
    
    def __init__(self):
        self.session_uuid = str(uuid.uuid4())
        self.command_id = None
        self.conn = get_db_connection()

    def start_command(self, ctx):
        """Registra o início de um comando CLI."""
        timestamp = datetime.now(timezone.utc).isoformat()
        command_name = ctx.command.name if ctx.command else "unknown"
        # Reconstrói a linha de comando exata usada
        full_command = "doxoade " + " ".join(sys.argv[1:])
        working_dir = os.getcwd()

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO command_history 
            (session_uuid, timestamp, command_name, full_command_line, working_dir, exit_code)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (self.session_uuid, timestamp, command_name, full_command, working_dir, -1)) # -1 = Running
        
        self.command_id = cursor.lastrowid
        self.conn.commit()
        return self.command_id

    def end_command(self, exit_code, duration_ms):
        """Atualiza o comando com o resultado final."""
        if not self.command_id: return
        
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE command_history 
            SET exit_code = ?, duration_ms = ?
            WHERE id = ?
        """, (exit_code, duration_ms, self.command_id))
        self.conn.commit()

    def log_file_change(self, file_path, old_content, new_content, operation='MODIFY'):
        """Registra uma alteração de arquivo (Diff)."""
        if not self.command_id: return

        # Gera o Diff unificado
        diff = ""
        if old_content and new_content:
            diff_lines = difflib.unified_diff(
                old_content.splitlines(),
                new_content.splitlines(),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm=""
            )
            diff = "\n".join(diff_lines)
        elif operation == 'CREATE':
            diff = "[ARQUIVO CRIADO]"
        elif operation == 'DELETE':
            diff = "[ARQUIVO DELETADO]"

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO file_audit (command_id, file_path, operation_type, diff_content)
            VALUES (?, ?, ?, ?)
        """, (self.command_id, file_path, operation, diff))
        self.conn.commit()

# Instância Global (Singleton)
chronos_recorder = Chronos()
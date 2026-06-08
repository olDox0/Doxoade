# -*- coding: utf-8 -*-
# doxoade/tools/telemetry_tools/logger.py
import time
import os
import sys
import json
import click
import hashlib
import inspect
from datetime import datetime

def chief_heartbeat(subsystem: str, action: str, details: dict):
    """Registra batimentos cardíacos com captura automática de contexto."""
    try:
        # Tenta capturar quem chamou (Triangulação Híbrida)
        if subsystem == "VULCAN" and "INVOCATION" in action:
            frame = inspect.currentframe()
            # Sobe 3 níveis: logger -> bridge -> executor
            try:
                caller = frame.f_back.f_back.f_back
                details['caller_context'] = {
                    'func': caller.f_code.co_name,
                    'file': os.path.basename(caller.f_code.co_filename),
                    'line': caller.f_lineno
                }
            except: pass

        from doxoade.database import get_db_connection
        import json
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO operational_logs (timestamp, subsystem, action, data, pid)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), subsystem.upper(), action.upper(), 
              json.dumps(details, ensure_ascii=False), os.getpid()))
        # 2. Auto-Pruning: Mantém apenas os últimos 50 eventos operacionais
        conn.execute('''
            DELETE FROM operational_logs 
            WHERE id NOT IN (SELECT id FROM operational_logs ORDER BY id DESC LIMIT 50)
        ''')
        conn.commit()
        conn.close()
    except Exception:
        pass

class ExecutionLogger:
    def __init__(self, command_name, path, arguments):
        self.command_name = command_name
        self.path = path
        self.arguments = arguments
        self.start_time = time.monotonic()
        self.results = {'summary': {'critical': 0, 'errors': 0, 'warnings': 0, 'info': 0}, 'findings': []}
        self.is_json_output = '--format=json' in sys.argv or (isinstance(arguments, dict) and arguments.get('output_format') == 'json')
        self.start_dt = datetime.now().strftime('%H:%M:%S')
        
        if not self.is_json_output:
            from doxoade.tools.doxcolors import Fore, Style
            click.echo(f"{Fore.CYAN}{Style.DIM}[{self.start_dt}] Executando {command_name}...{Style.RESET_ALL}")

    def add_finding(self, severity, message, category='UNCATEGORIZED', file=None, line=None, **kwargs):
        severity = severity.upper()
        category = category.upper()
        f_path = os.path.relpath(file, self.path) if file and os.path.isabs(file) else file
        
        finding_hash = None
        if f_path and line and message:
            unique_str = f"{f_path}:{line}:{message}"
            finding_hash = hashlib.sha256(unique_str.encode('utf-8', 'ignore')).hexdigest()

        finding = {
            'severity': severity, 'category': category, 'message': message,
            'hash': finding_hash, 'file': f_path, 'line': line
        }
        finding.update(kwargs)
        self.results['findings'].append(finding)
        
        sev_key = severity.lower() if severity.lower() in self.results['summary'] else 'info'
        self.results['summary'][sev_key] = self.results['summary'].get(sev_key, 0) + 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import json
        import zlib
        import traceback
        from doxoade.rescue import activate_protocol
        
        execution_time_ms = (time.monotonic() - self.start_time) * 1000
        exit_code = 0

        if exc_type is not None:
            if issubclass(exc_type, SystemExit):
                exit_code = exc_val.code if isinstance(exc_val.code, int) else (1 if exc_val.code else 0)
            elif not issubclass(exc_type, KeyboardInterrupt):
                exit_code = 1 # Erro de runtime Python

        # [MODO BRUTO] Se o resgate estiver desativado, não chama o Lazarus
        if os.environ.get('DOXOADE_RESCUE') == '0':
            return # Deixa o Python imprimir o traceback normal no console
            
        if exc_type is not None and not issubclass(exc_type, (SystemExit, KeyboardInterrupt)):
            # Só chama o Lazarus se o resgate estiver ATIVO (padrão)
            error_data = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            activate_protocol(error_data, exit_code=exit_code)

        # --- GERAÇÃO DE PAYLOAD CHIEF-GOLD ---
        compressed_payload = None
        try:
            payload_data = {
                "input": {"args": self.arguments},
                "output": {
                    "summary": self.results['summary'],
                    "findings": self.results['findings'][:100] # Limite para evitar DB gigante
                }
            }
            raw_payload = json.dumps(payload_data, ensure_ascii=False).encode('utf-8')
            compressed_payload = zlib.compress(raw_payload)
        except Exception: pass

        try:
            from doxoade.tools.db_utils import _log_execution, stop_persistence_worker
            # Envia para o banco
            _log_execution(
                self.command_name, self.path, self.results,
                self.arguments, execution_time_ms,
                exit_code=exit_code, payload=compressed_payload
            )
            stop_persistence_worker()
        except Exception: pass

        if not self.is_json_output:
            from doxoade.tools.doxcolors import Fore, Style
            duration = (time.monotonic() - self.start_time)
            color = Fore.GREEN if exit_code == 0 else Fore.RED
            label = "✔ Sucesso" if exit_code == 0 else "✘ Falha"
            click.echo(f'{color}{Style.DIM}[{self.command_name}] {label} em {duration:.3f}s{Style.RESET_ALL}')
            
            
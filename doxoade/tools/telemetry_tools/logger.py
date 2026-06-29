# -*- coding: utf-8 -*-
# doxoade/tools/telemetry_tools/logger.py

import time
import os
import sys
import json
import click
import hashlib
import inspect
from threading import RLock
from datetime import datetime
from doxoade.tools.alexandria.engine import alexandria_write

_CHIEF_CONN = None
_HEARTBEAT_LOCK = RLock()
#_HEARTBEAT_LOCK = False
_HEARTBEAT_CACHE = {}
_LOG_BUFFER = []
_LAST_FLUSH_TIME = time.monotonic()
BUFFER_SIZE_LIMIT = 50   # Descarrega ao acumular 50 logs
BUFFER_TIME_LIMIT = 2.0  # Ou a cada 2 segundos no máximo
THROTTLE_INTERVAL = 2.0

def chief_heartbeat(subsystem: str, action: str, details: dict):
    """Registra batimentos cardíacos com vazão otimizada via Throttling por Hash."""
    from doxoade.tools.alexandria.engine import alexandria_write

    global _CHIEF_CONN, _HEARTBEAT_CACHE

    # Tenta adquirir o lock — se outro thread já está gravando, descarta este log
    if not _HEARTBEAT_LOCK.acquire(blocking=False):
        return

    try:
        now_time = time.monotonic()
        subsystem_upper = subsystem.upper()
        action_upper = action.upper()

        # --- FILTRAGEM DE ALTA VAZÃO (COMPLIANCE PASC 6.4) ---
        cache_key = f"{subsystem_upper}:{action_upper}"
        if cache_key in _HEARTBEAT_CACHE:
            last_logged, last_details_hash = _HEARTBEAT_CACHE[cache_key]
            if (now_time - last_logged) < THROTTLE_INTERVAL:
                current_details_str = str(details.get('caller_context', '')) + str(details.get('category', ''))
                current_hash = hashlib.md5(current_details_str.encode('utf-8', 'ignore')).hexdigest()
                if current_hash == last_details_hash:
                    return

        # 1. Triangulação Híbrida (VULCAN/SHADOW INVOCATION)
        if (subsystem_upper in ["VULCAN", "SHADOW"]) and ("IN" in action_upper or "ENTER" in action_upper):
            frame = inspect.currentframe()
            try:
                caller = frame.f_back.f_back.f_back
                if caller:
                    details['caller_context'] = {
                        'func': caller.f_code.co_name,
                        'file': os.path.basename(caller.f_code.co_filename),
                        'line': caller.f_lineno
                    }
            except Exception as e:
                import logging as _dox_log
                _dox_log.error(f"[INFRA] chief_heartbeat: {e}")

        # Atualiza cache
        details_str = str(details.get('caller_context', '')) + str(details.get('category', ''))
        details_hash = hashlib.md5(details_str.encode('utf-8', 'ignore')).hexdigest()
        _HEARTBEAT_CACHE[cache_key] = (now_time, details_hash)

        # 2. Singleton de Conexão
        if _CHIEF_CONN is None:
            from doxoade.core_database import get_db_connection
            _CHIEF_CONN = get_db_connection()

        alexandria_write(
            'INSERT INTO operational_logs (timestamp, subsystem, action, data, pid) VALUES (?, ?, ?, ?, ?)',
            (datetime.now().isoformat(), subsystem_upper, action_upper,
             json.dumps(details, ensure_ascii=False), os.getpid())
        )

        if os.getpid() % 100 == 0:
            alexandria_write(
                'DELETE FROM operational_logs WHERE id NOT IN (SELECT id FROM operational_logs ORDER BY id DESC LIMIT 2000)'
            )

    except Exception as e:
        _CHIEF_CONN = None
        if os.environ.get('VULCAN_VERBOSE') == '1':
            print(f"\x1b[33m [LOG-FAIL] {subsystem}:{action} -> {e}\x1b[0m")
    finally:
        _HEARTBEAT_LOCK.release()
        
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
        import click
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
            
        if exc_type is not None and (not issubclass(exc_type, (SystemExit, KeyboardInterrupt))):
            if not issubclass(exc_type, (click.exceptions.Exit, click.exceptions.Abort)):
                error_data = ''.join(traceback.format_exception(exc_type, exc_val, exc_tb))
                from doxoade.rescue import activate_protocol
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

# -*- coding: utf-8 -*-
import time
import os
import sys
import hashlib
from datetime import datetime
import click

# PASC-6.6: Imports movidos para dentro do __exit__ para evitar circularidade e acelerar boot

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
        """Finaliza a execução e sela o log com tempo e exit_code reais."""
        execution_time_ms = (time.monotonic() - self.start_time) * 1000
        
        # Determina o status real da execução
        exit_code = 0
        if exc_type is not None:
            if issubclass(exc_type, SystemExit):
                exit_code = exc_val.code if hasattr(exc_val, 'code') else 0
            else:
                exit_code = 1 # Crash por exceção
                self.add_finding('CRITICAL', f'Crash: {exc_type.__name__}', details=str(exc_val))

        try:
            # Importação dinâmica para suporte Core/Silo
            try:
                from doxoade.tools.db_utils import _log_execution, stop_persistence_worker
            except ImportError:
                from .db_utils import _log_execution, stop_persistence_worker

            # Gravação de Ouro
            _log_execution(
                self.command_name, self.path, self.results, 
                self.arguments, execution_time_ms, exit_code=exit_code
            )
            
            # PASC-8.4: Garante que o SQLite finalize a escrita antes do CLI morrer
            stop_persistence_worker()
            
        except Exception:
            pass # Proteção para não quebrar o fluxo principal em falhas de log

        if not self.is_json_output:
            from doxoade.tools.doxcolors import Fore, Style
            duration = (time.monotonic() - self.start_time)
            color = Fore.GREEN if exit_code == 0 else Fore.RED
            label = "✔ Sucesso" if exit_code == 0 else "✘ Falha"
            click.echo(f'{color}{Style.DIM}[{self.command_name}] {label} em {duration:.3f}s{Style.RESET_ALL}')
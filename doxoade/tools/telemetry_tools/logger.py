# doxoade/doxoade/tools/telemetry_tools/logger.py
import time
import os
import sys
import hashlib
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style
import click
from doxoade.tools.db_utils import _log_execution

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
            click.echo(Fore.CYAN + Style.DIM + f'[{self.start_dt}] Executando {command_name}...' + Style.RESET_ALL)

    def add_finding(self, severity, message, category='UNCATEGORIZED', file=None, line=None, **kwargs):
        severity = severity.upper()
        category = category.upper()
        if file and line and message:
            rel_file_path = os.path.relpath(file, self.path) if os.path.isabs(file) else file
            unique_str = f'{rel_file_path}:{line}:{message}'
            finding_hash = hashlib.sha256(unique_str.encode('utf-8', 'ignore')).hexdigest()
        else:
            finding_hash = None
        finding = {'severity': severity, 'category': category, 'message': message, 'hash': finding_hash, 'file': os.path.relpath(file, self.path) if file and os.path.isabs(file) else file, 'line': line}
        finding.update(kwargs)
        self.results['findings'].append(finding)
        if severity == 'CRITICAL':
            self.results['summary']['critical'] += 1
        elif severity == 'ERROR':
            self.results['summary']['errors'] += 1
        elif severity == 'WARNING':
            self.results['summary']['warnings'] += 1
        else:
            self.results['summary']['info'] += 1

    def __enter__(self):
        """Ativa o protocolo Context Manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finaliza a execução e sela o log no banco de dados (Osíris)."""
        execution_time_ms = (time.monotonic() - self.start_time) * 1000
        try:
            _log_execution(self.command_name, self.path, self.results, self.arguments, execution_time_ms)
        except Exception as e:
            print(f'\x1b[0;33m logger - __exit__ - Exception: {e}')
        if exc_type and (not isinstance(exc_val, SystemExit)):
            self.add_finding('CRITICAL', 'Erro fatal interno no motor.', details=f'{exc_type.__name__}: {exc_val}')
        if self.command_name == 'check' and (not self.is_json_output):
            return
        if not self.is_json_output:
            duration = time.monotonic() - self.start_time
            color = Fore.GREEN if duration < 1.5 else Fore.YELLOW if duration < 4.0 else Fore.RED
            click.echo(f'{color}{Style.DIM}[{self.command_name}] Tempo total: {duration:.3f}s{Style.RESET_ALL}')
        return None
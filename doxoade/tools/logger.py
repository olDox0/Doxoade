# doxoade/tools/logger.py
import time
import os
import sys
import hashlib
from datetime import datetime
from colorama import Fore, Style
import click
from .db_utils import _log_execution

class ExecutionLogger:
    def __init__(self, command_name, path, arguments):
        self.command_name = command_name
        self.path = path
        self.arguments = arguments
        self.start_time = time.monotonic()
        self.results = {
            'summary': {'critical': 0, 'errors': 0, 'warnings': 0, 'info': 0},
            'findings': []
        }

        is_json = False
        if isinstance(arguments, dict) and arguments.get('output_format') == 'json': is_json = True
        if '--format=json' in sys.argv: is_json = True

        self.start_dt = datetime.now().strftime("%H:%M:%S")
        if not is_json:
            click.echo(Fore.CYAN + Style.DIM + f"[{self.start_dt}] Executando {command_name}..." + Style.RESET_ALL)

    def add_finding(self, severity, message, category='UNCATEGORIZED', file=None, line=None, details=None, snippet=None, suggestion_content=None, suggestion_line=None, finding_hash=None, import_suggestion=None, dependency_type=None, missing_import=None, suggestion_source=None, suggestion_action=None):
        severity = severity.upper()
        category = category.upper()

        if finding_hash is None and file and line and message:
            rel_file_path = os.path.relpath(file, self.path) if os.path.isabs(file) else file
            unique_str = f"{rel_file_path}:{line}:{message}"
            finding_hash = hashlib.sha256(unique_str.encode('utf-8', 'ignore')).hexdigest()

        finding = {
            'severity': severity, 'category': category, 'message': message, 'hash': finding_hash,
            'file': os.path.relpath(file, self.path) if file and os.path.isabs(file) else file,
            'line': line, 'details': details, 'snippet': snippet,
            'suggestion_content': suggestion_content, 'suggestion_line': suggestion_line,
            'suggestion_source': suggestion_source, 'suggestion_action': suggestion_action,
            'import_suggestion': import_suggestion, 'dependency_type': dependency_type,
            'missing_import': missing_import
        }

        self.results['findings'].append(finding)
        if severity == 'CRITICAL': self.results['summary']['critical'] += 1
        elif severity == 'ERROR': self.results['summary']['errors'] += 1
        elif severity == 'WARNING': self.results['summary']['warnings'] += 1
        elif severity == 'INFO': self.results['summary']['info'] += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time_ms = (time.monotonic() - self.start_time) * 1000
        if exc_type and not isinstance(exc_val, SystemExit):
            self.add_finding('CRITICAL', 'A Doxoade encontrou um erro fatal interno.', category='INTERNAL-ERROR', details=f"{exc_type.__name__}: {exc_val}")
        
        _log_execution(self.command_name, self.path, self.results, self.arguments, execution_time_ms)

        is_json = False
        if isinstance(self.arguments, dict) and self.arguments.get('output_format') == 'json': is_json = True
        if '--format=json' in sys.argv: is_json = True
        
        # [NEXUS SILENCE] Se for o check, encerramos silenciosamente
        # para permitir que o check_utils imprima o sumário Gold.
        if self.command_name == 'check' and '--format=json' not in sys.argv:
            return
            
        if not is_json:
            duration = time.monotonic() - self.start_time
            color = Fore.GREEN if duration < 1.0 else (Fore.YELLOW if duration < 3.0 else Fore.RED)
            click.echo(f"{color}{Style.DIM}[{self.command_name}] Tempo total: {duration:.3f}s{Style.RESET_ALL}")
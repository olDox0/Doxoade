# -*- coding: utf-8 -*-
"""
Hacking Suite - Active Defense & Technical Pentest.
Compliance: MPoT-4, MPoT-5, PASC-6.
"""
from typing import List # PASC-6.1: Import específico
from click import group, echo, pass_context, argument, option
from colorama import Fore, Style
from pathlib import Path
from ..shared_tools import ExecutionLogger

__all__ = ['hack']

@group('hack')
def hack():
    """🛡️ Ethical Hacking & Integrity Defense System."""
    pass

@hack.command('baseline')
@pass_context
def baseline(ctx):
    """Generates and stores the Core Integrity Signature (The Truth)."""
    from ..tools.security_utils import calculate_integrity_hash
    from ..database import get_db_connection

    core_path = Path(__file__).parent.parent
    if not core_path.exists(): raise RuntimeError("Core path missing.")

    with ExecutionLogger('hack:baseline', str(core_path), ctx.params) as _:
        echo(f"{Fore.CYAN}--- [AEGIS] Generating Core Integrity Baseline ---")
        h = calculate_integrity_hash(core_path)
        
        try:
            conn = get_db_connection()
            conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                        ("core_integrity_hash", h))
            conn.commit()
            conn.close()
            echo(f"{Fore.GREEN}✔ Baseline Gold established: {Fore.YELLOW}{h[:16]}...")
        except Exception as e:
            echo(f"{Fore.RED}[ERRO] Failed to save baseline: {e}")

@hack.command('verify')
def verify():
    """Detects if Doxoade source code has been tampered with."""
    from ..tools.security_utils import calculate_integrity_hash
    from ..database import get_db_connection
    import sys

    core_path = Path(__file__).parent.parent
    if not core_path.is_dir():
        raise RuntimeError(f"Integrity Failed: {core_path} is not a directory.")

    current_h = calculate_integrity_hash(core_path)
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = 'core_integrity_hash'").fetchone()
    except Exception: row = None
    finally: conn.close()

    if not row:
        echo(f"{Fore.RED}[!] Error: No baseline found. Run 'doxoade hack baseline' first.")
        return

    if current_h == row[0]:
        echo(f"{Fore.GREEN}🛡️  INTEGRITY OK: Source code matches baseline.{Style.RESET_ALL}")
    else:
        echo(f"{Fore.RED}{Style.BRIGHT}🚨 ALERT: TAMPER DETECTED!")
        echo(f"   Baseline: {Fore.YELLOW}{row[0][:16]}...")
        echo(f"   Current:  {Fore.RED}{current_h[:16]}...")
        echo(f"{Fore.YELLOW}   Action: Run 'doxoade diff -l' to audit changes.")
        sys.exit(1)

@hack.command('pentest')
@argument('target', default='.')
@option('--real', '-r', is_flag=True, help="Proves the vulnerability with a technical PoC.")
@pass_context
def pentest(ctx, target, real):
    """Audits files or directories for exploitable code injection paths."""
    from ..tools.security_utils import simulate_taint_analysis

    with ExecutionLogger('hack:pentest', target, ctx.params) as _:
        echo(f"{Fore.CYAN}--- [RED-TEAM] Starting Technical Pentest on '{target}' ---")
        
        files = _resolve_pentest_files(target)
        found_any = False

        for file_path in files:
            vulns = simulate_taint_analysis(file_path)
            if not vulns: continue
            
            found_any = True
            _render_pentest_results(file_path, vulns, real)

        if not found_any:
            echo(f"{Fore.GREEN}✔ No dynamic execution breaches detected in {len(files)} files.")

def _resolve_pentest_files(target: str) -> List[str]:
    """Expert: Efficiently scans for python files to audit."""
    import os
    if os.path.isfile(target): return [target]
    
    found = []
    for root, _, filenames in os.walk(target):
        # MPoT-17: Ignora infraestrutura
        if any(x in root for x in ['venv', '.git', 'tests']): continue
        for f in filenames:
            if f.endswith('.py'): found.append(os.path.join(root, f))
    return found

def _render_pentest_results(file_path: str, vulns: list, show_real: bool):
    """Expert: Renders finding cards with Chief-Gold standard."""
    from ..tools.security_utils import generate_exploit_poc
    for v in vulns:
        is_high = v['status'] == 'EXPLOITABLE'
        color = Fore.RED if is_high else Fore.CYAN
        echo(f"\n{color}[ {v['status']} ] {file_path}:{v['line']}")
        echo(f"   Sink: {v['function']}() | Impact: {v['impact']}")
        
        if is_high:
            t = v['trigger']
            echo(f"   {Fore.RED}{Style.BRIGHT}VULNERABILITY CONFIRMED!")
            echo(f"   Path: {t['origin']}() -> {t['var']} -> {v['function']}()")
            if show_real:
                poc = generate_exploit_poc(v['function'])
                echo(f"   [!] PoC Payload: {Fore.WHITE}{poc}")
        else:
            echo(f"   {Fore.BLUE}Audit: Controlled sink wrapped by Aegis Sandbox.")
# doxoade/doxoade/__main__.py
# Main satellite
import click
import sys
import os
from pathlib import Path

def _find_project_root():
    current = Path.cwd().resolve()
    for node in [current, *current.parents]:
        if (node / ".doxoade" / "vulcan" / "bin").exists(): return str(node)
    return str(current)

@click.group()
@click.option('--hbc6-audit', is_flag=True, help='Ativa auditoria de fallback do HBC6')
@click.option('--hbc6-audit-verbose', is_flag=True, help='Print em tempo real de cada decisão')
def cli(hbc6_audit, hbc6_audit_verbose):
    if hbc6_audit:
        os.environ["HERMES_HBC6_AUDIT"] = "1"
    if hbc6_audit_verbose:
        os.environ["HERMES_HBC6_AUDIT"] = "1"
        os.environ["HERMES_HBC6_AUDIT_VERBOSE"] = "1"

def main():
    import os
    os.environ["DOXOADE_QUIET_BOOT"] = "1"
    package_dir = Path(__file__).resolve().parent
    project_root = str(package_dir.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    cwd_root = _find_project_root()
    os.environ["DOXOADE_PROJECT_ROOT"] = cwd_root
    pure_mode = "--pure" in sys.argv
    if pure_mode:
        sys.argv.remove("--pure")
    else:
        from doxoade.boot import ignite_background_systems
        ignite_background_systems(cwd_root)
    os.environ["DOXOADE_QUIET_BOOT"] = "0"
    
    exit_code = 0
    try:
        from doxoade.cli import cli
        cli()
    except SystemExit as e:
        exit_code = getattr(e, 'code', 0) or 0
    except Exception as e:
        if "Exit" in type(e).__name__ or "Abort" in type(e).__name__:
            exit_code = getattr(e, 'exit_code', 0) or 0
        else:
            import traceback
            import os
            from datetime import datetime
            tb_text = traceback.format_exc()
            lines = tb_text.splitlines()
            # Forensic Extraction (Ma'at)
            info = {'error': lines[-1] if lines else 'Unknown', 'file': 'Unknown', 'line': '0', 'func': 'Unknown'}
            for line in reversed(lines):
                if 'File "' in line:
                    try:
                        parts = line.split('"')
                        info['file'] = parts[1]
                        info['line'] = line.split('line ')[1].split(',')[0]
                    except Exception:
                        pass
                    break
            for i, line in enumerate(lines):
                if f"line {info['line']}" in line and i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    if next_line.startswith("in "):
                        info['func'] = next_line[3:]
                    break
            # Terminal Output (Anúbis)
            print(f"\n\x1b[41;1m 🔥 CRASH NO SISTEMA (Forensic Report) \x1b[0m"
                  f"\n\x1b[1;31m  ■ Tipo de Falha: \x1b[0m\x1b[1m{type(e).__name__}\x1b[0m"
                  f"\x1b[1;31m  ■ Mensagem:      \x1b[0m{e}"
                  f"\x1b[1;33m  ■ Arquivo:       \x1b[0m{info['file']}"
                  f"\x1b[1;33m  ■ Linha:         \x1b[0m{info['line']}"
                  f"\x1b[1;33m  ■ Função:        \x1b[0m{info['func']}"
                  f"\n\x1b[2m--- Traceback Completo ---\x1b[0m" )
            print(tb_text)
            # Black Box Logger (Hades)
            try:
                log_dir = Path(os.environ.get("DOXOADE_PROJECT_ROOT", ".")) / ".doxoade" / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                crash_log = log_dir / "doxoade_crash.log"
                with open(crash_log, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\nCRASH EM: {datetime.now().isoformat()}\n")
                    f.write(f"FILE: {info['file']} | LINE: {info['line']} | FUNC: {info['func']}\n")
                    f.write(f"{'='*60}\n{tb_text}\n")
                print(f"\x1b[1;35m  💾 [HADES] Black Box salvo em: {crash_log}\x1b[0m")
            except Exception: pass
            exit_code = 1
    finally:
        # 🔥 FORÇA O DUMP DO HBC6 AUDITOR ANTES DE MORRER
        import os as _os
        if _os.environ.get("HERMES_HBC6_AUDIT") == "1":
            try:
                from doxoade.tools.hermes_systems.hbc6_audit import HBC6Auditor
                auditor = HBC6Auditor.get_instance()
                if auditor.entries:
                    auditor.print_report()
                    path = auditor.dump_json()
                    print(f"  💾 [HBC6-AUDIT] Dossiê salvo em: {path}")
            except Exception:
                pass
        
        sys.exit(exit_code)

if __name__ == "__main__":
    main()

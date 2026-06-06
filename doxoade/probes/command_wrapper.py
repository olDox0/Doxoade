# doxoade/doxoade/probes/command_wrapper.py
import sys, os, shlex
from click.testing import CliRunner
from doxoade.cli import cli

def run_internal_command(command_name, args):
    print(f"--- [WRAPPER] Alvo: {command_name} | Args: {args} ---")
    runner = CliRunner()
    # standalone_mode=False impede o encerramento do processo
    result = runner.invoke(cli, [command_name] + list(args), standalone_mode=False)
    if result.exception:
        from doxoade.tools.error_info import print_forensic_exception
        print_forensic_exception()
        raise result.exception
    print(result.output)

if __name__ == '__main__':
    # v128.0 Fix: Ignora TUDO que for caminho absoluto no início (Mata o Path-Mutilation)
    raw_args = sys.argv[1:]
    actual_parts = []
    try:
        for arg in raw_args:
            # Se contiver ':' ou comecar com '/', é rastro de infraestrutura do Windows/Unix, ignore
            if ":" in arg or arg.startswith("/") or "command_wrapper" in arg.lower():
                continue
            actual_parts.append(arg)

        if not actual_parts:
            # Tenta recuperar via shlex se vier colado
            import shlex
            actual_parts = [p for p in shlex.split(" ".join(raw_args)) if ":" not in p and "wrapper" not in p]

        if not actual_parts:
            print("Erro: Nenhum comando Nexus localizado nos argumentos.")
            sys.exit(1)

        cmd = actual_parts[0]
        cmd_args = actual_parts[1:]
        run_internal_command(cmd, cmd_args)
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        
        # Lógica simplificada para evitar erro de aspas no f-string
        exc_val = str(exc_obj).replace("'", "")
        print(f"\x1b[31m ■ Archive: {fname} - line: {line_number}")
        print(f" ■ Exception type: {type(e).__name__}")
        print(f" ■ Exception value: {exc_val}\x1b[0m")
        exc_trace(exc_tb)
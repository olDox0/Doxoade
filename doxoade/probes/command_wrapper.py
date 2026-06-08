# doxoade/doxoade/probes/command_wrapper.py
import sys, os, shlex, ctypes
from click.testing import CliRunner
from doxoade.cli import cli

def get_real_windows_cmd():
    try:
        GetCommandLineW = ctypes.windll.kernel32.GetCommandLineW
        GetCommandLineW.restype = ctypes.c_wchar_p
        return GetCommandLineW()
    except: return " ".join(sys.argv)

def run_internal_command(command_name, args):
    print(f"--- [NEXUS WRAPPER: DETECTADO {command_name.upper()}] ---")
    runner = CliRunner()
    result = runner.invoke(cli, [command_name] + list(args), standalone_mode=False)
    if result.output:
        sys.stdout.write(result.output)
        sys.stdout.flush()

if __name__ == '__main__':
    cmd_line = get_real_windows_cmd()
    # Limpa caminhos absolutos e aspas para achar o comando real
    parts = shlex.split(cmd_line)
    TARGETS = {'macrothon', 'moduloid', 'check', 'save', 'search', 'diagnose'}
    
    cmd = None
    cmd_args = []

    for i, p in enumerate(parts):
        # Pega apenas o nome do arquivo se for um path
        clean_token = p.lower().split('\\')[-1].split('/')[-1]
        if clean_token in TARGETS:
            cmd = clean_token
            cmd_args = parts[i+1:]
            break

    if cmd:
        run_internal_command(cmd, cmd_args)
    else:
        print(f"✘ [WRAPPER FATAL] Linha de comando ilegível.")
        print(f"   BRUTO: {cmd_line[:120]}...")
        sys.exit(1)
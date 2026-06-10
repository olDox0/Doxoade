# doxoade/doxoade/probes/command_wrapper.py
import sys, os, shlex, ctypes
from click.testing import CliRunner
from doxoade.cli import cli

def get_real_windows_cmd():
    try:
        # Pega a linha de comando bruta do kernel para evitar perdas do sys.argv
        GetCommandLineW = ctypes.windll.kernel32.GetCommandLineW
        GetCommandLineW.restype = ctypes.c_wchar_p
        return GetCommandLineW()
    except: return " ".join(sys.argv)

def run_internal_command(command_name, args):
    # Removido print ruidoso para não quebrar o rastro JSON do debug
    runner = CliRunner()
    # standalone_mode=False permite que exceções subam para o Debug Engine capturar
    result = runner.invoke(cli, [command_name] + list(args), standalone_mode=False)
    if result.output:
        sys.stdout.write(result.output)
        sys.stdout.flush()

if __name__ == '__main__':
    cmd_line = get_real_windows_cmd()
    # Limpeza radical de barras para o Windows
    parts = shlex.split(cmd_line.replace('\\', '/'))
    
    # [OURO] Se o Doxoade disse que está autorizado, nós não questionamos.
    if os.environ.get('DOXOADE_AUTHORIZED_RUN') == '1' or os.environ.get('DOXOADE_TEST_MODE') == '1':
        sys.exit(0)

    TARGETS = {'macrothon', 'moduloid', 'check', 'save', 'search', 'diagnose', 'debug', 'run'}
    
    # [OURO] Verificação de Autorização de Teste
    is_test_authorized = os.environ.get('DOXOADE_TEST_MODE') == '1'

    cmd = None
    for i, p in enumerate(parts):
        clean_token = p.lower().split('/')[-1]
        
        # Caso A: É um comando interno do Doxoade
        if clean_token in TARGETS:
            cmd = clean_token
            run_internal_command(cmd, parts[i+1:])
            sys.exit(0)
            
        # Caso B: É a sonda de debug tentando rodar um script
        if any("debug_probe.py" in p for p in parts):
            if is_test_authorized:
                sys.exit(0) # Autorizado! Sai com sucesso e deixa o interpretador seguir.
            else:
                print(f"✘ [AEGIS] Bloqueio: Use --test-mode para depurar scripts em tests/")
                sys.exit(1)

    # Se chegou aqui e não identificou o fluxo
    print(f"✘ [WRAPPER FATAL] Comando não autorizado ou ilegível.")
    sys.exit(1)
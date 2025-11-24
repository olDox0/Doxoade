# doxoade/commands/debug.py
import click
import subprocess
import sys
import os
import json
from colorama import Fore, Style
from ..shared_tools import _get_venv_python_executable

def _get_probe_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'probes', 'debug_probe.py')

def _generate_pytest_file(script_path, variables):
    """Gera um template de teste robusto com path injection."""
    
    abs_script_path = os.path.abspath(script_path)
    script_dir = os.path.dirname(abs_script_path)
    base_name = os.path.basename(script_path).replace('.py', '')
    
    # Salva o teste no mesmo diretório do script original para facilitar imports relativos
    # Ou na raiz, mas com path hack. Vamos manter na raiz por enquanto mas com path hack.
    test_file = f"test_{base_name}_gen.py"
    
    # Escapa barras invertidas para string python no windows
    safe_dir = script_dir.replace('\\', '\\\\')
    
    content = [
        "import sys",
        "import os",
        "import pytest",
        "",
        "# Adiciona o diretório do script original ao path para permitir importação",
        f"sys.path.insert(0, '{safe_dir}')",
        "",
        f"import {base_name}", 
        "",
        f"def test_{base_name}_state():",
        "    # Teste gerado automaticamente pelo Doxoade Debug",
        "    # Valida se o estado final corresponde à execução de referência",
        ""
    ]
    
    for var, val in variables.items():
        if isinstance(val, (int, float, bool, str)):
            if isinstance(val, str): val_repr = f"'{val}'"
            else: val_repr = str(val)
            content.append(f"    # assert {base_name}.{var} == {val_repr}")
    
    content.append("    pass # Ative os asserts acima conforme necessário")
    
    return test_file, "\n".join(content)

@click.command('debug')
@click.argument('script', type=click.Path(exists=True))
@click.option('--gen-test', is_flag=True, help="Gera um arquivo de teste (pytest) baseado no estado final.")
def debug(script, gen_test):
    """
    Executa uma 'Autópsia de Código' ou 'Inspeção de Estado'.
    
    Identifica variáveis e funções no momento da falha ou ao final da execução.
    Útil para entender o que aconteceu sem encher o código de prints.
    """
    venv_python = _get_venv_python_executable()
    if not venv_python:
        click.echo(Fore.RED + "[ERRO] Venv não encontrado.")
        sys.exit(1)

    probe = _get_probe_path()
    
    click.echo(Fore.CYAN + f"--- [DEBUG] Analisando {script} ---")
    
    # Executa a sonda
    result = subprocess.run(
        [venv_python, probe, script],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    
    # Separa o output do script dos dados de debug
    output_parts = result.stdout.split("---DOXOADE-DEBUG-DATA---")
    script_output = output_parts[0]
    
    if script_output.strip():
        click.echo(Fore.WHITE + Style.DIM + "--- Saída do Script ---")
        click.echo(script_output)
        click.echo(Fore.WHITE + Style.DIM + "-----------------------")

    if len(output_parts) < 2:
        click.echo(Fore.RED + "[ERRO] Falha crítica: A sonda de debug não retornou dados.")
        click.echo(result.stderr)
        return

    try:
        data = json.loads(output_parts[1])
    except json.JSONDecodeError:
        click.echo(Fore.RED + "[ERRO] Dados de debug corrompidos.")
        return

    # --- RELATÓRIO DE VOO ---
    
    if data['status'] == 'error':
        click.echo(Fore.RED + Style.BRIGHT + f"\n[CRASH DETECTADO] {data['error']}")
        click.echo(Fore.YELLOW + "Contexto da Falha (Variáveis Locais no momento do erro):")
    else:
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SUCESSO] Execução finalizada.")
        click.echo(Fore.CYAN + "Estado Final (Variáveis Globais):")

    # Tabela de Variáveis
    vars = data.get('variables', {})
    if vars:
        for k, v in vars.items():
            val_str = str(v)
            if len(val_str) > 60: val_str = val_str[:57] + "..."
            click.echo(f"   {Fore.BLUE}{k:<15} {Fore.WHITE}= {Style.DIM}{val_str}")
    else:
        click.echo(Fore.WHITE + Style.DIM + "   (Nenhuma variável significativa encontrada)")

    # Funções Identificadas
    funcs = data.get('functions', [])
    if funcs:
        click.echo(Fore.CYAN + "\nFunções Definidas:")
        click.echo(Fore.WHITE + f"   {', '.join(funcs)}")

    # Geração de Testes
    if gen_test and data['status'] == 'success':
        fname, fcontent = _generate_pytest_file(script, vars)
        click.echo(Fore.MAGENTA + Style.BRIGHT + f"\n[PYTEST] Gerando template de teste: {fname}")
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(fcontent)
            click.echo(Fore.GREEN + "   > Arquivo criado. Edite-o para ativar os asserts.")
        except Exception as e:
            click.echo(Fore.RED + f"   > Falha ao criar arquivo: {e}")

    elif data['status'] == 'error':
        click.echo(Fore.RED + "\n--- Traceback Original ---")
        click.echo(data.get('traceback', ''))
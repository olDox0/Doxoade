# doxoade/commands/run.py
import click
import subprocess
import sys
import os
from colorama import Fore, Style
from ..shared_tools import _get_venv_python_executable, _mine_traceback, _analyze_runtime_error

@click.command('run')
@click.argument('script', required=False)
@click.argument('args', nargs=-1)
@click.pass_context
def run(ctx, script, args):
    """Executa um script Python usando o 'venv' do projeto com análise de falhas."""
    
    venv_python = _get_venv_python_executable()
    
    if not venv_python:
        click.echo(Fore.RED + "[ERRO] Ambiente virtual não encontrado. Execute 'doxoade doctor' primeiro.")
        sys.exit(1)

    # Se não passar script, abre o REPL do Python
    if not script:
        subprocess.run([venv_python])
        return

    # Constrói o comando
    command = [venv_python, script] + list(args)
    
    click.echo(Fore.CYAN + f"--- [RUN] Executando: {script} ---")
    
    try:
        # Gênese V4: Usamos Popen para capturar stderr em tempo real mas também guardar para análise
        # Nota: Para manter a interatividade (input), não podemos capturar stdout facilmente sem threads complexas.
        # Vamos deixar o stdout ir pro terminal, mas capturar stderr se possível, ou confiar no exit code.
        
        # Abordagem Híbrida Simples:
        # Rodamos o processo. Se falhar, nós (infelizmente) não teremos o stderr capturado se ele foi pro terminal.
        # PARA TERMOS A ANÁLISE, precisamos capturar o stderr.
        
        process = subprocess.run(
            command, 
            capture_output=True, # Captura para analisar
            text=True, 
            encoding='utf-8', 
            errors='replace'
        )
        
        # Imprime o que aconteceu (já que capturamos, precisamos mostrar)
        if process.stdout:
            click.echo(process.stdout, nl=False)
        
        if process.stderr:
            click.echo(Fore.RED + process.stderr, nl=False)

        if process.returncode != 0:
            # Separador visual
            click.echo(Fore.WHITE + Style.DIM + "-" * 50)
            
            # 1. Minerar o Traceback
            error_data = _mine_traceback(process.stderr)
            
            if error_data:
                # Título do Erro em Vermelho Vivo
                click.echo(Fore.RED + Style.BRIGHT + f"[FALHA DE EXECUÇÃO] {error_data['error_type']}")
                
                # Detalhes em Branco/Ciano
                file_name = os.path.basename(error_data['file'])
                click.echo(Fore.CYAN + f"   Arquivo: {file_name}" + Fore.WHITE + f" (Linha {error_data['line']})")
                click.echo(Fore.CYAN + f"   Contexto: {error_data['context']}")
                
                # Código que quebrou (destacado)
                if error_data['code'] != 'N/A':
                    click.echo(Fore.YELLOW + f"   > {error_data['code']}")
                
                # Mensagem Original
                click.echo(Fore.WHITE + Style.DIM + f"   Detalhe: {error_data['message']}")

                # 2. Sugestão Automática
                suggestion = _analyze_runtime_error(error_data)
                if suggestion:
                    click.echo(Fore.GREEN + Style.BRIGHT + "\n[SUGESTÃO AUTOMÁTICA]")
                    click.echo(Fore.GREEN + f"   {suggestion}")
            else:
                # Fallback elegante
                click.echo(Fore.YELLOW + "[Gênese V4] O script falhou, mas não consegui isolar a causa exata no traceback.")
                click.echo(Fore.WHITE + "Verifique a saída padrão acima para detalhes.")
                
            sys.exit(process.returncode)

    except KeyboardInterrupt:
        click.echo(Fore.YELLOW + "\n[INFO] Execução interrompida pelo usuário.")
    except Exception as e:
        click.echo(Fore.RED + f"\n[ERRO CRÍTICO NO RUNNER] {e}")
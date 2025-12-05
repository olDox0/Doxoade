# doxoade/commands/style.py
import click
import os
import json
import sys
import subprocess
from colorama import Fore #, Style
from ..shared_tools import ExecutionLogger, collect_files_to_analyze, _get_project_config, _get_code_snippet

def _get_probe_path(probe_name):
    from importlib import resources
    try:
        with resources.path('doxoade.probes', probe_name) as probe_path:
            return str(probe_path)
    except (AttributeError, ModuleNotFoundError):
        from pkg_resources import resource_filename
        return resource_filename('doxoade', f'probes/{probe_name}')

@click.command('style')
@click.pass_context
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--comment', is_flag=True, help="Foca exclusivamente em documentação.")
@click.option('--ignore', multiple=True, help="Pastas para ignorar.")
def style(ctx, path, comment, ignore):
    """Analisa o estilo arquitetural (Modern Power of Ten)."""
    
    # CORREÇÃO: Suporte a arquivo único
    target_is_file = os.path.isfile(path)
    root_path = os.path.dirname(os.path.abspath(path)) if target_is_file else path
    
    with ExecutionLogger('style', root_path, ctx.params) as logger:
        mode_msg = "Análise de Documentação" if comment else "Análise MPoT"
        click.echo(Fore.CYAN + f"--- [STYLE] Iniciando {mode_msg} em '{path}' ---")

        if target_is_file:
            files = [path]
        else:
            config = _get_project_config(logger, start_path=path)
            files = collect_files_to_analyze(config, ignore)
        
        if not files:
            click.echo(Fore.YELLOW + "Nenhum arquivo Python encontrado.")
            return

        click.echo(f"   > Analisando {len(files)} arquivo(s)...")

        probe_path = _get_probe_path('style_probe.py')
        payload = {
            'files': [os.path.abspath(f) for f in files], # Garante caminhos absolutos para a sonda
            'comments_only': comment
        }
        
        try:
            result = subprocess.run(
                [sys.executable, probe_path],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode != 0:
                click.echo(Fore.RED + f"[ERRO] Falha na sonda: {result.stderr}")
                return

            findings = json.loads(result.stdout)
            
            if not findings:
                click.echo(Fore.GREEN + "[OK] Código em conformidade.")
                return

            for f in findings:
                logger.add_finding(
                    severity=f['severity'],
                    category=f['category'],
                    message=f['message'],
                    file=f['file'],
                    line=f['line'],
                    snippet=_get_code_snippet(f['file'], f['line'])
                )
                
                rel = os.path.relpath(f['file'], os.getcwd())
                click.echo(Fore.YELLOW + f"[{f['category']}] {f['message']}")
                click.echo(Fore.WHITE + f"   Em {rel}:{f['line']}")

            click.echo(Fore.CYAN + f"\nResumo: {len(findings)} avisos.")

        except json.JSONDecodeError:
            click.echo(Fore.RED + f"[ERRO] Resposta inválida da sonda:\n{result.stdout}")
        except Exception as e:
            click.echo(Fore.RED + f"[ERRO CRÍTICO] {e}")
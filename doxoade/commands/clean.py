# doxoade/commands/clean.py
import os
import shutil
import click
from pathlib import Path
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger

@click.command('clean')
def clean():
    """Limpa artefatos temporários, caches e builds do projeto."""
    with ExecutionLogger('clean', '.', {}) as logger:
        click.echo(Fore.CYAN + "-> [CLEAN] Procurando por artefatos de build e cache...")
        
        # Lista de padrões para remover
        TARGETS = [
            '__pycache__',
            '.pytest_cache',
            '.doxoade_cache',   # <--- O CULPADO
            '.dox_agent_workspace',
            'build',
            'dist',
            '*.egg-info',
            '.coverage',
            'htmlcov'
        ]
        
        found_items = []
        root = Path('.')
        
        # Varredura inteligente
        for pattern in TARGETS:
            # Se for glob (*.egg-info)
            if '*' in pattern:
                found_items.extend(list(root.glob(pattern)))
            else:
                # Busca recursiva para pastas comuns como __pycache__
                if pattern == '__pycache__':
                    found_items.extend(list(root.rglob(pattern)))
                else:
                    # Busca na raiz para pastas de config
                    p = root / pattern
                    if p.exists():
                        found_items.append(p)

        if not found_items:
            click.echo(Fore.GREEN + "   Nenhum lixo encontrado. O projeto está limpo.")
            return

        click.echo(f"Encontrados {len(found_items)} itens para remover:")
        for item in found_items[:10]:
            click.echo(f"  - {item}")
        if len(found_items) > 10:
            click.echo(f"  - ... e mais {len(found_items) - 10}")

        if click.confirm(Fore.YELLOW + "\nRemover permanentemente estes itens?", default=True):
            click.echo("\n-> Iniciando a limpeza...")
            count = 0
            for item in found_items:
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    count += 1
                except Exception as e:
                    click.echo(Fore.RED + f"   [ERRO] Não foi possível remover {item}: {e}")
            
            click.echo(Fore.GREEN + f"\n Limpeza concluída! {count} itens foram removidos.")
        else:
            click.echo("Operação cancelada.")
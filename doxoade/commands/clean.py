# doxoade/commands/clean.py
import os
import shutil
import click
from pathlib import Path
from colorama import Fore
import uuid
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
            count = 0
            for item in found_items:
                try:
                    if item.is_dir():
                        try:
                            shutil.rmtree(item)
                        except PermissionError:
                            # Tática de Guerra: Renomeia o que não pode deletar
                            temp_name = f"{item}_{uuid.uuid4().hex[:4]}.old"
                            os.rename(item, temp_name)
                            shutil.rmtree(temp_name, ignore_errors=True)
                    else:
                        item.unlink()
                    count += 1
                except Exception: pass
            click.echo(Fore.GREEN + f"\n Limpeza concluída! {count} itens removidos.")
        else:
            click.echo("Operação cancelada.")
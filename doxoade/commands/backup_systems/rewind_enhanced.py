# -*- coding: utf-8 -*-
# doxoade/commands/backup_systems/rewind_enhanced.py
""" Comando `doxoade rewind` aprimorado — Suporta backups Doxoade além do git. """
import click
import shutil
from pathlib import Path
from .backup_engine import BackupEngineStrap as BackupEngine
from doxoade.tools.doxcolors import Fore, Style

@click.command('rewind')
@click.argument('target', required=False)
@click.option('--commit', '-c', help='Hash do commit git (modo git)')
@click.option('--backup', '-b', help='ID do backup Doxoade (modo backup)')
@click.option('--list', '-l', 'show_list', is_flag=True, 
              help='Lista histórico (git ou backups)')
@click.option('--backup-dir', type=click.Path(),
              help='Diretório de backups (padrão: .doxoade/backups)')
def rewind(target, commit, backup, show_list, backup_dir):
    """
    Reverte para versão anterior via git ou backup Doxoade.
    
    Modos:
        Git:    doxoade rewind arquivo.py -c <hash>
        Backup: doxoade rewind --backup <backup_id>
    
    Exemplos:
        doxoade rewind --list                    # Lista tudo
        doxoade rewind arquivo.py -c a1b2c3      # Git: reverte arquivo
        doxoade rewind --backup backup_20260731  # Backup: restaura snapshot
    """
    project_root = Path.cwd()
    backup_path = Path(backup_dir) if backup_dir else project_root / '.doxoade' / 'backups'
    
    # Modo lista
    if show_list:
        _show_combined_history(project_root, backup_path)
        return
    
    # Modo backup Doxoade
    if backup:
        _restore_from_backup(project_root, backup_path, backup)
        return
    
    # Modo git (fallback)
    if commit and target:
        _restore_from_git(target, commit)
        return
    
    # Erro: nenhum modo especificado
    click.echo(f"{Fore.RED}Erro: especifique --backup <id> ou <arquivo> -c <commit>{Style.RESET_ALL}")
    click.echo(f"Dica: use 'doxoade rewind --list' para ver opções disponíveis")

def _show_combined_history(project_root: Path, backup_path: Path):
    """Mostra histórico combinado de git e backups."""
    # Backups Doxoade
    if backup_path.exists():
        engine = BackupEngine(project_root, backup_path)
        backups = engine.list_backups()
        if backups:
            click.echo(f"{Fore.CYAN}═══ Backups Doxoade ═══{Style.RESET_ALL}")
            for meta in backups:
                backup_type = Fore.GREEN + "FULL" if meta.backup_type == 'full' else Fore.YELLOW + "DELTA"
                click.echo(f"{backup_type}{Style.RESET_ALL} | {meta.backup_id} | "
                          f"{meta.included_files} arquivos | {meta.timestamp[:19]}")
    
    # Git history
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'log', '--oneline', '--graph', '--decorate', '-n', '20'],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if result.returncode == 0:
            click.echo(f"\n{Fore.CYAN}═══ Histórico Git ═══{Style.RESET_ALL}")
            click.echo(result.stdout)
    except Exception:
        pass

def _restore_from_backup(project_root: Path, backup_path: Path, backup_id: str):
    """Restaura projeto de um backup Doxoade."""
    engine = BackupEngine(project_root, backup_path)
    
    click.echo(f"{Fore.CYAN}Restaurando backup {backup_id}...{Style.RESET_ALL}")
    
    try:
        metadata = engine.restore_backup(backup_id)
        click.echo(f"{Fore.GREEN}✅ Backup restaurado com sucesso!{Style.RESET_ALL}")
        click.echo(f"   {metadata.included_files} arquivos restaurados")
    except Exception as e:
        click.echo(f"{Fore.RED}❌ Erro ao restaurar: {e}{Style.RESET_ALL}")
        raise

def _restore_from_git(target: str, commit: str):
    """Restaura arquivo específico via git."""
    import subprocess
    from datetime import datetime
    
    target_path = Path(target)
    if not target_path.exists():
        click.echo(f"{Fore.YELLOW}⚠️  Arquivo não existe atualmente{Style.RESET_ALL}")
    
    # Cria backup da versão atual
    if target_path.exists():
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{target}.{timestamp}.bak"
        shutil.copy2(target_path, backup_file)
        click.echo(f"{Fore.GREEN}📦 Backup criado: {backup_file}{Style.RESET_ALL}")
    
    # Reverte via git
    try:
        result = subprocess.run(
            ['git', 'checkout', commit, '--', target],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if result.returncode == 0:
            click.echo(f"{Fore.GREEN}✅ Arquivo revertido para commit {commit}{Style.RESET_ALL}")
        else:
            click.echo(f"{Fore.RED}❌ Erro no git:{Style.RESET_ALL}")
            click.echo(result.stderr)
    except Exception as e:
        click.echo(f"{Fore.RED}❌ Erro: {e}{Style.RESET_ALL}")
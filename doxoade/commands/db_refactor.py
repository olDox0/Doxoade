@db_group.command('refactor')
@click.option('--dry-run', is_flag=True, help="Apenas simula a refatoração.")
@click.argument('path', type=click.Path(exists=True), default='.')
def refactor(dry_run, path):
    """Refatora o acesso direto ao DB para usar o motor Alexandria."""
    from doxoade.tools.vulcan.db_refactorer import apply_refactor
    
    target = Path(path).resolve()
    for py_file in target.rglob('*.py'):
        # Pula arquivos de sistema e de dentro da pasta de refatoração
        if any(x in str(py_file) for x in ['venv', '.git', 'data', 'db_cmd.py']):
            continue
            
        success, msg = apply_refactor(py_file, dry_run=dry_run)
        if success:
            click.echo(f"  {Fore.GREEN}● {Fore.WHITE}{msg}{Style.RESET_ALL}")
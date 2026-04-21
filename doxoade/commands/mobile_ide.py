# doxoade/doxoade/commands/mobile_ide.py
"""
Doxoade Mobile IDE - Interface de desenvolvimento multiplataforma
Compatível com: Windows, Linux, macOS, Termux
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from rich.console import Console
from rich.prompt import Confirm
from doxoade.tools.system_utils import is_termux
from doxoade.commands.mobile_termux import termux_share_file, termux_clipboard_copy, termux_toast, setup_micro_split_workflow
from doxoade.commands.mobile_ux import show_file_info, git_status_visual
from doxoade.commands.mobile_ux import show_extended_menu
from doxoade.commands.mobile_ux import get_best_editor
try:
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.prompt import Prompt
except ImportError:
    print('❌ Dependência faltando. Instalando rich...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'rich', 'prompt_toolkit'])
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
console = Console()

def quick_search_in_files(directory: Path, term: str):
    """Busca rápida em arquivos"""
    console.print(f"\n[cyan]🔍 Buscando '{term}'...[/cyan]")
    results = []
    for file_path in directory.rglob('*.py'):
        try:
            lines = file_path.read_text(errors='ignore').splitlines()
            for i, line in enumerate(lines, 1):
                if term.lower() in line.lower():
                    results.append((file_path, i, line.strip()))
        except Exception:
            continue
    if results:
        table = Table(title=f'Encontrado {len(results)} resultado(s)')
        table.add_column('Arquivo', style='cyan')
        table.add_column('Linha', style='yellow', width=6)
        table.add_column('Conteúdo', style='white')
        for path, line_num, content in results[:20]:
            table.add_row(path.name, str(line_num), content[:60] + '...')
        console.print(table)
        if len(results) > 20:
            console.print(f'\n[dim]... e mais {len(results) - 20} resultado(s)[/dim]')
    else:
        console.print('[yellow]Nenhum resultado encontrado[/yellow]')
    input('\nPressione Enter...')

def clean_python_cache(directory: Path):
    """Remove arquivos __pycache__ e .pyc"""
    import shutil
    removed = 0
    for item in directory.rglob('__pycache__'):
        try:
            shutil.rmtree(item)
            removed += 1
        except Exception:
            pass
    for item in directory.rglob('*.pyc'):
        try:
            item.unlink()
            removed += 1
        except Exception:
            pass
    console.print(f'[green]✓ {removed} arquivo(s)/pasta(s) removido(s)[/green]')
    input('\nPressione Enter...')

def setup_termux_editors():
    """Instala os melhores editores para Termux"""
    if not is_termux():
        console.print('[yellow]Apenas para Termux[/yellow]')
        return
    console.print('\n[bold cyan]📦 Instalador de Editores para Termux[/bold cyan]\n')
    editors = [('micro', 'Editor moderno e intuitivo (RECOMENDADO)'), ('nano', 'Editor clássico e leve'), ('vim', 'Editor poderoso (curva de aprendizado)')]
    for editor, desc in editors:
        if Confirm.ask(f'Instalar {editor}? ({desc})'):
            console.print(f'[cyan]Instalando {editor}...[/cyan]')
            subprocess.run(['pkg', 'install', '-y', editor])
    console.print('\n[green]✓ Configuração concluída![/green]')

class MobileIDE:
    """IDE simplificada e multiplataforma"""

    def __init__(self, start_path: str='.'):
        self.start_path = Path(start_path).resolve()
        self.current_file: Optional[Path] = None
        self.buffer: List[str] = []
        self.modified = False
        if not self.start_path.exists():
            console.print(f'[red]❌ Caminho não existe: {start_path}[/red]')
            sys.exit(1)

    def clear_screen(self):
        """Limpa a tela de forma multiplataforma"""
        print('\x1b[2J\x1b[H', end='')

    def show_header(self, title: str):
        """Mostra cabeçalho"""
        console.print(Panel(f'[bold cyan]🚀 DOXOADE MOBILE IDE[/bold cyan]\n{title}', style='bold white on blue'))

    def file_explorer(self) -> Optional[Path]:
        """Explorador de arquivos interativo"""
        current_dir = self.start_path
        while True:
            self.clear_screen()
            self.show_header(f'📁 {current_dir}')
            try:
                items = sorted(current_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                items = [item for item in items if not item.name.startswith('.')]
            except PermissionError:
                console.print('[red]❌ Sem permissão para acessar este diretório[/red]')
                return None
            table = Table(show_header=True, header_style='bold magenta')
            table.add_column('#', style='dim', width=4)
            table.add_column('Tipo', width=6)
            table.add_column('Nome', style='cyan')
            table.add_column('Tamanho', justify='right')
            if current_dir != current_dir.parent:
                table.add_row('0', '📁', '..', '')
            for idx, item in enumerate(items, 1):
                if item.is_dir():
                    icon = '📁'
                    size = ''
                elif item.suffix == '.py':
                    icon = '🐍'
                    size = f'{item.stat().st_size} bytes'
                else:
                    icon = '📄'
                    size = f'{item.stat().st_size} bytes'
                table.add_row(str(idx), icon, item.name, size)
            console.print(table)
            console.print('\n[yellow]Comandos:[/yellow]')
            console.print('  [cyan]número[/cyan] - Abrir/Entrar')
            console.print('  [cyan]n[/cyan] - Novo arquivo')
            console.print('  [cyan]q[/cyan] - Sair')
            console.print('  [cyan]r[/cyan] - Executar arquivo Python')
            choice = Prompt.ask('\n> ', default='q').strip().lower()
            if choice == 'q':
                return None
            elif choice == 'n':
                return self.create_new_file(current_dir)
            elif choice == 'r':
                self.run_python_file(current_dir)
                continue
            elif choice == '0' and current_dir != current_dir.parent:
                current_dir = current_dir.parent
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(items):
                    selected = items[idx]
                    if selected.is_dir():
                        current_dir = selected
                    else:
                        return selected

    def create_new_file(self, directory: Path) -> Optional[Path]:
        """Cria novo arquivo"""
        console.print('\n[yellow]Criar novo arquivo[/yellow]')
        filename = Prompt.ask('Nome do arquivo (com extensão)')
        if not filename:
            return None
        new_file = directory / filename
        if new_file.exists():
            if not Confirm.ask('[yellow]Arquivo já existe. Sobrescrever?[/yellow]'):
                return None
        try:
            new_file.touch()
            console.print(f'[green]✓ Arquivo criado: {filename}[/green]')
            return new_file
        except Exception as e:
            console.print(f'[red]❌ Erro ao criar arquivo: {e}[/red]')
            return None

    def run_python_file(self, directory: Path):
        """Executa um arquivo Python"""
        console.print('\n[yellow]Digite o número do arquivo Python para executar[/yellow]')
        py_files = [f for f in directory.glob('*.py')]
        if not py_files:
            console.print('[red]Nenhum arquivo Python encontrado[/red]')
            input('\nPressione Enter...')
            return
        for idx, f in enumerate(py_files, 1):
            console.print(f'  {idx}. {f.name}')
        choice = Prompt.ask('> ')
        if not choice.isdigit():
            return
        idx = int(choice) - 1
        if 0 <= idx < len(py_files):
            self.execute_python(py_files[idx])

    def execute_python(self, file_path: Path):
        """Executa arquivo Python"""
        self.clear_screen()
        console.print(Panel(f'[bold]Executando: {file_path.name}[/bold]', style='green'))
        console.print('=' * 60)
        try:
            result = subprocess.run([sys.executable, str(file_path)], cwd=file_path.parent, capture_output=False, text=True)
            console.print('=' * 60)
            console.print(f"\n[{('green' if result.returncode == 0 else 'red')}]Código de saída: {result.returncode}[/]")
        except Exception as e:
            console.print(f'[red]❌ Erro: {e}[/red]')
        input('\nPressione Enter para continuar...')

    def load_file(self, file_path: Path) -> bool:
        """Carrega arquivo no buffer"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                self.buffer = f.read().splitlines()
            self.current_file = file_path
            self.modified = False
            return True
        except Exception as e:
            console.print(f'[red]❌ Erro ao carregar: {e}[/red]')
            return False

    def save_file(self) -> bool:
        """Salva buffer em arquivo"""
        if not self.current_file:
            console.print('[yellow]Nenhum arquivo aberto[/yellow]')
            return False
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.buffer))
            self.modified = False
            console.print(f'[green]✓ Salvo: {self.current_file.name}[/green]')
            return True
        except Exception as e:
            console.print(f'[red]❌ Erro ao salvar: {e}[/red]')
            return False

    def edit_file(self):
        """Editor de texto simples"""
        if not self.current_file:
            return
        while True:
            self.clear_screen()
            mod_indicator = '[+] ' if self.modified else ''
            self.show_header(f'📝 {mod_indicator}{self.current_file.name}')
            if self.current_file.suffix == '.py':
                syntax = Syntax('\n'.join(self.buffer), 'python', line_numbers=True, theme='monokai')
                console.print(Panel(syntax, title='Conteúdo'))
            else:
                for idx, line in enumerate(self.buffer[:50], 1):
                    console.print(f'[dim]{idx:3d}[/dim] | {line}')
                if len(self.buffer) > 50:
                    console.print(f'\n[dim]... e mais {len(self.buffer) - 50} linhas[/dim]')
            console.print('\n[yellow]Opções:[/yellow]')
            console.print('  [cyan]e[/cyan] - Editar no editor externo')
            console.print('  [cyan]r[/cyan] - Executar (se for Python)')
            console.print('  [cyan]s[/cyan] - Salvar')
            console.print('  [cyan]d[/cyan] - Ver Doxoade check')
            console.print('  [cyan]m[/cyan] - Menu avançado')
            console.print('  [cyan]q[/cyan] - Voltar ao explorador')
            choice = Prompt.ask('\n> ', default='q').strip().lower()
            if choice == 'q':
                if self.modified:
                    if Confirm.ask('[yellow]Arquivo modificado. Salvar?[/yellow]'):
                        self.save_file()
                break
            elif choice == 's':
                self.save_file()
                input('\nPressione Enter...')
            elif choice == 'e':
                self.open_external_editor()
            elif choice == 'r' and self.current_file.suffix == '.py':
                if self.modified:
                    self.save_file()
                self.execute_python(self.current_file)
            elif choice == 'd':
                self.run_doxoade_check()
            elif choice == 'm':
                show_extended_menu(self)

    def open_external_editor(self):
        """Abre arquivo no editor externo com detecção inteligente"""
        if not self.current_file:
            return
        editor = get_best_editor()
        if os.name == 'nt':
            if editor.lower() in ['notepad++', 'notepadpp']:
                possíveis = ['C:\\Program Files\\Notepad++\\notepad++.exe', 'C:\\Program Files (x86)\\Notepad++\\notepad++.exe']
                for caminho in possíveis:
                    if os.path.exists(caminho):
                        editor = caminho
                        break
                else:
                    editor = 'notepad++.exe'
        try:
            subprocess.run([editor, str(self.current_file)])
            self.load_file(self.current_file)
        except FileNotFoundError:
            console.print(f'[red]Editor não encontrado: {editor}[/red]')
            input('\nPressione Enter...')

    def run_doxoade_check(self):
        """Executa doxoade check no arquivo atual"""
        if not self.current_file:
            return
        self.clear_screen()
        console.print(Panel(f'[bold]Doxoade Check: {self.current_file.name}[/bold]', style='cyan'))
        try:
            subprocess.run(['doxoade', 'check', str(self.current_file)], cwd=self.current_file.parent, capture_output=False)
        except Exception as e:
            console.print(f'[red]❌ Erro: {e}[/red]')
        input('\n\nPressione Enter para continuar...')

    def run(self):
        """Loop principal"""
        while True:
            selected_file = self.file_explorer()
            if selected_file is None:
                break
            if self.load_file(selected_file):
                self.edit_file()

def mobile_ide_main(start_path: str='.', file: Optional[str]=None, editor: Optional[str]=None):
    """Função principal"""
    try:
        ide = MobileIDE(start_path)
        if editor:
            os.environ['EDITOR'] = editor
        if file:
            file_path = Path(file).resolve()
            if file_path.exists():
                ide.load_file(file_path)
                ide.edit_file()
            else:
                console.print(f'[red]❌ Arquivo não encontrado: {file}[/red]')
                return
        else:
            ide.run()
    except KeyboardInterrupt:
        console.print('\n[yellow]Saindo...[/yellow]')
    except Exception as e:
        console.print(f'[red]❌ Erro fatal: {e}[/red]')
        import traceback
        traceback.print_exc()
if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else '.'
    mobile_ide_main(path)
else:
    import click

    @click.command('ide')
    @click.option('--path', default='.', help='Diretório inicial')
    @click.option('--file', help='Abrir arquivo específico')
    @click.option('--editor', help='Forçar editor (micro, nano, vim, code, etc)')
    def ide(path, file, editor):
        """
        🚀 IDE móvel multiplataforma (Windows/Linux/Termux)
        
        Recursos:
        - Explorador de arquivos interativo
        - Visualização com syntax highlighting
        - Execução de scripts Python
        - Integração com Doxoade check
        - Editor externo (Notepad++/nano/vim)
        - Menu avançado (busca, git, etc)
        
        Exemplos:
          doxoade ide
          doxoade ide --path ~/projetos
          doxoade ide --file main.py
        """
        mobile_ide_main(path, file, editor)

    @click.command('ide-setup')
    def ide_setup():
        """Configura editores ideais para Termux"""
        setup_termux_editors()
        setup_micro_split_workflow()

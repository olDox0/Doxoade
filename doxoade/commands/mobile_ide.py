#!/usr/bin/env python3
"""
Doxoade Mobile IDE - Interface de desenvolvimento multiplataforma
Arquivo: doxoade/commands/mobile_ide.py

Compatível com: Windows, Linux, macOS, Termux
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.prompt import Prompt, Confirm
    from rich.layout import Layout # noqa
    from rich.live import Live # noqa
except ImportError:
    print("❌ Dependência faltando. Instalando rich...")
    subprocess.run([sys.executable, "-m", "pip", "install", "rich", "prompt_toolkit"])
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.prompt import Prompt, Confirm

console = Console()

class MobileIDE:
    """IDE simplificada e multiplataforma"""
    
    def __init__(self, start_path: str = "."):
        self.start_path = Path(start_path).resolve()
        self.current_file: Optional[Path] = None
        self.buffer: List[str] = []
        self.modified = False
        
        if not self.start_path.exists():
            console.print(f"[red]❌ Caminho não existe: {start_path}[/red]")
            sys.exit(1)
    
    def clear_screen(self):
        """Limpa a tela de forma multiplataforma"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def show_header(self, title: str):
        """Mostra cabeçalho"""
        console.print(Panel(
            f"[bold cyan]🚀 DOXOADE MOBILE IDE[/bold cyan]\n{title}",
            style="bold white on blue"
        ))
    
    def file_explorer(self) -> Optional[Path]:
        """Explorador de arquivos interativo"""
        current_dir = self.start_path
        
        while True:
            self.clear_screen()
            self.show_header(f"📁 {current_dir}")
            
            # Lista arquivos e pastas
            try:
                items = sorted(current_dir.iterdir(), 
                             key=lambda x: (not x.is_dir(), x.name.lower()))
                items = [item for item in items if not item.name.startswith('.')]
            except PermissionError:
                console.print("[red]❌ Sem permissão para acessar este diretório[/red]")
                return None
            
            # Cria tabela
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("#", style="dim", width=4)
            table.add_column("Tipo", width=6)
            table.add_column("Nome", style="cyan")
            table.add_column("Tamanho", justify="right")
            
            # Adiciona item para voltar
            if current_dir != current_dir.parent:
                table.add_row("0", "📁", "..", "")
            
            # Adiciona itens
            for idx, item in enumerate(items, 1):
                if item.is_dir():
                    icon = "📁"
                    size = ""
                elif item.suffix == ".py":
                    icon = "🐍"
                    size = f"{item.stat().st_size} bytes"
                else:
                    icon = "📄"
                    size = f"{item.stat().st_size} bytes"
                
                table.add_row(str(idx), icon, item.name, size)
            
            console.print(table)
            console.print("\n[yellow]Comandos:[/yellow]")
            console.print("  [cyan]número[/cyan] - Abrir/Entrar")
            console.print("  [cyan]n[/cyan] - Novo arquivo")
            console.print("  [cyan]q[/cyan] - Sair")
            console.print("  [cyan]r[/cyan] - Executar arquivo Python")
            
            choice = Prompt.ask("\n> ", default="q").strip().lower()
            
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
        console.print("\n[yellow]Criar novo arquivo[/yellow]")
        filename = Prompt.ask("Nome do arquivo (com extensão)")
        
        if not filename:
            return None
        
        new_file = directory / filename
        if new_file.exists():
            if not Confirm.ask("[yellow]Arquivo já existe. Sobrescrever?[/yellow]"):
                return None
        
        try:
            new_file.touch()
            console.print(f"[green]✓ Arquivo criado: {filename}[/green]")
            return new_file
        except Exception as e:
            console.print(f"[red]❌ Erro ao criar arquivo: {e}[/red]")
            return None
    
    def run_python_file(self, directory: Path):
        """Executa um arquivo Python"""
        console.print("\n[yellow]Digite o número do arquivo Python para executar[/yellow]")
        
        py_files = [f for f in directory.glob("*.py")]
        if not py_files:
            console.print("[red]Nenhum arquivo Python encontrado[/red]")
            input("\nPressione Enter...")
            return
        
        for idx, f in enumerate(py_files, 1):
            console.print(f"  {idx}. {f.name}")
        
        choice = Prompt.ask("> ")
        if not choice.isdigit():
            return
        
        idx = int(choice) - 1
        if 0 <= idx < len(py_files):
            self.execute_python(py_files[idx])
    
    def execute_python(self, file_path: Path):
        """Executa arquivo Python"""
        self.clear_screen()
        console.print(Panel(
            f"[bold]Executando: {file_path.name}[/bold]",
            style="green"
        ))
        console.print("=" * 60)
        
        try:
            result = subprocess.run(
                [sys.executable, str(file_path)],
                cwd=file_path.parent,
                capture_output=False,
                text=True
            )
            console.print("=" * 60)
            console.print(f"\n[{'green' if result.returncode == 0 else 'red'}]"
                        f"Código de saída: {result.returncode}[/]")
        except Exception as e:
            console.print(f"[red]❌ Erro: {e}[/red]")
        
        input("\nPressione Enter para continuar...")
    
    def load_file(self, file_path: Path) -> bool:
        """Carrega arquivo no buffer"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                self.buffer = f.read().splitlines()
            
            self.current_file = file_path
            self.modified = False
            return True
        except Exception as e:
            console.print(f"[red]❌ Erro ao carregar: {e}[/red]")
            return False
    
    def save_file(self) -> bool:
        """Salva buffer em arquivo"""
        if not self.current_file:
            console.print("[yellow]Nenhum arquivo aberto[/yellow]")
            return False
        
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.buffer))
            
            self.modified = False
            console.print(f"[green]✓ Salvo: {self.current_file.name}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Erro ao salvar: {e}[/red]")
            return False
    
    def edit_file(self):
        """Editor de texto simples"""
        if not self.current_file:
            return
        
        while True:
            self.clear_screen()
            mod_indicator = "[+] " if self.modified else ""
            self.show_header(f"📝 {mod_indicator}{self.current_file.name}")
            
            # Mostra conteúdo com syntax highlighting
            if self.current_file.suffix == '.py':
                syntax = Syntax(
                    '\n'.join(self.buffer),
                    "python",
                    line_numbers=True,
                    theme="monokai"
                )
                console.print(Panel(syntax, title="Conteúdo"))
            else:
                for idx, line in enumerate(self.buffer[:50], 1):  # Limita a 50 linhas
                    console.print(f"[dim]{idx:3d}[/dim] | {line}")
                
                if len(self.buffer) > 50:
                    console.print(f"\n[dim]... e mais {len(self.buffer) - 50} linhas[/dim]")
            
            console.print("\n[yellow]Opções:[/yellow]")
            console.print("  [cyan]e[/cyan] - Editar no editor externo")
            console.print("  [cyan]r[/cyan] - Executar (se for Python)")
            console.print("  [cyan]s[/cyan] - Salvar")
            console.print("  [cyan]d[/cyan] - Ver Doxoade check")
            console.print("  [cyan]q[/cyan] - Voltar ao explorador")
            
            choice = Prompt.ask("\n> ", default="q").strip().lower()
            
            if choice == 'q':
                if self.modified:
                    if Confirm.ask("[yellow]Arquivo modificado. Salvar?[/yellow]"):
                        self.save_file()
                break
            elif choice == 's':
                self.save_file()
                input("\nPressione Enter...")
            elif choice == 'e':
                self.open_external_editor()
            elif choice == 'r' and self.current_file.suffix == '.py':
                if self.modified:
                    self.save_file()
                self.execute_python(self.current_file)
            elif choice == 'd':
                self.run_doxoade_check()
    
    def open_external_editor(self):
        """Abre arquivo no editor externo"""
        if not self.current_file:
            return
        
        editors = {
            'nt': ['notepad.exe', 'notepad++.exe'],
            'posix': ['nano', 'vim', 'vi', 'code']
        }
        
        editor_list = editors.get(os.name, ['nano'])
        
        for editor in editor_list:
            try:
                subprocess.run([editor, str(self.current_file)])
                # Recarrega após edição
                self.load_file(self.current_file)
                return
            except FileNotFoundError:
                continue
        
        console.print("[red]Nenhum editor disponível[/red]")
        input("\nPressione Enter...")
    
    def run_doxoade_check(self):
        """Executa doxoade check no arquivo atual"""
        if not self.current_file:
            return
        
        self.clear_screen()
        console.print(Panel(
            f"[bold]Doxoade Check: {self.current_file.name}[/bold]",
            style="cyan"
        ))
        
        try:
            result = subprocess.run( # noqa
                ['doxoade', 'check', str(self.current_file)],
                cwd=self.current_file.parent,
                capture_output=False
            )
        except Exception as e:
            console.print(f"[red]❌ Erro: {e}[/red]")
        
        input("\n\nPressione Enter para continuar...")
    
    def run(self):
        """Loop principal"""
        while True:
            # Explorador de arquivos
            selected_file = self.file_explorer()
            
            if selected_file is None:
                break
            
            # Carrega e edita arquivo
            if self.load_file(selected_file):
                self.edit_file()


def mobile_ide_main(start_path: str = ".", file: Optional[str] = None):
    """Função principal"""
    try:
        ide = MobileIDE(start_path)
        
        # Se arquivo especificado, abre diretamente
        if file:
            file_path = Path(file).resolve()
            if file_path.exists():
                ide.load_file(file_path)
                ide.edit_file()
            else:
                console.print(f"[red]❌ Arquivo não encontrado: {file}[/red]")
                return
        else:
            ide.run()
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Saindo...[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Erro fatal: {e}[/red]")
        import traceback
        traceback.print_exc()


# === INTEGRAÇÃO COM DOXOADE CLI ===
if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    mobile_ide_main(path)
else:
    import click
    
    @click.command('ide')
    @click.option('--path', default='.', help='Diretório inicial')
    @click.option('--file', help='Abrir arquivo específico')
    def ide(path, file):
        """
        🚀 IDE móvel multiplataforma (Windows/Linux/Termux)
        
        Recursos:
        - Explorador de arquivos interativo
        - Visualização com syntax highlighting
        - Execução de scripts Python
        - Integração com Doxoade check
        - Editor externo (Notepad++/nano/vim)
        
        Exemplos:
          doxoade ide
          doxoade ide --path ~/projetos
          doxoade ide --file main.py
        """
        mobile_ide_main(path, file)
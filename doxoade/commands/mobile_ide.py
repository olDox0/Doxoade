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
from datetime import datetime  # ← ADICIONE ESTA LINHA
from rich.console import Console
from rich.prompt import Confirm

try:
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.prompt import Prompt, Confirm # noqa
    # [DOX-UNUSED] from rich.layout import Layout # noqa
    # [DOX-UNUSED] from rich.live import Live # noqa
except ImportError:
    print("❌ Dependência faltando. Instalando rich...")
    subprocess.run([sys.executable, "-m", "pip", "install", "rich", "prompt_toolkit"])
    # [DOX-UNUSED] from rich.console import Console # noqa
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.prompt import Prompt, Confirm

console = Console()

# DETECTOR DE AMBIENTE

def is_termux():
    """Detecta se está rodando no Termux"""
    return os.path.exists('/data/data/com.termux')

def get_best_editor():
    """Retorna o editor escolhido pelo usuário ou o melhor disponível"""

    # 1. Se o usuário definiu EDITOR no sistema, respeita
    env_editor = os.environ.get("EDITOR")
    if env_editor:
        return env_editor

    # 2. Se estiver no Termux, prioriza micro > nano > vim
    if is_termux():
        editors = ['micro', 'nano', 'vim', 'vi']
    else:
        if os.name == 'nt':
            editors = ['notepad++.exe', 'code', 'notepad.exe']
        else:
            editors = ['code', 'gedit', 'nano', 'vim']

    for editor in editors:
        try:
            subprocess.run(
                ['which', editor] if os.name != 'nt' else ['where', editor],
                capture_output=True,
                check=True
            )
            return editor
        except Exception:
            continue

    return 'nano'

# COMANDOS TERMUX-SPECIFIC

def termux_share_file(file_path: Path):
    """Compartilha arquivo usando o Termux API"""
    if not is_termux():
        console.print("[yellow]Comando disponível apenas no Termux[/yellow]")
        return
    
    try:
        subprocess.run(['termux-share', str(file_path)])
        console.print(f"[green]✓ Compartilhando: {file_path.name}[/green]")
    except FileNotFoundError:
        console.print("[red]Instale termux-api: pkg install termux-api[/red]")

def termux_clipboard_copy(text: str):
    """Copia texto para área de transferência (Termux)"""
    if not is_termux():
        console.print("[yellow]Comando disponível apenas no Termux[/yellow]")
        return
    
    try:
        subprocess.run(['termux-clipboard-set'], input=text.encode())
        console.print("[green]✓ Copiado para área de transferência[/green]")
    except FileNotFoundError:
        console.print("[red]Instale termux-api: pkg install termux-api[/red]")

def termux_toast(message: str):
    """Mostra notificação toast (Termux)"""
    if is_termux():
        try:
            subprocess.run(['termux-toast', message])
        except Exception:
            pass

def setup_micro_split_workflow():
    """Configura atalho Alt-d no micro para workflow de split."""
    import json
    
    config_dir = Path.home() / ".config" / "micro"
    config_dir.mkdir(parents=True, exist_ok=True)
    bindings_file = config_dir / "bindings.json"
    
    current_bindings = {}
    if bindings_file.exists():
        try:
            current_bindings = json.loads(bindings_file.read_text())
        except Exception:
            pass
            
    # Adiciona o atalho Dual View
    current_bindings["Alt-d"] = "command:hsplit,command:new"
    
    # Salva
    bindings_file.write_text(json.dumps(current_bindings, indent=4))
    console.print("[green]✓ Workflow 'Alt-d' configurado no Micro![/green]")
    console.print("   > Abra um arquivo e pressione Alt+d para abrir o painel de rascunho.")

# NOVOS COMANDOS PARA A IDE

def show_file_info(file_path: Path):
    """Mostra informações detalhadas do arquivo"""
    stat = file_path.stat()
    
    table = Table(title=f"📊 Informações: {file_path.name}")
    table.add_column("Propriedade", style="cyan")
    table.add_column("Valor", style="white")
    
    table.add_row("Tamanho", f"{stat.st_size:,} bytes")
    table.add_row("Linhas", str(len(file_path.read_text(errors='ignore').splitlines())))
    table.add_row("Modificado", str(datetime.fromtimestamp(stat.st_mtime)))  # ← AGORA FUNCIONA
    table.add_row("Permissões", oct(stat.st_mode)[-3:])
    table.add_row("Caminho completo", str(file_path.resolve()))
    
    console.print(table)
    input("\nPressione Enter...")

def git_status_visual():
    """Mostra status do Git de forma visual"""
    try:
        result = subprocess.run(
            ['git', 'status', '--short'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            syntax = Syntax(result.stdout, "diff", theme="monokai")
            console.print("\n[bold cyan]📊 Git Status:[/bold cyan]")
            console.print(syntax)
        else:
            console.print("[yellow]Não é um repositório Git[/yellow]")
    except FileNotFoundError:
        console.print("[red]Git não instalado[/red]")
    
    input("\nPressione Enter...")

def quick_search_in_files(directory: Path, term: str):
    """Busca rápida em arquivos"""
    console.print(f"\n[cyan]🔍 Buscando '{term}'...[/cyan]")
    
    results = []
    for file_path in directory.rglob("*.py"):
        try:
            lines = file_path.read_text(errors='ignore').splitlines()
            for i, line in enumerate(lines, 1):
                if term.lower() in line.lower():
                    results.append((file_path, i, line.strip()))
        except Exception:
            continue
    
    if results:
        table = Table(title=f"Encontrado {len(results)} resultado(s)")
        table.add_column("Arquivo", style="cyan")
        table.add_column("Linha", style="yellow", width=6)
        table.add_column("Conteúdo", style="white")
        
        for path, line_num, content in results[:20]:  # Limita a 20
            table.add_row(path.name, str(line_num), content[:60] + "...")
        
        console.print(table)
        
        if len(results) > 20:
            console.print(f"\n[dim]... e mais {len(results) - 20} resultado(s)[/dim]")
    else:
        console.print("[yellow]Nenhum resultado encontrado[/yellow]")
    
    input("\nPressione Enter...")


# MENU ESTENDIDO PARA A IDE

def show_extended_menu(ide_instance):
    """Menu com comandos avançados"""
    while True:
        ide_instance.clear_screen()
        
        console.print(Panel(
            "[bold cyan]🛠️  MENU AVANÇADO[/bold cyan]",
            style="bold white on blue"
        ))
        
        options = [
            ("1", "📊", "Informações do arquivo"),
            ("2", "🔍", "Buscar em arquivos"),
            ("3", "📋", "Git status"),
            ("4", "📤", "Compartilhar arquivo (Termux)"),
            ("5", "📋", "Copiar caminho"),
            ("6", "🧹", "Limpar cache Python"),
            ("7", "🔙", "Voltar")
        ]
        
        for key, icon, desc in options:
            color = "cyan" if key != "7" else "yellow"
            console.print(f"  [{color}]{key}. {icon} {desc}[/{color}]")
        
        choice = Prompt.ask("\n> ", default="7")
        
        if choice == "1" and ide_instance.current_file:
            show_file_info(ide_instance.current_file)
        elif choice == "2":
            term = Prompt.ask("Buscar por")
            if term:
                quick_search_in_files(ide_instance.start_path, term)
        elif choice == "3":
            git_status_visual()
        elif choice == "4" and ide_instance.current_file:
            termux_share_file(ide_instance.current_file)
            input("\nPressione Enter...")
        elif choice == "5" and ide_instance.current_file:
            path_str = str(ide_instance.current_file.resolve())
            if is_termux():
                termux_clipboard_copy(path_str)
            else:
                console.print(f"\n[cyan]{path_str}[/cyan]")
            input("\nPressione Enter...")
        elif choice == "6":
            clean_python_cache(ide_instance.start_path)
        elif choice == "7":
            break

def clean_python_cache(directory: Path):
    """Remove arquivos __pycache__ e .pyc"""
    import shutil
    removed = 0
    
    for item in directory.rglob("__pycache__"):
        try:
            shutil.rmtree(item)
            removed += 1
        except Exception:
            pass
    
    for item in directory.rglob("*.pyc"):
        try:
            item.unlink()
            removed += 1
        except Exception:
            pass
    
    console.print(f"[green]✓ {removed} arquivo(s)/pasta(s) removido(s)[/green]")
    input("\nPressione Enter...")


# INSTALAÇÃO AUTOMÁTICA DE EDITORES (TERMUX)

def setup_termux_editors():
    """Instala os melhores editores para Termux"""
    if not is_termux():
        console.print("[yellow]Apenas para Termux[/yellow]")
        return
    
    console.print("\n[bold cyan]📦 Instalador de Editores para Termux[/bold cyan]\n")
    
    editors = [
        ("micro", "Editor moderno e intuitivo (RECOMENDADO)"),
        ("nano", "Editor clássico e leve"),
        ("vim", "Editor poderoso (curva de aprendizado)"),
    ]
    
    for editor, desc in editors:
        if Confirm.ask(f"Instalar {editor}? ({desc})"):
            console.print(f"[cyan]Instalando {editor}...[/cyan]")
            subprocess.run(['pkg', 'install', '-y', editor])
    
    console.print("\n[green]✓ Configuração concluída![/green]")


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
        print("\033[2J\033[H", end="")
    
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
            console.print("  [cyan]m[/cyan] - Menu avançado")
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
            elif choice == 'm':
                show_extended_menu(self)
    
    def open_external_editor(self):
        """Abre arquivo no editor externo com detecção inteligente"""
        if not self.current_file:
            return
    
        editor = get_best_editor()
    
        # Correção automática para Windows
        if os.name == 'nt':
            if editor.lower() in ['notepad++', 'notepadpp']:
                possíveis = [
                    r"C:\Program Files\Notepad++\notepad++.exe",
                    r"C:\Program Files (x86)\Notepad++\notepad++.exe"
                ]
                for caminho in possíveis:
                    if os.path.exists(caminho):
                        editor = caminho
                        break
                else:
                    editor = "notepad++.exe"
    
        try:
            subprocess.run([editor, str(self.current_file)])
            self.load_file(self.current_file)
        except FileNotFoundError:
            console.print(f"[red]Editor não encontrado: {editor}[/red]")
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
            subprocess.run(
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


def mobile_ide_main(start_path: str = ".", file: Optional[str] = None, editor: Optional[str] = None):
    """Função principal"""
    try:
        ide = MobileIDE(start_path)
        if editor:
            os.environ["EDITOR"] = editor

        
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
    path = sys.argv[1] if len(sys.argv) > 1 else "."
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

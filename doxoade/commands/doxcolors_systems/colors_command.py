# doxoade/doxoade/commands/doxcolors_systems/colors_command.py

import click
import os
import re
import shutil
import time
from pathlib import Path
import doxoade.tools as dox_tools
from doxoade.tools.doxcolors import Fore, Style

# Localização do arquivo fonte para injeção
DOXCOLORS_SOURCE_PATH = Path(dox_tools.__file__).parent / 'doxcolors.py'
#COLORS_CONF_TEMPLATE = '\n# Arquivo de Paleta de Cores do Doxcolors\n# Formatos: NOME = #RRGGBB ou NOME = Código;ANSI\n[SUCCESS] = #26bc5f\n[ERROR] = #FF6700\n[WARNING] = #E8AA00\n[INFO] = #006CFF\n[HIGHLIGHT] = 1;36\n'.strip()
COLORS_CONF_TEMPLATE = """
# Padrão Nexus de Identidade Visual
[PRIMARY]   = #006CFF
[SUCCESS]   = #26bc5f
[ERROR]     = #FF6700
[WARNING]   = #E8AA00
[STABLE]    = #B0B0B0
[VOLATILE]  = #FF00FF
[DEBUG]     = 1;30
""".strip()

class ColorMigrator:
    def __init__(self, target_path, dry_run=True, package_name='doxoade'):
        self.target_path = Path(target_path).resolve()
        self.dry_run = dry_run
        self.modifications = 0
        self.package_name = package_name
        self.init_call_pattern = re.compile(r'^\s*init\(.*\)\s*$', re.MULTILINE)
        self.colorama_import_pattern = re.compile(r'from\s+colorama\s+import\s+(.*)')

    def run_migration(self):
        """Orquestra o processo de migração."""
        label = "SIMULANDO" if self.dry_run else "EXECUTANDO"
        click.secho(f"--- {label} MIGRAÇÃO: {self.target_path.name} ---", fg="cyan", bold=True)
        
        self._inject_doxcolors()
        self._scan_and_refactor()
        
        click.echo('\n' + Fore.CYAN + '--- Resumo ---')
        if self.modifications == 0:
            click.secho('Nenhuma modificação necessária.', fg="green")
        else:
            click.secho(f'Detectadas {self.modifications} modificações.', fg="yellow")

    def _inject_doxcolors(self):
        """Injeta o doxcolors.py no projeto alvo."""
        project_root = self.target_path if self.target_path.is_dir() else self.target_path.parent
        tools_dir = project_root / self.package_name / 'tools'
        target_file = tools_dir / 'doxcolors.py'

        if self.dry_run:
            if not target_file.exists():
                click.secho(f"    [DRY] Injetaria: {target_file.relative_to(project_root)}", fg="yellow")
            return

        if not target_file.exists():
            tools_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DOXCOLORS_SOURCE_PATH, target_file)
            click.secho(f"    [OK] Injetado: {target_file.name}", fg="green")

    def _scan_and_refactor(self):
        """Varre os arquivos .py para refatoração."""
        if self.target_path.is_file():
            self._refactor_file(self.target_path)
        else:
            ignore_dirs = {'venv', '.git', '__pycache__', 'build', 'dist'}
            for root, dirs, files in os.walk(self.target_path):
                dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
                for file in files:
                    if file.endswith('.py'):
                        self._refactor_file(Path(root) / file)

    def _sub_colorama_import(self, match):
        """Converte import do colorama para doxcolors."""
        imported_names_str = match.group(1).strip().replace('(', '').replace(')', '')
        names = [name.strip() for name in imported_names_str.split(',')]
        filtered_names = [name for name in names if not name.startswith('init')]
        if not filtered_names:
            return ''
        return f'from {self.package_name}.tools.doxcolors import {", ".join(filtered_names)}'

    def _refactor_file(self, file_path: Path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            new_lines, made_change, file_diff = [], False, []

            for i, line in enumerate(lines):
                new_line = line
                stripped = line.strip()

                # 1. Caso: init(...)
                if self.init_call_pattern.search(line):
                    new_line, made_change = "", True
                
                # 2. Caso: from colorama import ...
                elif "from colorama import" in line:
                    match = self.colorama_import_pattern.search(line)
                    if match:
                        replacement = self._sub_colorama_import(match)
                        new_line, made_change = (replacement + "\n") if replacement else "", True
                
                # 3. Caso: import colorama (NOVO: Para legados)
                elif stripped == "import colorama":
                    new_line = f"import {self.package_name}.tools.doxcolors as colorama\n"
                    made_change = True

                if new_line != line:
                    file_diff.append((i + 1, line.strip(), new_line.strip()))
                
                if new_line or not line.strip():
                    new_lines.append(new_line)

            if made_change:
                self.modifications += 1
                if self.dry_run:
                    click.secho(f"\n[INSIGHT] {file_path.name}", fg="bright_cyan", bold=True)
                    for ln, old, new in file_diff:
                        click.echo(f"  L{ln}: ", nl=False)
                        click.secho(f"- {old}", fg="red", nl=False)
                        click.echo("  ->  ", nl=False)
                        click.secho(new, fg="green")
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    click.secho(f"  [FIXED] {file_path.name}", fg="green")
        except Exception as e:
            click.secho(f"  [ERRO] {file_path.name}: {e}", fg="red")

@click.group(name='doxcolors', invoke_without_command=True)
@click.option('--path', '-p', default='.', type=click.Path(exists=True))
@click.option('--apply', is_flag=True, help='Aplica as mudanças.')
@click.option('--package-name', default='doxoade')
def doxcolors_cmd(path, apply, package_name):
    """Refatoração Colorama -> Doxcolors."""
    ctx = click.get_current_context()
    if ctx.invoked_subcommand is None:
        migrator = ColorMigrator(target_path=path, dry_run=not apply, package_name=package_name)
        migrator.run_migration()

@doxcolors_cmd.command('config')
def config():
    """Cria arquivo colors.conf."""
    config_file = Path('colors.conf')
    if config_file.exists() and not click.confirm("Sobrescrever colors.conf?"): return
    config_file.write_text(COLORS_CONF_TEMPLATE, encoding='utf-8')
    click.secho("[OK] colors.conf criado.", fg="green")
    
@doxcolors_cmd.command('play')
@click.argument('file', type=click.Path(exists=True))
@click.option('--interval', '-i', default=0.1, help="Velocidade da animação.")
@click.option('--loops', '-l', default=1, help="Quantidade de repetições.")
def play_animation_command(file, interval, loops):
    """Reproduz um arquivo de animação Nexus (.nxa ou .txt)."""
    from doxoade.tools.doxcolors import colors
    
    frames = colors.UI.load_animation(file)
    if not frames:
        click.secho("[ERRO] Nenhum frame encontrado no arquivo.", fg="red")
        return
        
    click.secho(f"[*] Reproduzindo: {file}", fg="cyan")
    colors.UI.play_animation(frames, interval=interval, loops=loops)
    
@doxcolors_cmd.command('new-anim')
@click.argument('name')
def create_anim_template(name):
    """Cria um template de animação para o usuário editar."""
    filename = f"{name}.nxa"
    template = "Frame 1\n===FRAME===\nFrame 2\n===FRAME===\nFrame 3"
    Path(filename).write_text(template, encoding='utf-8')
    click.secho(f"[OK] Template criado: {filename}", fg="green")
    
@doxcolors_cmd.command('load')
@click.argument('file', type=click.Path(exists=True))
@click.option('--seconds', '-s', default=3)
def load_test_command(file, seconds):
    """Testa uma animação assíncrona com proteção contra crash."""
    from doxoade.tools.doxcolors import colors
    
    # O 'with' garante que anim.stop() seja chamado mesmo se der erro dentro do bloco
    with colors.UI.loader(file, interval=0.15) as anim:
        # Aqui simulamos o trabalho real
        time.sleep(seconds)
        
    click.secho("\n[OK] Trabalho finalizado com sucesso!", fg="green")
# doxoade/commands/migrate_colors.py
import click
import os
import re
import shutil
from pathlib import Path

# Corrigido: A importação do próprio módulo também deve ser absoluta.
from doxoade.tools.doxcolors import Fore, Style

# Caminho para o código-fonte do doxcolors, para que ele possa ser injetado.
try:
    DOXCOLORS_SOURCE_PATH = Path(__file__).resolve().parent.parent / "tools" / "doxcolors.py"
except NameError:
    # Fallback para ambientes onde __file__ não está definido
    DOXCOLORS_SOURCE_PATH = Path("doxoade/tools/doxcolors.py")

# Template para o arquivo de configuração de cores (mantido)
COLORS_CONF_TEMPLATE = """
# Arquivo de Paleta de Cores do Doxcolors
# Formatos: NOME = #RRGGBB ou NOME = Código;ANSI
[SUCCESS] = #26bc5f
[ERROR] = #FF6700
[WARNING] = #E8AA00
[INFO] = #006CFF
[HIGHLIGHT] = 1;36
""".strip()

class ColorMigrator:
    def __init__(self, target_path, dry_run=True, package_name="doxoade"):
        self.target_path = Path(target_path).resolve()
        self.dry_run = dry_run
        self.modifications = 0
        self.package_name = package_name
        # Expressão regular para encontrar a chamada `init()` do colorama
        self.init_call_pattern = re.compile(r"^\s*init\(autoreset=True\)\s*$", re.MULTILINE)
        # Expressão regular para encontrar a linha de importação do colorama
        self.colorama_import_pattern = re.compile(r"from\s+colorama\s+import\s+(.*)")

    def run_migration(self):
        """Orquestra o processo de migração."""
        click.echo(Fore.CYAN + f"--- Analisando caminho: {self.target_path} ---")
        if not self.dry_run:
            self._inject_doxcolors()
        
        self._scan_and_refactor()
        
        click.echo("\n" + Fore.CYAN + "--- Resumo da Migração ---")
        if self.modifications == 0:
            click.echo(Fore.GREEN + "Nenhuma modificação necessária.")
        else:
            click.echo(Fore.YELLOW + f"Detectadas {self.modifications} modificações em potencial.")
        
        if self.dry_run:
            click.echo(Fore.MAGENTA + f"\nModo de simulação. Para aplicar, use a flag {Style.BRIGHT}--apply{Style.NORMAL}.")
        else:
            click.echo(Fore.GREEN + Style.BRIGHT + "\nMigração aplicada com sucesso!")

    def _inject_doxcolors(self):
        """Copia o arquivo doxcolors.py para a pasta 'tools' do projeto alvo."""
        project_root = self.target_path if self.target_path.is_dir() else self.target_path.parent
        # Corrigido: assume uma estrutura de pasta 'tools' ou similar
        tools_dir = project_root / self.package_name / "tools"
        target_file = tools_dir / "doxcolors.py"

        if target_file.exists():
            click.echo(f"{Fore.WHITE}{Style.DIM}   > Módulo 'doxcolors.py' já existe.")
            return

        click.echo(f"{Fore.YELLOW}[+] Injetando 'doxcolors.py' em {tools_dir}...")
        try:
            os.makedirs(tools_dir, exist_ok=True)
            if not DOXCOLORS_SOURCE_PATH.exists():
                raise FileNotFoundError(f"Arquivo fonte não encontrado: {DOXCOLORS_SOURCE_PATH}")
            shutil.copy2(DOXCOLORS_SOURCE_PATH, target_file)
            click.echo(f"{Fore.GREEN}    -> Injetado com sucesso.")
        except Exception as e:
            click.echo(Fore.RED + f"    -> FALHA ao injetar 'doxcolors.py': {e}", err=True)
            raise

    def _sub_colorama_import(self, match):
        """
        Função de substituição para a regex. Remove 'init' da lista e corrige o caminho.
        """
        imported_names_str = match.group(1).strip()
        
        # Divide os nomes importados, remove espaços extras
        names = [name.strip() for name in imported_names_str.split(',')]
        
        # Filtra 'init' e qualquer variação que possa ter um 'as'
        filtered_names = [name for name in names if not name.startswith('init')]
        
        # Se não sobrar nada (só importava 'init'), retorna uma string vazia para apagar a linha.
        if not filtered_names:
            return ""
        
        # Reconstrói a string de importação com o caminho correto e sem 'init'.
        new_names_str = ", ".join(filtered_names)
        return f"from {self.package_name}.tools.doxcolors import {new_names_str}"

    def _scan_and_refactor(self):
        """Varre arquivos .py em um diretório ou processa um único arquivo."""
        if self.target_path.is_file():
            self._refactor_file(self.target_path)
        else:
            ignore_dirs = {'venv', '.git', '__pycache__', 'build', 'dist', '.doxoade_cache'}
            for root, dirs, files in os.walk(self.target_path):
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                for file in files:
                    if file.endswith(".py"):
                        self._refactor_file(Path(root) / file)

    def _refactor_file(self, file_path: Path):
        """Aplica as regras de refatoração em um único arquivo."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            modified_content = original_content
            made_change = False

            # 1. Remove a chamada `init(autoreset=True)`
            modified_content, num_subs_call = self.init_call_pattern.subn("", modified_content)
            if num_subs_call > 0:
                made_change = True

            # 2. Converte `from doxoade.tools.doxcolors import ...` usando a lógica inteligente
            modified_content, num_subs_import = self.colorama_import_pattern.subn(self._sub_colorama_import, modified_content)
            if num_subs_import > 0:
                made_change = True

            # Limpa linhas vazias múltiplas que podem ter sido deixadas para trás
            if made_change:
                modified_content = re.sub(r'\n{3,}', '\n\n', modified_content).strip()

            if made_change:
                self.modifications += 1
                display_path = file_path.relative_to(self.target_path.parent)
                click.echo(f"{Fore.WHITE}  -> Modificação sugerida em: {display_path}")
                if not self.dry_run:
                    # Cria backup antes de salvar
                    shutil.copy2(file_path, f"{file_path}.bak")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
        except Exception as e:
            click.echo(f"{Fore.RED}  -> Erro ao processar {file_path}: {e}", err=True)

# --- Definição dos Comandos CLI ---

@click.group(invoke_without_command=True)
@click.option('--path', '-p', 'path', type=click.Path(exists=True, file_okay=True, dir_okay=True, resolve_path=True), default='.', help="Caminho do projeto ou arquivo a ser migrado.")
@click.option('--apply', is_flag=True, help="Aplica as modificações e cria backups (.bak).")
@click.option('--package-name', default='doxoade', help="Nome do pacote raiz para o caminho de importação.")
@click.pass_context
def migrate_colors(ctx, path, apply, package_name):
    """Automatiza a migração de 'colorama' para o módulo 'doxcolors'."""
    if ctx.invoked_subcommand is None:
        migrator = ColorMigrator(target_path=path, dry_run=not apply, package_name=package_name)
        migrator.run_migration()

@migrate_colors.command()
def config():
    """Cria um arquivo de configuração 'colors.conf' no diretório atual."""
    config_file = Path("colors.conf")
    click.echo(Fore.CYAN + "--- Configuração da Paleta Doxcolors ---")
    if config_file.exists():
        if not click.confirm(Fore.YELLOW + f"O arquivo '{config_file}' já existe. Deseja sobrescrevê-lo?"):
            click.echo("Operação cancelada.")
            return
    try:
        config_file.write_text(COLORS_CONF_TEMPLATE, encoding='utf-8')
        click.echo(Fore.GREEN + f"[OK] Arquivo '{config_file}' criado/atualizado com sucesso.")
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] Falha ao criar arquivo de configuração: {e}", err=True)
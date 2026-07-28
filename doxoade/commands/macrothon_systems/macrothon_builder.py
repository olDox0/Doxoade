# -*- coding: utf-8 -*-
# doxoade/commands/macrothon_systems/macrothon_builder.py
"""
Macrothon Builder - O Ativador de Infraestrutura Soberana.
Compliance: PASC-8 (Sincronização Sem Fricção), OSL-4.
A House não é uma pasta. A House é o Silo.
"""
import os
import click
from pathlib import Path
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.telemetry_tools.logger import ExecutionLogger
from .uroboros_engine import UroborosEngine

class MacrothonHouseEngine:
    def __init__(self, name):
        self.raw_name = name.replace("_house", "")
        self.house_name = f"{self.raw_name}_house"
        self.base_path = Path(os.getcwd()) / self.house_name

    def setup_environment(self):
        """Cria o canteiro de obras industrial."""
        click.secho(f"[*] Construindo House Industrial: {Fore.CYAN}{self.house_name}{Style.RESET_ALL}...", fg="cyan")
        
        for folder in ["bricks", "data", "logs", "output"]:
            (self.base_path / folder).mkdir(parents=True, exist_ok=True)

        blueprint_name = f"{self.raw_name}.macrothon"
        # [FIX] Passando o nome corretamente para o template
        blueprint_content = self._generate_empty_template(blueprint_name)
        (self.base_path / blueprint_name).write_text(blueprint_content, encoding='utf-8')
        
        self._generate_metal_toml()

        click.secho(f"\n✅ House '{self.house_name}' pronta!", fg="green", bold=True)
        click.echo(f"   🏠 Arquitetura: {blueprint_name}")
        click.echo(f"   ⚒️  Metalurgia : {self.raw_name}_metalcraft.toml")

    def _generate_metal_toml(house_name: str) -> str:
        """Gera o contrato em UTF-8 puro (Anti-Unicode-Bug)."""
        return f"""# Metalcraft Configuration for House: {house_name}
[project]
name = "{house_name}"
version = "1.0.0"
type = "shared_lib"

[compiler]
engine = "gcc"
std = "c11"
opt = "O3"
shield = true
incremental = true

[paths]
sources = ["src/native/*.c"]
headers = ["src/native/include/"]
output  = "bin/"
"""

    def _generate_empty_template(self, name):
        now = datetime.now().strftime("%Y-%m-%d")
        return f"""# Macrothon Blueprint: {name}
# Criado em: {now}

IMPORT {{
    # Exemplo: acervo modulo:funcao as ALIAS
    from doxoade.tools.doxcolors import Fore
}}

TREE {{
    data/
    bricks/
}}

# --- VARIÁVEIS ---

# --- SCRIPT DE FLUXO ---
print(Fore.CYAN + ">>> Maquinário {self.raw_name} iniciado.")
"""

@click.group('macrothon')
def macrothon_group():
    """🚀 Macrothon: Orquestração Semântica e Gestão de Houses."""
    pass

@macrothon_group.command('build')
@click.argument('name', required=False)
@click.option('--path', '-p', default='.', type=click.Path(exists=True), help='Caminho do Silo alvo.')
@click.pass_context
def macrothon_build(ctx, name, path):
    """Ativa a infraestrutura Macrothon (Blueprint + Metalcraft) no Silo atual."""
    target_path = Path(path).resolve()
    house_name = name or target_path.name
    
    if name:
        house_name = Path(name).name.rstrip('/\\')
    else:
        house_name = target_path.name
    
    if not house_name:
        click.secho("✘ Erro: Nome da House inválido.", fg="red")
        return
    
    with ExecutionLogger('macrothon_build', str(target_path), ctx.params) as _:
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [MACROTHON BUILD] ---{Style.RESET_ALL}")
        click.echo(f"[*] Ativando House Soberana: {Fore.YELLOW}{house_name}{Style.RESET_ALL} em {target_path}")

        # 🛡️ GARANTIA: Cria o diretório da house se ele não existir
        house_dir = target_path / "src" / "houses" / house_name
        house_dir.mkdir(parents=True, exist_ok=True)

        # 1. O Blueprint (O Contrato de Orquestração)
        blueprint_name = f"{house_name}.macrothon"
        blueprint_path = house_dir / blueprint_name
        
        blueprint_content = _generate_blueprint(house_name)
        blueprint_path.write_text(blueprint_content, encoding='utf-8')
        click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Blueprint selado: {Fore.CYAN}{blueprint_path.relative_to(target_path)}{Style.RESET_ALL}")

        # 2. O Metalcraft (O Contrato da Forja C) - Vai para a raiz do Silo
        metal_name = f"{house_name}_metalcraft.toml"
        metal_path = target_path / metal_name
        
        metal_content = _generate_metal_toml(house_name)
        metal_path.write_text(metal_content, encoding='utf-8')
        click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Forja C configurada: {Fore.CYAN}{metal_name}{Style.RESET_ALL}")

        # 3. Sincroniza o pyproject.toml se ainda não tiver o DNA
        pyproject_path = target_path / 'pyproject.toml'
        if pyproject_path.exists():
            toml_content = pyproject_path.read_text(encoding='utf-8')
            if '[tool.doxoade.macrothon]' not in toml_content:
                house_contract = f"""
[tool.doxoade.macrothon]
is_house = true
house_name = "{house_name}"
auto_sync = true
requires = [] 
"""
                pyproject_path.write_text(toml_content + house_contract, encoding='utf-8')
                click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} DNA Macrothon injetado no pyproject.toml.")

        click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✅ House '{house_name}' operacional!{Style.RESET_ALL}")
        click.echo(f"   🏠 Blueprint: {blueprint_path}")
        click.echo(f"   ⚒️  Metalcraft: {metal_path}")

def _generate_pyproject_toml(project_name: str) -> str:
    """Gera o contrato base do Silo (pyproject.toml) com suporte a dependências."""
    return f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "Silo Soberano forjado pelo Doxoade."
requires-python = ">=3.10"
# Declare as dependências aqui. O 'pip install .' resolve tudo.
dependencies = [
    "click",
    "libzim>=3.9.0",
    "zstandard",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["src*", "utils*"]

[tool.doxoade]
ignore = ["venv/", ".git/", "__pycache__/", ".doxoade/", "build/", "dist/"]
source_dir = "."
"""

def _generate_blueprint(house_name: str) -> str:
    """Gera o template do blueprint .macrothon."""
    return f"""# Blueprint Macrothon: {house_name}
# Forjado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

IMPORT {{
    from utils.doxcolors import Fore, Style
}}

TREE {{
    data/
    docs/
    src/
    tests/
}}

# Lógica de Orquestração (Executada pelo MacrothonRuntime)
print(Fore.CYAN + f">>> Maquinário {house_name} iniciado." + Style.RESET_ALL)
"""

@macrothon_group.command('run')
@click.argument('house_name')
def macrothon_run(house_name):
    """Executa a lógica de uma House específica."""
    from .macrothon_executor import MacrothonRuntime
    target_path = Path(os.getcwd()) / (house_name if "_house" in house_name else f"{house_name}_house")
    
    if not target_path.exists():
        click.secho(f"✘ Erro: House '{house_name}' não localizada.", fg="red")
        return

    runtime = MacrothonRuntime(target_path)
    runtime.run()
    
@macrothon_group.command('list')
def macrothon_list():
    """Lista os Silos/Houses localizados no diretório atual ou pai."""
    root = Path(os.getcwd())
    # Procura por pyproject.toml com a tag macrothon
    houses = []
    for pyproj in root.rglob('pyproject.toml'):
        try:
            content = pyproj.read_text(encoding='utf-8')
            if '[tool.doxoade.macrothon]' in content:
                houses.append(pyproj.parent)
        except Exception:
            continue

    if not houses:
        click.echo(f"{Fore.YELLOW}[-] Nenhuma House Macrothon localizada neste diretório.{Style.RESET_ALL}")
        return

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}--- 🏘️  INVENTÁRIO DE HOUSES ({len(houses)}) ---{Style.RESET_ALL}")
    for house in houses:
        blueprint = house / f"{house.name}.macrothon"
        status = "✅ Ativa" if blueprint.exists() else "⚪ Sem Blueprint"
        click.echo(f"\n{Fore.GREEN}🏠 {house.name}{Style.RESET_ALL}")
        click.echo(f"   {Fore.WHITE}Caminho : {Style.RESET_ALL}{house}")
        click.echo(f"   {Fore.WHITE}Status  : {Style.RESET_ALL}{status}")
    click.echo("")

def run_sync_logic(project_root):
    import hashlib
    from doxoade.tools.filesystem import _get_project_config
    from doxoade.core_database import get_db_connection
    
    config = _get_project_config(start_path=project_root)
    bricks_to_sync = config.get('bricks', {}) # Pega do TOML

    if not bricks_to_sync:
        click.echo("[-] Nenhum brick vinculado neste projeto.")
        return

    conn = get_db_connection()
    for name, local_path in bricks_to_sync.items():
        # 1. Busca o arquivo original no Acervo
        row = conn.execute("SELECT filename FROM moduloid_acervo WHERE name=?", (name,)).fetchone()
        if not row:
            click.echo(f"  [!] Brick '{name}' não encontrado no Acervo.")
            continue
            
        from doxoade.commands.moduloid_systems.moduloid_acervo import BRICKS_DIR
        source_path = BRICKS_DIR / row[0]
        
        # 2. Comparação por Hash (Zero I/O desnecessário)
        if os.path.exists(local_path):
            with open(local_path, 'rb') as f:
                local_hash = hashlib.md5(f.read()).hexdigest()
            with open(source_path, 'rb') as f:
                remote_hash = hashlib.md5(f.read()).hexdigest()
            
            if local_hash == remote_hash:
                continue # Estão em sincronia
        
        # 3. Sincronia Real
        click.secho(f"   [SYNC] Atualizando {name} -> {local_path}", fg='cyan')
        shutil.copy2(source_path, local_path)
    conn.close()
    
@macrothon_group.command('sync')
@click.option('--dry-run', is_flag=True)
def macrothon_sync(dry_run):
    """Sincroniza e Audita a integridade dos Bricks."""
    from .macrothon_sync import run_silent_sync
    click.secho("[*] Verificando DNA dos Bricks no Acervo...", fg="cyan")
    
    changes = run_silent_sync(os.getcwd(), dry_run=True)
    
    if not changes:
        click.secho("   [OK] Todos os Bricks estão em conformidade e estáveis.", fg='green')
        return

    click.echo(f"\n{'BRICK':<15} | {'QUALIDADE ESTÁTICA':<25} | {'DESTINO'}")
    click.echo("-" * 75)
    
    for c in changes:
        q_color = "green" if "ESTÁVEL" in c['quality'] else "red" if "CRÍTICO" in c['quality'] else "yellow"
        click.echo(f"{Fore.WHITE}{c['brick']:<15} | {click.style(c['quality'], fg=q_color):<34} | {c['path']}")

    if dry_run:
        click.secho("\n[MODO AUDITORIA] Nenhuma alteração foi feita.", fg='yellow', bold=True)
    else:
        if click.confirm("\nDeseja aplicar as atualizações nos Bricks estáveis?"):
            run_silent_sync(os.getcwd(), dry_run=False)
            click.secho("✅ Sincronia concluída.", fg='green', bold=True)

@macrothon_group.command('harvest')
@click.pass_context
def macrothon_harvest(ctx):
    """🌾 Colheita Uroboros: Promove sistemas locais para o Acervo Global."""
    from .uroboros_engine import UroborosEngine
    with ExecutionLogger('macrothon_harvest', os.getcwd(), ctx.params) as _:
        try:
            engine = UroborosEngine(os.getcwd())
            engine.harvest()
        except FileNotFoundError as e:
            click.secho(f"✘ Erro: {e}. Este projeto não é uma House Macrothon.", fg="red")
        except Exception as e:
            click.secho(f"✘ Falha na colheita: {e}", fg="red")

@macrothon_group.command('sync')
@click.pass_context
def macrothon_sync(ctx):
    """📥 Sincronização Uroboros: Puxa atualizações do Acervo Global para a House."""
    from .uroboros_engine import UroborosEngine
    with ExecutionLogger('macrothon_sync', os.getcwd(), ctx.params) as _:
        try:
            engine = UroborosEngine(os.getcwd())
            engine.sync()
        except FileNotFoundError as e:
            click.secho(f"✘ Erro: {e}. Este projeto não é uma House Macrothon.", fg="red")
        except Exception as e:
            click.secho(f"✘ Falha na sincronização: {e}", fg="red")
# -*- coding: utf-8 -*-
# doxoade/commands/macrothon_systems/macrothon_builder.py
import os
import click
from pathlib import Path
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style

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

    def _generate_metal_toml(self):
        """Gera o contrato em UTF-8 puro (Anti-Unicode-Bug)."""
        toml_name = f"{self.raw_name}_metalcraft.toml"
        toml_content = f"""# Nexus Metalcraft Build Contract
[project]
name = "{self.raw_name}"
house = "{self.house_name}"

[build]
# Bricks C para auto-compilacao
targets = [
    "bricks/cpu_math.c"
]
output_dir = "bricks"
options = "-shared -O3"
"""
        (self.base_path / toml_name).write_text(toml_content, encoding='utf-8')

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
@click.argument('name')
def macrothon_build(name):
    """Cria uma nova 'House' (ambiente de projeto) para o Macrothon."""
    engine = MacrothonHouseEngine(name)
    engine.setup_environment()

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
    """Lista todas as Houses (projetos) localizadas no diretório atual."""
    root = Path(os.getcwd())
    houses = [d for d in root.iterdir() if d.is_dir() and d.name.endswith("_house")]

    if not houses:
        click.echo(Fore.YELLOW + "[-] Nenhuma House localizada neste diretório.")
        return

    click.secho(f"\n--- 🏘️  INVENTÁRIO DE HOUSES ({len(houses)}) ---", fg="cyan", bold=True)
    
    for house in houses:
        # Busca o Blueprint principal
        prefix = house.name.replace("_house", "")
        blueprint = house / f"{prefix}.macrothon"
        if not blueprint.exists(): blueprint = house / "main.macrothon"
        
        # Conta os Bricks injetados
        bricks_count = len(list((house / "bricks").glob("*.py"))) if (house / "bricks").exists() else 0
        db_exists = "✅ DB Ativo" if (house / "data").exists() and list((house / "data").glob("*.db")) else "⚪ Sem DB"

        click.echo(f"\n{Fore.GREEN}🏠 {house.name}{Style.RESET_ALL}")
        if blueprint.exists():
            click.echo(f"   {Fore.CYAN}Blueprint: {Style.RESET_ALL}{blueprint.name}")
        click.echo(f"   {Fore.WHITE}Status   : {bricks_count} Bricks injetados | {db_exists}")
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

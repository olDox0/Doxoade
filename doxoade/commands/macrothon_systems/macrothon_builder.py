# doxoade/commands/macrothon_systems/macrothon_builder.py
import os
import click
from pathlib import Path
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style

class MacrothonHouseEngine:
    def __init__(self, name):
        self.house_name = f"{name}_house"
        self.base_path = Path(os.getcwd()) / self.house_name

    def setup_environment(self):
        """Cria o ambiente físico da House (A infraestrutura)."""
        click.secho(f"[*] Gerando ambiente: {Fore.CYAN}{self.house_name}{Style.RESET_ALL}...", fg="cyan")
        
        # 1. Estrutura de Pastas Padrão
        folders = ["bricks", "data", "logs", "output"]
        self.base_path.mkdir(exist_ok=True)
        
        for folder in folders:
            (self.base_path / folder).mkdir(exist_ok=True)
            click.echo(f"   {Fore.GREEN}├─{Style.RESET_ALL} /{folder}")

        # 2. Geração do Blueprint virgem (main.macrothon)
        blueprint_content = self._generate_empty_template()
        (self.base_path / "main.macrothon").write_text(blueprint_content, encoding='utf-8')
        
        click.secho(f"\n✅ House '{self.house_name}' construída com sucesso!", fg="green", bold=True)
        click.echo(f"📍 Coordenada: {self.base_path}")
        click.echo(f"📝 Comece a arquitetar em: {self.house_name}/main.macrothon")

    def _generate_empty_template(self):
        """O esqueleto inicial do arquiteto."""
        now = datetime.now().strftime("%Y-%m-%d")
        return f"""# Macrothon Blueprint v1.0
# House: {self.house_name} | Criado em: {now}

IMPORT {{
    # Exemplo: acervo modulo_nome: funcao as ALIAS
    from doxoade.tools.doxcolors import Fore
}}

TREE {{
    data/
    logs/
    bricks/
}}

# --- VARIÁVEIS ---
# Defina seus dados brutos aqui

# --- SCRIPT DE FLUXO ---
# Declare sua lógica semântica abaixo
"""

# --- COMANDO CLI ---

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
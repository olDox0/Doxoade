# -*- coding: utf-8 -*-
# doxoade/commands/init.py
import os
import sys
import re
import shutil
import click
from pathlib import Path
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

# --- CONFIGURAÇÃO DE FONTES DO NÚCLEO (DNA DO SISTEMA) ---
DOXOADE_ROOT = Path(__file__).resolve().parents[2]
CORE_TOOLS = {
    'doxcolors.py':   DOXOADE_ROOT / 'doxoade' / 'tools' / 'doxcolors.py',
    'error_info.py':  DOXOADE_ROOT / 'doxoade' / 'tools' / 'error_info.py',
    'rescue.py':      DOXOADE_ROOT / 'doxoade' / 'rescue.py',
    'telemetry.py':   DOXOADE_ROOT / 'doxoade' / 'tools' / 'telemetry_tools' / 'logger.py',
    'db_utils.py':    DOXOADE_ROOT / 'doxoade' / 'tools' / 'db_utils.py',
    'database.py':    DOXOADE_ROOT / 'doxoade' / 'database.py',
    'nexus_db.py':    DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'nexus_db.py', # NOVO
    'aegis_core.py':  DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'aegis_core.py',
    'warden.py':      DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'warden.py',
    'nexus.py':       DOXOADE_ROOT / 'doxoade' / 'tools' / 'templates' / 'embedded' / 'nexus.py',
}

def generate_silo_header(project_name, module_name):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return (
        f"# -*- coding: utf-8 -*-\n"
        f"# {'=' * 60}\n"
        f"# SILO INDEPENDENTE: {project_name.upper()}\n# MÓDULO: {module_name}\n"
        f"# SYNC: {ts}\n# {'=' * 60}\n\n"
    )

def _refactor_to_silo(content):
    """Refatorador Nexus v2: Colapsa a hierarquia para modo flat."""
    # 1. Redireciona o Wrapper de Banco de Dados (Aegis Shield)
    content = content.replace('import doxoade.tools.aegis.nexus_db as sqlite3', 'from . import nexus_db as sqlite3')
    content = content.replace('from doxoade.tools.aegis.nexus_db import', 'from .nexus_db import')
    
    # 2. Redireciona a conexão principal
    content = content.replace('from doxoade.database import', 'from .database import')
    
    # 3. Redireciona Ferramentas e Telemetria
    content = content.replace('from doxoade.tools.telemetry_tools.logger import', 'from .telemetry import')
    content = content.replace('from doxoade.tools.telemetry_tools import logger', 'from . import telemetry as logger')
    content = content.replace('from doxoade.rescue import', 'from .rescue import')
    
    # 4. Transforma ferramentas de ferramentas em ferramentas locais
    content = re.sub(r'from doxoade\.tools\.(\w+) import', r'from .\1 import', content)
    content = re.sub(r'from doxoade\.tools import (\w+)', r'from . import \1', content)
    
    # 5. Fix de imports diretos (Fallback except)
    content = re.sub(r'(?m)^(\s*)import (doxcolors|error_info|telemetry|rescue|database|nexus_db)(\b)', r'\1from . import \2\3', content)
    
    return content

@click.command('init')
@click.argument('project_name', required=False)
@click.pass_context
def init(ctx, project_name):
    if not project_name: project_name = click.prompt('Nome do novo projeto')
    
    project_path = Path(os.getcwd()) / project_name
    
    # 1. Criação da Topologia
    utils_path = project_path / 'utils'
    utils_path.mkdir(parents=True, exist_ok=True)
    (project_path / 'tests').mkdir(exist_ok=True)
    (project_path / 'docs').mkdir(exist_ok=True)

    with ExecutionLogger('init', '.', ctx.params) as _:
        click.echo(f"[*] {Fore.YELLOW}Injetando Motores Silo em {utils_path}...{Style.RESET_ALL}")
        
        for filename, source_path in CORE_TOOLS.items():
            dest_path = utils_path / filename
            if source_path.exists():
                raw_code = source_path.read_text(encoding='utf-8')
                silo_code = _refactor_to_silo(raw_code)
                
                # Patch de Path do Banco para histórico centralizado
                db_path = str(Path.home() / '.doxoade' / 'doxoade.db').replace('\\', '/')
                silo_code = silo_code.replace('Path.home() / ".doxoade" / "doxoade.db"', f'"{db_path}"')

                header = generate_silo_header(project_name, filename)
                dest_path.write_text(header + silo_code, encoding='utf-8')
                click.echo(f"   [✔] {filename}")

        # 3. Garantia de Pacote e Main
        (utils_path / '__init__.py').write_text("# Nexus Silo Package\n", encoding='utf-8')
        
        # CORREÇÃO AQUI: Usamos f-string para injetar o valor de project_name no texto, 
        # mas escapamos as chaves do Fore/Style com {{ }} para que elas fiquem no arquivo final.
        main_template = (
            "from utils.nexus import monitor, ignite\n\n"
            "Fore, Style = ignite()\n\n"
            "@monitor\n"
            "def main():\n"
            f"    print(f'{{Fore.GREEN}}✔ Silo {project_name} ativo e protegido!{{Style.RESET_ALL}}')\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        (project_path / 'main.py').write_text(main_template, encoding='utf-8')

    click.secho(f"\n✨ Projeto '{project_name}' pronto!", fg="green", bold=True)
    click.echo(f"Caminho: {project_path}")
    click.echo(f"Dica: Execute 'python main.py' para testar os motores embarcados.")

# --- TEMPLATES NEXUS GOLD ---

TEMPLATE_MAIN_PY = """# -*- coding: utf-8 -*-
import sys
import os

# Ativa o reconhecimento do pacote 'utils' local
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'utils')))

from utils.telemetry import ExecutionLogger
from utils.vulcan_link import VulcanBridge

def run_logic():
    \"\"\"Lógica de Negócio Nexus Gold.\"\"\"
    print("🚀 {project_name} operando via Nexus Engine.")

def main():
    # 1. Ativa ponte de aceleração Vulcan (Embedded)
    vb = VulcanBridge(os.getcwd())
    vb.apply_turbo('main', globals())

    # 2. Telemetria Síncrona (Garante registro em 0.000s)
    with ExecutionLogger('{project_name}', os.getcwd(), sys.argv) as logger:
        run_logic()

if __name__ == '__main__':
    try:
        main()
    except Exception:
        from utils.rescue import activate_protocol
        import traceback
        activate_protocol(traceback.format_exc())
        sys.exit(1)
"""

TEMPLATE_PYPROJECT = """
[project]
name = "{project_name}"
version = "0.1.0"

[tool.doxoade]
source_dir = "."
ignore = ["venv", ".git", "__pycache__", "build", "dist"]

[tool.vulcan]
enabled = true
"""

TEMPLATE_VOL1 = """# 📄 Volume 1: Identidade e Escopo ({project_name})

## 1️⃣ Existência (POR QUÊ?)
1. Qual problema real {project_name} resolve?
2. O que acontece se ele não existir?

## 2️⃣ Usuário Real (QUEM?)
3. Quem usa?
4. O que o usuário mais erra hoje?

## 🧠 Regra de Ouro
> **Projeto bom não é o que faz tudo. É o que sabe exatamente o que não faz.**
"""

TEMPLATE_VOL2 = """# 🏗️ Volume 2: Arquitetura e Motores

## 🛡️ utils/rescue.py
Proteção automática contra crash com interface forense.

## 📊 utils/telemetry.py
Grava CPU/RAM no banco de dados central (~/.doxoade/doxoade.db).

## 🔥 utils/vulcan_link.py
Suporte nativo para carregar binários .pyd/.so de alta performance.
"""

TEMPLATE_README = """# {project_name}

Projeto desenvolvido sob os padrões de excelência **Chief-Gold**.

## 🛠 Comandos Úteis
- Rodar: `python main.py`
- Auditar: `dox check .`
- Performance: `dox telemetry -c {project_name}`
"""
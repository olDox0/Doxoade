# -*- coding: utf-8 -*-
# doxoade/commands/init.py
import os
import sys
import re
import shutil
import click
import subprocess

from pathlib  import Path
from datetime import datetime
from doxoade.tools.doxcolors              import Fore, Style
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

# --- CONFIGURAÇÃO DE FONTES DO NÚCLEO (DNA DO SISTEMA) ---
DOXOADE_ROOT = Path(__file__).resolve().parents[2]
CORE_TOOLS = {
    'doxcolors.py':     DOXOADE_ROOT / 'doxoade' / 'tools' / 'doxcolors.py',
    'error_info.py':    DOXOADE_ROOT / 'doxoade' / 'tools' / 'error_info.py',
    'rescue.py':        DOXOADE_ROOT / 'doxoade' / 'rescue.py',
    'telemetry.py':     DOXOADE_ROOT / 'doxoade' / 'tools' / 'telemetry_tools' / 'logger.py',
    'db_utils.py':      DOXOADE_ROOT / 'doxoade' / 'tools' / 'db_utils.py',
    'database.py':      DOXOADE_ROOT / 'doxoade' / 'database.py',
    'nexus_db.py':      DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'nexus_db.py',
    'aegis_core.py':    DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'aegis_core.py',
    'warden.py':        DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'warden.py',
    'nexus.py':         DOXOADE_ROOT / 'doxoade' / 'tools' / 'templates' / 'embedded' / 'nexus.py',
    
    # MOTORES VULCAN SILO EMBEDDED
    'runtime.py':       DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'runtime.py',
    'meta_finder.py':   DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'meta_finder.py',
    'opt_cache.py':     DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'opt_cache.py',
    'lib_optimizer.py': DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'lib_optimizer.py',
    'safe_loader.py':   DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'vulcan_safe_loader.py',
}

def generate_silo_header(project_name, module_name):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return (
        f"# -*- coding: utf-8 -*-\n"
        f"# {'=' * 60}\n"
        f"# SILO INDEPENDENTE: {project_name.upper()}\n"
        f"# MÓDULO: {module_name}\n"
        f"# SYNC: {ts} / Nexus v3\n"
        f"# {'=' * 60}\n\n"
    )

def _refactor_to_silo(content):
    """Ajusta imports para funcionarem dentro da pasta utils/ de forma relativa."""
    # 1. Aegis & Hades
    content = content.replace('import doxoade.tools.aegis.nexus_db as sqlite3', 'from . import nexus_db as sqlite3')
    content = content.replace('from doxoade.database import', 'from .database import')
    # 2. Vulcan Core Flattening (O segredo da soberania nativa)
    content = content.replace('from doxoade.tools.vulcan.runtime import', 'from .runtime import')
    content = content.replace('from doxoade.tools.vulcan.opt_cache import', 'from .opt_cache import')
    content = content.replace('from doxoade.tools.vulcan.vulcan_safe_loader import', 'from .safe_loader import')
    content = content.replace('from doxoade.tools.vulcan import', 'from . import')
    # 3. Telemetria e Resgate
    content = content.replace('from doxoade.tools.telemetry_tools.logger import', 'from .telemetry import')
    content = content.replace('from doxoade.rescue import', 'from .rescue import')
    # 4. Ferramentas Genéricas
    content = re.sub(r'from doxoade\.tools\.(\w+)', r'from .\1', content)
    content = re.sub(r'from doxoade\.tools import (\w+)', r'from . import \1', content) # content = re.sub(r'from doxoade\.tools import', 'from . import', content)
    # 5. Fix de imports diretos (Fallback except) e Prevenção de duplicados
    content = re.sub(r'(?m)^(\s*)import (doxcolors|error_info|telemetry|rescue|database|nexus_db|runtime|meta_finder|opt_cache|safe_loader)(\b)', r'\1from . import \2\3', content)
    return content

@click.command('init')
@click.argument('project_name', required=False)
@click.option('--remote', help='URL para publicação automática no GitHub.')
@click.pass_context
def init(ctx, project_name, remote):
    """🚀 Nexus Project Genesis: Cria um Silo Soberano Chief-Gold."""
    
    if not project_name: project_name = click.prompt('Nome do novo projeto')
    if not re.match('^[a-zA-Z0-9_-]+$', project_name):
        click.secho("[ERRO] Nome inválido.", fg="red"); sys.exit(1)

    project_path = Path(os.getcwd()) / project_name
    if project_path.exists():
        click.secho(f"[ERRO] O diretório '{project_name}' já existe.", fg="red"); sys.exit(1)

    with ExecutionLogger('init', '.', ctx.params) as _:
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [NEXUS PROJECT GENESIS] ---{Style.RESET_ALL}")
        
        # 1. TOPOLOGIA INDUSTRIAL
        utils_path = project_path / 'utils'
        utils_path.mkdir(parents=True)
        (project_path / 'tests').mkdir(); (project_path / 'docs').mkdir()
        (project_path / '.doxoade' / 'vulcan' / 'bin').mkdir(parents=True)
        (project_path / '.doxoade' / 'vulcan' / 'foundry').mkdir()
        (project_path / '.doxoade' / 'vulcan' / 'opt_py').mkdir()

        # 2. INJEÇÃO DE MOTORES (SILO DNA)
        click.echo(f"[*] {Fore.YELLOW}Injetando Motores de Soberania...{Style.RESET_ALL}")
        for filename, source_path in CORE_TOOLS.items():
            dest_path = utils_path / filename
            if source_path.exists():
                raw = source_path.read_text(encoding='utf-8', errors='ignore')
                silo_code = _refactor_to_silo(raw)
                db_p = str(Path.home() / '.doxoade' / 'doxoade.db').replace('\\', '/')
                silo_code = silo_code.replace('Path.home() / ".doxoade" / "doxoade.db"', f'"{db_p}"')
                dest_path.write_text(generate_silo_header(project_name, filename) + silo_code, encoding='utf-8')
        
        (utils_path / '__init__.py').write_text("# Silo Package\n", encoding='utf-8')

        # 3. IDENTIDADE E DOCUMENTAÇÃO (VOLUME 1)
        click.echo(f"[*] {Fore.YELLOW}Gerando Delimitação de Escopo (indentity.md)...{Style.RESET_ALL}")
        (project_path / 'indentity.md').write_text(TEMPLATE_IDENTITY.format(project_name=project_name), encoding='utf-8')
        (project_path / 'README.md').write_text(TEMPLATE_README.format(project_name=project_name), encoding='utf-8')
        (project_path / 'pyproject.toml').write_text(TEMPLATE_PYPROJECT.format(project_name=project_name), encoding='utf-8')
        (project_path / '.gitignore').write_text(TEMPLATE_GITIGNORE.format(project_name=project_name), encoding='utf-8')

        # 4. CRIAÇÃO DO MAIN (TIER 1 READY)
        main_content = TEMPLATE_MAIN.format(project_name=project_name)
        (project_path / 'main.py').write_text(main_content, encoding='utf-8')

        # 5. REPOSITÓRIO E PUBLICAÇÃO
        click.echo(f"[*] {Fore.YELLOW}Inicializando Git Local...{Style.RESET_ALL}")
        os.chdir(project_path)
        subprocess.run(['git', 'init', '-b', 'main'], capture_output=True)
        
        if remote:
            click.echo(f"[*] {Fore.CYAN}Publicando em {remote}...{Style.RESET_ALL}")
            subprocess.run(['git', 'remote', 'add', 'origin', remote])
            subprocess.run(['git', 'add', '.'])
            subprocess.run(['git', 'commit', '-m', f'Genesis: {project_name} Silo initialized'])
            subprocess.run(['git', 'push', '-u', 'origin', 'main'])

    click.secho(f"\n✔ Silo '{project_name}' criado com sucesso!", fg="green", bold=True)
    click.echo(f"Dica: Execute 'python main.py' para testar a soberania Vulcan.")

# --- TEMPLATES NEXUS ---

TEMPLATE_MAIN = """# -*- coding: utf-8 -*-
from utils.nexus import monitor, ignite
from utils.runtime import install_meta_finder, activate_vulcan
import os

# Inicializa UI e Aceleração
Fore, Style = ignite()
install_meta_finder(os.getcwd())

@monitor
def main():
    # Injeta binários nativos se existirem
    activate_vulcan(globals(), __file__)
    print(f'{{Fore.GREEN}}✔ Silo {project_name} operando via Nexus Engine.{{Style.RESET_ALL}}')

if __name__ == '__main__':
    main()
"""

TEMPLATE_IDENTITY = """# 📄 Identidade e Escopo: {project_name}

## 1️⃣ Existência (POR QUÊ?)
1. Qual problema real {project_name} resolve?
2. O que acontece se {project_name} não existir?

## 2️⃣ Usuário Real (QUEM?)
3. Quem usa?
4. O que o usuário mais erra hoje?

## 🧠 Regra de Ouro
> **Projeto bom não é o que faz tudo. É o que sabe exatamente o que não faz.**
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

TEMPLATE_README = """# {project_name}

Silo Independente desenvolvido sob o padrão **Chief-Gold**.

## 🛠 Motores Embarcados (utils/)
- **Aegis Shield**: Segurança e Anti-Injeção.
- **Lazarus Protocol**: Resgate automático de crash.
- **Vulcan Runtime**: Aceleração nativa Tier 1/2.
- **Chronos Telemetry**: Log industrial de performance.
"""

TEMPLATE_GITIGNORE = """
# ====== Arquivos de Cache do Python
__pycache__/
*.py[cod]
*.pyc
*.pyo
*.pyd


# ====== Arquivos de Ambiente Virtual ======
venv/
.venv/
env/
.env


# ====== Arquivos de Build e Distribuição (para PyInstaller) ======
pytest_temp_dir/
build/
dist/
*.egg-info/
*.spec


# ====== SENSÍVEIS ======
chief_dossier.json
chief_dossier_llm.md
doxoade_report.json
graph.html
chief_dossier_llm.xml

*.db
*.log
*.txt
*.bkp
*.bak
*.dox
*.pyx
*.old_trash
*.xml


# ====== Arquivos de Configuração de IDE ======
.vscode/
.idea/


# ====== Arquivos de sistema do Windows ======
desktop.ini
Thumbs.db


# ====== BACKUPS E ARQUIVOS TEMPORÁRIOS ======
regression_tests/canon/
recovery_zone/
credentials.json
token.json
config.json

.nppBackup
nppBackup/
./nppBackup/

tmp/
Vers/

*.mak
*.log

data/
test/
tests/
teste/
testes/


# ====== Doxoade cache files ======
.doxoade_cache/
.doxoade/
.doxoade/vulcan/foundry/
.doxoade/vulcan/opt_py/
.dox_agent_workspace/
.dox_lab/


# ====== terceirizados ======
thirdparty/w64devkit/


# ====== Exceções ======
!requirements.txt
!PipelineHelp.txt

"""
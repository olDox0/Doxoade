# -*- coding: utf-8 -*-
# doxoade/commands/init.py
"""
Nexus Project Genesis v2.2 - Provisionador de Silos Soberanos.
Responsável por forjar a infraestrutura base (Hefesto) e injetar o DNA do Doxoade.
Compliance: OSL-4, PASC-6.1, PASC-8.4.
"""
import os
import sys
import re
import json
import click
import subprocess
from pathlib import Path
from datetime import datetime

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

# Caminho raiz da instalação do Doxoade (para buscar os Core Tools)
DOXOADE_ROOT = Path(__file__).resolve().parents[2]

# 🧬 DNA DOXOADE: Módulos essenciais que serão injetados no Silo (pasta utils/)
CORE_TOOLS = {
    'doxcolors.py':     DOXOADE_ROOT / 'doxoade' / 'tools' / 'doxcolors.py',
    'error_info.py':    DOXOADE_ROOT / 'doxoade' / 'tools' / 'error_info.py',
    'rescue.py':        DOXOADE_ROOT / 'rescue.py',
    'telemetry.py':     DOXOADE_ROOT / 'doxoade' / 'tools' / 'telemetry_tools' / 'logger.py',
    'db_utils.py':      DOXOADE_ROOT / 'doxoade' / 'tools' / 'db_utils.py',
    'core_database.py': DOXOADE_ROOT / 'doxoade' / 'core_database.py',
    'nexus_db.py':      DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'nexus_db.py',
    'aegis_core.py':    DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'aegis_core.py',
    'warden.py':        DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'warden.py',
    'nexus.py':         DOXOADE_ROOT / 'doxoade' / 'tools' / 'templates' / 'embedded' / 'nexus.py',
    'runtime.py':       DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'runtime.py',
    'meta_finder.py':   DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'meta_finder.py',
    'opt_cache.py':     DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'opt_cache.py',
    'lib_optimizer.py': DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'lib_optimizer.py',
    'safe_loader.py':   DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'vulcan_safe_loader.py',
}

def generate_silo_header(project_name: str) -> str:
    """Gera o cabeçalho sagrado do Silo."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return (
        f"# {'=' * 70}\n"
        f"# SILO SOBERANO: {project_name.upper()}\n"
        f"# Forjado pelo Nexus Project Genesis v2.2 em {ts}\n"
        f"# DNA Doxoade Injetado e Refatorado para Autonomia Total.\n"
        f"# {'=' * 70}\n"
    )

def _refactor_to_silo(content: str) -> str:
    """
    Ajusta imports absolutos do Doxoade para funcionarem de forma relativa 
    dentro da pasta utils/ do Silo (Garantindo Soberania).
    """
    replacements = {
        'import doxoade.tools.aegis.nexus_db as sqlite3': 'from . import nexus_db as sqlite3',
        'from doxoade.database import': 'from .database import',
        'from doxoade.tools.vulcan.runtime import': 'from .runtime import',
        'from doxoade.tools.vulcan.opt_cache import': 'from .opt_cache import',
        'from doxoade.tools.vulcan.vulcan_safe_loader import': 'from .safe_loader import',
        'from doxoade.tools.vulcan import': 'from . import',
        'from doxoade.tools.telemetry_tools.logger import': 'from .telemetry import',
        'from doxoade.rescue import': 'from .rescue import',
    }
    for old, new in replacements.items():
        content = content.replace(old, new)

    content = re.sub(r'from doxoade\.tools\.(\w+)', r'from .\1', content)
    content = re.sub(r'from doxoade\.tools import (\w+)', r'from . import \1', content)
    content = re.sub(r'(?m)^(\s*)import (doxcolors|error_info|telemetry|rescue|database|nexus_db|runtime|meta_finder|opt_cache|safe_loader)(\b)', r'\1from . import \2\3', content)
    
    return content

def _generate_pyproject_toml(project_name: str) -> str:
    """Gera o contrato base do Silo (pyproject.toml)."""
    return f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "Silo Soberano forjado pelo Doxoade."
requires-python = ">=3.10"

[tool.doxoade]
ignore = ["venv/", ".git/", "__pycache__/", ".doxoade/", "build/", "dist/"]
source_dir = "."
"""

def _generate_metalcraft_toml(project_name: str) -> str:
    """Gera o contrato da Forja C (metalcraft.toml)."""
    return f"""[project]
name = "{project_name}"
version = "1.0.0"
type = "executable"

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

def _generate_main_c(project_name: str) -> str:
    """Gera o boilerplate do main.c com a Sotéria embarcada."""
    return f"""// {'=' * 60}
// SILO NATIVE ENTRYPOINT: {project_name.upper()}
// Forjado pelo Nexus Metalcraft.
// {'=' * 60}

#include <stdio.h>
#include <stdlib.h>

// A Sotéria Scribe injetará os headers de resgate aqui durante o build.

int main(int argc, char** argv) {{
    printf("🔥 [NEXUS METALCRAFT] Silo {project_name} operacional.\\n");
    printf("🛡️  [SOTERIA] Escudo de resgate ativo.\\n");
    
    // Lógica nativa do Silo começa aqui.
    
    return 0;
}}
"""

def _generate_gitignore(project_name: str) -> str:
    """Gera o escudo de exclusão do Silo (Padrão Chief-Gold Híbrido)."""
    return f"""# ==========================================
# .gitignore - Silo Soberano: {project_name.upper()}
# Forjado pelo Nexus Project Genesis v2.2
# ==========================================

# ====== Python (Cache & Venv) ======
__pycache__/
*.py[cod]
*$py.class
*.so
*.pyd
*.egg-info/
dist/
build/
*.egg
.venv/
venv/
ENV/
env/

# ====== C/C++ (Metalcraft & Native) ======
*.o
*.obj
*.exe
*.dll
*.dylib
*.lib
*.out
*.app
bin/
obj/
*.gch
*.pch
*.nm
*.map

# ====== Doxoade Local & Cache ======
.doxoade/
.doxoade_cache/
.dox_agent_workspace/
.dox_lab/

# ====== Persistência (Hades) ======
# Ignora bancos de dados locais para evitar conflitos de caminhos absolutos
*.db
*.db-shm
*.db-wal
*.sqlite
*.sqlite3
# Exceção: Se houver um diretório de acervo compartilhado
!data/acervo/
!data/acervo/bricks/
!data/acervo/bricks/*.py

# ====== Logs e Dossiês Sensíveis ======
*.log
*.trace
*.dump
*.bak
*.bkp
*.old
*.tmp
*.temp
chief_dossier*.json
chief_dossier*.xml
doxoade_report.json
graph.html
credentials.json
token.json
config.json
.env

# ====== IDEs e Editores ======
.vscode/
.idea/
*.swp
*.swo
*~
.nppBackup/
*.sublime-project
*.sublime-workspace

# ====== Sistema Operacional ======
.DS_Store
Thumbs.db
desktop.ini
ehthumbs.db

# ====== Testes e Quarentena ======
pytest_temp_dir/
regression_tests/canon/
recovery_zone/
htmlcov/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/

# ====== Exceções (Auto-fixed pelo Doxoade) ======
!requirements.txt
!PipelineHelp.txt
!*.dox
"""

@click.command('init')
@click.argument('project_name', required=False)
@click.option('--remote', help='URL para publicação automática no GitHub.')
@click.option('--metalcraft', '-mc', is_flag=True, help='Embarca a Forja C (Metalcraft) no Silo.')
@click.option('--macrothon', '-mt', is_flag=True, help='Prepara o Silo para orquestração Macrothon (Houses).')
@click.option('--house', '-h', is_flag=True, help='Transforma o Silo em uma House Macrothon (Sincronização Automática).')
@click.option('--architecture', '-a', type=click.Path(exists=True), help='Constrói topologia baseada em arquivo blueprint.')
@click.option('--no-venv', '-nv', is_flag=True, help='Pula a criação do ambiente virtual (venv).')
@click.option('--up', is_flag=True, help='Abre os arquivos criados/modificados no Notepad++.')
@click.pass_context
def init(ctx, project_name, remote, metalcraft, macrothon, house, architecture, no_venv, up):
    """🚀 Nexus Project Genesis: Cria um Silo Soberano Chief-Gold."""
    if not project_name:
        project_name = click.prompt('Nome do novo projeto')
        
    if not re.match(r'^[a-zA-Z0-9_-]+$', project_name):
        click.secho("[ERRO] Nome inválido. Use apenas letras, números, '_' e '-'.", fg="red")
        sys.exit(1)

    project_path = Path(os.getcwd()) / project_name
    if project_path.exists():
        click.secho(f"[ERRO] O diretório '{project_name}' já existe.", fg="red")
        sys.exit(1)

    # 🛡️ GÊNESE DA RAIZ: Cria o diretório do projeto ANTES de qualquer fase (Fix do Crash)
    project_path.mkdir(parents=True, exist_ok=True)

    # Lista para rastrear arquivos para a flag --up
    affected_files = []

    with ExecutionLogger('init', '.', ctx.params) as _:
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [NEXUS PROJECT GENESIS v2.2] ---{Style.RESET_ALL}")
        click.echo(f"[*] Forjando Silo Soberano: {Fore.YELLOW}{project_name}{Style.RESET_ALL}")

        # 1. FUNDAÇÃO (Diretórios Base)
        click.echo(f"[*] {Fore.YELLOW}Forjando a Fundação do Silo...{Style.RESET_ALL}")
        dirs_to_create = [
            project_path / 'utils',
            project_path / 'src',
            project_path / 'docs',
            project_path / 'data',
            project_path / 'tests',
            project_path / '.doxoade' / 'vulcan' / 'bin',
            project_path / '.doxoade' / 'vulcan' / 'foundry',
            project_path / '.doxoade' / 'vulcan' / 'opt_py',
        ]
        if metalcraft:
            dirs_to_create.append(project_path / 'src' / 'native' / 'include')
            dirs_to_create.append(project_path / 'bin')
        if macrothon or house:
            dirs_to_create.append(project_path / 'src' / 'houses')
            
        for d in dirs_to_create:
            d.mkdir(parents=True, exist_ok=True)
        click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Estrutura de diretórios criada.")

        # 2. CONTRATOS (TOMLs e Git)
        pyproject_path = project_path / 'pyproject.toml'
        pyproject_path.write_text(_generate_pyproject_toml(project_name), encoding='utf-8')
        affected_files.append(str(pyproject_path))

        gitignore_path = project_path / '.gitignore'
        # 🛡️ USANDO O NOVO GERADOR SOBERANO
        gitignore_path.write_text(_generate_gitignore(project_name), encoding='utf-8')
        affected_files.append(str(gitignore_path))
        click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Contratos (pyproject.toml, .gitignore) selados.")

        # 3. INJEÇÃO DE DNA (Core Tools)
        click.echo(f"[*] {Fore.YELLOW}Injetando Motores Doxoade (DNA)...{Style.RESET_ALL}")
        utils_path = project_path / 'utils'
        injected_count = 0
        for target_name, source_path in CORE_TOOLS.items():
            if source_path.exists():
                content = source_path.read_text(encoding='utf-8', errors='ignore')
                refactored = _refactor_to_silo(content)
                dest = utils_path / target_name
                dest.write_text(refactored, encoding='utf-8')
                affected_files.append(str(dest))
                injected_count += 1
            else:
                click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} Origem ausente: {source_path.name}")
                
        init_py = utils_path / '__init__.py'
        init_py.write_text(generate_silo_header(project_name), encoding='utf-8')
        affected_files.append(str(init_py))
        click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} {injected_count} motores injetados e refatorados.")

        # 4. O AMBIENTE VIRTUAL (Venv Soberano)
        if not no_venv:
            click.echo(f"[*] {Fore.YELLOW}Forjando Ambiente Virtual (Venv)...{Style.RESET_ALL}")
            venv_path = project_path / 'venv'
            try:
                subprocess.run(
                    [sys.executable, '-m', 'venv', str(venv_path)], 
                    check=True, capture_output=True, text=True
                )
                click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Venv isolado criado em: {Fore.CYAN}venv/{Style.RESET_ALL}")
            except subprocess.CalledProcessError as e:
                click.echo(f"   {Fore.RED}✘ Falha ao criar venv: {e.stderr.strip()}{Style.RESET_ALL}")
            except Exception as e:
                click.echo(f"   {Fore.RED}✘ Erro inesperado ao criar venv: {e}{Style.RESET_ALL}")
        else:
            click.echo(f"[*] {Fore.DIM}Venv pulado (modo --no-venv).{Style.RESET_ALL}")

        # 5. O DNA DA HOUSE (Condicional: --house ou -mt)
        if house or macrothon:
            click.echo(f"[*] {Fore.MAGENTA}Injetando DNA Macrothon (Uroboros)...{Style.RESET_ALL}")
            
            # Atualiza o pyproject.toml com o Contrato da House
            toml_content = pyproject_path.read_text(encoding='utf-8')
            if '[tool.doxoade.macrothon]' not in toml_content:
                house_contract = f"""
[tool.doxoade.macrothon]
is_house = true
house_name = "{project_name}"
auto_sync = true
requires = [] 
"""
                pyproject_path.write_text(toml_content + house_contract, encoding='utf-8')
            
            # Cria o Manifesto da House (O RG do Sistema)
            doxoade_dir = project_path / '.doxoade'
            doxoade_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "house_name": project_name,
                "last_sync": None,
                "synced_systems": {}
            }
            manifest_path = doxoade_dir / 'house_manifest.json'
            manifest_path.write_text(json.dumps(manifest, indent=4), encoding='utf-8')
            affected_files.append(str(manifest_path))
            
            click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} DNA Macrothon injetado. Uroboros ativado (Sem pasta bricks).")

        # 6. A FORJA (Condicional: --metalcraft)
        if metalcraft:
            click.echo(f"[*] {Fore.MAGENTA}Configurando Forja C (Metalcraft)...{Style.RESET_ALL}")
            toml_path = project_path / 'metalcraft.toml'
            toml_path.write_text(_generate_metalcraft_toml(project_name), encoding='utf-8')
            affected_files.append(str(toml_path))

            main_c_path = project_path / 'src' / 'native' / 'main.c'
            main_c_path.write_text(_generate_main_c(project_name), encoding='utf-8')
            affected_files.append(str(main_c_path))
            click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} metalcraft.toml e main.c forjados.")

        # 7. A TOPOLOGIA (Condicional: -a blueprint.txt)
        if architecture:
            click.echo(f"[*] {Fore.BLUE}Construindo Topologia via MkEngine...{Style.RESET_ALL}")
            from doxoade.commands.mk_systems.mk_engine import MkEngine
            engine = MkEngine(base_path=str(project_path))
            for path, kind in engine.parse_architecture_file(architecture):
                color = Fore.YELLOW if kind == 'Movido' else (Fore.BLUE if kind == 'Mantido' else Fore.GREEN)
                click.echo(f"   {color}[{kind.upper():<10}]{Style.RESET_ALL}: {path}")
            
            affected_files.extend(engine.affected_files)
            click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Topologia '{Path(architecture).name}' erguida.")

        # 8. CONSAGRAÇÃO (Git Init)
        try:
            subprocess.run(['git', 'init'], cwd=project_path, capture_output=True, check=True)
            click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Repositório Git inicializado.")
        except Exception:
            click.echo(f"   {Fore.YELLOW}⚠{Style.RESET_ALL} Git não encontrado ou falha ao inicializar.")

        # 9. O DESPERTAR (Condicional: --up)
        if up:
            from doxoade.commands.mk_systems.mk_utils import open_in_notepadpp
            files_to_open = [f for f in affected_files if os.path.isfile(f)]
            if files_to_open:
                click.echo(f"\n{Fore.MAGENTA}--- [UP] Abrindo {len(files_to_open)} arquivo(s) no Notepad++ ---{Style.RESET_ALL}")
                open_in_notepadpp(files_to_open)

        click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✅ Silo '{project_name}' forjado com sucesso!{Style.RESET_ALL}")
        click.echo(f"   🚀 Entre no Silo: {Fore.YELLOW}cd {project_name}{Style.RESET_ALL}")

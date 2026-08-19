# -*- coding: utf-8 -*-
# doxoade/commands/init_system/init_setup.py
"""
Nexus Setup Genesis Engine - v2.0
================================================================================
Responsável por forjar e implantar o instalador soberano autônomo (`install_setup.py`)
e contratos do LAN Git em Silos novos ou existentes (ex: SysUtils).
Compliance: MPoT-7, PASC-6.3, Aegis-Protocol.
================================================================================
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional
import click
from doxoade.tools.doxcolors import Fore, Style


def extract_existing_requirements(root: Path) -> List[str]:
    """Extrai dependências de um requirements.txt existente ou pyproject.toml."""
    req_file = root / "requirements.txt"
    if req_file.exists():
        lines = []
        for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        if lines:
            return lines

    # Fallback padrão para novos projetos
    return [
        "click>=8.1.0",
        "colorama>=0.4.6",
        "psutil>=5.9.5",
    ]


def detect_cli_name(root: Path, project_name: str) -> str:
    """Tenta descobrir o nome do comando CLI pelo setup.py ou nome da pasta."""
    setup_file = root / "setup.py"
    if setup_file.exists():
        content = setup_file.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r'["\']([a-zA-Z0-9_-]+)\s*=\s*[a-zA-Z0-9_.]+', content)
        if match:
            return match.group(1)
    return project_name.lower().replace(" ", "_").replace("-", "_")


def generate_setup_install_code(
    project_name: str,
    cli_command_name: str,
    runtime_packages: Optional[List[str]] = None,
) -> str:
    """Gera o código-fonte Python puro para o instalador `install_setup.py` V4 Soberano."""
    pkgs = runtime_packages or [
        "click>=8.1.0",
        "colorama>=0.4.6",
        "psutil>=5.9.5",
    ]
    formatted_pkgs = ",\n    ".join([f'"{p}"' for p in pkgs])
    proj_title = project_name.upper()

    return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
⚡ NEXUS SOVEREIGN SETUP & INSTALLER V4.0 (VULCAN CORE)
Projeto: {project_name} (CLI: {cli_command_name})
================================================================================
Instalador autônomo e resiliente para Windows, Linux e Termux.
Cria o ambiente virtual, atualiza ferramentas de build e instala o sistema.
================================================================================
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Força UTF-8 no ambiente Python para subprocessos
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

if os.name == 'nt':
    os.system('')  # Ativa suporte a ANSI no Windows CMD/PowerShell

class UI:
    CYAN    = '\\033[1;36m'
    GREEN   = '\\033[1;32m'
    YELLOW  = '\\033[1;33m'
    RED     = '\\033[1;31m'
    MAGENTA = '\\033[1;35m'
    BOLD    = '\\033[1m'
    DIM     = '\\033[2m'
    RESET   = '\\033[0m'

def log_header(title: str):
    print(f"\\n{{UI.CYAN}}{{UI.BOLD}}{{'='*68}}")
    print(f" 🚀 {{title}}")
    print(f"{{'='*68}}{{UI.RESET}}")

def log_step(step: str, desc: str):
    print(f"\\n{{UI.MAGENTA}}[FASE {{step}}]{{UI.RESET}} {{UI.BOLD}}{{desc}}{{UI.RESET}}")

def log_ok(msg: str):
    print(f"  {{UI.GREEN}}✔{{UI.RESET}} {{msg}}")

def log_warn(msg: str):
    print(f"  {{UI.YELLOW}}⚠{{UI.RESET}} {{msg}}")

def log_err(msg: str):
    print(f"  {{UI.RED}}✘{{UI.RESET}} {{msg}}")

def get_venv_paths(root: Path):
    venv_dir = root / "venv"
    if os.name == "nt":
        scripts_dir = venv_dir / "Scripts"
        python_exe = scripts_dir / "python.exe"
        pip_exe = scripts_dir / "pip.exe"
        activate_cmd = f"call {{scripts_dir / 'activate.bat'}}"
    else:
        scripts_dir = venv_dir / "bin"
        python_exe = scripts_dir / "python"
        pip_exe = scripts_dir / "pip"
        activate_cmd = f"source {{scripts_dir / 'activate'}}"

    return {{
        "venv_dir": venv_dir,
        "scripts_dir": scripts_dir,
        "python": python_exe,
        "pip": pip_exe,
        "activate": activate_cmd
    }}

def safe_run(cmd, cwd=None, check=True) -> subprocess.CompletedProcess:
    """Executor blindado contra UnicodeDecodeError no Windows."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env
    )

def main():
    log_header("{proj_title}: INSTALADOR SOBERANO V4.0")
    paths = get_venv_paths(ROOT)

    # FASE 1: Verificação
    log_step("1/5", "Auditoria do Interpretador Base...")
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        log_err(f"Python 3.10+ é obrigatório. Versão atual: {{v.major}}.{{v.minor}}.{{v.micro}}")
        sys.exit(1)
    log_ok(f"Python Base compatível: {{v.major}}.{{v.minor}}.{{v.micro}}")

    # FASE 2: Venv
    log_step("2/5", "Isolamento de Ambiente Virtual (venv)...")
    if not paths["venv_dir"].exists():
        safe_run([sys.executable, "-m", "venv", str(paths["venv_dir"])])
        log_ok("Ambiente virtual forjado com sucesso.")
    else:
        log_ok("Ambiente virtual existente detectado.")

    # FASE 3: Build Tools
    log_step("3/5", "Bootstrapping de Ferramentas de Build...")
    safe_run([
        str(paths["python"]), "-m", "pip", "install", "--upgrade",
        "pip", "setuptools>=68.0.0", "wheel>=0.41.0"
    ])
    log_ok("Ferramentas de build atualizadas.")

    # FASE 4: Instalação
    log_step("4/5", "Instalação do Pacote em Modo Editável...")
    safe_run([str(paths["python"]), "-m", "pip", "install", "-e", str(ROOT)])
    log_ok("Projeto registrado no ambiente virtual.")

    # FASE 5: Diretórios
    log_step("5/5", "Diretórios de Dados e Persistência...")
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    log_ok("Diretórios essenciais verificados.")

    log_header("INSTALAÇÃO CONCLUÍDA!")
    print(f"{{UI.GREEN}}{{UI.BOLD}}Para ativar o ambiente neste terminal:{{UI.RESET}}\\n")
    print(f"  {{UI.CYAN}}{{UI.BOLD}}{{paths['activate']}}{{UI.RESET}}\\n")

if __name__ == '__main__':
    main()
'''


def inject_setup_existing(root: Path, apply_changes: bool = True) -> None:
    """Injeta ou atualiza o `install_setup.py` em um projeto existente (Retrocompatível)."""
    root = Path(root).resolve()
    project_name = root.name
    cli_name = detect_cli_name(root, project_name)
    requirements = extract_existing_requirements(root)

    click.echo()
    click.secho(f"⚡ [NEXUS:SETUP] Implantando Instalador Soberano em '{project_name}'...", fg="cyan", bold=True)
    click.echo(f"   CLI Detectado : {Fore.YELLOW}{cli_name}{Style.RESET_ALL}")
    click.echo(f"   Dependências  : {Fore.GREEN}{len(requirements)} pacote(s){Style.RESET_ALL}")

    target_file = root / "install_setup.py"
    code = generate_setup_install_code(
        project_name=project_name,
        cli_command_name=cli_name,
        runtime_packages=requirements,
    )

    if apply_changes:
        target_file.write_text(code, encoding="utf-8")
        click.secho(f"   [OK] install_setup.py gerado com sucesso em: {target_file}", fg="green")
        click.secho("   Dica: Execute 'python install_setup.py' para testar a instalação.", fg="yellow")
    else:
        click.secho("   [DRY-RUN] Nenhuma alteração gravada.", fg="yellow")


# Alias de compatibilidade
forge_setup_installer = inject_setup_existing


def inject_lan_git_silo(root: Path, apply_changes: bool = False) -> None:
    """
    Injeta o DNA do LAN Git, o marcador de exportação e o install_setup.py V4 no Silo (ex: SysUtils).
    """
    root = Path(root).resolve()
    project_name = root.name
    cli_name = detect_cli_name(root, project_name)
    requirements = extract_existing_requirements(root)

    click.echo()
    click.secho("[HEFESTO] Injeção de DNA LAN Git & Sovereign Installer", fg="cyan", bold=True)
    click.echo(f"Silo Alvo : {root}")
    click.echo(f"Projeto   : {project_name} (CLI: {cli_name})")
    click.echo("=" * 75)

    if not apply_changes:
        click.secho("[MA'AT] Modo DRY-RUN ativo. Nenhuma alteração gravada. Use --apply para confirmar.", fg="yellow", bold=True)

    # 1. Arquivo install_setup.py
    installer_path = root / "install_setup.py"
    installer_content = generate_setup_install_code(project_name, cli_name, requirements)

    # 2. Marcador de exportação git daemon
    git_dir = root / ".git"
    marker_path = git_dir / "git-daemon-export-ok"

    # 3. Seção no pyproject.toml
    pyproject_path = root / "pyproject.toml"
    toml_snippet = f"""\n[tool.doxoade.lan_git]
enabled = true
silo_name = "{project_name}"
default_port = 9418
smart_http_port = 8080
"""

    actions = [
        (installer_path, installer_content, "install_setup.py V4 Soberano"),
    ]

    for path, content, desc in actions:
        if path.exists():
            click.secho(f"  [ATUALIZAR] {desc}: {path.name}", fg="cyan")
        else:
            click.secho(f"  [CRIAR]     {desc}: {path.name}", fg="green")

        if apply_changes:
            path.write_text(content, encoding="utf-8")

    # Aplica o marcador .git/git-daemon-export-ok
    if git_dir.exists() and git_dir.is_dir():
        if marker_path.exists():
            click.secho("  [MANTIDO]   Marcador .git/git-daemon-export-ok", fg="blue")
        else:
            click.secho("  [CRIAR]     Marcador .git/git-daemon-export-ok", fg="green")
            if apply_changes:
                open(marker_path, "a").close()

    # Aplica o contrato no pyproject.toml
    if pyproject_path.exists():
        current_toml = pyproject_path.read_text(encoding="utf-8", errors="ignore")
        if "[tool.doxoade.lan_git]" not in current_toml:
            click.secho("  [CONTRATO]  Injetando [tool.doxoade.lan_git] em pyproject.toml", fg="green")
            if apply_changes:
                with open(pyproject_path, "a", encoding="utf-8") as f:
                    f.write(toml_snippet)
        else:
            click.secho("  [MANTIDO]   Contrato [tool.doxoade.lan_git] já existente.", fg="blue")

    click.echo("=" * 75)
    if apply_changes:
        click.secho(f"✔ DNA LAN Git implantado com sucesso no silo '{project_name}'!", fg="green", bold=True)
    else:
        click.secho("Simulação concluída. Rode com --apply para escrever.", fg="yellow", bold=True)
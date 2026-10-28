# doxoade/doxoade/commands/init_systems/init_setup.py
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
    pkgs = runtime_packages or [
        "click>=8.1.0",
        "colorama>=0.4.6",
        "psutil>=5.9.5",
    ]
    formatted_pkgs = ",\n    ".join([f'"{p}"' for p in pkgs])
    proj_title = project_name.upper()
    return f'''
import os, sys, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
if os.name == 'nt': os.system('')
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
def log_step(step: str, desc: str): print(f"\\n{{UI.MAGENTA}}[FASE {{step}}]{{UI.RESET}} {{UI.BOLD}}{{desc}}{{UI.RESET}}")
def log_ok(msg: str):   print(f"  {{UI.GREEN}}✔{{UI.RESET}} {{msg}}")
def log_warn(msg: str): print(f"  {{UI.YELLOW}}⚠{{UI.RESET}} {{msg}}")
def log_err(msg: str):  print(f"  {{UI.RED}}✘{{UI.RESET}} {{msg}}")

def get_venv_paths(root: Path):
    venv_dir = root / "venv"
    if os.name == "nt":
        scripts_dir = venv_dir / "Scripts"
        python_exe  = scripts_dir / "python.exe"
        pip_exe     = scripts_dir / "pip.exe"
        activate_cmd = f"call {{scripts_dir / 'activate.bat'}}"
    else:
        scripts_dir = venv_dir / "bin"
        python_exe  = scripts_dir / "python"
        pip_exe     = scripts_dir / "pip"
        activate_cmd = f"source {{scripts_dir / 'activate'}}"
    return {{
        "venv_dir": venv_dir,
        "scripts_dir": scripts_dir,
        "python": python_exe,
        "pip": pip_exe,
        "activate": activate_cmd,
    }}

def safe_run(cmd, cwd=None, check=True) -> subprocess.CompletedProcess:
    """Executa subprocesso re-emitindo stdout/stderr em caso de falha (DT-02)."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        cmd, cwd=cwd, check=False,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    if check and result.returncode != 0:
        sys.stderr.write(
            f"\\n[SAFE_RUN] Comando falhou (exit {{result.returncode}}):\\n"
            f"  CMD: {{' '.join(str(c) for c in cmd)}}\\n"
            f"  --- STDOUT ---\\n{{result.stdout or '(vazio)'}}\\n"
            f"  --- STDERR ---\\n{{result.stderr or '(vazio)'}}\\n"
        )
        sys.stderr.flush()
        err = subprocess.CalledProcessError(result.returncode, cmd)
        err.stdout = result.stdout
        err.stderr = result.stderr
        raise err
    return result

def generate_enter_venv_files(root: Path, paths: dict):
    """Gera enter_venv.cmd (Windows) e enter_venv.sh (Unix) na raiz do silo."""
    if os.name == "nt":
        cmd_path = root / "enter_venv.cmd"
        cmd_path.write_text(
            "@echo off\\r\\n"
            f'call "%~dp0venv\\\\Scripts\\\\activate.bat"\\r\\n'
            "echo.\\r\\n"
            "echo ✔ Venv ativado. Python: %VIRTUAL_ENV%\\\\Scripts\\\\python.exe\\r\\n"
            "echo    Para sair: deactivate\\r\\n",
            encoding="utf-8",
        )
    sh_path = root / "enter_venv.sh"
    sh_path.write_text(
        "#!/usr/bin/env bash\\n"
        '# Entra no venv do silo\\n'
        'source "$(dirname "$0")/venv/bin/activate"\\n'
        'echo "✔ Venv ativado."\\n'
        'echo "   Para sair: deactivate"\\n',
        encoding="utf-8",
    )
    try:
        sh_path.chmod(0o755)
    except Exception:
        pass

def main():
    log_header("{proj_title}: INSTALADOR SOBERANO V4.1")
    paths = get_venv_paths(ROOT)

    # ── FASE 1/6 ──
    log_step("1/6", "Auditoria do Interpretador Base...")
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        log_err(f"Python 3.10+ é obrigatório. Versão atual: {{v.major}}.{{v.minor}}.{{v.micro}}")
        sys.exit(1)
    log_ok(f"Python Base compatível: {{v.major}}.{{v.minor}}.{{v.micro}}")

    # ── FASE 2/6 ──
    log_step("2/6", "Isolamento de Ambiente Virtual (venv)...")
    if not paths["venv_dir"].exists():
        safe_run([sys.executable, "-m", "venv", str(paths["venv_dir"])])
        log_ok("Ambiente virtual forjado com sucesso.")
    else:
        log_ok("Ambiente virtual existente detectado.")

    # ── FASE 3/6 ──
    log_step("3/6", "Bootstrapping de Ferramentas de Build...")
    safe_run([
        str(paths["python"]), "-m", "pip", "install", "--upgrade",
        "pip", "setuptools>=68.0.0", "wheel>=0.41.0"
    ])
    log_ok("Ferramentas de build atualizadas.")

    # ── FASE 4/6 — PRÉ-CONDIÇÃO (DT-03) ──
    log_step("4/6", "Validando Contrato de Projeto (pyproject.toml / setup.py)...")
    has_pyproject = (ROOT / "pyproject.toml").exists()
    has_setup_py  = (ROOT / "setup.py").exists()
    if not has_pyproject and not has_setup_py:
        log_err("Pré-condição NÃO atendida: pyproject.toml / setup.py ausentes.")
        log_err(f"  Diretório: {{ROOT}}")
        try:
            contents = sorted(p.name for p in ROOT.iterdir() if p.name not in ("venv", "__pycache__"))
            log_err(f"  Conteúdo atual ({{len(contents)}} itens): {{contents[:10]}}")
        except Exception:
            pass
        log_err("")
        log_err("  ── COMO CORRIGIR ──")
        log_err(f"    Rode de fora do diretório:")
        log_err(f"      doxoade init {{ROOT.name}} --lua --no-venv --no-git")
        log_err(f"    Depois re-execute este instalador.")
        sys.exit(1)
    log_ok(f"Contrato encontrado: {{'pyproject.toml' if has_pyproject else 'setup.py'}}")

    # ── FASE 6/6 — DIRETÓRIOS E HOOKS ──
    log_step("6/6", "Pós-instalação e Diretórios Essenciais...")
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    log_ok("Diretórios essenciais verificados.")

    post_install = ROOT / "post_install.py"
    if post_install.exists():
        log_ok(f"Executando {{post_install.name}} dentro do venv...")
        try:
            safe_run([str(paths["python"]), str(post_install)], cwd=str(ROOT))
            log_ok("Pós-instalação concluída.")
        except subprocess.CalledProcessError:
            log_warn("post_install.py falhou — instalação base OK, mas hook não concluiu.")
    else:
        log_ok("Sem post_install.py — pulando.")

    generate_enter_venv_files(ROOT, paths)
    log_ok("Helpers enter_venv.{{cmd,sh}} gerados na raiz.")

    log_header("INSTALAÇÃO CONCLUÍDA!")
    print(f"Próximos passos:\n")
    print(f"  1. Entrar no venv (recomendado):")
    print(f"     enter_venv.cmd     (Windows)")
    print(f"     source enter_venv.sh (Unix)\n")
    print(f"  2. Ou ativar manualmente")
    print(f"  3. Rodar o CLI do silo:")
    print(f"     mechatools --help\n")
    print(f"  4. Rodar scripts Lua:")
    print(f"     python lua_sys\\runner.py main.lua\n")

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

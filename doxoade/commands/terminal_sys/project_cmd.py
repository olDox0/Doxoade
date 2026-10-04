# -*- coding: utf-8 -*-
# doxoade/commands/terminal_sys/project_cmd.py
"""
Gerenciador de Atalhos de Projetos (PASC-8.4 / Janus-Shell).
Permite abrir instantaneamente Explorer + Shell Admin com venv ativado.
"""
import os
import sys
import json
import ctypes
import subprocess
from pathlib import Path
import click

PROJECTS_FILE = Path.home() / ".doxoade" / "projects.json"


def _load_projects() -> dict:
    if not PROJECTS_FILE.exists():
        return {}
    try:
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_projects(data: dict):
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _locate_activate_bat(project_dir: Path) -> Path:
    """Busca activate.bat em estruturas comuns (venv ou .venv)."""
    candidates = [
        project_dir / "venv" / "Scripts" / "activate.bat",
        project_dir / ".venv" / "Scripts" / "activate.bat",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _launch_project_environment(name: str, target_path_str: str):
    target_path = Path(target_path_str).resolve()
    if not target_path.exists():
        click.secho(f"[!] Diretório não encontrado: {target_path}", fg="red")
        return

    click.secho(f"🚀 [DOXOADE] Abrindo projeto '{name}'...", fg="cyan", bold=True)

    # 1. Abre o Windows Explorer em background
    if os.name == "nt":
        subprocess.Popen(f'explorer "{target_path}"', shell=True)

    # 2. Localiza o script de ativação do venv
    activate_bat = _locate_activate_bat(target_path)

    window_title = f"DOXOADE_VENV_{name.upper()}"
    
    if os.name == "nt":
        if activate_bat:
            cmd_chain = f'cd /d "{target_path}" && title {window_title} && "{activate_bat}"'
        else:
            click.secho(" [!] Venv não localizado na raiz. Abrindo shell padrão.", fg="yellow")
            cmd_chain = f'cd /d "{target_path}" && title {window_title}'

        cmd_args = f'/k "{cmd_chain}"'

        # Elevação de privilégios como Administrador
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            "cmd.exe",
            cmd_args,
            str(target_path),
            1  # SW_SHOWNORMAL
        )
    else:
        click.secho("Abertura automática com elevação configurada para Windows (NT).", fg="yellow")


class ProjectQuickGroup(click.Group):
    """
    Permite invocar `doxoade project <nome>` diretamente,
    sem quebrar subcomandos como `add`, `list`, `remove`.
    """
    def parse_args(self, ctx, args):
        if args and not args[0].startswith("-"):
            cmd_name = args[0]
            if cmd_name not in self.commands:
                # Se não for 'add', 'list', etc., redireciona para 'open <nome>'
                args = ["open"] + args
        return super().parse_args(ctx, args)


@click.group(cls=ProjectQuickGroup)
def project_group():
    """Gerenciamento rápido de atalhos de projetos e ambientes de desenvolvimento."""
    pass


@project_group.command(name="add")
@click.argument("name")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
def add_project(name, path):
    """Cadastra um projeto no índice rápido."""
    projects = _load_projects()
    abs_path = str(Path(path).resolve())
    projects[name.lower()] = abs_path
    _save_projects(projects)
    click.secho(f"✅ Projeto '{name}' registrado -> {abs_path}", fg="green")


@project_group.command(name="open")
@click.argument("name")
def open_project(name):
    """Abre Explorer e CMD Admin com venv ativado."""
    projects = _load_projects()
    key = name.lower()
    if key not in projects:
        click.secho(f"[!] Projeto '{name}' não está cadastrado.", fg="red")
        click.echo("Cadastre com: doxoade project add <nome> <caminho>")
        return
    _launch_project_environment(name, projects[key])


@project_group.command(name="list")
def list_projects():
    """Lista todos os projetos cadastrados."""
    projects = _load_projects()
    if not projects:
        click.echo("Nenhum projeto registrado.")
        return
    click.secho("\nProjetos cadastrados:", fg="cyan", bold=True)
    for name, p in projects.items():
        click.echo(f"  • {name.ljust(15)} -> {p}")
    click.echo()


@project_group.command(name="remove")
@click.argument("name")
def remove_project(name):
    """Remove um projeto do índice."""
    projects = _load_projects()
    key = name.lower()
    if key in projects:
        del projects[key]
        _save_projects(projects)
        click.secho(f"🗑️ Projeto '{name}' removido.", fg="yellow")
    else:
        click.secho(f"[!] Projeto '{name}' não encontrado.", fg="red")

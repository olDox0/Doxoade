# -*- coding: utf-8 -*-
# doxoade/commands/terminal_sys/venv_cmd.py
"""
Ativa o VENV do projeto em um novo terminal.

Orquestra abertura de shell Windows/POSIX com venv ativado,
preservando cwd e respeitando escolha de admin (default: não-admin).

Delegações (ProDeNov §3.1.1):
  - doxoade.tools.filesystem._get_venv_python_executable  → detecção de venv
  - ctypes.windll.shell32.ShellExecuteW                    → elevação (--admin)
  - subprocess.Popen                                       → shell não-elevado
  - os.system('start ...')                                 → fallback Windows

Compliance: ProDeNov 1.2.1 | PASC-8.4 | OSL-1
"""
from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import click

from doxoade.tools.filesystem import _get_venv_python_executable


# ───────────────────────────────────────────────────────────────────────────
# Helpers de descoberta de venv
# ───────────────────────────────────────────────────────────────────────────

def _find_activate_script(venv_python: Path) -> Optional[Path]:
    """Localiza o script de ativação ao lado do python do venv.

    Windows: activate.bat (ou activate.ps1 se só ele existir)
    POSIX  : activate
    """
    scripts_dir = venv_python.parent
    candidates = [
        scripts_dir / "activate.bat",
        scripts_dir / "activate",
        scripts_dir / "Activate.ps1",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _quote_if_needed(path: str) -> str:
    """Aspas seguras para paths com espaços (Windows cmd)."""
    if not path:
        return path
    if " " in path or "&" in path or "(" in path:
        # Remove aspas existentes e re-adiciona uma única camada
        inner = path.strip('"')
        return f'"{inner}"'
    return path


# ───────────────────────────────────────────────────────────────────────────
# Detecção do venv (com fallback para cwd sem venv)
# ───────────────────────────────────────────────────────────────────────────

def _resolve_venv_context() -> dict:
    """Resolve o contexto de venv para o cwd.

    Retorna dict com:
      ok          : bool — se há venv detectado
      python      : Path | None — caminho do python do venv
      activate    : Path | None — caminho do activate.{bat,ps1,sh}
      cwd         : str — diretório do projeto (raiz do venv)
      reason      : str | None — motivo de falha, se ok=False
    """
    venv_python_str = _get_venv_python_executable()
    if not venv_python_str:
        return {
            "ok": False,
            "python": None,
            "activate": None,
            "cwd": os.path.normpath(os.getcwd()),
            "reason": "venv não localizado a partir do cwd",
        }

    venv_python = Path(venv_python_str).resolve()
    if not venv_python.exists():
        return {
            "ok": False,
            "python": venv_python,
            "activate": None,
            "cwd": os.path.normpath(os.getcwd()),
            "reason": f"python do venv declarado mas ausente: {venv_python}",
        }

    activate = _find_activate_script(venv_python)
    # cwd do projeto = pai de venv/Scripts (venv_python.parent = venv/Scripts)
    project_cwd = str(venv_python.parent.parent.parent.resolve())

    return {
        "ok": True,
        "python": venv_python,
        "activate": activate,
        "cwd": os.path.normpath(project_cwd),
        "reason": None,
    }


# ───────────────────────────────────────────────────────────────────────────
# Abertura de shell — Windows
# ───────────────────────────────────────────────────────────────────────────

def _open_windows_shell(
    cwd: str,
    activate: Optional[Path],
    title: str,
    admin: bool,
) -> None:
    """Abre um novo cmd.exe com venv (ou shell puro) no cwd."""
    # Monta a cadeia de comandos (cd + title + activate)
    parts = [f'cd /d "{cwd}"', f'title {title}']
    if activate is not None:
        parts.append(f'"{activate}"')
    cmd_chain = " && ".join(parts)
    cmd_args = f'/k "{cmd_chain}"'

    if admin:
        # Elevação UAC
        import ctypes
        # ShellExecuteW(HWND, lpVerb, lpFile, lpParameters, lpDirectory, nShowCmd)
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "cmd.exe", cmd_args, cwd, 1
        )
        # ShellExecuteW retorna >32 em sucesso
        if result <= 32:
            raise RuntimeError(
                f"ShellExecuteW runas falhou (código {result}). "
                "Verifique se você confirmou o UAC."
            )
        return

    # Não-admin: usar Popen com CREATE_NEW_CONSOLE (mais confiável que os.system)
    CREATE_NEW_CONSOLE = 0x00000010
    try:
        subprocess.Popen(
            ["cmd.exe", "/k", cmd_chain],
            cwd=cwd,
            creationflags=CREATE_NEW_CONSOLE,
            close_fds=True,
        )
    except FileNotFoundError:
        # Fallback raro: cmd.exe não no PATH? improvável, mas seguro
        os.system(f'start "" cmd.exe {cmd_args}')


# ───────────────────────────────────────────────────────────────────────────
# Abertura de shell — POSIX (Linux/macOS)
# ───────────────────────────────────────────────────────────────────────────

def _open_posix_shell(
    cwd: str,
    activate: Optional[Path],
    title: str,
) -> None:
    """Abre shell POSIX (bash/zsh) com venv ativado.

    Tenta, em ordem:
      1. Terminal gráfico detectado (gnome-terminal / konsole / xterm / Terminal.app)
      2. Fallback: imprime instrução para o usuário (sem GUI)
    """
    shell = os.environ.get("SHELL", "/bin/bash")
    if activate:
        inner = f'cd "{cwd}" && source "{activate}" && exec {shell}'
    else:
        inner = f'cd "{cwd}" && exec {shell}'

    # Detecta terminal gráfico
    candidates = [
        ("gnome-terminal", ["gnome-terminal", f"--title={title}", "--", "bash", "-c", inner]),
        ("konsole",        ["konsole", "-p", f"tabtitle={title}", "-e", "bash", "-c", inner]),
        ("xterm",          ["xterm", "-T", title, "-e", "bash", "-c", inner]),
        ("open -a Terminal", ["open", "-a", "Terminal", cwd]),  # macOS
    ]
    for name, cmd in candidates:
        exe = name.split()[0]
        if shutil.which(exe):
            try:
                subprocess.Popen(cmd)
                return
            except Exception:
                continue

    # Fallback sem GUI: instrução clara
    print(f"\n[!] Nenhum terminal gráfico detectado.")
    print(f"    Execute manualmente:")
    if activate:
        print(f"      cd \"{cwd}\" && source \"{activate}\"")
    else:
        print(f"      cd \"{cwd}\"")


# ───────────────────────────────────────────────────────────────────────────
# API pública compartilhada (outros comandos podem importar)
# ───────────────────────────────────────────────────────────────────────────

def open_venv_shell(
    admin: bool = False,
    title: Optional[str] = None,
    project_name: Optional[str] = None,
    cwd: Optional[str] = None,
) -> int:
    """Abre um novo shell com o venv do projeto ativado.

    Args:
        admin: se True, eleva via UAC (Windows).
        title: título customizado da janela. Default: DOXOADE_VENV_<projeto>.
        project_name: nome usado no título quando title=None.
        cwd: diretório do projeto. Default: cwd atual.

    Returns:
        0 em sucesso, 1 em falha (não levanta exceção).
    """
    work_cwd = os.path.normpath(cwd or os.getcwd())
    ctx = _resolve_venv_context()

    if not ctx["ok"] and cwd is None:
        # Só falha se o usuário não passou cwd explícito (senão respeita)
        click.secho(f" [!] {ctx['reason']}", fg="red")
        click.echo("     Verifique se há venv/ ou .venv/ no projeto.")
        return 1

    target_cwd = ctx["cwd"] if ctx["ok"] else work_cwd
    activate = ctx["activate"]

    if activate is None and ctx["ok"]:
        click.secho(
            f" [!] Script de ativação ausente em {ctx['python'].parent}",
            fg="yellow",
        )
        click.echo("     Abrindo shell puro (sem activate).")

    final_title = title or f"DOXOADE_VENV_{Path(target_cwd).name}"

    try:
        if os.name == "nt":
            _open_windows_shell(target_cwd, activate, final_title, admin)
        else:
            _open_posix_shell(target_cwd, activate, final_title)
        return 0
    except Exception as e:
        click.secho(f" [✘] Falha ao abrir shell: {e}", fg="red")
        return 1


# ───────────────────────────────────────────────────────────────────────────
# CLI `doxoade venv`
# ───────────────────────────────────────────────────────────────────────────

@click.command("venv")
@click.option("--admin", is_flag=True, help="Abrir com privilégios de Administrador (UAC).")
@click.option("--title", default=None, help="Título customizado para a janela.")
@click.option("--name", "project_name", default=None, help="Nome do projeto (usado no título default).")
@click.option("--dry-run", is_flag=True, help="Mostra o que faria, sem abrir janela (ProDeNov §5.3).")
def venv_cmd(admin: bool, title: Optional[str], project_name: Optional[str], dry_run: bool):
    """Ativa o VENV do projeto em um novo terminal (PASC-8.4).

    Detecção automática:
      • venv/ ou .venv/ na raiz do cwd
      • activate.bat / activate / Activate.ps1 ao lado do python do venv

    Por padrão, abre terminal NÃO-elevado (sem UAC). Use --admin para elevar.
    """
    ctx = _resolve_venv_context()

    if dry_run:
        click.secho("\n🔍 VENV — DRY-RUN (nada será aberto)\n", fg="cyan", bold=True)
        if ctx["ok"]:
            click.echo(f"  ✔ venv detectado:")
            click.echo(f"      python   : {ctx['python']}")
            click.echo(f"      activate : {ctx['activate'] or '(ausente)'}")
            click.echo(f"      cwd      : {ctx['cwd']}")
        else:
            click.secho(f"  ⚠ {ctx['reason']}", fg="yellow")
            click.echo(f"      cwd      : {ctx['cwd']}")
        click.echo(f"  Comando alvo:")
        if os.name == "nt":
            chain = f'cd /d "{ctx["cwd"]}" && title DOXOADE_VENV_<proj>'
            if ctx["activate"]:
                chain += f' && "{ctx["activate"]}"'
            click.echo(f'      cmd.exe /k "{chain}"')
            if admin:
                click.echo(f"      [elevação UAC ativa]")
        else:
            click.echo(f"      bash -c 'cd \"{ctx['cwd']}\" && source \"{ctx['activate']}\"'")
        click.echo()
        return

    rc = open_venv_shell(
        admin=admin,
        title=title,
        project_name=project_name,
    )
    sys.exit(rc)

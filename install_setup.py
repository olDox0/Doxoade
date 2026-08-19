#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# install_setup.py
"""
================================================================================
⚡ NEXUS SOVEREIGN SETUP & INSTALLER V4.1 (FASTPACK & OFFLINE AWARE)
Projeto: DOXOADE (olDox222 Advanced Development Environment)
================================================================================
Instalador autônomo com auto-detecção de Wheelhouse Offline e criação de venv.
================================================================================
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

if os.name == 'nt':
    os.system('')


class UI:
    CYAN    = '\033[1;36m'
    GREEN   = '\033[1;32m'
    YELLOW  = '\033[1;33m'
    RED     = '\033[1;31m'
    MAGENTA = '\033[1;35m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'
    RESET   = '\033[0m'


def log_header(title: str):
    print(f"\n{UI.CYAN}{UI.BOLD}{'='*68}")
    print(f" 🚀 {title}")
    print(f"{'='*68}{UI.RESET}")


def log_step(step: str, desc: str):
    print(f"\n{UI.MAGENTA}[FASE {step}]{UI.RESET} {UI.BOLD}{desc}{UI.RESET}")


def log_ok(msg: str):
    print(f"  {UI.GREEN}✔{UI.RESET} {msg}")


def log_warn(msg: str):
    print(f"  {UI.YELLOW}⚠{UI.RESET} {msg}")


def log_err(msg: str):
    print(f"  {UI.RED}✘{UI.RESET} {msg}")


def get_venv_paths(root: Path):
    venv_dir = root / "venv"
    if os.name == "nt":
        scripts_dir = venv_dir / "Scripts"
        python_exe = scripts_dir / "python.exe"
        pip_exe = scripts_dir / "pip.exe"
        doxoade_exe = scripts_dir / "doxoade.exe"
        activate_cmd = f"call {scripts_dir / 'activate.bat'}"
    else:
        scripts_dir = venv_dir / "bin"
        python_exe = scripts_dir / "python"
        pip_exe = scripts_dir / "pip"
        doxoade_exe = scripts_dir / "doxoade"
        activate_cmd = f"source {scripts_dir / 'activate'}"

    return {
        "venv_dir": venv_dir,
        "scripts_dir": scripts_dir,
        "python": python_exe,
        "pip": pip_exe,
        "doxoade": doxoade_exe,
        "activate": activate_cmd
    }


def safe_run(cmd, cwd=None, check=True) -> subprocess.CompletedProcess:
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
    log_header("DOXOADE SOVEREIGN INSTALLER - V4.1 (OFFLINE-AWARE)")
    paths = get_venv_paths(ROOT)

    # FASE 1: Verificação de Python
    log_step("1/6", "Auditoria do Interpretador Base...")
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        log_err(f"Python 3.10+ é obrigatório. Versão atual: {v.major}.{v.minor}.{v.micro}")
        sys.exit(1)
    log_ok(f"Python Base compatível: {v.major}.{v.minor}.{v.micro}")

    # FASE 2: Ambiente Virtual
    log_step("2/6", "Isolamento de Ambiente Virtual (venv)...")
    if not paths["venv_dir"].exists():
        print(f"  {UI.DIM}Criando ambiente virtual em '{paths['venv_dir']}'...{UI.RESET}")
        try:
            safe_run([sys.executable, "-m", "venv", str(paths["venv_dir"])])
            log_ok("Ambiente virtual forjado com sucesso.")
        except Exception as e:
            log_err(f"Falha ao criar venv: {e}")
            sys.exit(1)
    else:
        log_ok(f"Ambiente virtual existente detectado.")

    # FASE 3 & 4: Instalação das Dependências (Auto-Detecção Offline)
    log_step("3/6", "Instalação de Dependências...")
    wheelhouse_dir = ROOT / "_fastpack_whl"

    if wheelhouse_dir.exists() and any(wheelhouse_dir.glob("*.whl")):
        print(f"  {UI.CYAN}⚡ Wheelhouse Offline detectada ({len(list(wheelhouse_dir.glob('*.whl')))} wheels).{UI.RESET}")
        print(f"  {UI.DIM}Instalando pacotes locais em alta velocidade (Zero Internet)...{UI.RESET}")
        try:
            cmd = [
                str(paths["python"]), "-m", "pip", "install",
                "--no-index",
                "--no-build-isolation",
                f"--find-links={str(wheelhouse_dir)}",
                "-e", str(ROOT)
            ]
            safe_run(cmd)
            log_ok("Dependências locais instaladas em modo offline com sucesso!")
        except subprocess.CalledProcessError as e:
            log_warn(f"Instalação offline parcial: {e.stderr.strip()[:120]}")
    else:
        print(f"  {UI.DIM}Instalando via pip padrão no venv...{UI.RESET}")
        try:
            safe_run([str(paths["python"]), "-m", "pip", "install", "-e", str(ROOT)])
            log_ok("Dependências instaladas com sucesso.")
        except subprocess.CalledProcessError as e:
            log_err(f"Falha no pip install:\n{e.stderr}")
            sys.exit(1)

    # FASE 5: Diretórios Soberanos
    log_step("4/6", "Inicialização de Diretórios de Persistência...")
    for d in (ROOT / "data" / "db", ROOT / ".doxoade" / "logs", ROOT / ".doxoade" / "vulcan"):
        d.mkdir(parents=True, exist_ok=True)
    log_ok("Diretórios de dados e telemetria inicializados.")

    # FASE 6: Rastreabilidade
    log_step("5/6", "Validação de Rastreabilidade e Integridade...")
    if paths["doxoade"].exists():
        log_ok(f"Binário verificado: {paths['doxoade']}")
    else:
        log_warn("O binário 'doxoade' não foi encontrado no local esperado.")

    # Conclusão
    log_header("INSTALAÇÃO CONCLUÍDA COM SUCESSO!")
    print(f"{UI.GREEN}{UI.BOLD}Para ativar o ambiente neste terminal:{UI.RESET}\n")
    print(f"  {UI.CYAN}{UI.BOLD}{paths['activate']}{UI.RESET}\n")
    print(f"E sincronize com o Host rodando: {UI.YELLOW}doxoade lan-git pull{UI.RESET}\n")


if __name__ == "__main__":
    main()
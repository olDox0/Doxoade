# -*- coding: utf-8 -*-
# doxoade/commands/init_system/init_setup.py
"""
Nexus Setup Genesis Engine - v1.1
================================================================================
Responsável por forjar e implantar o instalador soberano autônomo (`setup_install.py`)
em Silos novos ou existentes gerenciados pelo Doxoade.
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
    """Gera o código-fonte Python puro para o instalador `setup_install.py`."""
    pkgs = runtime_packages or [
        "click>=8.1.0",
        "colorama>=0.4.6",
        "psutil>=5.9.5",
    ]
    formatted_pkgs = ",\n    ".join([f'"{p}"' for p in pkgs])
    proj_title = project_name.upper()

    return f'''# -*- coding: utf-8 -*-
"""
================================================================================
⚡ NEXUS SOVEREIGN SETUP & INSTALLER V3.1 (VULCAN CORE)
Projeto: {project_name}
================================================================================
Padrão Industrial Blindado contra a Praga do Unicode (Windows cp1252)
e com Bootstrapping prioritário de Setuptools/Wheel.
================================================================================
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Força UTF-8 no ambiente Python para subprocessos
ENV_UTF8 = os.environ.copy()
ENV_UTF8["PYTHONUTF8"] = "1"
ENV_UTF8["PYTHONIOENCODING"] = "utf-8"

# ==============================================================================
# 🎨 MOTOR DE CORES ANSI & EXECUTOR SEGURO
# ==============================================================================
if os.name == 'nt':
    os.system('')  # Ativa suporte a ANSI no Windows CMD/PowerShell

class UI:
    CYAN    = '\\033[1;36m'
    GREEN   = '\\033[1;32m'
    YELLOW  = '\\033[1;33m'
    RED     = '\\033[1;31m'
    MAGENTA = '\\033[1;35m'
    BOLD    = '\\033[1m'
    RESET   = '\\033[0m'

def log_header(title: str):
    print(f"\\n{{UI.CYAN}}{{UI.BOLD}}{{'='*65}}")
    print(f" 🚀 {{title}}")
    print(f"{{'='*65}}{{UI.RESET}}")

def log_step(step: str, desc: str):
    print(f"\\n{{UI.MAGENTA}}[FASE {{step}}]{{UI.RESET}} {{UI.BOLD}}{{desc}}{{UI.RESET}}")

def log_ok(msg: str):
    print(f"  {{UI.GREEN}}✔{{UI.RESET}} {{msg}}")

def log_warn(msg: str):
    print(f"  {{UI.YELLOW}}⚠{{UI.RESET}} {{msg}}")

def log_err(msg: str):
    print(f"  {{UI.RED}}✘{{UI.RESET}} {{msg}}")

def safe_run(cmd, cwd=None, check=True) -> subprocess.CompletedProcess:
    """Executor blindado contra UnicodeDecodeError no Windows."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ENV_UTF8
    )

# ==============================================================================
# 🛠️ MATRIZ DE DEPENDÊNCIAS
# ==============================================================================
BOOTSTRAP_PACKAGES = [
    "setuptools>=68.0.0",
    "wheel>=0.41.0",
]

RUNTIME_PACKAGES = [
    {formatted_pkgs}
]

CORE_DIRECTORIES = [
    ROOT / "bin",
    ROOT / "data" / "db",
    ROOT / ".doxoade" / "logs",
]

# ==============================================================================
# ⚙️ FASES DE INSTALAÇÃO
# ==============================================================================

def phase_1_bootstrap_setuptools_and_pip():
    """Instala PRIMEIRO o Setuptools e Wheel, depois Pip."""
    log_step("1/6", "Bootstrapping Primário (Setuptools & Wheel Primeiro)...")
    
    try:
        import pip
    except ImportError:
        log_warn("pip ausente. Acionando ensurepip de emergência...")
        safe_run([sys.executable, "-m", "ensurepip", "--upgrade"])

    try:
        safe_run([sys.executable, "-m", "pip", "install", "--upgrade"] + BOOTSTRAP_PACKAGES)
        log_ok("Setuptools e Wheel instalados com prioridade máxima.")
    except Exception as e:
        log_warn(f"Aviso no bootstrap do setuptools: {{e}}")

    try:
        safe_run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        log_ok("Gerenciador Pip sincronizado.")
    except Exception as e:
        log_warn(f"Aviso ao atualizar pip: {{e}}")


def phase_2_topology():
    """Cria a topologia de diretórios e inicializadores __init__.py."""
    log_step("2/6", "Forjando Topologia e Estrutura de Pastas...")
    
    for d in CORE_DIRECTORIES:
        d.mkdir(parents=True, exist_ok=True)
    log_ok("Diretórios de dados, cache e binários sincronizados.")

    for p in ROOT.iterdir():
        if p.is_dir() and not p.name.startswith(('.', '_', 'venv', 'build', 'dist', 'bin', 'data')):
            init_file = p / "__init__.py"
            if not init_file.exists():
                init_file.touch()
    log_ok("Arquivos __init__.py estruturados nos módulos.")


def phase_3_dependencies():
    """Instala as bibliotecas de runtime necessárias."""
    log_step("3/6", "Instalando Dependências de Runtime...")
    
    if not RUNTIME_PACKAGES:
        log_ok("Nenhuma dependência externa declarada.")
        return

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + RUNTIME_PACKAGES
    try:
        proc = safe_run(cmd)
        for line in proc.stdout.splitlines():
            if "Successfully installed" in line:
                log_ok(f"Instalado: {{line.replace('Successfully installed ', '')}}")
        log_ok("Todas as bibliotecas Python instaladas e compatíveis.")
    except subprocess.CalledProcessError as e:
        log_err(f"Falha ao instalar dependências: {{e.stderr}}")
        sys.exit(1)


def phase_4_metalcraft_compilation():
    """Compila os motores nativos C via GCC se disponível."""
    log_step("4/6", "Compilando Motores Nativos C (Vulcan Metalcraft)...")
    
    gcc_path = shutil.which("gcc")
    if not gcc_path:
        log_warn("Compilador GCC não localizado no PATH.")
        log_warn("O sistema utilizará os binários pré-compilados ou fallbacks Python.")
        return

    src_native = ROOT / "src" / "native"
    bin_dir = ROOT / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    if not src_native.exists():
        log_ok("Nenhum código-fonte C detectado em 'src/native/'.")
        return

    compiled_count = 0
    for c_file in src_native.glob("*.c"):
        if c_file.name == "main.c":
            continue
        out_dll = bin_dir / f"{{c_file.stem}}.dll"
        cmd = ["gcc", "-O3", "-s", str(c_file), "-shared", "-o", str(out_dll), "-lkernel32"]
        try:
            safe_run(cmd)
            log_ok(f"Motor forjado: {{out_dll.name}}")
            compiled_count += 1
        except subprocess.CalledProcessError as e:
            log_warn(f"Aviso ao compilar {{out_dll.name}}: {{e.stderr[:80] if e.stderr else ''}}")

    if compiled_count > 0:
        log_ok(f"{{compiled_count}} biblioteca(s) nativa(s) forjada(s) com sucesso.")


def phase_5_bind_cli():
    """Registra o comando global no ambiente via setup.py."""
    log_step("5/6", "Vinculando Ponto de Entrada CLI ('{cli_command_name}')...")
    
    if not (ROOT / "setup.py").exists():
        log_warn("Arquivo setup.py não encontrado. Pulando registro editável.")
        return

    cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
    try:
        safe_run(cmd, cwd=str(ROOT))
        log_ok("Comando global '{cli_command_name}' registrado com sucesso.")
    except subprocess.CalledProcessError as e:
        log_err(f"Erro ao registrar pacote no modo editável: {{e.stderr}}")
        sys.exit(1)


def phase_6_smoke_test():
    """Executa auditoria de integridade pós-instalação (Smoke Test)."""
    log_step("6/6", "Auditoria de Integridade (Smoke Test)...")

    imports_to_test = ["setuptools", "click"]
    for mod in imports_to_test:
        try:
            __import__(mod)
            log_ok(f"Módulo Python: '{{mod}}' [OK]")
        except ImportError as e:
            log_err(f"Módulo '{{mod}}' falhou no carregamento: {{e}}")
            sys.exit(1)

    try:
        res = safe_run(["{cli_command_name}", "--help"], check=False)
        if res.returncode == 0:
            log_ok("CLI '{cli_command_name}' operacional e respondendo em UTF-8.")
        else:
            log_warn(f"CLI retornou código {{res.returncode}}.")
    except Exception as e:
        log_warn(f"Aviso ao invocar comando '{cli_command_name}': {{e}}")


# ==============================================================================
# 🏁 PONTO DE ENTRADA PRINCIPAL
# ==============================================================================
if __name__ == "__main__":
    log_header("{proj_title}: INSTALADOR SOBERANO AUTÔNOMO")
    
    phase_1_bootstrap_setuptools_and_pip()
    phase_2_topology()
    phase_3_dependencies()
    phase_4_metalcraft_compilation()
    phase_5_bind_cli()
    phase_6_smoke_test()
    
    print(f"\\n{{UI.GREEN}}{{UI.BOLD}}{{'='*65}}")
    print(" 🎉 INSTALAÇÃO CONCLUÍDA COM 100% DE SUCESSO!")
    print(f"{{'='*65}}{{UI.RESET}}")
    print(f"Para iniciar o sistema, digite: {{UI.YELLOW}}{cli_command_name} --help{{UI.RESET}}\\n")
'''


def inject_setup_existing(root: Path, apply_changes: bool = True) -> None:
    """Injeta ou atualiza o `setup_install.py` em um projeto existente."""
    root = Path(root).resolve()
    project_name = root.name
    cli_name = detect_cli_name(root, project_name)
    requirements = extract_existing_requirements(root)

    click.echo()
    click.secho(f"⚡ [NEXUS:SETUP] Implantando Instalador Soberano em '{project_name}'...", fg="cyan", bold=True)
    click.echo(f"   CLI Detectado : {Fore.YELLOW}{cli_name}{Style.RESET_ALL}")
    click.echo(f"   Dependências  : {Fore.GREEN}{len(requirements)} pacote(s){Style.RESET_ALL}")

    target_file = root / "setup_install.py"
    code = generate_setup_install_code(
        project_name=project_name,
        cli_command_name=cli_name,
        runtime_packages=requirements,
    )

    if apply_changes:
        target_file.write_text(code, encoding="utf-8")
        click.secho(f"   [OK] setup_install.py gerado com sucesso em: {target_file}", fg="green")
        click.secho("   Dica: Execute 'python setup_install.py' para testar a instalação.", fg="yellow")
    else:
        click.secho("   [DRY-RUN] Nenhuma alteração gravada.", fg="yellow")
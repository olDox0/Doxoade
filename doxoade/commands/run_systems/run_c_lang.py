# doxoade/doxoade/commands/run_systems/run_c_lang.py
"""
Execução de linguagens C/C++ para o comando run.

Responsabilidade:
- detectar fontes C/C++
- compilar com gcc/g++
- executar o binário gerado
- manter o resto do pipeline intacto
"""
from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Final
import click

C_SOURCE_EXTS: Final[dict[str, dict[str, object]]] = {'.c': {'compiler': 'gcc', 'std_flag': '-std=c11'}, '.cpp': {'compiler': 'g++', 'std_flag': '-std=c++17'}, '.cc': {'compiler': 'g++', 'std_flag': '-std=c++17'}, '.cxx': {'compiler': 'g++', 'std_flag': '-std=c++17'}}
BIN_EXTS = {'.exe', '.bin', '.out'}

def is_c_family_source(script_path: str | os.PathLike[str]) -> bool:
    """Retorna True se o arquivo for C/C++ suportado."""
    suffix = Path(script_path).suffix.lower()
    return suffix in C_SOURCE_EXTS

def _resolve_toolchain(ext: str) -> tuple[str, str]:
    """Resolve compilador e flags base por extensão."""
    info = C_SOURCE_EXTS.get(ext.lower())
    if not info:
        raise click.ClickException(f'Extensão não suportada para C/C++: {ext}')
    compiler_name = str(info['compiler'])
    std_flag = str(info['std_flag'])
    compiler_path = shutil.which(compiler_name)
    if not compiler_path:
        raise click.ClickException(f"Compilador '{compiler_name}' não encontrado no PATH. Instale o w64devkit ou ajuste o PATH.")
    return (compiler_path, std_flag)

def _build_output_path(source_path: Path, build_dir: Path) -> Path:
    """Nome do executável gerado no diretório temporário."""
    exe_name = source_path.stem + ('.exe' if os.name == 'nt' else '')
    return build_dir / exe_name

def compile_c_family_source(script_path):
    source_path = Path(script_path).resolve()
    build_dir = get_build_dir(source_path)
    output_path = build_dir / (source_path.stem + '.exe')
    ext = source_path.suffix.lower()
    compiler, std_flag = _resolve_toolchain(ext)
    cmd = [compiler, str(source_path), std_flag, '-O2', '-Wall', '-Wextra', '-o', str(output_path)]
    proc = subprocess.run(cmd, cwd=str(source_path.parent), capture_output=True, text=True)
    if proc.returncode != 0:
        raise click.ClickException(proc.stderr)
    return output_path

def execute_binary(binary_path, limits: dict = None) -> None:
    """Executa o binário nativo com proteção do Warden."""
    from doxoade.tools.aegis.warden import apply_resource_limits
    import subprocess
    
    click.echo(f'\x1b[36m--- [RUN:C/C++] {os.path.basename(binary_path)} ---\x1b[0m')
    
    # Função para injetar limites antes do processo nativo começar (apenas Unix)
    def preexec():
        if limits:
            apply_resource_limits(limits)

    # No Windows, preexec_fn não é suportado, então o Warden apenas emite o aviso
    if os.name == 'nt':
        apply_resource_limits(limits)
        proc = subprocess.run([str(binary_path)])
    else:
        proc = subprocess.run([str(binary_path)], preexec_fn=preexec)
    
    if proc.returncode != 0:
        click.echo(f"\x1b[31m[EXIT] O processo terminou com erro: {proc.returncode}\x1b[0m")

def run_c_lang(script_path, limits: dict = None, flow: bool = False):
    source_or_bin = Path(script_path).resolve()
    suffix = source_or_bin.suffix.lower()

    # Caso 1: É um executável já pronto
    if suffix in BIN_EXTS or (suffix == '' and os.access(source_or_bin, os.X_OK)):
        exe_path = source_or_bin
    else:
        # Caso 2: É código fonte, precisa compilar
        build_dir = get_build_dir(source_or_bin)
        exe_path = build_dir / (source_or_bin.stem + ('.exe' if os.name == 'nt' else ''))
        if needs_recompile(source_or_bin, exe_path):
            click.echo('\x1b[33m[BUILD] Compilando fonte...\x1b[0m')
            compile_c_family_source(script_path)

    # Execução
    if flow:
        run_c_with_flow(exe_path, limits)
    else:
        execute_binary(exe_path, limits)

def is_c_family_target(script_path: str) -> bool:
    """Detecta se é fonte C ou um binário nativo."""
    suffix = Path(script_path).suffix.lower()
    # Se não tem extensão e é executável (Linux) ou se tem extensão binária/fonte
    return suffix in C_SOURCE_EXTS or suffix in BIN_EXTS or (suffix == '' and os.access(script_path, os.X_OK))

def maybe_run_c_lang(script_path: str, limits: dict = None, flow: bool = False) -> bool:
    if not is_c_family_target(script_path):
        return False
    run_c_lang(script_path, limits=limits, flow=flow)
    return True

def needs_recompile(src_path: Path, exe_path: Path):
    if not exe_path.exists():
        return True
    return src_path.stat().st_mtime > exe_path.stat().st_mtime

def get_build_dir(source_path: Path) -> Path:
    build_dir = source_path.parent / '.doxoade' / 'c_lang_build'
    build_dir.mkdir(parents=True, exist_ok=True)
    return build_dir
    
def run_c_with_flow(exe_path, limits):
    """🌊 Nexus Flow para Binários: Rastro de chamadas de sistema."""
    from doxoade.tools.aegis.warden import apply_resource_limits
    import shutil
    
    click.echo(f"\x1b[34m🌊 Injetando Sonda Nexus Flow em Binário Nativo...\x1b[0m")
    apply_resource_limits(limits)

    # Verifica se há strace (Linux) ou gdb (Windows) para fazer o rastro
    if shutil.which("strace"):
        cmd = ["strace", "-e", "trace=memory,write,read,openat", str(exe_path)]
        subprocess.run(cmd)
    elif shutil.which("gdb"):
        # Modo batch do GDB para ver o rastro de execução básico no Windows
        cmd = ["gdb", "-batch", "-ex", "run", "-ex", "bt", "--args", str(exe_path)]
        subprocess.run(cmd)
    else:
        click.echo("\x1b[33m⚠️  Ferramentas de rastro (strace/gdb) não encontradas. Execução padrão.\x1b[0m")
        subprocess.run([str(exe_path)])


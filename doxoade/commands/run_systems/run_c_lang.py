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

def execute_binary(binary_path: str | os.PathLike[str]) -> None:
    """Executa o binário gerado."""
    binary = Path(binary_path).resolve()
    if not binary.exists():
        raise click.ClickException(f'Executável não encontrado: {binary}')
    proc = subprocess.run([str(binary)], cwd=str(binary.parent))
    if proc.returncode != 0:
        raise click.ClickException(f'Execução terminou com código {proc.returncode}: {binary.name}')

def run_c_lang(script_path):
    source = Path(script_path).resolve()
    build_dir = get_build_dir(source)
    exe_path = build_dir / (source.stem + '.exe')
    import time
    t0 = time.time()
    if needs_recompile(source, exe_path):
        t_build0 = time.time()
        click.echo('[BUILD] Compilando...')
        exe_path = compile_c_family_source(script_path)
        click.echo(f'[BUILD] Tempo: {time.time() - t_build0:.3f}s')
    t_exec0 = time.time()
    execute_binary(exe_path)
    click.echo(f'[EXEC] Tempo: {time.time() - t_exec0:.3f}s')
    click.echo(f'[TOTAL] {time.time() - t0:.3f}s')
    click.echo(f'\x1b[36m--- [RUN:C/C++] {exe_path.name} ---\x1b[0m')
    execute_binary(exe_path)

def maybe_run_c_lang(script_path: str | os.PathLike[str]) -> bool:
    """
    Se for C/C++, executa e retorna True.
    Caso contrário, retorna False.
    """
    if not is_c_family_source(script_path):
        return False
    run_c_lang(script_path)
    return True

def needs_recompile(src_path: Path, exe_path: Path):
    if not exe_path.exists():
        return True
    return src_path.stat().st_mtime > exe_path.stat().st_mtime

def get_build_dir(source_path: Path) -> Path:
    build_dir = source_path.parent / '.doxoade' / 'c_lang_build'
    build_dir.mkdir(parents=True, exist_ok=True)
    return build_dir
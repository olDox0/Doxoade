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
# [DOX-UNUSED] import tempfile
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
    
    try:
        # Tenta import absoluto (se rodando como pacote)
        from doxoade.diagnostic.soteria.scribe import SoteriaScribe
    except (ImportError, ModuleNotFoundError):
        # Tenta rastro relativo: run_systems -> commands -> doxoade -> diagnostic
#        from ...diagnostic.soteria.scribe import SoteriaScribe
        from doxoade.tools.vulcan.diagnostic.soteria.scribe import SoteriaScribe

    scribe = SoteriaScribe() # <--- Garanta que esta linha tenha EXATAMENTE 4 espaços
    
    shadow_src = build_dir / f"{source_path.stem}_vax.c"
    content = source_path.read_text(encoding='utf-8', errors='ignore')
    vax_content = scribe.instrument_code(content, source_path.name)
    shadow_src.write_text(vax_content, encoding='utf-8')
    
    # Localiza caminhos internos do sistema de resgate
    core_dir = Path(__file__).resolve().parents[3]
    soteria_inc = core_dir / "doxoade" / "tools" / "vulcan" / "diagnostic" / "soteria" / "include"
    soteria_src = core_dir / "doxoade" / "tools" / "vulcan" / "diagnostic" / "soteria" / "src"
    
    # Coleta todas as fontes da Sotéria
    diag_sources = [str(f).replace("\\", "/") for f in soteria_src.glob("*.c")]
    
    ext = source_path.suffix.lower()
    compiler, std_flag = _resolve_toolchain(ext)
    
    # --- ORDEM DE METALURGIA NEXUS ---
    cmd = [
        compiler, 
        str(shadow_src).replace("\\", "/"),
#        str(source_path).replace("\\", "/"), # Fonte do usuário
        std_flag, "-O0", "-g",
        f"-I{soteria_inc}",                  # Header da Sotéria
    ] 
    
    # Injeta as fontes da Sotéria no build
    cmd += diag_sources 
    
    # Finaliza com o Output e as Bibliotecas do Windows (O Linker as exige no fim)
    cmd += [
        "-o", str(output_path).replace("\\", "/"),
        "-lpsapi", "-ldbghelp" # <--- AS BIBLIOTECAS DEVEM FICAR AQUI
    ]
    
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        raise click.ClickException(f"Falha na Metalurgia Vulcan:\n{proc.stderr}")
    return output_path

def execute_binary(binary_path, limits=None, extra_args=None):
    import subprocess
    from doxoade.rescue import activate_protocol
    from doxoade.tools.telemetry_tools.logger import chief_heartbeat

    click.echo(f'\x1b[36m--- [RUN:C/C++] {os.path.basename(binary_path)} ---\x1b[0m')
    cmd = [str(binary_path)] + (extra_args or [])
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    stdout_data, stderr_data = proc.communicate()
    output = (stdout_data or "") + (stderr_data or "")

    # Filtra tags do Sotéria da saída do usuário
    if stdout_data:
        for line in stdout_data.splitlines():
            if not any(tag in line for tag in ["@SOTERIA_", "TAG_", "@NEXUS_"]):
                print(line)
    if stderr_data:
        for line in stderr_data.splitlines():
            if not any(tag in line for tag in ["@SOTERIA_", "TAG_", "@NEXUS_"]):
                print(line)

    chief_heartbeat("PIPELINE", "BINARY_OUTPUT_CAPTURE", {
        "size": len(output),
        "exit_code": proc.returncode
    })

    # ═══════════════════════════════════════════════════════════════
    # [FIX] Distinguir CRASH NATIVO de EXIT NORMAL
    # ═══════════════════════════════════════════════════════════════
    # Um teste que falha (exit 1) NÃO é crash.
    # Um crash real tem exit code de NTSTATUS (>= 0xC0000000) ou
    # signal Unix (128+), ou evidência textual de crash.
    # ═══════════════════════════════════════════════════════════════
    rc = proc.returncode

    # Classificação do exit code
    if rc is None:
        is_crash = False
    elif os.name == 'nt':
        # Windows: exit normal é 0..0xC0000000-1, crash é 0xC0000000+
        is_crash = rc < 0 or rc >= 0xC0000000
    else:
        # Unix: exit normal é 0..127, killed-by-signal é 128+
        is_crash = rc < 0 or rc >= 128

    # Marcadores textuais de crash (mesmo que exit seja "normal")
    crash_markers = [
        "FATAL: ",
        "CRASH DETECTED",
        "AccessViolation",
        "SegmentationFault",
        "SIGSEGV",
        "Heap Corruption",
        "Stack Smashing",
        "TAG_MOTIVO: 0xC",
        "TAG_MOTIVO: 0xc",
        "TAG_MOTIVO: SIG",
    ]
    has_crash_marker = any(m in output for m in crash_markers)

    # Sotéria pode emitir begin/end mesmo em exit normal
    # (via atexit). Só é crash se combinado com marcadores.
    has_soteria_block = "@SOTERIA_BEGIN@" in output

    # Decisão final
    is_real_crash = is_crash or has_crash_marker

    if is_real_crash:
        # Crash nativo — aciona protocolo forense
        activate_protocol(output, exit_code=rc)
        return False

    # Exit normal (0 ou != 0 por motivo lógico — testes, validação)
    if rc != 0:
        click.echo(
            f"\n{Fore.YELLOW}[EXIT] Programa encerrou com código {rc}.{Style.RESET_ALL}"
        )
        click.echo(
            f"{Style.DIM}Isso não é um crash — verifique a saída acima "
            f"para detalhes.{Style.RESET_ALL}"
        )
        return False

    click.echo(f"   {Fore.GREEN}✔ Execução finalizada normalmente.{Style.RESET_ALL}")
    return True
    
def run_c_lang(script_path, limits: dict = None, flow: bool = False, extra_args: list = None):
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
        run_c_with_flow(exe_path, limits, extra_args=extra_args)
    else:
        execute_binary(exe_path, limits, extra_args=extra_args)

def is_c_family_target(script_path: str) -> bool:
    """
    Garante que só tentaremos rodar como C se for um arquivo real 
    com as extensões corretas.
    """
    path = Path(script_path)
    # Bloqueia se for apenas um comando (como 'doxoade' ou 'pip')
    if not path.exists():
        return False
        
    valid_exts = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp'}
    # Se não tiver extensão de C e não for um .exe real, não é alvo C
    if path.suffix.lower() not in valid_exts and path.suffix.lower() != '.exe':
        return False
        
    return True

def maybe_run_c_lang(script_path, limits=None, flow=False, extra_args=None):
    if not is_c_family_target(script_path):
        return False
    run_c_lang(script_path, limits=limits, flow=flow, extra_args=extra_args)
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
    
    click.echo("\x1b[34m🌊 Injetando Sonda Nexus Flow em Binário Nativo...\x1b[0m")
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


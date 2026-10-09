# -*- coding: utf-8 -*-
# doxoade\commands\asm_cmd.py
"""
[ZEUS] CLI Assembly — doxoade asm {build,status,run,clean}.
"""
import os
import subprocess
import sys

import click

try:
    from doxoade.tools.doxcolors import Fore, Style
except Exception:
    class _NC:
        def __getattr__(self, _): return ""
    Fore = Style = _NC()

from doxoade.tools.assembly_systems import AssemblyEngine


@click.group("asm", help="🔨 Assembly Systems — Forja de baixo nível (NASM/GAS).")
def asm_group():
    pass


@asm_group.command("status")
@click.argument("project_root", default=".", type=click.Path(exists=True))
def asm_status(project_root):
    """🔍 Diagnóstico da toolchain Assembly."""
    engine = AssemblyEngine(project_root)
    status = engine.status()

    click.echo(f"\n{Fore.CYAN}═══════ [ASM STATUS] ═══════{Style.RESET_ALL}")

    # Assemblers
    click.echo(f"\n{Fore.YELLOW}⚙️  Assemblers:{Style.RESET_ALL}")
    for name, info in status["assemblers"].items():
        if info:
            click.echo(f"  {Fore.GREEN}✔{Style.RESET_ALL} {info}")
        else:
            click.echo(f"  {Fore.RED}✘{Style.RESET_ALL} {name.upper()} não encontrado no PATH")

    # Linker
    click.echo(f"\n{Fore.YELLOW}🔗 Linker:{Style.RESET_ALL}")
    click.echo(f"  {Fore.CYAN}{status['linker']}{Style.RESET_ALL}")

    # Config
    cfg = status["config"]
    click.echo(f"\n{Fore.YELLOW}📋 Configuração:{Style.RESET_ALL}")
    click.echo(f"  Projeto: {cfg.get('project', {}).get('name', '?')}")
    click.echo(f"  Output:  {cfg.get('build', {}).get('output', '?')}")

    # Sources
    srcs = status["sources"]
    click.echo(f"\n{Fore.YELLOW}📂 Fontes detectados:{Style.RESET_ALL}")
    click.echo(f"  Assembly: {len(srcs['asm'])} arquivo(s)")
    for s in srcs["asm"]:
        click.echo(f"    • {s}")
    click.echo(f"  C:        {len(srcs['c'])} arquivo(s)")
    for s in srcs["c"]:
        click.echo(f"    • {s}")

    click.echo(f"\n{Fore.CYAN}════════════════════════════{Style.RESET_ALL}\n")


@asm_group.command("build")
@click.argument("project_root", default=".", type=click.Path(exists=True))
@click.option("--clean/--no-clean", default=False, help="Limpa .o antes de compilar")
@click.option("--verbose", "-v", is_flag=True, help="Mostra comandos executados")
def asm_build(project_root, clean, verbose):
    """🔨 Compila e linka o projeto (Assembly + C)."""
    engine = AssemblyEngine(project_root)

    click.echo(f"{Fore.CYAN}⚒️  [ASM BUILD] Iniciando forja...{Style.RESET_ALL}")
    results = engine.build(clean=clean)

    # Relatório de compilação
    ok = sum(1 for r in results["compile"] if r.success)
    fail = sum(1 for r in results["compile"] if not r.success)
    click.echo(f"  Compilação: {Fore.GREEN}{ok} OK{Style.RESET_ALL} / {Fore.RED}{fail} falhas{Style.RESET_ALL}")

    for r in results["compile"]:
        if not r.success:
            click.echo(f"\n{Fore.RED}✘ Falha em: {r.source}{Style.RESET_ALL}")
            click.echo(f"  cmd: {' '.join(r.command)}")
            click.echo(f"  stderr: {r.stderr[:500]}")
            if verbose:
                click.echo(f"  stdout: {r.stdout[:500]}")
            sys.exit(1)

        if verbose:
            click.echo(f"  {Fore.GREEN}✔{Style.RESET_ALL} {' '.join(r.command)}")

    # Relatório de link
    lr = results.get("link")
    if lr:
        if lr.success:
            size_kb = lr.size_bytes / 1024
            click.echo(f"\n{Fore.GREEN}✔ Link concluído: {lr.output} ({size_kb:.1f} KB){Style.RESET_ALL}")
        else:
            click.echo(f"\n{Fore.RED}✘ Falha no link:{Style.RESET_ALL}")
            click.echo(f"  cmd: {' '.join(lr.command)}")
            click.echo(f"  stderr: {lr.stderr[:800]}")
            sys.exit(1)

    if results["success"]:
        click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}🏁 Build concluído com sucesso!{Style.RESET_ALL}")
    else:
        sys.exit(1)


@asm_group.command("clean")
@click.argument("project_root", default=".", type=click.Path(exists=True))
def asm_clean(project_root):
    """🧹 Remove objetos (.o) e binários finais."""
    engine = AssemblyEngine(project_root)
    removed = engine.clean()
    click.echo(f"{Fore.GREEN}✔ {removed} arquivo(s) removido(s).{Style.RESET_ALL}")


@asm_group.command("run")
@click.argument("project_root", default=".", type=click.Path(exists=True))
@click.option("--emulator", "-e", default="qemu-system-i386",
              help="Emulador (qemu-system-i386, qemu-system-x86_64, bochs)")
@click.option("--ram", "-m", default="32M", help="RAM alocada")
@click.option("--kernel/--no-kernel", default=True,
              help="Usa -kernel (multiboot) ao invés de -drive")
def asm_run(project_root, emulator, ram, kernel):
    """🚀 Executa o binário no QEMU/Bochs."""
    engine = AssemblyEngine(project_root)
    output = engine.config.get("build", {}).get("output", "kernel.bin")
    bin_path = os.path.join(project_root, output)

    if not os.path.exists(bin_path):
        click.echo(f"{Fore.RED}✘ Binário não encontrado: {bin_path}{Style.RESET_ALL}")
        click.echo(f"  Rode 'doxoade asm build' primeiro.")
        sys.exit(1)

    if "qemu" in emulator:
        if kernel:
            cmd = [emulator, "-kernel", bin_path, "-m", ram, "-nographic"]
        else:
            cmd = [emulator, "-drive", f"format=raw,file={bin_path}", "-m", ram]
    elif "bochs" in emulator:
        cmd = [emulator, "-q", "-f", "bochsrc.txt"]
    else:
        cmd = [emulator, bin_path]

    click.echo(f"{Fore.CYAN}▶ {Style.RESET_ALL}{' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=project_root)
    except FileNotFoundError:
        click.echo(f"{Fore.RED}✘ Emulador '{emulator}' não encontrado no PATH.{Style.RESET_ALL}")
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo(f"\n{Fore.YELLOW}⚠ Emulador encerrado pelo usuário.{Style.RESET_ALL}")

@asm_group.command("setup-tools")
def asm_setup_tools():
    """🛠️ Provisiona NASM e GNU AS (Binutils) automaticamente."""
    import urllib.request
    import zipfile
    import io
    
    from doxoade.tools.assembly_systems.asm_detector import AssemblyDetector
    
    click.echo(f"{Fore.CYAN}⚒️  [ASM SETUP] Verificando Toolchain Assembly...{Style.RESET_ALL}")
    
    # 1. Checa GAS (GNU AS)
    gas_info = AssemblyDetector.detect("gas")
    if gas_info:
        click.echo(f"  {Fore.GREEN}✔ GNU AS encontrado: {gas_info}{Style.RESET_ALL}")
    else:
        click.echo(f"  {Fore.YELLOW}⚠ GNU AS não encontrado. Certifique-se de que o GCC (Winlibs/MinGW) está instalado.{Style.RESET_ALL}")

    # 2. Checa e Provisiona NASM
    nasm_info = AssemblyDetector.detect("nasm")
    if nasm_info:
        click.echo(f"  {Fore.GREEN}✔ NASM encontrado: {nasm_info}{Style.RESET_ALL}")
        return

    click.echo(f"  {Fore.YELLOW}⚠ NASM não encontrado. Baixando versão portable (Win64)...{Style.RESET_ALL}")
    
    # Provisionamento Automático (Futuro: Salvar em .doxoade/toolchain/nasm)
    url = "https://www.nasm.us/pub/nasm/releasebuilds/2.16.01/win64/nasm-2.16.01-win64.zip"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'doxoade/1.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            
        toolchain_dir = Path.home() / ".doxoade" / "toolchain" / "nasm"
        toolchain_dir.mkdir(parents=True, exist_ok=True)
        
        click.echo(f"  {Fore.YELLOW}  Extraindo em {toolchain_dir}...{Style.RESET_ALL}")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(toolchain_dir)
            
        # O zip extrai em uma subpasta nasm-2.16.01, precisamos achar o exe
        nasm_exe = next(toolchain_dir.rglob("nasm.exe"), None)
        if nasm_exe:
            click.echo(f"  {Fore.GREEN}✔ NASM provisionado com sucesso em: {nasm_exe}{Style.RESET_ALL}")
            click.echo(f"  {Fore.CYAN}💡 Dica: Adicione '{nasm_exe.parent}' ao seu PATH de sistema.{Style.RESET_ALL}")
        else:
            click.echo(f"  {Fore.RED}✘ Falha ao localizar nasm.exe após extração.{Style.RESET_ALL}")
            
    except Exception as e:
        click.echo(f"  {Fore.RED}✘ Falha no provisionamento de rede: {e}{Style.RESET_ALL}")

@asm_group.command("image")
@click.argument("project_root", default=".", type=click.Path(exists=True))
@click.option("--run", is_flag=True, help="Boota a imagem no QEMU apos a forja.")
@click.option("--clean", is_flag=True, help="Limpa objetos antes do build.")
def asm_image(project_root, run, clean):
    """📀 Forja a imagem bootavel: build + flat + imagem (+ QEMU opcional)."""
    import shutil, subprocess
    from doxoade.tools.assembly_systems.image_builder import ImageBuilder

    engine = AssemblyEngine(project_root)
    results = engine.build(clean=clean)
    if not results["success"]:
        click.echo(f"{Fore.RED}✘ Build falhou — forja de imagem abortada.{Style.RESET_ALL}")
        if results.get("link") and results["link"].stderr:
            click.echo(results["link"].stderr[:800])
        sys.exit(1)

    if not engine.extract_flat():
        click.echo(f"{Fore.RED}✘ Falha ao extrair o flat binary.{Style.RESET_ALL}")
        sys.exit(1)

    info = ImageBuilder(project_root).build()
    click.echo(f"{Fore.CYAN}📀 Imagem forjada: {info['output']} ({info['bytes']} bytes){Style.RESET_ALL}")
    click.echo(f"   MBR 0xAA55 : {'✔' if info['mbr_ok'] else '✘'}")
    click.echo(f"   DAP        : {info['dap_sectors']} >= {info['sectors_needed']} setores {'✔' if info['dap_ok'] else '✘'}")

    if run:
        qemu = shutil.which("qemu-system-i386") or r"C:\Program Files\qemu\qemu-system-i386.exe"
        click.echo(f"{Fore.CYAN}▶ Bootando no QEMU...{Style.RESET_ALL}")
        subprocess.run([qemu, "-drive", f"file={info['output']},format=raw,if=ide", "-boot", "c"])

@asm_group.command("setup-tools")
@click.option("--skip-nasm", is_flag=True, help="Não instala NASM.")
@click.option("--skip-zig", is_flag=True, help="Não instala Zig.")
@click.option("--skip-qemu", is_flag=True, help="Não instala QEMU.")
def asm_setup_tools(skip_nasm, skip_zig, skip_qemu):
    """🛠️ Provisiona a toolchain OS-Dev (NASM + Zig + QEMU) via winget."""
    import os, shutil, subprocess
    from doxoade.tools.assembly_systems.asm_detector import AssemblyDetector

    local = Path(os.environ.get("LOCALAPPDATA", ""))
    zig_ok = bool(shutil.which("zig")) or (local / "Microsoft/WinGet/Links/zig.exe").exists() \
             or any(local.glob("Microsoft/WinGet/Packages/zig.zig_*/zig-*/zig.exe"))
    qemu_ok = bool(shutil.which("qemu-system-i386")) or Path(r"C:\Program Files\qemu\qemu-system-i386.exe").exists()
    nasm_ok = AssemblyDetector.detect("nasm") is not None

    plan = []
    if not skip_nasm and not nasm_ok: plan.append(("NASM.NASM", "assembler x86"))
    if not skip_zig and not zig_ok:   plan.append(("zig.zig", "cross-compiler ELF32/LLD"))
    if not skip_qemu and not qemu_ok: plan.append(("SoftwareFreedomConservancy.QEMU", "emulador"))

    if not plan:
        click.echo(f"{Fore.GREEN}✔ Toolchain OS-Dev completa detectada. Nada a prover.{Style.RESET_ALL}")
        return

    for pkg, desc in plan:
        click.echo(f"{Fore.CYAN}📦 Provisionando {desc}: winget install --id {pkg}{Style.RESET_ALL}")
        subprocess.run(["winget", "install", "--id", pkg,
                        "--accept-package-agreements", "--accept-source-agreements"])

    click.echo(f"{Fore.GREEN}✔ Provisionamento concluído.{Style.RESET_ALL}")
    click.echo(f"{Fore.YELLOW}💡 Abra um NOVO terminal para ativar os aliases (ou rode 'doxoade asm doctor').{Style.RESET_ALL}")

@asm_group.command("doctor")
def asm_doctor():
    """🩺 Auditoria Ma'at da toolchain OS-Dev."""
    import os, shutil
    from doxoade.tools.assembly_systems.asm_detector import AssemblyDetector

    local = Path(os.environ.get("LOCALAPPDATA", ""))
    zig = shutil.which("zig") or next(
        (str(p) for p in local.glob("Microsoft/WinGet/Packages/zig.zig_*/zig-*/zig.exe")), None)
    qemu = shutil.which("qemu-system-i386") or (
        r"C:\Program Files\qemu\qemu-system-i386.exe"
        if Path(r"C:\Program Files\qemu\qemu-system-i386.exe").exists() else None)

    rows = [
        ("NASM (bootloader)", AssemblyDetector.detect("nasm")),
        ("GAS  (fallback .s)", AssemblyDetector.detect("gas")),
        ("Zig  (C freestanding + LLD)", zig),
        ("QEMU (emulação)", qemu),
    ]
    click.echo(f"\n{Fore.CYAN}🩺 [ASM DOCTOR] Toolchain OS-Dev{Style.RESET_ALL}")
    for name, info in rows:
        ok = info is not None
        detail = str(info) if ok and not isinstance(info, str) else (info or "ausente")
        click.echo(f"  {'✔' if ok else Fore.RED + '✘' + Style.RESET_ALL} {name:<28} {Fore.DIM if not ok else ''}{detail}{Style.RESET_ALL}")
    click.echo()

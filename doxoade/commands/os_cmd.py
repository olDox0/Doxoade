# -*- coding: utf-8 -*-
# doxoade/commands/os_cmd.py
"""
[ZEUS] Interface CLI Soberana para Gestão de OS Dev e Emulação.
Comandos: doxoade os {doctor, run, trace, debug} com salvaguarda --dry-run.
Em total conformidade com o protocolo ProDeNov v2.0.
"""

import sys
from pathlib import Path
import click

try:
    from doxoade.tools.doxcolors import Fore, Style
except Exception:
    class _NC:
        def __getattr__(self, _): return ""
    Fore = Style = _NC()

from doxoade.tools.emulator_systems import (
    QemuDetector,
    QemuRunner,
    QemuRunConfig,
    RunResult,
    DiskForge,
    DiskForgeConfig,
    DiskForgeResult,
)


@click.group("os", help="🦅 OS Dev Systems — Supervisão, telemetria e diagnóstico bare-metal.")
def os_group():
    """Grupo de comandos para pesquisa e execução de sistemas operacionais."""
    pass


@os_group.command("doctor")
def os_doctor():
    """🩺 Diagnóstico Ma'at da infraestrutura de emuladores e firmwares."""
    click.echo(f"\n{Fore.CYAN}🩺 [OS DOCTOR] Auditoria de Infraestrutura Bare-Metal{Style.RESET_ALL}\n")

    audit = QemuDetector.audit_w5h2()
    details = audit["detalhes"]

    # 1. Emuladores
    click.echo(f"{Fore.YELLOW}⚙️  Emuladores QEMU:{Style.RESET_ALL}")
    for arch in ["i386", "x86_64"]:
        info = details.get(arch)
        if info and info.is_operational:
            accel_tag = f"[{info.accel.upper()}]" if info.accel else "[TCG]"
            click.echo(
                f"  {Fore.GREEN}✔{Style.RESET_ALL} {arch:<8} v{info.version:<8} "
                f"{Fore.CYAN}{accel_tag:<8}{Style.RESET_ALL} @ {info.path}"
            )
        else:
            click.echo(f"  {Fore.RED}✘{Style.RESET_ALL} {arch:<8} não localizado no sistema.")

    # 2. Firmwares UEFI (OVMF)
    click.echo(f"\n{Fore.YELLOW}🛡️  Firmwares UEFI (OVMF):{Style.RESET_ALL}")
    for rom_arch in ["ia32", "x64"]:
        rom_info = details.get(f"ovmf_{rom_arch}")
        if rom_info:
            click.echo(f"  {Fore.GREEN}✔{Style.RESET_ALL} OVMF-{rom_arch.upper()}: {rom_info.path}")
        else:
            click.echo(
                f"  {Fore.YELLOW}⚠{Style.RESET_ALL} OVMF-{rom_arch.upper()}: ausente "
                f"{Fore.DIM}(necessário apenas para boot UEFI puro){Style.RESET_ALL}"
            )

    # 3. Resumo W5+2H
    click.echo(f"\n{Fore.YELLOW}📋 Resumo do Ambiente:{Style.RESET_ALL}")
    click.echo(f"  Emuladores ativos   : {Fore.GREEN}{audit['quanto']['emuladores_ativos']}{Style.RESET_ALL}")
    click.echo(f"  Firmwares detectados: {audit['quanto']['firmwares_encontrados']}")
    click.echo(f"  Origem              : {audit['origem']}")
    click.echo(f"\n{Fore.CYAN}══════════════════════════════════════════════════════════{Style.RESET_ALL}\n")


@os_group.command("run")
@click.argument("image", default="laurix.img", type=click.Path())
@click.option("--arch", "-a", default="i386", type=click.Choice(["i386", "x86_64"]), help="Arquitetura alvo.")
@click.option("--media", "-m", default="fda", type=click.Choice(["fda", "drive", "cdrom", "kernel"]), help="Tipo de mídia.")
@click.option("--ram", default=128, type=int, help="RAM alocada em MB.")
@click.option("--serial", default="stdio", type=click.Choice(["stdio", "file", "none"]), help="Canal da COM1.")
@click.option("--uefi", is_flag=True, help="Tenta boot UEFI via OVMF correspondente.")
@click.option("--dry-run", is_flag=True, help="Exibe comando sem disparar emulador.")
def os_run(image, arch, media, ram, serial, uefi, dry_run):
    """🚀 Executa a imagem bootável no QEMU com telemetria serial."""
    runner = QemuRunner(".")

    uefi_path = None
    if uefi:
        rom_arch = "ia32" if arch == "i386" else "x64"
        rom_info = QemuDetector.find_ovmf(rom_arch)
        if not rom_info:
            click.echo(f"{Fore.RED}✘ ROM UEFI (OVMF-{rom_arch.upper()}) não encontrada.{Style.RESET_ALL}")
            click.echo("  Coloque o arquivo OVMF na pasta 'firmware/' ou instale o pacote de OVMF.")
            sys.exit(1)
        uefi_path = rom_info.path

    cfg = QemuRunConfig(
        image_path=image,
        arch=arch,
        memory_mb=ram,
        media_type=media,
        serial_mode=serial,
        uefi_rom=uefi_path,
        dry_run=dry_run,
    )

    if dry_run:
        click.echo(f"{Fore.YELLOW}🛡️  [DRY-RUN] Simulação de Inicialização:{Style.RESET_ALL}")

    res: RunResult = runner.run(cfg)

    if dry_run:
        click.echo(f"  cmd: {' '.join(res.command)}\n")
        return

    if not res.success:
        click.echo(f"{Fore.RED}✘ Falha na execução do emulador:{Style.RESET_ALL} {res.message}")
        if res.command:
            click.echo(f"  cmd: {' '.join(res.command)}")
        sys.exit(1)

    click.echo(f"{Fore.GREEN}✔ {res.message}{Style.RESET_ALL}")


@os_group.command("trace")
@click.argument("image", default="laurix.img", type=click.Path())
@click.option("--arch", "-a", default="i386", type=click.Choice(["i386", "x86_64"]), help="Arquitetura alvo.")
@click.option("--media", "-m", default="fda", type=click.Choice(["fda", "drive", "cdrom", "kernel"]), help="Tipo de mídia.")
@click.option("--ram", default=128, type=int, help="RAM em MB.")
@click.option("--dry-run", is_flag=True, help="Simula sem disparar.")
def os_trace(image, arch, media, ram, dry_run):
    """🔬 Executa em modo forense gravando CPU resets e interrupções em qemu_trace.log."""
    runner = QemuRunner(".")

    click.echo(f"{Fore.CYAN}🔬 [HÓRUS TRACE] Modo Forense Ativado.{Style.RESET_ALL}")
    click.echo(f"  Capturando: interrupções (INT), resets de CPU e falhas de memória.")
    click.echo(f"  Arquivo alvo: {Fore.YELLOW}qemu_trace.log{Style.RESET_ALL}\n")

    cfg = QemuRunConfig(
        image_path=image,
        arch=arch,
        memory_mb=ram,
        media_type=media,
        trace_cpu=True,
        force_tcg=True,
        dry_run=dry_run,
    )

    res = runner.run(cfg)

    if dry_run:
        click.echo(f"{Fore.YELLOW}🛡️  [DRY-RUN] cmd:{Style.RESET_ALL} {' '.join(res.command)}")
        return

    if not res.success and res.return_code != 130:
        click.echo(f"{Fore.RED}✘ Falha no trace:{Style.RESET_ALL} {res.message}")
        sys.exit(1)

    if res.trace_file and res.trace_file.exists():
        size_kb = res.trace_file.stat().st_size / 1024
        click.echo(f"\n{Fore.GREEN}✔ Log de CPU gravado com sucesso:{Style.RESET_ALL} {res.trace_file} ({size_kb:.1f} KB)")
        click.echo(f"  {Fore.CYAN}💡 Abra 'qemu_trace.log' para dissecar as interrupções disparadas.{Style.RESET_ALL}")


@os_group.command("debug")
@click.argument("image", default="laurix.img", type=click.Path())
@click.option("--arch", "-a", default="i386", type=click.Choice(["i386", "x86_64"]), help="Arquitetura alvo.")
@click.option("--media", "-m", default="fda", type=click.Choice(["fda", "drive", "cdrom", "kernel"]), help="Tipo de mídia.")
@click.option("--port", "-p", default=1234, type=int, help="Porta TCP do servidor GDB.")
@click.option("--dry-run", is_flag=True, help="Simula sem disparar.")
def os_debug(image, arch, media, port, dry_run):
    """🐛 Pausa a CPU no clock 0 e abre servidor GDB remoto (porta :1234)."""
    runner = QemuRunner(".")

    click.echo(f"{Fore.MAGENTA}🐛 [GDB DEBUGGER] Modo de Depuração Remota{Style.RESET_ALL}")
    click.echo(f"  CPU congelada no primeiro ciclo de execução.")
    click.echo(f"  Servidor aguardando em: {Fore.CYAN}localhost:{port}{Style.RESET_ALL}")
    click.echo(f"  Para conectar, abra outro terminal e execute:")
    click.echo(f"    {Fore.YELLOW}gdb -ex 'target remote localhost:{port}' -ex 'set architecture i386'{Style.RESET_ALL}\n")

    cfg = QemuRunConfig(
        image_path=image,
        arch=arch,
        media_type=media,
        debug_gdb=True,
        gdb_port=port,
        force_tcg=True,
        dry_run=dry_run,
    )

    res = runner.run(cfg)

    if dry_run:
        click.echo(f"{Fore.YELLOW}🛡️  [DRY-RUN] cmd:{Style.RESET_ALL} {' '.join(res.command)}")
        return

    if not res.success and res.return_code != 130:
        click.echo(f"{Fore.RED}✘ Falha ao iniciar debug:{Style.RESET_ALL} {res.message}")
        sys.exit(1)

@os_group.command("forge")
@click.argument("output", default="uefi_disk.img", type=click.Path())
@click.option("--kernel", "-k", default=None, type=click.Path(), help="Binário EFI (.efi). Se omitido, injeta stub seguro.")
@click.option("--arch", "-a", default="ia32", type=click.Choice(["ia32", "x64"]), help="Arquitetura do bootloader UEFI.")
@click.option("--size", "-s", default=32, type=int, help="Tamanho total da imagem em MB.")
@click.option("--dry-run", is_flag=True, help="Simula forja sem gravar em disco.")
def os_forge(output, kernel, arch, size, dry_run):
    """📀 Forja imagem MBR/ESP FAT16 com árvore /EFI/BOOT/BOOT{ARCH}.EFI."""
    click.echo(f"\n{Fore.CYAN}📀 [HEFESTO DISK FORGE] Criando mídia UEFI soberana...{Style.RESET_ALL}")
    
    forge = DiskForge(".")
    k_path = Path(kernel) if kernel else None
    
    cfg = DiskForgeConfig(
        output_image=output,
        kernel_payload=k_path,
        arch=arch,
        disk_size_mb=size,
        dry_run=dry_run,
    )
    
    res: DiskForgeResult = forge.forge_uefi(cfg)
    
    if not res.success:
        click.echo(f"{Fore.RED}✘ Falha na forja:{Style.RESET_ALL} {res.message}")
        sys.exit(1)
        
    click.echo(f"  {Fore.GREEN}✔{Style.RESET_ALL} {res.message}")
    click.echo(f"  Partição: {Fore.YELLOW}MBR ESP (Tipo 0xEF){Style.RESET_ALL} alinhada em 1 MB")
    click.echo(f"  Binário : {Fore.CYAN}/EFI/BOOT/{res.target_efi_name}{Style.RESET_ALL}")
    click.echo(f"  Tamanho : {res.size_bytes / (1024*1024):.1f} MB\n")


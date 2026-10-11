# -*- coding: utf-8 -*-
# doxoade/commands/izanami_cmd.py
"""
[IZANAMI] Interface CLI para Gestão do Bootloader Soberano.
Orquestra o ciclo de vida completo: Build GCC -> Forja ESP -> QEMU Test -> Deploy Físico.
Em total conformidade com o protocolo ProDeNov v2.0.
"""

import os
import shutil
import subprocess
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
    DiskForge,
    DiskForgeConfig,
    SimulationMatrix,
)
from doxoade.tools.emulator_systems.esp_manager import EspManager

IZANAMI_ROOT = Path(__file__).resolve().parent.parent / "izanami"

@click.group("izanami", help="🌸 Izanami Systems — Gestão do Bootloader Soberano.")
def izanami_group():
    """Grupo de comandos para gestão do Izanami Systems."""
    pass


def _find_gcc() -> str:
    """Localiza o GCC no PATH ou no w64devkit embutido do Doxoade."""
    gcc_path = shutil.which("gcc")
    if gcc_path:
        return gcc_path

    # Varredura canônica no w64devkit
    base = Path().resolve()
    candidates = [
        base / "thirdparty" / "w64devkit" / "bin" / "gcc.exe",
        base.parent / "doxoade" / "thirdparty" / "w64devkit" / "bin" / "gcc.exe",
        Path(r"C:\winlibs\mingw64\bin\gcc.exe"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    return "gcc"


@izanami_group.command("build")
@click.option("--output", "-o", default="BOOTX64.EFI", help="Nome do binário PE32+ gerado.")
def izanami_build(output):
    """🔨 Compila o código C do Izanami em executável PE32+ de 64 bits via GCC."""
    src_dir = IZANAMI_ROOT / "src"
    sources = [
        src_dir / "izanami_core.c",
        src_dir / "izanami_memory.c",
        src_dir / "izanami_gop.c",
        src_dir / "izanami_handoff.c",
    ]

    for s in sources:
        if not s.exists():
            click.echo(f"{Fore.RED}✘ Fonte não encontrado: {s}{Style.RESET_ALL}")
            sys.exit(1)

    gcc = _find_gcc()
    click.echo(f"\n{Fore.CYAN}🔨 [IZANAMI BUILD 64-BIT] Compilando com {gcc}...{Style.RESET_ALL}")

    cmd = [
        gcc,
        "-m64",
        "-nostdlib",
        "-shared",
        "-Wl,--dll",
        "-Wl,--subsystem,10",
        "-Wl,--image-base,0x10000000",
        "-Wl,--entry,efi_main",
        "-Wl,--pie",
        "-fno-stack-protector",
        "-fshort-wchar",
        *[str(s) for s in sources],
        "-o", output
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        click.echo(f"{Fore.RED}✘ Falha na compilação:{Style.RESET_ALL}\n{res.stderr}")
        sys.exit(1)

    out_file = Path(output)
    size_kb = out_file.stat().st_size / 1024 if out_file.exists() else 0
    click.echo(f"  {Fore.GREEN}✔ Binário PE32+ (x86_64) forjado:{Style.RESET_ALL} {output} ({size_kb:.1f} KB)\n")


@izanami_group.command("forge")
@click.option("--kernel", "-k", default="BOOTX64.EFI", help="Binário EFI a injetar na imagem.")
@click.option("--image", "-i", default="uefi_x64.img", help="Imagem de disco gerada.")
@click.option("--size", default=32, type=int, help="Tamanho da imagem em MB.")
def izanami_forge(kernel, image, size):
    """📀 Forja a imagem de disco MBR/ESP FAT16 pronta para o firmware de 64 bits."""
    click.echo(f"{Fore.CYAN}📀 [IZANAMI FORGE] Criando imagem particionada x86_64...{Style.RESET_ALL}")
    forge = DiskForge(".")
    cfg = DiskForgeConfig(
        output_image=image,
        kernel_payload=Path(kernel),
        arch="x64",
        disk_size_mb=size
    )
    res = forge.forge_uefi(cfg)
    if not res.success:
        click.echo(f"{Fore.RED}✘ Falha na forja: {res.message}{Style.RESET_ALL}")
        sys.exit(1)

    click.echo(f"  {Fore.GREEN}✔ {res.message}{Style.RESET_ALL}\n")


@izanami_group.command("run")
@click.option("--image", "-i", default="uefi_baytrail.img", help="Imagem a rodar.")
@click.option("--rebuild/--no-rebuild", default=True, help="Recompila e reforja antes de rodar.")
def izanami_run(image, rebuild):
    """🚀 Pipeline completo: Build -> Forge -> Run no QEMU."""
    ctx = click.get_current_context()

    if rebuild:
        ctx.invoke(izanami_build)
        ctx.invoke(izanami_forge, image=image)

    click.echo(f"{Fore.CYAN}🚀 [IZANAMI RUN] Disparando QEMU via PFlash...{Style.RESET_ALL}")
    rom_info = QemuDetector.find_ovmf("ia32")
    if not rom_info:
        click.echo(f"{Fore.RED}✘ ROM EDK2 IA-32 não encontrada.{Style.RESET_ALL}")
        sys.exit(1)

    runner = QemuRunner(".")
    cfg = QemuRunConfig(
        image_path=image,
        arch="i386",
        media_type="drive",
        uefi_rom=rom_info.path,
        serial_mode="file"
    )
    runner.run(cfg)


@izanami_group.command("deploy")
@click.option("--kernel", "-k", default="BOOTIA32.EFI", help="Binário a instalar na partição física.")
@click.option("--label", default="Izanami Systems (IA-32)", help="Rótulo no menu de boot.")
def izanami_deploy(kernel, label):
    """🛡️ Instalação segura na partição ESP física do Windows (Requer Admin)."""
    k_path = Path(kernel)
    if not k_path.exists():
        click.echo(f"{Fore.RED}✘ Binário {kernel} não encontrado. Execute 'doxoade izanami build' primeiro.{Style.RESET_ALL}")
        sys.exit(1)

    mgr = EspManager(".")
    if not mgr.is_admin():
        click.echo(f"{Fore.RED}✘ Permissão negada. Abra o CMD como Administrador para fazer deploy no disco.{Style.RESET_ALL}")
        sys.exit(1)

    click.echo(f"\n{Fore.YELLOW}🛡️  [IZANAMI DEPLOY] Instalando na partição de boot interna...{Style.RESET_ALL}")
    try:
        res = mgr.install(k_path, label=label)
        click.echo(f"  {Fore.GREEN}✔ Sucesso absoluto!{Style.RESET_ALL}")
        if res and isinstance(res, dict):
            click.echo(f"  GUID Registrado: {Fore.CYAN}{res.get('guid', 'OK')}{Style.RESET_ALL}")
            click.echo(f"  Rótulo no Boot : {res.get('label', label)}")
            click.echo(f"  Arquivo Copiado: {res.get('file', 'ESP')}")
        click.echo(f"\n{Fore.GREEN}O Izanami está pronto para rodar fisicamente ao reiniciar o computador!{Style.RESET_ALL}\n")
    except Exception as e:
        click.echo(f"{Fore.RED}✘ Erro no deploy: {e}{Style.RESET_ALL}")


@izanami_group.command("uninstall")
def izanami_uninstall():
    """🔄 Reversão segura: Remove o Izanami do disco interno e restaura o Windows."""
    mgr = EspManager(".")
    if not mgr.is_admin():
        click.echo(f"{Fore.RED}✘ Permissão negada. Abra o CMD como Administrador.{Style.RESET_ALL}")
        sys.exit(1)

    click.echo(f"\n{Fore.YELLOW}🔄 [IZANAMI REVERT] Removendo entrada do disco interno...{Style.RESET_ALL}")
    try:
        res = mgr.uninstall()
        click.echo(f"  {Fore.GREEN}✔ {res['message']}{Style.RESET_ALL}")
        click.echo(f"  O Windows 10 permanece 100% original.\n")
    except Exception as e:
        click.echo(f"{Fore.RED}✘ Erro na reversão: {e}{Style.RESET_ALL}")


@izanami_group.command("status")
def izanami_status():
    """📋 Inspeciona o estado da instalação do Izanami no computador."""
    mgr = EspManager(".")
    st = mgr.status()
    click.echo(f"\n{Fore.CYAN}📋 [IZANAMI STATUS] Estado do Hardware Físico:{Style.RESET_ALL}")
    if st.is_installed:
        click.echo(f"  Status: {Fore.GREEN}INSTALADO NO DISCO INTERNO{Style.RESET_ALL}")
        click.echo(f"  GUID  : {st.guid}")
        click.echo(f"  Rótulo: {st.label}")
    else:
        click.echo(f"  Status: {Fore.YELLOW}NÃO INSTALADO NO HARDWARE FÍSICO{Style.RESET_ALL} (Apenas em sandbox/QEMU)")
    click.echo()

@izanami_group.command("sim")
@click.option("--image", "-i", default="uefi_x64.img", help="Imagem a rodar.")
@click.option("--rebuild/--no-rebuild", default=True, help="Recompila e reforja antes de rodar.")
@click.option("--dry-run", is_flag=True, help="Simula sem disparar o QEMU.")
def izanami_sim(image, rebuild, dry_run):
    """🌐 Simulação de alta fidelidade do Amaranth (Q35 + UEFI x86_64 + SMBIOS)."""
    ctx = click.get_current_context()

    if rebuild and not dry_run:
        ctx.invoke(izanami_build, output="BOOTX64.EFI")
        ctx.invoke(izanami_forge, kernel="BOOTX64.EFI", image=image)

    matrix = SimulationMatrix(".")
    click.echo(f"{Fore.CYAN}🌸 [IZANAMI SIM] Disparando simulação de 64 bits Positivo H14BT58...{Style.RESET_ALL}")
    
    # Parâmetros fieis ao Positivo H14BT58 no hardware x86_64
    extra_smbios = [
        "-smp", "2,cores=2,sockets=1",
        "-cpu", "Nehalem",
        "-smbios", "type=0,vendor=American Megatrends Inc.,version=1.07.U,date=05/15/2015",
        "-smbios", "type=1,manufacturer=Positivo Informatica SA,product=H14BT58"
    ]
    
    res = matrix.run("uefi64", custom_image=image, dry_run=dry_run, extra_args=extra_smbios)

    if dry_run:
        click.echo(f"{Fore.YELLOW}🛡️  [DRY-RUN] cmd:{Style.RESET_ALL} {' '.join(res.command)}")
        return

    if not res.success:
        click.echo(f"{Fore.RED}✘ Falha na simulação: {res.message}{Style.RESET_ALL}")
        sys.exit(1)

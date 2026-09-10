# -*- coding: utf-8 -*-
# doxoade/commands/image_systems/cmd_image.py
""" 🖼️ CLI Zeus — Comandos de Gestão e Sincronização de Imagens e Sidecars RLE. """
from __future__ import annotations
import sys
import os
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.image_systems.image_manager import ImageAssetManager
from doxoade.tools.image_systems.thumbnail_engine import ThumbnailEngine


@click.group("image", help="🖼️ Gestão de imagens, capturas e sidecars binários (CAS).")
def image_group():
    """Grupo de comandos de imagens do Doxoade."""
    pass


@image_group.command("sync", help="Sincroniza todos os sidecars .thumb.rlebin do projeto.")
@click.option("--force", "-f", is_flag=True, help="Força a regeneração de todas as thumbnails.")
def cmd_sync(force: bool):
    """Varre as imagens do projeto e atualiza sidecars binários."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🖼️ SINCRONIZAÇÃO DE ATIVOS VISUAIS (DOXRLE1){Style.RESET_ALL}\n")
    report = ImageAssetManager.sync_project_thumbnails(force=force)
    
    print(f"  {Fore.WHITE}Total de Imagens:{Fore.RESET} {report['total_scanned']}")
    print(f"  {Fore.GREEN}Geradas/Atualizadas:{Fore.RESET} {report['generated']}")
    print(f"  {Fore.BLUE}Em Cache (Íntegras):{Fore.RESET} {report['cache_hits']}")
    if report["failed"] > 0:
        print(f"  {Fore.RED}Falhas:{Fore.RESET} {report['failed']}\n")
        for item in report["results"]:
            if item["status"] not in ("GENERATED", "CACHE_HIT"):
                print(f"    {Fore.RED}✖ {item['file']}: {item['error']}{Fore.RESET}")
        sys.exit(1)
    else:
        print(f"\n{Fore.GREEN}✔ Todos os sidecars estão 100% sincronizados!{Fore.RESET}\n")


@image_group.command("thumb", help="Gera o sidecar binário para uma imagem específica.")
@click.argument("image_path", type=click.Path(exists=True))
@click.option("--preset", "-p", type=click.Choice(["card", "compact", "hd_preview"]), default="card", help="Preset de resolução.")
def cmd_thumb(image_path: str, preset: str):
    """Gera thumbnail binária para um único arquivo."""
    engine = ThumbnailEngine()
    res = engine.generate(image_path, preset=preset, force=True)
    if res.ok:
        print(f"{Fore.GREEN}✔ Sidecar gerado com sucesso: {res.sidecar_path.name}{Fore.RESET}")
        print(f"   Dimensões: {res.orig_w}x{res.orig_h} ➔ Grid: {res.grid_w}x{res.grid_h} ({res.rects} blocos | {res.bytes:,} bytes)")
    else:
        print(f"{Fore.RED}✖ Falha ao gerar thumbnail: {res.error}{Fore.RESET}")
        sys.exit(1)

@image_group.command("paste", help="Salva a imagem do clipboard e gera tag [DOX-IMG].")
@click.option("--dir", "-d", "target_dir", default=None, help="Diretório de destino.")
@click.option("--out", "-o", "out_file", default=None, help="Arquivo JSON de saída.")
def cmd_paste(target_dir: Optional[str], out_file: Optional[str]):
    """Captura o print da área de transferência e gera o arquivo PNG + Thumbnail."""
    import json
    from datetime import datetime
    from doxoade.tools.image_systems.clipboard_grabber import grab_image_hybrid
    from doxoade.tools.image_systems.thumbnail_engine import ThumbnailEngine

    res = grab_image_hybrid()
    if res["status"] != "SUCCESS":
        err_payload = json.dumps({"status": "EMPTY", "error": res["error"]})
        if out_file:
            Path(out_file).write_text(err_payload, encoding="utf-8")
        print(err_payload)
        sys.exit(1)

    img = res["image"]
    root = Path(target_dir or os.getcwd()).resolve()
    assets_dir = root / ".doxoade" / "assets" / "images"
    assets_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"print_{ts}.png"
    dest_png = assets_dir / filename

    img.convert("RGB").save(dest_png, format="PNG")

    engine = ThumbnailEngine(root)
    thumb_res = engine.generate(dest_png, preset="card", force=True)

    output = {
        "status": "SUCCESS",
        "filename": filename,
        "full_path": str(dest_png),
        "tag": f"[DOX-IMG: {filename} | {img.width}x{img.height} | {date_str}]",
        "markdown": f"![{filename}](.doxoade/assets/images/{filename})",
        "width": img.width,
        "height": img.height,
        "thumb_rects": thumb_res.rects
    }

    out_json_str = json.dumps(output)
    if out_file:
        Path(out_file).write_text(out_json_str, encoding="utf-8")
    print(out_json_str)

@image_group.command("copy", help="Copia uma imagem PNG de volta para a área de transferência do Windows.")
@click.argument("image_path", type=click.Path(exists=True))
def cmd_copy(image_path: str):
    """Lê o arquivo PNG e injeta o bitmap na área de transferência do Windows."""
    from doxoade.tools.image_systems.clipboard_grabber import copy_image_to_clipboard_win32

    ok, msg = copy_image_to_clipboard_win32(image_path)
    if ok:
        print(f"{Fore.GREEN}✔ {msg}{Fore.RESET}")
    else:
        print(f"{Fore.RED}✖ {msg}{Fore.RESET}")
        sys.exit(1)
    
    import platform
    if platform.system() == "Windows":
        try:
            import ctypes
            u32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32

            with Image.open(img_p) as img:
                output = io.BytesIO()
                img.convert("RGB").save(output, "BMP")
                bmp_data = output.getvalue()[14:]  # Remove cabeçalho BMP de 14 bytes para obter DIB puro

            if u32.OpenClipboard(None):
                u32.EmptyClipboard()
                h_glob = k32.GlobalAlloc(0x0002, len(bmp_data))  # GMEM_MOVEABLE = 0x0002
                p_glob = k32.GlobalLock(h_glob)
                ctypes.memmove(p_glob, bmp_data, len(bmp_data))
                k32.GlobalUnlock(h_glob)
                u32.SetClipboardData(8, h_glob)  # CF_DIB = 8
                u32.CloseClipboard()
                print(f"{Fore.GREEN}✔ Imagem copiada para a área de transferência do Windows: {img_p.name}{Fore.RESET}")
                return
        except Exception as e:
            print(f"{Fore.RED}✖ Falha ao copiar para clipboard Win32: {e}{Fore.RESET}")
            sys.exit(1)

    print(f"{Fore.YELLOW}⚠ Cópia direta de bitmap suportada no Windows.{Fore.RESET}")


# doxoade/doxoade/commands/gui_cmd.py
import click
import os
import subprocess
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root
from doxoade.tools.metalcraft.metal_toolchain import NexusToolchain

@click.group('gui')
def gui_group():
    """🖼️ Benzaiten Engine: Criação de Interfaces Nativas e WebViews."""
    pass


# ─── build ────────────────────────────────────────────────────────────────────

@gui_group.command('build')
def build_gui():
    """Forja as bibliotecas nativas (DLL/SO) do Benzaiten para o projeto atual."""
    doxoade_dir    = Path(__file__).resolve().parents[1]
    native_src_dir = doxoade_dir / "tools" / "benzaiten_gui" / "native"

    project_root = Path(_find_project_root(os.getcwd()))
    out_dir      = project_root / ".doxoade" / "benzaiten"
    out_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [BENZAITEN FORGE] Compilando Motor Gráfico ---{Style.RESET_ALL}")

    toolchain = NexusToolchain()
    if not toolchain.detect():
        click.echo(f"{Fore.RED}[ERRO] Compilador GCC não encontrado.{Style.RESET_ALL}")
        return

    compiler = toolchain.compiler_path

    if os.name == 'nt':
        src = native_src_dir / "dxgui_win.c"
        out = out_dir / "dxgui.dll"

        # Dois diretórios de include:
        # 1. native/include/          — headers webview/webview (webview.h, webview/...)
        # 2. native/include/webview2/ — WebView2.h extraído do NuGet
        inc_webview  = native_src_dir / "include"
        inc_webview2 = native_src_dir / "include" / "webview2"

        # g++ (C++17 necessário para webview/webview)
        gpp = str(Path(compiler).parent / "g++.exe")
        if not Path(gpp).exists():
            gpp = compiler

        # Verifica dependências
        webview_h = inc_webview / "webview" / "webview.h"
        wv2_h     = inc_webview2 / "WebView2.h"
        loader    = out_dir / "WebView2Loader.dll"

        missing = []
        if not webview_h.exists(): missing.append("webview/webview.h")
        if not wv2_h.exists():     missing.append("WebView2.h (NuGet SDK)")
        if not loader.exists():    missing.append("WebView2Loader.dll")

        if missing:
            click.echo(f"{Fore.RED}[ERRO] Dependências ausentes: {', '.join(missing)}\n"
                       f"       Execute: doxoade gui fetch-deps{Style.RESET_ALL}")
            return

        # Gera import lib se não existir
        import_lib = out_dir / "libWebView2Loader.a"
        if not import_lib.exists():
            dlltool = str(Path(compiler).parent / "dlltool.exe")
            if Path(dlltool).exists():
                click.echo(f"{Fore.YELLOW}  Gerando import lib para WebView2Loader...{Style.RESET_ALL}")
                subprocess.run([
                    dlltool, "-D", str(loader), "-l", str(import_lib)
                ], capture_output=True, text=True)

        cmd = [
            gpp, "-shared", "-O2", "-std=c++17",
            f"-I{inc_webview}",    # para #include "webview/webview.h"
            f"-I{inc_webview2}",   # para #include "WebView2.h"
            "-o", str(out), str(src),
            "-mwindows",
            "-lgdi32", "-luser32",
            "-lole32", "-loleaut32", "-luuid", "-lshlwapi",
            f"-L{out_dir}",
            "-lWebView2Loader",
        ]
        os_name  = "Windows"
        used_cmp = gpp
    else:
        src      = native_src_dir / "dxgui_x11.c"
        out      = out_dir / "libdxgui.so"
        cmd      = [compiler, "-shared", "-O2", "-fPIC",
                    "-o", str(out), str(src), "-lX11"]
        os_name  = "Linux"
        used_cmp = compiler

    if not src.exists():
        click.echo(f"{Fore.RED}[ERRO] Fonte não encontrada: {src}{Style.RESET_ALL}")
        return

    try:
        click.echo(f"{Fore.YELLOW}⚙️  Metalurgia ativada para {os_name} usando: {Path(used_cmp).name}...{Style.RESET_ALL}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        click.echo(f"{Fore.GREEN}✅ Sucesso! DLL forjada em: {out.relative_to(project_root)}{Style.RESET_ALL}")
    except subprocess.CalledProcessError as e:
        click.echo(f"{Fore.RED}❌ Falha na compilação:\n{e.stderr}{Style.RESET_ALL}")


# ─── fetch-deps ───────────────────────────────────────────────────────────────

@gui_group.command('fetch-deps')
def fetch_deps():
    """
    Baixa todas as dependências de build e runtime do Benzaiten:

      webview/webview headers  → native/include/webview/
      WebView2.h (NuGet SDK)   → native/include/webview2/WebView2.h
      WebView2Loader.dll       → .doxoade/benzaiten/

    Fonte única: NuGet (Microsoft.Web.WebView2) + GitHub (webview/webview).
    Tudo extraído do mesmo download — sem dependências extras.
    """
    if os.name != 'nt':
        click.echo(f"{Fore.YELLOW}fetch-deps é necessário apenas no Windows.{Style.RESET_ALL}")
        return

    doxoade_dir    = Path(__file__).resolve().parents[1]
    native_src_dir = doxoade_dir / "tools" / "benzaiten_gui" / "native"
    inc_dir        = native_src_dir / "include"
    inc_wv2_dir    = inc_dir / "webview2"
    inc_dir.mkdir(parents=True, exist_ok=True)
    inc_wv2_dir.mkdir(parents=True, exist_ok=True)

    project_root = Path(_find_project_root(os.getcwd()))
    out_dir      = project_root / ".doxoade" / "benzaiten"
    out_dir.mkdir(parents=True, exist_ok=True)

    import urllib.request
    import urllib.error
    import zipfile
    import io

    # ── 1. NuGet: WebView2.h + WebView2Loader.dll (mesmo pacote) ─────────────
    NUGET_PKG  = "Microsoft.Web.WebView2"
    NUGET_VER  = "1.0.2792.45"
    NUGET_URL  = f"https://www.nuget.org/api/v2/package/{NUGET_PKG}/{NUGET_VER}"

    loader_dst = out_dir / "WebView2Loader.dll"
    wv2h_dst   = inc_wv2_dir / "WebView2.h"

    need_nuget = (not loader_dst.exists()) or (not wv2h_dst.exists())

    if need_nuget:
        click.echo(f"{Fore.CYAN}--- [DEPS] Baixando pacote NuGet {NUGET_PKG} {NUGET_VER} ---{Style.RESET_ALL}")
        try:
            req = urllib.request.Request(NUGET_URL, headers={"User-Agent": "doxoade/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                nupkg_data = r.read()
            click.echo(f"{Fore.YELLOW}  Extraindo artefatos...{Style.RESET_ALL}")

            with zipfile.ZipFile(io.BytesIO(nupkg_data)) as zf:
                names = zf.namelist()

                # WebView2Loader.dll — runtimes/win-x64/native/
                if not loader_dst.exists():
                    DLL_PATH = "runtimes/win-x64/native/WebView2Loader.dll"
                    if DLL_PATH in names:
                        loader_dst.write_bytes(zf.read(DLL_PATH))
                        click.echo(f"{Fore.GREEN}  ✔ WebView2Loader.dll ({loader_dst.stat().st_size // 1024} KB){Style.RESET_ALL}")
                    else:
                        click.echo(f"{Fore.RED}  ❌ WebView2Loader.dll não encontrada no pacote{Style.RESET_ALL}")

                # WebView2.h — build/native/include/
                if not wv2h_dst.exists():
                    WV2H_PATH = "build/native/include/WebView2.h"
                    if WV2H_PATH in names:
                        wv2h_dst.write_bytes(zf.read(WV2H_PATH))
                        click.echo(f"{Fore.GREEN}  ✔ WebView2.h ({wv2h_dst.stat().st_size // 1024} KB){Style.RESET_ALL}")
                    else:
                        # Fallback: procura qualquer WebView2.h no pacote
                        candidates = [n for n in names if n.endswith("WebView2.h")]
                        if candidates:
                            wv2h_dst.write_bytes(zf.read(candidates[0]))
                            click.echo(f"{Fore.GREEN}  ✔ WebView2.h (via {candidates[0]}){Style.RESET_ALL}")
                        else:
                            click.echo(f"{Fore.RED}  ❌ WebView2.h não encontrado no pacote NuGet{Style.RESET_ALL}")

        except urllib.error.URLError as e:
            click.echo(f"{Fore.RED}  ❌ Falha de rede ao acessar NuGet: {e}{Style.RESET_ALL}")
            return
        except Exception as e:
            click.echo(f"{Fore.RED}  ❌ Falha ao processar pacote NuGet: {e}{Style.RESET_ALL}")
            return
    else:
        click.echo(f"{Fore.GREEN}✔ WebView2Loader.dll e WebView2.h já presentes.{Style.RESET_ALL}")

    # ── 2. webview/webview headers (GitHub zipball) ───────────────────────────
    webview_h = inc_dir / "webview" / "webview.h"
    if webview_h.exists():
        click.echo(f"{Fore.GREEN}✔ webview/webview headers já presentes.{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.CYAN}--- [DEPS] Baixando webview/webview headers ---{Style.RESET_ALL}")
        ZIPBALL_URL = "https://github.com/webview/webview/archive/refs/heads/master.zip"
        try:
            req = urllib.request.Request(ZIPBALL_URL, headers={"User-Agent": "doxoade/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()

            PREFIX = "webview-master/core/include/"
            extracted = 0
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    if name.startswith(PREFIX) and not name.endswith('/'):
                        rel  = name[len(PREFIX):]
                        dest = inc_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(zf.read(name))
                        extracted += 1

            if extracted == 0:
                click.echo(f"{Fore.RED}  ❌ Nenhum header extraído do zipball{Style.RESET_ALL}")
                return
            click.echo(f"{Fore.GREEN}  ✔ {extracted} headers instalados{Style.RESET_ALL}")

        except Exception as e:
            click.echo(f"{Fore.RED}  ❌ Falha ao baixar webview headers: {e}{Style.RESET_ALL}")
            return

    click.echo(f"{Fore.GREEN}✅ Dependências prontas. Rode: doxoade gui build{Style.RESET_ALL}")


# ─── diag ─────────────────────────────────────────────────────────────────────

@gui_group.command('diag')
def diag_gui():
    """Diagnóstico de Saúde da Engine Benzaiten."""
    click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [BENZAITEN DIAGNOSTIC] ---{Style.RESET_ALL}")

    doxoade_dir    = Path(__file__).resolve().parents[1]
    native_src_dir = doxoade_dir / "tools" / "benzaiten_gui" / "native"

    root       = Path(_find_project_root(os.getcwd()))
    bin_dir    = root / ".doxoade" / "benzaiten"
    lib_name   = "dxgui.dll" if os.name == 'nt' else "libdxgui.so"
    target_lib = bin_dir / lib_name

    inc_dir = native_src_dir / "include"

    checks = [
        ("webview/webview.h", inc_dir / "webview" / "webview.h"),
        ("WebView2.h (NuGet)", inc_dir / "webview2" / "WebView2.h"),
    ]
    if os.name == 'nt':
        checks.append(("WebView2Loader.dll", bin_dir / "WebView2Loader.dll"))
    checks.append((lib_name, target_lib))

    all_ok = True
    for label, path in checks:
        if path.exists():
            size = f" ({path.stat().st_size // 1024} KB)" if path.suffix != '.h' else ""
            click.echo(f"  {Fore.GREEN}✔ {label}:{Style.RESET_ALL}{size} OK")
        else:
            click.echo(f"  {Fore.RED}✘ {label}:{Style.RESET_ALL} Ausente — rode 'doxoade gui fetch-deps'")
            all_ok = False

    if not target_lib.exists():
        return

    import ctypes
    try:
        if os.name == 'nt':
            os.add_dll_directory(str(bin_dir))
        lib = ctypes.CDLL(str(target_lib))
        click.echo(f"  {Fore.GREEN}✔ Ligação Ctypes:{Style.RESET_ALL} OK")
        symbols = [
            "dxgui_create_window", "dxgui_navigate",
            "dxgui_load_html",     "dxgui_eval_js",
            "dxgui_set_ready_callback", "dxgui_set_msg_callback",
            "dxgui_is_ready",      "dxgui_run_loop",
        ]
        missing = [s for s in symbols if not hasattr(lib, s)]
        if not missing:
            click.echo(f"  {Fore.GREEN}✔ Símbolos Exportados:{Style.RESET_ALL} Todos os {len(symbols)} presentes.")
        else:
            click.echo(f"  {Fore.YELLOW}⚠ Símbolos Ausentes:{Style.RESET_ALL} {missing}")
            click.echo(f"     → DLL antiga. Rode: doxoade gui build")
    except OSError as e:
        click.echo(f"  {Fore.RED}✘ Ligação Ctypes:{Style.RESET_ALL} {e}")
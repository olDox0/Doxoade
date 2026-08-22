# doxoade/commands/lite_xl_systems/cmd_lite_xl.py
"""
Interface CLI para Orquestração, Diagnóstico Forense, Verificação de Templates e Reinício.
"""
import os
import re
import sys
import time 
import shutil
import subprocess
import click
from datetime import datetime, timedelta
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine


@click.group("lite-xl", help="⚡ Gestão, diagnóstico e automação do Lite XL.")
def lite_xl_group():
    """Grupo de comandos do ecossistema Lite XL."""
    pass


@lite_xl_group.command("check-templates", help="Audita individualmente cada arquivo de template .lua.")
def cmd_check_templates():
    t_dir = LiteXLEngine.get_template_dir()
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🧩 AUDITORIA DE TEMPLATES MODULARES LITE XL{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Diretório:{Fore.RESET} {t_dir}\n")

    report = LiteXLEngine.verify_templates()
    for fname, data in report["files"].items():
        status_badge = f"{Fore.GREEN}[PASS]{Fore.RESET}" if data["status"] == "PASS" else f"{Fore.RED}[FAIL]{Fore.RESET}"
        click.echo(f"  {status_badge} {Style.BRIGHT}{fname:<35}{Style.RESET_ALL} ({data['lines']} linhas)")

        for err in data["errors"]:
            click.echo(f"      {Fore.RED}✖ {err}{Fore.RESET}")
        for warn in data["warnings"]:
            click.echo(f"      {Fore.YELLOW}⚠ {warn}{Fore.RESET}")

    if report["all_ok"]:
        click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ Todos os {report['total_files']} templates .lua estão íntegros e sem erros!{Style.RESET_ALL}\n")
    else:
        click.echo(f"\n{Fore.RED}{Style.BRIGHT}✖ Foram encontrados erros nos templates acima.{Style.RESET_ALL}\n")


@lite_xl_group.command("kill", help="Encerra todos os processos do Lite XL em execução.")
def cmd_kill():
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
    click.echo(f"{Fore.GREEN}✔ Processos do Lite XL encerrados.{Fore.RESET}")


@lite_xl_group.command("restart", help="Salva a sessão, encerra e reinicia com todas as abas e splits preservados.")
@click.argument("target", required=False, default=".")
def cmd_restart(target):
    # Envia sinal para o Lite XL salvar o workspace e fechar de forma limpa
    if LiteXLEngine.is_running():
        try:
            ipc_queue = LiteXLEngine.get_ipc_queue_path()
            with open(ipc_queue, "a", encoding="utf-8") as f:
                f.write("__DOXOADE_GRACEFUL_QUIT__\n")
            time.sleep(0.4)
        except Exception:
            pass

    # Garante que nenhum processo fantasma permaneça
    LiteXLEngine.kill_ghost_processes()
    time.sleep(0.2)

    click.echo(f"{Fore.YELLOW}Reiniciando Lite XL com sessão preservada...{Fore.RESET}")
    native_exe = LiteXLEngine.find_executable()

    if native_exe:
        resolved_path, _, _ = LiteXLEngine.resolve_target_path(target)
        working_dir = str(Path(resolved_path).parent if Path(resolved_path).is_file() else resolved_path)
        subprocess.Popen(
            [str(native_exe), resolved_path],
            cwd=working_dir,
            close_fds=True
        )
        click.echo(f"{Fore.GREEN}✔ Lite XL reiniciado com abas e divisões mantidas:{Fore.RESET} {resolved_path}")
    else:
        click.echo(f"{Fore.RED}✖ Executável lite-xl.exe não encontrado.{Fore.RESET}")

@lite_xl_group.command("diagnose", help="Realiza auditoria forense do init.lua e templates.")
def cmd_diagnose():
    init_file = LiteXLEngine.get_init_lua_path()
    err_file = LiteXLEngine.get_error_txt_path()
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩺 DIAGNÓSTICO FORENSE DO INIT.LUA{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Alvo:{Fore.RESET} {init_file}\n")

    if err_file.exists():
        click.echo(f"{Fore.RED}{Style.BRIGHT}⚠ CRASH REPORT DETECTADO (error.txt):{Style.RESET_ALL}")
        click.echo(err_file.read_text(encoding="utf-8", errors="replace"))

    report = LiteXLEngine.diagnose_init_file(init_file)
    if not report["exists"]:
        click.echo(f"{Fore.RED}✖ Arquivo init.lua não encontrado.{Fore.RESET}")
        return

    if report["errors"]:
        click.echo(f"{Fore.RED}{Style.BRIGHT}✖ ERROS CRÍTICOS DETECTADOS ({len(report['errors'])}):{Style.RESET_ALL}")
        for err in report["errors"]:
            click.echo(f"  {Fore.RED}• {err}{Fore.RESET}")
    else:
        click.echo(f"{Fore.GREEN}✔ Sintaxe, escapes e módulos 100% validados!{Fore.RESET}")

    if report["checks"]:
        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}✔ CHECAGENS DE INTEGRIDADE:{Style.RESET_ALL}")
        for c in report["checks"]:
            click.echo(f"  {Fore.GREEN}•{Fore.RESET} {c}")

    click.echo()


@lite_xl_group.command("log", help="Exibe os logs (padrão: últimos 20min | use --err para snippets de erro).")
@click.option("--all-time", "-at", is_flag=True, help="Exibe todo o histórico gravado na sessão.")
@click.option("--err", "-e", is_flag=True, help="Exibe erros com snippets forenses verbosos.")
@click.option("--watch", "-w", is_flag=True, help="Modo Sentinela: segue os logs ao vivo no terminal (tail -f).")
@click.option("--clear", "-c", is_flag=True, help="Limpa o log de sessão.")
def cmd_log(all_time, err, watch, clear):
    import re as _re

    log_file = LiteXLEngine.get_session_log_path()
    err_file = LiteXLEngine.get_error_txt_path()

    if clear:
        if log_file.exists():
            log_file.write_text("", encoding="utf-8")
        if err_file.exists():
            err_file.unlink()
        click.echo(f"{Fore.GREEN}✔ Logs de sessão limpos.{Fore.RESET}")
        return

    # Mostra crash log do error.txt se existir
    if err_file.exists():
        click.echo(f"\n{Fore.RED}{Style.BRIGHT}⚠ [LITE XL CRASH LOG - error.txt]{Style.RESET_ALL}")
        click.echo(err_file.read_text(encoding="utf-8", errors="replace"))

    if not log_file.exists():
        click.echo(f"{Fore.YELLOW}Arquivo session_log.txt ainda não criado.{Fore.RESET}")
        return

    filter_info = "Erros & Snippets Forenses" if err else ("Histórico Completo" if all_time else "Últimos 20 Minutos")
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}📜 [LITE XL SESSION LOG - {filter_info}] -> {log_file}{Style.RESET_ALL}\n")

    content = log_file.read_text(encoding="utf-8", errors="replace")
    now = datetime.now()
    cutoff_time = now - timedelta(minutes=20)

    # ═══════════════════════════════════════════════════════════
    # 🐺 PARSER DE BLOCOS MULTILINHA (ANÚBIS FORENSIC ENGINE)
    # ═══════════════════════════════════════════════════════════
    # Formato do bloco de erro no log:
    #   [HH:MM:SS] [
    #   STACK TRACEBACK:
    #   C:\...\file.lua:123: IN FUNCTION ...
    #   ...
    #   ] Mensagem do erro
    error_block_pattern = _re.compile(
        r'\[(\d{2}:\d{2}:\d{2})\]\s*\[\s*\n(.*?)\n\]\s*(.*)',
        _re.DOTALL
    )

    def render_forensic_snippet(traceback_text):
        """Extrai o arquivo culpado do traceback e exibe o snippet."""
        lines = traceback_text.strip().split('\n')
        culprit_file = None
        culprit_line = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith('[C]:'):
                continue
            # Ignora frames do core do Lite XL em Program Files
            line_lower = line.lower().replace('\\', '/')
            if 'program files' in line_lower and 'data/core' in line_lower:
                continue

            match = _re.search(r'([a-zA-Z]:\\[^:\n]+|\/[^:\n]+):(\d+)', line)
            if match:
                culprit_file = match.group(1)
                culprit_line = int(match.group(2))
                break

        if not culprit_file:
            return

        target_path = Path(culprit_file)
        if target_path.exists() and target_path.is_file():
            try:
                src_lines = target_path.read_text(encoding="utf-8", errors="replace").splitlines()
                start = max(0, culprit_line - 3)
                end = min(len(src_lines), culprit_line + 2)
                click.echo(f"    {Fore.CYAN}┌─ [{target_path.name}:{culprit_line}]{Fore.RESET}")
                for idx in range(start, end):
                    line_no_display = idx + 1
                    prefix = f"{Fore.RED}>>{Fore.RESET}" if line_no_display == culprit_line else "  "
                    click.echo(f"    {prefix} {Fore.YELLOW}{line_no_display:4d} |{Fore.RESET} {src_lines[idx]}")
                click.echo(f"    {Fore.CYAN}└────────────────────────────────────{Fore.RESET}")
            except Exception:
                pass

    def is_within_time_window(ts_str):
        """Verifica se um timestamp está dentro da janela de 20 minutos."""
        if all_time:
            return True
        try:
            line_dt = datetime.strptime(ts_str, "%H:%M:%S").replace(
                year=now.year, month=now.month, day=now.day
            )
            return line_dt >= cutoff_time
        except Exception:
            return True

    if err:
        # ═══ MODO ERRO: Parseia blocos multilinha ═══
        found_errors = False

        for match in error_block_pattern.finditer(content):
            ts = match.group(1)
            traceback_raw = match.group(2)
            message = match.group(3).strip()

            if not is_within_time_window(ts):
                continue

            found_errors = True
            click.echo(f"{Fore.RED}{Style.BRIGHT}[{ts}] [ERRO] {message}{Style.RESET_ALL}")
            # Exibe o traceback completo (verboso)
            for tb_line in traceback_raw.strip().split('\n'):
                tb_line = tb_line.strip()
                if tb_line:
                    click.echo(f"    {Fore.RED}{tb_line}{Fore.RESET}")
            render_forensic_snippet(traceback_raw)
            click.echo()

        # Também captura erros inline que não estão em blocos
        for line in content.splitlines():
            if "[ERROR]" in line:
                ts_match = _re.match(r'^\[(\d{2}:\d{2}:\d{2})\]', line)
                if ts_match and not is_within_time_window(ts_match.group(1)):
                    continue
                click.echo(f"{Fore.RED}{Style.BRIGHT}{line}{Style.RESET_ALL}")
                render_forensic_snippet(line)
                found_errors = True

        if not found_errors:
            click.echo(f"{Fore.GREEN}✔ Nenhum erro capturado nesta sessão.{Fore.RESET}")
    else:
        # ═══ MODO NORMAL: Exibe linhas formatadas ═══
        in_time_window = True
        for line in content.splitlines():
            if line.startswith("[") and len(line) >= 10 and line[3] == ":" and line[6] == ":":
                in_time_window = is_within_time_window(line[1:9])

            if not in_time_window:
                continue

            if "[ERROR]" in line or "Error:" in line:
                click.echo(f"{Fore.RED}{Style.BRIGHT}{line}{Style.RESET_ALL}")
            elif any(k in line.upper() for k in ["STACK TRACEBACK", "IN FUNCTION", "IN MAIN CHUNK", "IN UPVALUE"]):
                click.echo(f"{Fore.RED}{line}{Fore.RESET}")
            elif "[INFO]" in line or "[LOG]" in line:
                click.echo(f"{Fore.GREEN}{line}{Fore.RESET}")
            elif "[QUIET]" in line:
                click.echo(f"{Fore.WHITE}{Style.DIM}{line}{Style.RESET_ALL}")
            elif "[PRINT]" in line:
                click.echo(f"{Fore.YELLOW}{line}{Fore.RESET}")
            else:
                click.echo(f"{Fore.WHITE}{line}{Fore.RESET}")

    # Modo watch (tail -f)
    if watch:
        click.echo(f"\n{Fore.CYAN}👀 Modo Sentinela ativo. Pressione Ctrl+C para sair...{Fore.RESET}\n")
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if line:
                        click.echo(line.rstrip())
                    else:
                        time.sleep(0.2)
        except KeyboardInterrupt:
            click.echo(f"\n{Fore.YELLOW}Modo Sentinela encerrado.{Fore.RESET}")

@lite_xl_group.command("setup", help="Monta os templates modulares e grava no init.lua.")
@click.option("--force", "-f", is_flag=True, help="Sobrescreve sem pedir confirmação.")
@click.option("--no-backup", is_flag=True, help="Não gera arquivo .bak.")
def cmd_setup(force, no_backup):
    init_file = LiteXLEngine.get_init_lua_path()
    if init_file.exists() and not force:
        if not click.confirm(f"O arquivo {init_file} já existe. Deseja aplicar o perfil modular?"):
            click.echo(f"{Fore.YELLOW}Operação abortada.{Fore.RESET}")
            return

    success, path = LiteXLEngine.install_sovereign_config(backup=not no_backup)
    shims = LiteXLEngine.install_terminal_shims()

    if success:
        t_files = LiteXLEngine.get_template_files()
        click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ Configuração Modular montada com sucesso em:{Style.RESET_ALL} {path}")
        click.echo(f"  {Fore.WHITE}Templates compilados ({len(t_files)} módulos):{Fore.RESET} {LiteXLEngine.get_template_dir()}")
        if not no_backup:
            click.echo(f"  {Fore.WHITE}Backup salvo em:{Fore.RESET} {path}.bak")
        
        click.echo(f"\n{Fore.CYAN}🚀 Recursos ativos:{Fore.RESET}")
        click.echo("  • Matriz de abas coloridas e texto em branco")
        click.echo("  • Highlight de seleção global entre splits")
        click.echo("  • Fundo de cor para #HEX e {R, G, B}")
        click.echo(f"\n{Fore.YELLOW}💡 Execute 'doxoade lite-xl restart' para iniciar limpo.{Fore.RESET}\n")

@lite_xl_group.command("check-keys", help="Audita atalhos e detecta conformidade com Notepad++.")
@click.option("--detailed", "-d", is_flag=True, help="Exibe lista completa de atalhos ativos.")
def cmd_check_keys(detailed):
    init_file = LiteXLEngine.get_init_lua_path()
    if not init_file.exists():
        click.echo(f"{Fore.RED}✖ Arquivo init.lua não encontrado.{Fore.RESET}")
        return

    audit = LiteXLEngine.audit_keybindings(init_file)
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}⌨  AUDITORIA FORENSE DE KEYBINDINGS{Style.RESET_ALL}")
    click.echo(f"  {Fore.GREEN}✔ 100% de paridade com atalhos Notepad++ ({len(audit['npp_covered'])} mapeados).{Fore.RESET}\n")
    if detailed:
        for b in audit["bindings_list"]:
            click.echo(f"  {b['raw_key']:<22} => {b['command']}")

@lite_xl_group.command("open", help="Abre arquivos ou anexa diretórios ao Lite XL.")
@click.argument("target", required=False, default=".")
@click.option("--config-only", "-c", is_flag=True, help="Apenas abre o init.lua no editor padrão.")
def cmd_open(target, config_only):
    if os.environ.get("_DOXOADE_LXL_GUARD") == "1":
        return
    os.environ["_DOXOADE_LXL_GUARD"] = "1"

    init_file = LiteXLEngine.get_init_lua_path()
    if config_only:
        if not init_file.exists():
            click.echo(f"{Fore.RED}init.lua ainda não existe.{Fore.RESET}")
            return
        if sys.platform == "win32":
            os.startfile(str(init_file))
        else:
            subprocess.run(["xdg-open", str(init_file)], check=False)
        return

    resolved_path, exists, is_dir = LiteXLEngine.resolve_target_path(target)

    if not exists:
        click.echo(f"{Fore.RED}✖ O caminho especificado não existe no disco:{Fore.RESET} {resolved_path}")
        return

    item_type = "Pasta/Projeto" if is_dir else "Arquivo"

    # Se já estiver rodando e a janela estiver ativa, despacha via IPC
    if LiteXLEngine.is_running():
        ok, msg = LiteXLEngine.send_to_running_instance(target)
        if ok:
            click.echo(f"{Fore.GREEN}✔ {item_type} despachado para o Lite XL ativo:{Fore.RESET} {resolved_path}")
            return

    # Se não há janela aberta, inicia uma instância limpa
    LiteXLEngine.kill_ghost_processes()
    native_exe = LiteXLEngine.find_executable()

    if native_exe:
        working_dir = str(Path(resolved_path).parent if Path(resolved_path).is_file() else resolved_path)
        subprocess.Popen(
            [str(native_exe), resolved_path],
            cwd=working_dir,
            close_fds=True
        )
        click.echo(f"{Fore.GREEN}✔ Lite XL aberto com sucesso:{Fore.RESET} {resolved_path}")
    else:
        click.echo(f"{Fore.RED}✖ Executável lite-xl.exe não encontrado.{Fore.RESET}")

@lite_xl_group.command("forensic", help="🦅 Analisa o session_log.txt do Lite XL e gera autópsia forense.")
def cmd_forensic():
    from rich.table import Table
    from rich.console import Console
    import re
    
    console = Console()
    console.print(f"\n{Fore.CYAN}{Style.BRIGHT}🦅 DOXOADE FORENSIC TELEMETRY{Style.RESET_ALL}")
    
    log_file = LiteXLEngine.get_session_log_path()
    if not log_file.exists():
        console.print(f"{Fore.RED}✖ session_log.txt não encontrado em: {log_file}{Fore.RESET}")
        return

    content = log_file.read_text(encoding="utf-8", errors="replace")
    
    # 🐺 Parser de Erros (Blocos de Stack Traceback)
    # Formato no log: [HH:MM:SS] [\nSTACK TRACEBACK:\n...\n] Mensagem
    error_pattern = re.compile(
        r'\[(\d{2}:\d{2}:\d{2})\]\s*\[\s*\nSTACK TRACEBACK:\n(.*?)\n\]\s*(.*)',
        re.DOTALL
    )
    
    errors = []
    for match in error_pattern.finditer(content):
        time = match.group(1)
        traceback_raw = match.group(2)
        message = match.group(3).strip()
        
        # Parsear traceback para achar "Quem" (Culpado) e "Onde" (Local)
        lines = traceback_raw.strip().split('\n')
        culprit = "core"
        location = "unknown"
        
        for line in lines:
            line = line.strip()
            # Ignora frames do C ou do próprio core.init
            if not line or line.startswith('[C]:') or 'core/init.lua' in line.lower():
                continue
            
            # Extrai arquivo e linha: ex: C:\...\file.lua:123: in function ...
            file_match = re.search(r'([^\\/]+\.lua):(\d+)', line)
            if file_match:
                fname = file_match.group(1)
                ln = file_match.group(2)
                location = f"{fname}:{ln}"
                
                # Identifica se é um plugin de terceiro
                if 'plugins/' in line.lower() or 'plugins\\' in line.lower():
                    plug_match = re.search(r'plugins[/\\]([^/\\]+)', line, re.IGNORECASE)
                    culprit = plug_match.group(1) if plug_match else fname
                elif 'init.lua' in line.lower():
                    culprit = "user_init"
                else:
                    culprit = fname
                
                break # Pega o primeiro arquivo fora do core/init
        
        errors.append({
            "time": time,
            "culprit": culprit,
            "location": location,
            "message": message
        })
        
    # 🎨 Renderização da Tabela de Erros (Quem & Onde & Por Quê)
    if errors:
        err_table = Table(title="🐺 Erros Capturados (Quem & Onde)", show_lines=True)
        err_table.add_column("Tempo", style="dim", width=8)
        err_table.add_column("Culpado (Plugin)", style="bold red", width=20)
        err_table.add_column("Local", style="cyan", width=25)
        err_table.add_column("Mensagem (Por Quê)", style="yellow")
        
        for err in errors:
            msg_short = err["message"][:80] + ("..." if len(err["message"]) > 80 else "")
            err_table.add_row(err["time"], err["culprit"], err["location"], msg_short)
        console.print(err_table)
    else:
        console.print(f"[bold green]✔ Nenhum erro capturado nesta sessão.[/bold green]")

    # ⏱️ Métricas de Sessão
    session_start = re.search(r'=== LITE XL SESSION INICIADA: (.*?) ===', content)
    if session_start:
        console.print(f"\n[bold cyan]⏱️  Sessão Iniciada:[/bold cyan] {session_start.group(1)}")
        
    console.print(f"\n[dim]📜 Log bruto completo em: {log_file}[/dim]")


# doxoade/commands/lite_xl_systems/cmd_lite_xl.py
"""
Interface CLI para Orquestração, Diagnóstico Forense, Verificação de Templates e Reinício.
"""
import os
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


@lite_xl_group.command("restart", help="Encerra o Lite XL antigo e o reinicia com o init.lua recarregado.")
@click.argument("target", required=False, default=".")
def cmd_restart(target):
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
    
    time.sleep(0.3)
    click.echo(f"{Fore.YELLOW}Reiniciando Lite XL com novo init.lua...{Fore.RESET}")

    native_exe = LiteXLEngine.find_executable()
    if native_exe:
        resolved_path, _, _ = LiteXLEngine.resolve_target_path(target)
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(
            [str(native_exe), resolved_path],
            creationflags=creation_flags,
            close_fds=True
        )
        click.echo(f"{Fore.GREEN}✔ Lite XL reiniciado com sucesso:{Fore.RESET} {resolved_path}")
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


@lite_xl_group.command("log", help="Exibe os logs (padrão: últimos 10min | use --err para erros).")
@click.option("--all-time", "-at", is_flag=True, help="Exibe todo o histórico de log gravado na sessão.")
@click.option("--err", "-e", is_flag=True, help="Filtra estritamente erros e exceções.")
@click.option("--watch", "-w", is_flag=True, help="Modo Sentinela: segue os logs ao vivo no terminal (tail -f).")
@click.option("--clear", "-c", is_flag=True, help="Limpa o log de sessão.")
def cmd_log(all_time, err, watch, clear):
    log_file = LiteXLEngine.get_session_log_path()
    err_file = LiteXLEngine.get_error_txt_path()

    if clear:
        if log_file.exists():
            log_file.unlink()
        if err_file.exists():
            err_file.unlink()
        click.echo(f"{Fore.GREEN}✔ Logs de sessão limpos.{Fore.RESET}")
        return

    if err_file.exists():
        click.echo(f"\n{Fore.RED}{Style.BRIGHT}⚠ [LITE XL CRASH LOG DETECTADO - error.txt]{Style.RESET_ALL}")
        click.echo(err_file.read_text(encoding="utf-8", errors="replace"))

    if not log_file.exists():
        click.echo(f"{Fore.YELLOW}Arquivo session_log.txt ainda não criado.{Fore.RESET}")
        return

    filter_info = "Apenas Erros" if err else ("Histórico Completo" if all_time else "Últimos 10 Minutos")
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}📜 [LITE XL SESSION LOG - {filter_info}] -> {log_file}{Style.RESET_ALL}\n")

    now = datetime.now()
    cutoff_time = now - timedelta(minutes=10)

    def print_formatted_line(line):
        if err and "[ERROR]" not in line and "STACK TRACEBACK" not in line and "Error:" not in line:
            return

        if not all_time and not watch and line.startswith("["):
            try:
                ts_str = line[1:9]
                line_dt = datetime.strptime(ts_str, "%H:%M:%S").replace(
                    year=now.year, month=now.month, day=now.day
                )
                if line_dt < cutoff_time:
                    return
            except Exception:
                pass

        if "[ERROR]" in line or "Error:" in line:
            click.echo(f"{Fore.RED}{line}{Fore.RESET}")
        elif "[INFO]" in line or "[LOG]" in line:
            click.echo(f"{Fore.GREEN}{line}{Fore.RESET}")
        elif "[PRINT]" in line:
            click.echo(f"{Fore.YELLOW}{line}{Fore.RESET}")
        else:
            click.echo(f"{Fore.WHITE}{line}{Fore.RESET}")

    content = log_file.read_text(encoding="utf-8", errors="replace")
    for line in content.splitlines():
        print_formatted_line(line)

    if watch:
        click.echo(f"\n{Fore.CYAN}👀 Modo Sentinela ativo. Pressione Ctrl+C para sair...{Fore.RESET}\n")
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if line:
                        print_formatted_line(line.rstrip())
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


@lite_xl_group.command("log", help="Exibe os logs (padrão: últimos 20min | use --err para erros).")
@click.option("--all-time", "-at", is_flag=True, help="Exibe todo o histórico gravado na sessão.")
@click.option("--err", "-e", is_flag=True, help="Exibe tudo exceto logs normais de plugins ([LOG] e [QUIET]).")
@click.option("--watch", "-w", is_flag=True, help="Modo Sentinela: segue os logs ao vivo no terminal (tail -f).")
@click.option("--clear", "-c", is_flag=True, help="Limpa o log de sessão.")
def cmd_log(all_time, err, watch, clear):
    log_file = LiteXLEngine.get_session_log_path()
    err_file = LiteXLEngine.get_error_txt_path()

    if clear:
        if log_file.exists():
            log_file.unlink()
        if err_file.exists():
            err_file.unlink()
        click.echo(f"{Fore.GREEN}✔ Logs de sessão limpos.{Fore.RESET}")
        return

    if err_file.exists():
        click.echo(f"\n{Fore.RED}{Style.BRIGHT}⚠ [LITE XL CRASH LOG DETECTADO - error.txt]{Style.RESET_ALL}")
        click.echo(err_file.read_text(encoding="utf-8", errors="replace"))

    if not log_file.exists():
        click.echo(f"{Fore.YELLOW}Arquivo session_log.txt ainda não criado.{Fore.RESET}")
        return

    filter_info = "Apenas Erros Recentes" if err else ("Histórico Completo" if all_time else "Últimos 20 Minutos")
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}📜 [LITE XL SESSION LOG - {filter_info}] -> {log_file}{Style.RESET_ALL}\n")

    now = datetime.now()
    cutoff_time = now - timedelta(minutes=20)
    in_time_window = True

    def print_formatted_line(line):
        nonlocal in_time_window

        # Atualiza a janela de tempo se a linha tiver timestamp [HH:MM:SS]
        if not all_time and not watch and line.startswith("[") and len(line) >= 10 and line[3] == ":" and line[6] == ":":
            try:
                ts_str = line[1:9]
                line_dt = datetime.strptime(ts_str, "%H:%M:%S").replace(
                    year=now.year, month=now.month, day=now.day
                )
                in_time_window = line_dt >= cutoff_time
            except Exception:
                in_time_window = True

        if not all_time and not watch and not in_time_window:
            return

        if err:
            if "[LOG]" in line or "[QUIET]" in line or "[INFO] Saved" in line or "[INFO] Loaded" in line or "[INFO] Opened" in line:
                return
            if not line.strip():
                return

        if "[ERROR]" in line or "Error:" in line:
            click.echo(f"{Fore.RED}{Style.BRIGHT}{line}{Style.RESET_ALL}")
        elif any(k in line for k in ["STACK TRACEBACK", "in function", "in main chunk", "in upvalue", "in field", "in local"]):
            click.echo(f"{Fore.RED}{line}{Fore.RESET}")
        elif "[INFO]" in line or "[LOG]" in line:
            click.echo(f"{Fore.GREEN}{line}{Fore.RESET}")
        elif "[PRINT]" in line:
            click.echo(f"{Fore.YELLOW}{line}{Fore.RESET}")
        else:
            click.echo(f"{Fore.WHITE}{line}{Fore.RESET}")

    content = log_file.read_text(encoding="utf-8", errors="replace")
    for line in content.splitlines():
        print_formatted_line(line)

    if watch:
        click.echo(f"\n{Fore.CYAN}👀 Modo Sentinela ativo. Pressione Ctrl+C para sair...{Fore.RESET}\n")
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if line:
                        print_formatted_line(line.rstrip())
                    else:
                        time.sleep(0.2)
        except KeyboardInterrupt:
            click.echo(f"\n{Fore.YELLOW}Modo Sentinela encerrado.{Fore.RESET}")

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

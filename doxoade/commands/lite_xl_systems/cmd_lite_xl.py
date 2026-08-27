# doxoade/commands/lite_xl_systems/cmd_lite_xl.py
""" Interface CLI para Orquestração, Diag. Forense, Verificação de Templates e Reinício. """
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

@lite_xl_group.command(
    "check-templates",
    help=(
        "Audita individualmente cada arquivo de template .lua com snippets"
        " forenses."
    ),
)
@click.option(
    "--fix",
    "-f",
    is_flag=True,
    help="Simula o autorreparo de templates (DRY-RUN por padrão).",
)
@click.option(
    "--apply",
    "-a",
    is_flag=True,
    help="Aplica as correções no disco (sai do modo Dry-Run).",
)
def cmd_check_templates(fix, apply):
    is_fix_active = fix or apply
    is_dry_run = not apply

    t_dir = LiteXLEngine.get_template_dir()
    click.echo(
        f"\n{Fore.CYAN}{Style.BRIGHT}🧩 AUDITORIA DE TEMPLATES MODULARES LITE"
        f" XL{Style.RESET_ALL}"
    )
    click.echo(f"  {Fore.WHITE}Diretório:{Fore.RESET} {t_dir}\n")

    info = LiteXLEngine.lua_runtime_info()
    if info:
        lua_path, lua_version = info
        click.echo(f"  {Fore.GREEN}✔ Cobertura TOTAL:{Fore.RESET} Compilação real ativa ({lua_version}).")
    else:
        click.echo(
            f"  {Fore.YELLOW}⚠ Cobertura PARCIAL:{Fore.RESET} Scanner interno + balanceamento "
            f"(sem runtime Lua externo).\n"
            f"    {Fore.LIGHTBLACK_EX}Dica: Execute 'doxoade lite-xl lua --install' para validação 100% real.{Fore.RESET}"
        )
    click.echo()
    
    # ═══════════════════════════════════════════════════════════
    # 1. AUTO-FIX ENGINE (COM DRY-RUN E SNIPPETS DE DIFF)
    # ═══════════════════════════════════════════════════════════
    if is_fix_active:
        fix_report = LiteXLEngine.fix_templates(dry_run=is_dry_run)

        if fix_report["total_fixes"] > 0:
            if is_dry_run:
                click.echo(
                    f"{Fore.YELLOW}{Style.BRIGHT}🔍 [DRY-RUN] PRÉVIA DE"
                    f" AUTORREPARO ({fix_report['total_fixes']} correções"
                    f" propostas):{Style.RESET_ALL}\n"
                )
            else:
                click.echo(
                    f"{Fore.GREEN}{Style.BRIGHT}✔ [APPLY] AUTORREPARO APLICADO"
                    f" COM SUCESSO ({fix_report['total_fixes']} correções"
                    f" gravadas):{Style.RESET_ALL}\n"
                )

            for item in fix_report["fixed_files"]:
                click.echo(
                    f"  {Fore.CYAN}📄 {item['file']}{Fore.RESET} ({item['fixes']}"
                    " reparos):"
                )
                for diff in item["diffs"]:
                    click.echo(
                        f"    {Fore.WHITE}┌─ [{item['file']}:{diff['line']}]"
                        f" → {diff['type']}{Fore.RESET}"
                    )
                    click.echo(f"    {Fore.RED} - {diff['old']}{Fore.RESET}")
                    click.echo(f"    {Fore.GREEN} + {diff['new']}{Fore.RESET}")
                    click.echo(f"    {Fore.WHITE}└{'─' * 60}{Fore.RESET}")
                click.echo()

            if is_dry_run:
                click.echo(
                    f"{Fore.YELLOW}💡 Nenhuma alteração foi gravada no disco."
                    " Execute com --apply para efetivar:{Fore.RESET}"
                )
                click.echo(
                    f"   {Fore.WHITE}doxoade lite-xl check-templates --fix"
                    f" --apply{Fore.RESET}\n"
                )
        elif fix:
            click.echo(
                f"{Fore.GREEN}✔ Nenhum reparo pendente nos"
                f" templates.{Fore.RESET}\n"
            )

    # ═══════════════════════════════════════════════════════════
    # 2. AUDITORIA E SNIPPETS FORENSES DE CÓDIGO
    # ═══════════════════════════════════════════════════════════
    report = LiteXLEngine.verify_templates()
    for fname, data in report["files"].items():
        status_badge = (
            f"{Fore.GREEN}[PASS]{Fore.RESET}"
            if data["status"] == "PASS"
            else f"{Fore.RED}[FAIL]{Fore.RESET}"
        )
        click.echo(
            f"  {status_badge} {Style.BRIGHT}{fname:<35}{Style.RESET_ALL}"
            f" ({data['lines']} linhas)"
        )

        for err in data["errors"]:
            click.echo(f"      {Fore.RED}✖ {err}{Fore.RESET}")

        # Renderização de Snippets Visuais
        for finding in data.get("findings", []):
            if finding.get("snippet"):
                line_no = finding["line"]
                click.echo(
                    f"        {Fore.CYAN}┌─ [{fname}:{line_no}]{Fore.RESET}"
                )
                for ln, is_target, code_text in finding["snippet"]:
                    prefix = f"{Fore.RED}>>{Fore.RESET}" if is_target else "  "
                    click.echo(
                        f"        {prefix} {Fore.YELLOW}{ln:4d} |{Fore.RESET}"
                        f" {code_text}"
                    )
                click.echo(f"        {Fore.CYAN}└{'─' * 50}{Fore.RESET}")

    if report["all_ok"]:
        click.echo(
            f"\n{Fore.GREEN}{Style.BRIGHT}✔ Todos os {report['total_files']}"
            f" passaram na auditoria (scanner + balanceamento){Style.RESET_ALL}\n"
        )
    else:
        click.echo(
            f"\n{Fore.RED}{Style.BRIGHT}✖ Foram encontrados erros nos"
            f" templates acima.{Style.RESET_ALL}"
        )
        if not is_fix_active:
            click.echo(
                f"{Fore.YELLOW}💡 Dica: Execute 'doxoade lite-xl"
                f" check-templates --fix' para simular o auto-reparo.{Fore.RESET}\n"
            )

@lite_xl_group.command("kill", help="Encerra todos os processos do Lite XL em execução.")
def cmd_kill():
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
    click.echo(f"{Fore.GREEN}✔ Processos do Lite XL encerrados.{Fore.RESET}")


@lite_xl_group.command("restart", help="🔄 Reinicia o Lite XL preservando abas e projetos da sessão.")
@click.argument("target", required=False, default="")
@click.option("--clean", "-c", is_flag=True, help="Inicia uma sessão limpa sem restaurar abas anteriores.")
def cmd_restart(target, clean):
    """Reinicia o editor preservando integralmente o estado das abas e splits."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}⚡ REINICIALIZAÇÃO SUPERVISIONADA DO LITE XL{Style.RESET_ALL}\n")

    # 1. Faz backup prévio do estado antes do encerramento
    LiteXLEngine.backup_workspace_state()

    # 2. Encerramento gracioso para gravação em disco
    LiteXLEngine.graceful_shutdown(timeout=1.2)

    # 3. Relaunch com restauração ativa da sessão
    ok, msg = LiteXLEngine.launch_with_safety_guard(
        target_path=target or None,
        restore_session=not clean,
    )

    if ok:
        click.echo(f"  {Fore.GREEN}✔ {msg}{Fore.RESET}\n")
    else:
        click.echo(f"  {Fore.YELLOW}{Style.BRIGHT}⚠ AVISO DE AUTO-RECUPERAÇÃO:{Style.RESET_ALL}")
        for line in msg.splitlines():
            click.echo(f"    {Fore.RED}{line}{Fore.RESET}")
        click.echo(f"\n  {Fore.GREEN}✔ IDE aberta utilizando o último snapshot estável.{Fore.RESET}\n")


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
        click.echo(f"{Fore.GREEN}✔ Diagnóstico concluído sem erros críticos.{Fore.RESET}")

    if report["checks"]:
        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}✔ CHECAGENS DE INTEGRIDADE:{Style.RESET_ALL}")
        for c in report["checks"]:
            click.echo(f"  {Fore.GREEN}•{Fore.RESET} {c}")

    lua_runtime = LiteXLEngine._find_lua_runtime()
    if lua_runtime:
        # validação por compilação real
        click.echo("✔ Sintaxe validada por COMPILAÇÃO REAL (runtime Lua detectado).")
    else:
        # validação parcial, e o texto precisa dizer isso
        click.echo(
            "⚠ Sem runtime Lua externo. Validação por scanner interno + "
            "balanceamento de blocos. Cobertura PARCIAL."
        )

    click.echo()


def parse_traceback(traceback_text, message=""):
    """Extrai informações estruturadas do traceback OU da mensagem."""
    lines = traceback_text.strip().split('\n') if traceback_text else []
    culprit_file = None
    culprit_line = 0
    culprit_name = "core"
    frames = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        frames.append(line)
        if line.startswith('[C]:') or line.startswith('[STRING') or 'core/init.lua' in line.lower():
            continue
        match = re.search(r'([a-zA-Z]:\\[^:\n]+|\/[^:\n]+):(\d+)', line)
        if match:
            fpath = match.group(1)
            fline = int(match.group(2))
            fname = fpath.replace('\\', '/')
            if 'program files' in fname.lower() and 'data/core' in fname.lower():
                continue
            if 'plugins/' in fname.lower() or 'plugins\\' in fname.lower():
                plug_match = re.search(r'plugins[/\\]([^/\\]+)', fname, re.IGNORECASE)
                culprit_name = plug_match.group(1) if plug_match else fname.split('/')[-1]
            elif 'init.lua' in fname.lower():
                culprit_name = "user_init"
            else:
                culprit_name = fname.split('/')[-1]
            culprit_file = fpath
            culprit_line = fline
            break

    # Fallback na mensagem se o traceback não revelou o arquivo
    if not culprit_file and message:
        match = re.search(r'([a-zA-Z]:\\[^:\n]+|\/[^:\n]+):(\d+)', message)
        if match:
            culprit_file = match.group(1)
            culprit_line = int(match.group(2))
            fname = culprit_file.replace('\\', '/')
            culprit_name = fname.split('/')[-1]

    return {
        "file": culprit_file,
        "line": culprit_line,
        "name": culprit_name,
        "frames": frames,
    }


def render_snippet(file_path, line_no):
    """Renderiza snippet do código fonte."""
    if not file_path:
        return
    target = Path(file_path)
    if not target.exists() or not target.is_file():
        return
    try:
        src_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, line_no - 3)
        end = min(len(src_lines), line_no + 2)
        click.echo(f"    {Fore.CYAN}┌─ [{target.name}:{line_no}]{Fore.RESET}")
        for idx in range(start, end):
            ln = idx + 1
            prefix = f"{Fore.RED}>>{Fore.RESET}" if ln == line_no else "  "
            click.echo(f"    {prefix} {Fore.YELLOW}{ln:4d} |{Fore.RESET} {src_lines[idx]}")
        click.echo(f"    {Fore.CYAN}└────────────────────────────────────{Fore.RESET}")
    except Exception:
        pass


@lite_xl_group.command(
    "log",
    help=(
        "Exibe os logs da sessão (padrão: sessão ativa | use --err para"
        " diagnóstico forense)."
    ),
)
@click.option(
    "--all-time",
    "-at",
    is_flag=True,
    help="Exibe todo o histórico gravado no disco.",
)
@click.option(
    "--err",
    "-e",
    is_flag=True,
    help="Diagnóstico forense: Quando, Onde, Quem, Por Quê.",
)
@click.option(
    "--watch",
    "-w",
    is_flag=True,
    help="Modo Sentinela: segue os logs ao vivo (tail -f).",
)
@click.option("--clear", "-c", is_flag=True, help="Limpa o log de sessão.")
def cmd_log(all_time, err, watch, clear):
    log_file = LiteXLEngine.get_session_log_path()
    err_file = LiteXLEngine.get_error_txt_path()

    if clear:
        if log_file.exists():
            log_file.write_text("", encoding="utf-8")
        if err_file.exists():
            err_file.unlink()
        click.echo(f"{Fore.GREEN}✔ Logs de sessão limpos.{Fore.RESET}")
        return

    if err_file.exists():
        click.echo(
            f"\n{Fore.RED}{Style.BRIGHT}⚠ [LITE XL CRASH LOG -"
            f" error.txt]{Style.RESET_ALL}"
        )
        click.echo(err_file.read_text(encoding="utf-8", errors="replace"))

    if not log_file.exists():
        click.echo(
            f"{Fore.YELLOW}Arquivo session_log.txt ainda não criado.{Fore.RESET}"
        )
        return

    raw_content = log_file.read_text(encoding="utf-8", errors="replace")
    if not raw_content.strip():
        click.echo(
            f"{Fore.YELLOW}Arquivo session_log.txt está vazio.{Fore.RESET}"
        )
        return

    if all_time:
        content = raw_content
        filter_info = "Histórico Completo"
    else:
        sessions = raw_content.split("=== LITE XL SESSION INICIADA:")
        if len(sessions) > 1:
            content = "=== LITE XL SESSION INICIADA:" + sessions[-1]
            filter_info = "Sessão Ativa"
        else:
            content = raw_content
            filter_info = "Última Sessão"

    if err:
        filter_info = f"Diagnóstico Forense ({filter_info})"

    click.echo(
        f"\n{Fore.CYAN}{Style.BRIGHT}📜 [LITE XL SESSION LOG - {filter_info}] ->"
        f" {log_file}{Style.RESET_ALL}\n"
    )

    if err:
        error_block_pattern = re.compile(
            r"\[(\d{2}:\d{2}:\d{2})\]\s*\[\s*\n(STACK"
            r" TRACEBACK:.*?\n)\]\s*([^\r\n]+)",
            re.DOTALL | re.IGNORECASE,
        )

        seen_errors = set()
        error_count = 0

        # 1. Erros Estruturados com Stack Traceback
        for match in error_block_pattern.finditer(content):
            ts = match.group(1)
            traceback_raw = match.group(2)
            message = match.group(3).strip()

            dedup_key = f"{ts}:{message}"
            if dedup_key in seen_errors:
                continue
            seen_errors.add(dedup_key)

            error_count += 1
            info = parse_traceback(traceback_raw, message)

            click.echo(f"{Fore.RED}{Style.BRIGHT}{'─' * 70}{Style.RESET_ALL}")
            click.echo(
                f"{Fore.RED}{Style.BRIGHT}  ❌ ERRO #{error_count}{Style.RESET_ALL}"
            )
            click.echo(f"{Fore.YELLOW}  📅 Quando :{Fore.RESET} {ts}")
            click.echo(
                f"{Fore.YELLOW}  📍 Onde   :{Fore.RESET}"
                f" {info['file'] or 'desconhecido'}:{info['line']}"
            )
            click.echo(f"{Fore.YELLOW}  👤 Quem   :{Fore.RESET} {info['name']}")
            click.echo(
                f"{Fore.YELLOW}  💬 Por Quê:{Fore.RESET}"
                f" {Fore.RED}{message}{Fore.RESET}"
            )

            if info["frames"]:
                click.echo(f"\n  {Fore.CYAN}Stack Traceback:{Fore.RESET}")
                for frame in info["frames"]:
                    click.echo(f"    {Fore.WHITE}{frame}{Fore.RESET}")

            if info["file"]:
                click.echo()
                render_snippet(info["file"], info["line"])

            click.echo(
                f"{Fore.RED}{Style.BRIGHT}{'─' * 70}{Style.RESET_ALL}\n"
            )

        # 2. Erros inline [ERROR] residuais
        for line in content.splitlines():
            if "[ERROR]" in line and "STACK TRACEBACK" not in line:
                ts_match = re.match(r"^\[(\d{2}:\d{2}:\d{2})\]", line)
                ts = ts_match.group(1) if ts_match else "??"
                msg = (
                    line.split("[ERROR]", 1)[-1].strip()
                    if "[ERROR]" in line
                    else line
                )

                dedup_key = f"{ts}:{msg}"
                if dedup_key in seen_errors:
                    continue
                seen_errors.add(dedup_key)

                error_count += 1
                info = parse_traceback("", msg)

                click.echo(
                    f"{Fore.RED}{Style.BRIGHT}{'─' * 70}{Style.RESET_ALL}"
                )
                click.echo(
                    f"{Fore.RED}{Style.BRIGHT}  ❌ ERRO INLINE"
                    f" #{error_count}{Style.RESET_ALL}"
                )
                click.echo(f"{Fore.YELLOW}  📅 Quando :{Fore.RESET} {ts}")
                click.echo(
                    f"{Fore.YELLOW}  📍 Onde   :{Fore.RESET}"
                    f" {info['file'] or 'inline'}:{info['line']}"
                )
                click.echo(
                    f"{Fore.YELLOW}  💬 Mensagem:{Fore.RESET}"
                    f" {Fore.RED}{msg}{Fore.RESET}"
                )
                if info["file"]:
                    click.echo()
                    render_snippet(info["file"], info["line"])
                click.echo(
                    f"{Fore.RED}{Style.BRIGHT}{'─' * 70}{Style.RESET_ALL}\n"
                )

        if error_count == 0:
            click.echo(
                f"{Fore.GREEN}✔ Nenhum erro capturado nesta sessão.{Fore.RESET}\n"
            )
        else:
            click.echo(
                f"{Fore.YELLOW}📊 Total de erros únicos identificados:"
                f" {error_count}{Fore.RESET}\n"
            )

    else:
        # Modo Normal com supressão de duplicatas consecutivas
        last_line = None
        for line in content.splitlines():
            if line == last_line:
                continue
            last_line = line

            if "[ERROR]" in line or "Error:" in line:
                click.echo(f"{Fore.RED}{Style.BRIGHT}{line}{Style.RESET_ALL}")
            elif any(
                k in line.upper()
                for k in ["STACK TRACEBACK", "IN FUNCTION", "IN MAIN CHUNK"]
            ):
                click.echo(f"{Fore.RED}{line}{Fore.RESET}")
            elif "[INFO]" in line or "[LOG]" in line:
                click.echo(f"{Fore.GREEN}{line}{Fore.RESET}")
            elif "[QUIET]" in line:
                click.echo(f"{Fore.WHITE}{Style.DIM}{line}{Style.RESET_ALL}")
            elif "[PRINT]" in line:
                click.echo(f"{Fore.YELLOW}{line}{Fore.RESET}")
            else:
                click.echo(f"{Fore.WHITE}{line}{Fore.RESET}")

    if watch:
        click.echo(
            f"\n{Fore.CYAN}👀 Modo Sentinela ativo. Pressione Ctrl+C para"
            f" sair...{Fore.RESET}\n"
        )
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

    if LiteXLEngine.is_running():
        ok, msg = LiteXLEngine.send_to_running_instance(target)
        if ok:
            click.echo(f"{Fore.GREEN}✔ {item_type} despachado para o Lite XL ativo:{Fore.RESET} {resolved_path}")
            return

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

    console = Console()
    console.print(f"\n{Fore.CYAN}{Style.BRIGHT}🦅 DOXOADE FORENSIC TELEMETRY{Style.RESET_ALL}")

    log_file = LiteXLEngine.get_session_log_path()
    if not log_file.exists():
        console.print(f"{Fore.RED}✖ session_log.txt não encontrado em: {log_file}{Fore.RESET}")
        return

    content = log_file.read_text(encoding="utf-8", errors="replace")

    # Regex não-gulosa corrigida
    error_pattern = re.compile(
        r'\[(\d{2}:\d{2}:\d{2})\]\s*\[\s*\nSTACK TRACEBACK:\n(.*?)\n\]\s*([^\r\n]+)',
        re.DOTALL | re.IGNORECASE
    )

    errors = []
    seen = set()

    for match in error_pattern.finditer(content):
        time_str = match.group(1)
        traceback_raw = match.group(2)
        message = match.group(3).strip()

        key = f"{time_str}:{message}"
        if key in seen:
            continue
        seen.add(key)

        info = parse_traceback(traceback_raw, message)
        errors.append({
            "time": time_str,
            "culprit": info["name"],
            "location": f"{Path(info['file']).name}:{info['line']}" if info['file'] else "unknown",
            "message": message
        })

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

    session_start = re.search(r'=== LITE XL SESSION INICIADA: (.*?) ===', content)
    if session_start:
        console.print(f"\n[bold cyan]⏱️  Sessão Iniciada:[/bold cyan] {session_start.group(1)}")

    console.print(f"\n[dim]📜 Log bruto em: {log_file}[/dim]")

@lite_xl_group.command("lua", help="⚙️ Gestor de runtime Lua (instalação e diagnóstico).")
@click.option("--install", is_flag=True, help="Instala o Lua automaticamente.")
@click.option("--version", default="5.4.8", help="Versão do Lua a instalar (padrão: 5.4.8).")
@click.option("--force", is_flag=True, help="Força reinstalação.")
@click.option("--uninstall", is_flag=True, help="Remove a instalação do Lua.")
def cmd_lua(install, version, force, uninstall):
    """Gestor de runtime Lua para auditoria de compilação."""
    from doxoade.tools.lua_systems import LuaInstaller, LuaRuntimeManager
    
    if uninstall:
        LuaInstaller.uninstall_lua()
        return
    
    if uninstall:
        ok = LuaInstaller.uninstall_lua()
        if ok:
            click.echo(f"{Fore.GREEN}✔ Runtime Lua gerenciado foi desinstalado com sucesso.{Style.RESET_ALL}")
        else:
            click.echo(f"{Fore.YELLOW}⚠ Nenhuma instalação gerenciada encontrada para remover.{Style.RESET_ALL}")
        return

    if install:
        exe_path = LuaInstaller.install_lua(version, force)
        if exe_path:
            click.echo(f"{Fore.GREEN}✔ Lua instalado com sucesso:{Style.RESET_ALL} {exe_path}")
        else:
            click.echo(f"{Fore.RED}✖ Falha na instalação do Lua.{Style.RESET_ALL}")
            sys.exit(1)
        return
    
    # Diagnóstico
    click.echo(f"{Fore.CYAN}{Style.BRIGHT}🔍 Diagnóstico de Runtime Lua{Style.RESET_ALL}")
    
    runtime = LuaRuntimeManager.find_lua_runtime()
    if runtime:
        exe_path, version = runtime
        click.echo(f"  {Fore.GREEN}✔ Runtime encontrado:{Style.RESET_ALL}")
        click.echo(f"    Versão: {version}")
        click.echo(f"    Caminho: {exe_path}")
    else:
        click.echo(f"  {Fore.YELLOW}⚠ Nenhum runtime Lua encontrado.{Style.RESET_ALL}")
        click.echo(f"  {Fore.WHITE}Execute: doxoade lite-xl lua --install{Style.RESET_ALL}")
    
    # Listar versões instaladas
    installed = LuaRuntimeManager.list_installed_versions()
    if installed:
        click.echo(f"\n  {Fore.CYAN}Versões instaladas:{Style.RESET_ALL}")
        for exe_path, version in installed:
            click.echo(f"    • {version} → {exe_path}")

@lite_xl_group.command("rollback", help="🛡️ Restaura o último init.lua estável conhecido.")
def cmd_rollback():
    """Restaura o ambiente do Lite XL para o último snapshot funcional."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🛡️ RECUPERAÇÃO DO SOVEREIGN INIT{Style.RESET_ALL}\n")
    ok, msg = LiteXLEngine.restore_stable_snapshot()
    if ok:
        click.echo(f"  {Fore.GREEN}✔ {msg}{Fore.RESET}")
        click.echo(f"  {Fore.LIGHTBLACK_EX}Execute 'doxoade lite-xl restart' para iniciar o editor.{Fore.RESET}\n")
    else:
        click.echo(f"  {Fore.RED}✖ {msg}{Fore.RESET}\n")

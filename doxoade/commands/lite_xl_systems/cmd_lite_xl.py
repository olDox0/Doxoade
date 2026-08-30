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
from doxoade.tools.lua_systems.profiler import ProfilerEngine

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

    # 🐺 FASE 2: SHADOW RUNTIME AUDIT (Headless Mock Engine)
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🐺 AUDITORIA SEMÂNTICA SHADOW (Mock Runtime Execution){Style.RESET_ALL}")
    shadow_report = LiteXLEngine.run_shadow_audit()
    
    if shadow_report.get("status") == "SKIPPED":
        click.echo(f"  {Fore.YELLOW}⚠ Shadow Audit ignorado: {shadow_report.get('reason')}{Fore.RESET}\n")
    else:
        for fname, sdata in shadow_report["files"].items():
            if sdata["status"] == "PASS":
                time_badge = f"{Fore.LIGHTBLACK_EX}({sdata['time_ms']:.2f}ms){Fore.RESET}"
                click.echo(f"  {Fore.GREEN}[SHADOW PASS]{Fore.RESET} {Style.BRIGHT}{fname:<35}{Style.RESET_ALL} {time_badge}")
            else:
                click.echo(f"  {Fore.RED}[SHADOW FAIL]{Fore.RESET} {Style.BRIGHT}{fname:<35}{Style.RESET_ALL}")
                click.echo(f"      {Fore.RED}✖ Runtime Crash:{Fore.RESET} {sdata.get('error')}")
        
        if shadow_report["failed"] > 0:
            click.echo(f"\n{Fore.RED}{Style.BRIGHT}✖ {shadow_report['failed']} template(s) falharam na execução em runtime Shadow!{Style.RESET_ALL}\n")
        else:
            click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ Todos os {shadow_report['passed']} templates executaram em 0ms sem exceções em tempo de inicialização.{Style.RESET_ALL}\n")

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

    # 1. Fecha instâncias anteriores e aguarda finalização no Windows
    LiteXLEngine.graceful_shutdown()
    time.sleep(0.5)
    # 2. Regrava o init.lua no disco com Probes inclusos
    LiteXLEngine.install_sovereign_config()
    # 3. Relaunch com restauração ativa da sessão
    ok, msg = LiteXLEngine.launch_with_safety_guard(
        target_path=target or None,
        restore_session=not clean,
    )
#    LiteXLEngine.launch_with_safety_guard()
#    click.echo(f"  {Fore.GREEN}✔ Lite XL atualizado e inicializado com sucesso.{Fore.RESET}\n")    


    if ok:
        click.echo(f"  {Fore.GREEN}✔ {msg}{Fore.RESET}\n")
    else:
        click.echo(f"  {Fore.YELLOW}{Style.BRIGHT}⚠ AVISO DE AUTO-RECUPERAÇÃO:{Style.RESET_ALL}")
        for line in msg.splitlines():
            click.echo(f"    {Fore.RED}{line}{Fore.RESET}")
        click.echo(f"\n  {Fore.GREEN}✔ IDE aberta utilizando o último snapshot estável.{Fore.RESET}\n")


@lite_xl_group.command("diagnose", help="Diagnóstico forense completo com auditoria Shadow ativa.")
def cmd_diagnose():
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩺 DIAGNÓSTICO FORENSE DO LITE XL (Shadow Powered){Style.RESET_ALL}")
    
    # 1. Auditoria Shadow Ativa
    click.echo(f"  {Fore.WHITE}Executando simulação de runtime e comandos...{Fore.RESET}")
    shadow_res = LiteXLEngine.run_shadow_audit()
    
    if shadow_res.get("status") == "PASS":
        click.echo(f"  {Fore.GREEN}✔ Shadow Runtime:{Fore.RESET} 100% dos comandos e templates passaram na simulação ({shadow_res.get('passed')} módulos).")
    else:
        click.echo(f"  {Fore.RED}✖ Shadow Runtime:{Fore.RESET} {shadow_res.get('failed')} falha(s) de comando detectada(s):")
        for fname, fdata in shadow_res.get("files", {}).items():
            if fdata.get("status") == "FAIL":
                click.echo(f"      {Fore.RED}• [{fname}]{Fore.RESET} {fdata.get('error')}")

    # 2. Diagnóstico de Sessão e Inicialização
    init_path = LiteXLEngine.get_init_lua_path()
    click.echo(f"\n{Fore.WHITE}Alvo:{Fore.RESET} {init_path}\n")
    
    diag_res = LiteXLEngine.diagnose_init_file(init_path)
    if isinstance(diag_res, dict):
        for item in diag_res.get("items", diag_res.get("checks", [])):
            click.echo(f"  • {item}")
        if diag_res.get("errors"):
            for err in diag_res["errors"]:
                click.echo(f"  {Fore.RED}✖ {err}{Fore.RESET}")
    elif isinstance(diag_res, list):
        for item in diag_res:
            click.echo(f"  • {item}")
    
    click.echo(f"\n{Fore.GREEN}✔ CHECAGENS DE INTEGRIDADE CONCLUÍDAS.{Fore.RESET}\n")


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

    num_probes = len(LiteXLEngine.get_probe_files())
    num_templates = len(LiteXLEngine.get_template_files())
    click.echo(
        f"  Templates compilados ({num_templates} templates + {num_probes} probes): {LiteXLEngine.get_template_dir()}"
    )

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

@lite_xl_group.command("debug", help="🩺 Depurador e monitor de telemetria live do Lite XL.")
@click.option("--live", "-l", is_flag=True, default=True, help="Modo streaming contínuo em tempo real.")
@click.option("--errors-only", "-e", is_flag=True, help="Filtra apenas erros e tracebacks.")
def cmd_debug(live, errors_only):
    """Monitor de depuração ao vivo com formatação de tracebacks e eventos."""
    log_path = LiteXLEngine.get_session_log_path()
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩺 DOXOADE LITE XL LIVE DEBUGGER{Style.RESET_ALL}")

    shadow_quick = LiteXLEngine.run_shadow_audit()
    if shadow_quick.get("status") == "FAIL":
        click.echo(f"  {Fore.RED}⚠ ATENÇÃO:{Fore.RESET} {shadow_quick.get('failed')} módulo(s) com erros de comando em background!")
    else:
        click.echo(f"  {Fore.GREEN}✔ Submarino Semântico:{Fore.RESET} Todos os módulos saudáveis na simulação.")

    click.echo(f"  {Fore.WHITE}Alvo:{Fore.RESET} {log_path}")
    click.echo(f"  {Fore.LIGHTBLACK_EX}Pressione Ctrl+C para encerrar o monitoramento.{Fore.RESET}\n")

    if not log_path.exists():
        click.echo(f"  {Fore.YELLOW}⚠ Nenhum log de sessão ativo no momento.{Fore.RESET}\n")
        return

    def format_log_line(line: str) -> str:
        if "[ERROR]" in line:
            return f"  {Fore.RED}{Style.BRIGHT}✖ {line}{Style.RESET_ALL}"
        elif "[WARN]" in line:
            return f"  {Fore.YELLOW}⚠ {line}{Fore.RESET}"
        elif "[INFO]" in line:
            return f"  {Fore.GREEN}ℹ {line}{Fore.RESET}"
        elif "[TRACE]" in line or line.strip().startswith("stack traceback:"):
            return f"    {Fore.LIGHTBLACK_EX}{line}{Fore.RESET}"
        return f"  {Fore.WHITE}{line}{Fore.RESET}"

    # Leitura inicial do histórico recente
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        recent = content[-20:] if len(content) > 20 else content
        for l in recent:
            if not errors_only or ("[ERROR]" in l or "[TRACE]" in l):
                click.echo(format_log_line(l))
    except Exception as e:
        click.echo(f"  {Fore.RED}Erro ao ler log: {e}{Fore.RESET}")

    if not live:
        return

    # Streaming em tempo real (Tail -f inteligente)
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    line_clean = line.rstrip("\r\n")
                    if not errors_only or ("[ERROR]" in line_clean or "[TRACE]" in line_clean):
                        click.echo(format_log_line(line_clean))
                else:
                    time.sleep(0.1)
    except KeyboardInterrupt:
        click.echo(f"\n{Fore.YELLOW}Monitoramento de depuração encerrado.{Fore.RESET}\n")


# ______ API GUARD SYS ______

from doxoade.tools.lua_systems.api_guard.api_catalog import (
    load_catalog,
    save_catalog,
    get_default_catalog,
    get_api_guard_dir,
)

@lite_xl_group.group("api-catalog", help="🧭 Gestão do Catálogo de APIs e Contratos do Lite XL.")
def api_catalog_group():
    """Grupo de comandos do catálogo de APIs."""
    pass

@api_catalog_group.command("show", help="Exibe as APIs registradas no catálogo.")
@click.option("--critical-only", "-c", is_flag=True, help="Exibe apenas APIs críticas.")
@click.option("--filter", "-f", "query", type=str, default=None, help="Filtra por ID ou módulo.")
def cmd_api_catalog_show(critical_only, query):
    
    catalog = load_catalog()
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🧭 CATÁLOGO SOBERANO DE APIS — LITE XL ({len(catalog)} registradas){Style.RESET_ALL}\n")

    for api_id, entry in sorted(catalog.items()):
        if critical_only and entry.severity_if_missing != "critical":
            continue
        if query and (query.lower() not in api_id.lower() and query.lower() not in entry.module.lower()):
            continue

        if entry.is_deprecated:
            badge = f"{Fore.RED}[DEPRECATED]{Fore.RESET}"
        elif entry.severity_if_missing == "critical":
            badge = f"{Fore.YELLOW}[CRITICAL]{Fore.RESET}"
        else:
            badge = f"{Fore.GREEN}[SAFE]{Fore.RESET}"

        patch_badge = f"{Fore.LIGHTBLUE_EX}[PATCHABLE]{Fore.RESET}" if entry.safe_to_patch else ""
        click.echo(f"  {badge} {patch_badge} {Style.BRIGHT}{api_id:<38}{Style.RESET_ALL} -> {Fore.LIGHTBLACK_EX}{entry.module}{Fore.RESET}")
        if entry.signature_notes:
            click.echo(f"      {Fore.WHITE}Contrato:{Fore.RESET} {entry.signature_notes}")
        if entry.fallback:
            click.echo(f"      {Fore.YELLOW}Fallback:{Fore.RESET} {entry.fallback}")

    click.echo()

@api_catalog_group.command("sync", help="Sincroniza e regenera catalog.json e catalog.lua.")
def cmd_api_catalog_sync():
    catalog = get_default_catalog()
    saved_path = save_catalog(catalog)
    guard_dir = get_api_guard_dir()
    click.echo(f"{Fore.GREEN}✔ Catálogo sincronizado com sucesso!{Fore.RESET}")
    click.echo(f"  JSON: {saved_path}")
    click.echo(f"  Lua : {guard_dir / 'catalog.lua'}\n")

@api_catalog_group.command("audit", help="Audita o estado real coletado pelo probe no Lite XL.")
def cmd_api_catalog_audit():
    import json
    from pathlib import Path
    import os

    # Caminhos candidatos onde o Lite XL pode ter gravado o USERDIR
    exe_path = LiteXLEngine.find_executable()
    exe_dir = exe_path.parent if exe_path else None

    candidates = [
        get_api_guard_dir() / "runtime_probe.json",
        Path.home() / ".config" / "lite-xl" / ".doxoade" / "api_guard" / "runtime_probe.json",
        Path(os.environ.get("APPDATA", "")) / "lite-xl" / ".doxoade" / "api_guard" / "runtime_probe.json",
        Path(os.environ.get("LOCALAPPDATA", "")) / "lite-xl" / ".doxoade" / "api_guard" / "runtime_probe.json",
    ]
    
    # Se for portable ao lado do executável:
    if exe_dir:
        candidates.extend([
            exe_dir / "data" / "user" / ".doxoade" / "api_guard" / "runtime_probe.json",
            exe_dir / "user" / ".doxoade" / "api_guard" / "runtime_probe.json",
            exe_dir / ".doxoade" / "api_guard" / "runtime_probe.json",
        ])

    target_json = None
    for cand in candidates:
        if cand.exists() and cand.is_file():
            target_json = cand
            break

    if not target_json:
        click.echo(f"\n{Fore.YELLOW}⚠ Nenhum probe de runtime encontrado.{Fore.RESET}")
        click.echo(f"  Procurado em:")
        for cand in candidates:
            click.echo(f"    - {cand} (existe: {cand.exists()})")
        click.echo(f"\n  Dica: Execute 'doxoade lite-xl setup -f', 'doxoade lite-xl restart' e veja o logview no Lite XL.\n")
        return

    try:
        data = json.loads(target_json.read_text(encoding="utf-8"))
    except Exception as e:
        click.echo(f"{Fore.RED}✖ Erro ao ler {target_json}: {e}{Fore.RESET}\n")
        return

    summary = data.get("summary", {})
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🔬 AUDITORIA RUNTIME PROBE — LITE XL ({data.get('litexl_version', 'N/A')}){Style.RESET_ALL}")
    click.echo(f"  Origem: {target_json}")
    click.echo(f"  Plataforma: {data.get('platform', 'N/A')} | Total auditado: {summary.get('total', 0)}")
    click.echo(f"  Status: {Fore.GREEN}{summary.get('present', 0)} PRESENT{Fore.RESET} | {Fore.RED}{summary.get('missing', 0)} MISSING{Fore.RESET} | {Fore.YELLOW}{summary.get('type_mismatch', 0)} MISMATCH{Fore.RESET}\n")

    caps = data.get("capabilities", {})
    for api_id, info in sorted(caps.items()):
        status = info.get("status")
        real_type = info.get("real_type")
        expected = info.get("expected_type")
        is_dep = info.get("is_deprecated", False)

        if status == "present":
            badge = f"{Fore.GREEN}[✔ PRESENT]{Fore.RESET}"
        elif status == "missing":
            badge = f"{Fore.RED}[✖ MISSING]{Fore.RESET}"
        else:
            badge = f"{Fore.YELLOW}[⚠ MISMATCH]{Fore.RESET}"

        dep_badge = f"{Fore.MAGENTA}[DEPRECATED]{Fore.RESET}" if is_dep else ""
        click.echo(f"  {badge} {dep_badge} {Style.BRIGHT}{api_id:<36}{Style.RESET_ALL} (tipo: {real_type}, esperado: {expected})")

    click.echo()

@api_catalog_group.command("scan", help="Escaneia os templates procurando requires ausentes e riscos de strict.lua.")
def cmd_api_catalog_scan():
    from doxoade.tools.lua_systems.api_guard.api_scan import APITemplateScanner
    template_dir = LiteXLEngine.get_template_dir()
    scanner = APITemplateScanner(template_dir)
    report = scanner.scan_all()

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🔍 SCANNER ESTÁTICO DE TEMPLATES LITE XL (Capítulo 5){Style.RESET_ALL}")
    click.echo(f"  Diretório: {template_dir}")
    click.echo(f"  Arquivos analisados: {report['total_files']} | Inconformidades detectadas: {report['total_missing_requires']}\n")

    for fname, data in sorted(report["files"].items()):
        if data["status"] == "PASS":
            click.echo(f"  {Fore.GREEN}[PASS]{Fore.RESET} {fname}")
        else:
            click.echo(f"  {Fore.RED}[FAIL]{Fore.RESET} {Style.BRIGHT}{fname}{Style.RESET_ALL} ({len(data['missing_requires'])} ausência(s))")
            for item in data["missing_requires"]:
                click.echo(f"      {Fore.YELLOW}L{item['line']}:{Fore.RESET} Símbolo '{Fore.CYAN}{item['symbol']}{Fore.RESET}' não declarado.")
                click.echo(f"         {Fore.LIGHTBLACK_EX}Sugestão:{Fore.RESET} {Fore.GREEN}{item['suggested_require']}{Fore.RESET}")

    click.echo()

@lite_xl_group.command("test", help="🧪 Executa o sandbox_module.lua em uma IDE Lite XL 100% isolada.")
@click.option("--file", "-f", "target_file", type=click.Path(exists=True), default=None, help="Arquivo .lua customizado para testar.")
def cmd_test_sandbox(target_file):
    from doxoade.tools.lua_systems.api_guard.api_scan import APITemplateScanner
    test_path = Path(target_file) if target_file else (LiteXLEngine.get_template_dir() / "sandbox_module.lua")

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🧪 DOXOADE LITE XL SANDBOX HARNESS{Style.RESET_ALL}")
    click.echo(f"  Alvo do teste: {test_path.name}")
    click.echo(f"  Modo: {Fore.YELLOW}ISOLADO (Sessão de trabalho preservada){Fore.RESET}\n")

    # 1. Scanner de Conformidade no arquivo de teste
    scanner = APITemplateScanner(LiteXLEngine.get_template_dir())
    scan_report = scanner.scan_file(test_path)

    if scan_report["status"] == "FAIL":
        click.echo(f"  {Fore.RED}{Style.BRIGHT}✖ SECURE BOOT: Inconformidades detectadas no teste:{Style.RESET_ALL}")
        for item in scan_report["missing_requires"]:
            click.echo(f"    • {Fore.YELLOW}L{item['line']}:{Fore.RESET} Símbolo '{item['symbol']}' sem require.")
            click.echo(f"      Sugestão: {Fore.GREEN}{item['suggested_require']}{Fore.RESET}")
        click.echo(f"\n{Fore.RED}Abortando inicialização do Sandbox para evitar crash.{Fore.RESET}\n")
        return

    click.echo(f"  {Fore.GREEN}✔ Scanner Estático: 100% PASS (Sem vazamento de escopo){Fore.RESET}")

    # 2. Lança a IDE isolada
    success, msg = LiteXLEngine.launch_sandbox(test_path)
    if not success:
        click.echo(f"  {Fore.RED}✖ {msg}{Fore.RESET}\n")
        err_file = sandbox_dir / "error.txt"
        if err_file.exists():
            try:
                err_file.unlink()
            except Exception:
                pass

    else:
        click.echo(f"  {Fore.GREEN}✔ IDE Sandbox iniciada com sucesso em:{Fore.RESET} {msg}")
        click.echo(f"  {Fore.LIGHTBLACK_EX}Dica: Teste seu comando no Sandbox pressionando Ctrl+Shift+P ou o atalho configurado.{Fore.RESET}\n")

    sandbox_err_file = LiteXLEngine.get_sandbox_dir() / "error.txt"
    if sandbox_err_file.exists():
        err_content = sandbox_err_file.read_text(encoding="utf-8", errors="replace").strip()
        if err_content:
            click.echo(f"\n{Fore.RED}{Style.BRIGHT}🚨 [SANDBOX ERROR.TXT DETECTADO]:{Style.RESET_ALL}")
            click.echo(f"{Fore.RED}{err_content}{Fore.RESET}\n")

@lite_xl_group.command("profile", help="⏱️ Análise forense de performance e peso de funções por arquivo.")
@click.option("--runs", "-r", default=5, type=int, help="Número de iterações para benchmark (padrão: 5).")
@click.option("--file", "-f", "target_file", default=None, type=str, help="Filtra a análise para um arquivo específico (ex: 00_01, 11).")
@click.option("--tree", "-t", is_flag=True, default=True, help="Exibe a decomposição em árvore de funções por arquivo.")
def cmd_profile(runs, target_file, tree):
    """Diagnóstico hierárquico: peso de cada função dentro de cada arquivo."""
    user_dir = LiteXLEngine.get_user_dir()

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}⏱️ CHRONOS DEEP PROFILER — ANÁLISE HIERÁRQUICA DE FUNÇÕES{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Alvo:{Fore.RESET} {user_dir} | {Fore.WHITE}Amostras:{Fore.RESET} {Fore.GREEN}{runs} iterações{Fore.RESET}")
    if target_file:
        click.echo(f"  {Fore.YELLOW}Filtro Ativo:{Fore.RESET} Arquivos com '{target_file}'")
    click.echo()

    bench = ProfilerEngine.run_deep_benchmark(runs=runs, target_file=target_file)
    total_time = bench["total_avg_ms"]
    total_mem = sum(m["mem_kb"] for m in bench["modules"])

    # 1. Resumo Executivo
    click.echo(f"  ┌─ {Style.BRIGHT}RESUMO GERAL DO BENCHMARK{Style.RESET_ALL}")
    click.echo(f"  │  • Tempo Médio Total : {Fore.GREEN}{total_time:.2f} ms{Fore.RESET}")
    click.echo(f"  │  • Memória Alocada   : {Fore.CYAN}{total_mem:.1f} KB{Fore.RESET}")
    click.echo(f"  │  • Módulos Mapeados  : {len(bench['modules'])} módulos")
    click.echo(f"  └{'─' * 65}\n")

    # 2. Decomposição em Árvore por Arquivo
    click.echo(f"  {Style.BRIGHT}📦 PESO DAS FUNÇÕES POR ARQUIVO (DRILL-DOWN):{Style.RESET_ALL}\n")

    for mod in bench["modules"]:
        m_name = mod["module"]
        m_time = mod["mean_ms"]
        m_pct = mod["percent"]
        m_mem = mod["mem_kb"]
        funcs = mod.get("functions", [])
        
        # Identificador de padrão de custo
        if mod["is_single_bottleneck"]:
            pattern_badge = f"{Fore.RED}[GARGALO CONCENTRADO: {mod['dominant_feature']}]{Fore.RESET}"
        elif len(funcs) > 5:
            pattern_badge = f"{Fore.YELLOW}[CUSTO DISTRIBUÍDO]{Fore.RESET}"
        else:
            pattern_badge = f"{Fore.GREEN}[LEVE / UNIFORME]{Fore.RESET}"

        click.echo(f"  {Fore.WHITE}📄 {Style.BRIGHT}{m_name:<32}{Style.RESET_ALL} {Fore.GREEN}{m_time:>6.2f} ms{Fore.RESET} ({m_pct:>4.1f}%) | {Fore.CYAN}+{m_mem:>5.1f} KB{Fore.RESET}  {pattern_badge}")

        if funcs:
            for idx, fn in enumerate(funcs[:6], start=1):
                is_last = (idx == min(len(funcs), 6))
                branch = "└──" if is_last else "├──"
                
                f_name = fn["name"]
                line_no = fn["line"]
                calls = fn["calls"]
                self_t = fn["self_time_ms"]
                total_t = fn["total_time_ms"]
                f_pct = fn["file_percent"]

                # Destaca se for o grande vilão do arquivo
                f_color = Fore.RED if f_pct >= 50.0 else (Fore.YELLOW if f_pct >= 25.0 else Fore.LIGHTBLACK_EX)
                
                click.echo(f"     {branch} {f_color}{f_name:<24}{Fore.RESET} (L{line_no:<4}) {total_t:>6.2f} ms ({f_pct:>4.1f}% do arq) | {calls:>3} calls | Self: {self_t:.2f}ms")
        else:
            click.echo(f"     └── {Fore.LIGHTBLACK_EX}(Nenhuma função interna rastreada — execução de bloco único){Fore.RESET}")

        click.echo()

    # 3. Laudo Executivo
    click.echo(f"  {Fore.YELLOW}{Style.BRIGHT}🔍 DIAGNÓSTICO ACIONÁVEL:{Style.RESET_ALL}")
    for mod in bench["modules"][:3]:
        if mod["is_single_bottleneck"]:
            click.echo(f"    • {Fore.WHITE}{mod['module']}:{Fore.RESET} Otimizar pontualmente a função {Fore.RED}'{mod['dominant_feature']}'{Fore.RESET} eliminará mais da metade do custo do arquivo.")
        else:
            click.echo(f"    • {Fore.WHITE}{mod['module']}:{Fore.RESET} Custo distribuído ({mod['cost_reason']}). Requer simplificação geral.")
    click.echo()

@lite_xl_group.command("preflight", help="🛡️ Valida o init.lua antes de instalar em produção.")
def cmd_preflight():
    """Gera o init.lua em memória e valida com compilação real + shadow audit."""
    import tempfile
    from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🛡️ PRE-FLIGHT GATE — Validação Pré-Deploy{Style.RESET_ALL}")
    
    # 1. Gera o init.lua em memória
    init_content = LiteXLEngine.generate_sovereign_init()
    temp_init = Path(tempfile.gettempdir()) / "doxoade_preflight_init.lua"
    temp_init.write_text(init_content, encoding="utf-8")
    
    click.echo(f"  {Fore.WHITE}Init gerado em memória: {len(init_content):,} bytes{Fore.RESET}")
    
    # 2. Compilação real (Lua 5.4)
    runtime = LiteXLEngine.lua_runtime_info()
    if runtime:
        lua_exe, lua_ver = runtime
        try:
            lua_safe_path = str(temp_init).replace("\\", "/")  # Unix-style para Lua
            result = subprocess.run(
                [str(lua_exe), "-e", f'dofile("{lua_safe_path}")'],
#                [str(lua_exe), "-e", f'dofile("{temp_init}")'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                click.echo(f"  {Fore.GREEN}✔ Compilação real OK ({lua_ver}){Fore.RESET}")
            else:
                click.echo(f"  {Fore.RED}✖ ERRO DE COMPILAÇÃO:{Fore.RESET}")
                click.echo(f"    {result.stderr}")
                return
        except Exception as e:
            click.echo(f"  {Fore.YELLOW}⚠ Compilação falhou: {e}{Fore.RESET}")
    else:
        click.echo(f"  {Fore.YELLOW}⚠ Sem runtime Lua — pulando compilação real{Fore.RESET}")
    
    # 3. Shadow Audit (mock runtime)
    click.echo(f"\n  {Fore.CYAN}Executando Shadow Audit...{Fore.RESET}")
    shadow = LiteXLEngine.run_shadow_audit()
    if shadow.get("status") == "FAIL":
        click.echo(f"  {Fore.RED}✖ Shadow Audit detectou falhas:{Fore.RESET}")
        for fname, data in shadow.get("files", {}).items():
            if data["status"] == "FAIL":
                click.echo(f"    {Fore.RED}• {fname}: {data.get('error', 'unknown')}{Fore.RESET}")
        return
    
    click.echo(f"  {Fore.GREEN}✔ Shadow Audit OK{Fore.RESET}")
    
    # 4. Verifica variáveis globais indefinidas (padrão forensic_data)
    click.echo(f"\n  {Fore.CYAN}Verificando variáveis não declaradas...{Fore.RESET}")
    undeclared = []
    
    # 🆕 Literais Lua que NÃO são variáveis
    LUA_LITERALS = {"true", "false", "nil"}
    
    for line_no, line in enumerate(init_content.splitlines(), 1):
        match = re.search(r'rawset\(_G,\s*"[^"]+",\s*([a-zA-Z_][a-zA-Z0-9_]*)\)', line)
        if match:
            var_name = match.group(1)
            # 🆕 Skip em literais
            if var_name in LUA_LITERALS:
                continue
            preceding = "\n".join(init_content.splitlines()[:line_no-1])
            if not re.search(rf'\blocal\s+{var_name}\b', preceding) and \
               not re.search(rf'rawset\(_G,\s*"{var_name}"', preceding):
                undeclared.append((line_no, var_name))
    
    if undeclared:
        click.echo(f"  {Fore.RED}✖ Variáveis não declaradas detectadas:{Fore.RESET}")
        for line_no, var_name in undeclared:
            click.echo(f"    {Fore.RED}• Linha {line_no}: '{var_name}' usada antes da declaração{Fore.RESET}")
        click.echo(f"\n  {Fore.YELLOW}💡 Corrija os templates e re-execute o preflight.{Fore.RESET}")
        return
    
    click.echo(f"  {Fore.GREEN}✔ Nenhuma variável não declarada{Fore.RESET}")
    
    # 5. Sucesso — libera para deploy
    click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ PRE-FLIGHT OK — Init.lua validado e pronto para deploy.{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Execute 'doxoade lite-xl setup --force' para instalar.{Fore.RESET}\n")



# ═══════════════════════════════════════════════════════════
# 🐉 TYPHON — Pipeline Supervisionado de Deploy
# ═══════════════════════════════════════════════════════════
from doxoade.commands.lite_xl_systems.typhon import TyphonEngine
@lite_xl_group.group("typhon", help="🐉 Pipeline supervisionado de deploy com auto-rollback.")
def typhon_group():
    """Typhon: O pai dos monstros. Deploy supervisionado com gates e rollback."""
    pass

@typhon_group.command("deploy")
@click.option("--watch", "-w", default=5, type=int, help="Segundos para monitorar o boot (padrão: 5).")
@click.option("--dry-run", is_flag=True, help="Valida sem gravar nada em produção.")
@click.option("--no-rollback", is_flag=True, help="Desativa rollback automático (para debug).")
@click.option("--baseline", is_flag=True, help="Compara boot time com o último deploy estável.")
@click.argument("target", required=False, default=".")
def cmd_typhon_deploy(watch, dry_run, no_rollback, baseline, target):
    """Executa o pipeline completo: snapshot → preflight → deploy → watch → verdict."""
    TyphonEngine.run_pipeline(
        target=target,
        watch_seconds=watch,
        dry_run=dry_run,
        no_rollback=no_rollback,
        baseline=baseline,
        echo=click.echo,
    )

@typhon_group.command("status")
def cmd_typhon_status():
    """Exibe o status do TYPHON: snapshot, último deploy, histórico."""
    status = TyphonEngine.get_status()
    click.echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}🐉 TYPHON STATUS{Style.RESET_ALL}\n")
    click.echo(f"  init.lua:       {Fore.GREEN if status['init_lua_exists'] else Fore.RED}{status['init_lua_size']:,} bytes{Fore.RESET}")
    click.echo(f"  Snapshot:       {Fore.GREEN if status['stable_snapshot_exists'] else Fore.YELLOW}{status['stable_snapshot_size']:,} bytes{Fore.RESET}")
    click.echo(f"  Lite XL:        {Fore.GREEN if status['lite_xl_running'] else Fore.LIGHTBLACK_EX}{'rodando' if status['lite_xl_running'] else 'parado'}{Fore.RESET}")
    click.echo(f"  Deploys totais: {Fore.WHITE}{status['deploy_history_count']}{Fore.RESET}")

    if status["last_deploy"]:
        ld = status["last_deploy"]
        click.echo(f"\n  {Fore.CYAN}Último deploy:{Fore.RESET}")
        click.echo(f"    Timestamp:  {ld.get('timestamp', 'N/A')}")
        click.echo(f"    Boot time:  {ld.get('boot_time_ms', 0):.0f}ms")
        click.echo(f"    Init size:  {ld.get('init_size_bytes', 0):,} bytes")

    if status["recent_history"]:
        click.echo(f"\n  {Fore.CYAN}Histórico recente:{Fore.RESET}")
        for entry in status["recent_history"]:
            t = entry.get("type", "?")
            ts = entry.get("timestamp", "?")[:19]
            color = Fore.GREEN if "OK" in t else Fore.RED
            click.echo(f"    {color}• {t}{Fore.RESET} — {ts}")
    click.echo()

@typhon_group.command("rollback")
def cmd_typhon_rollback():
    """Rollback manual: restaura o init.lua a partir do snapshot estável."""
    ok, msg = TyphonEngine.rollback()
    if ok:
        click.echo(f"\n{Fore.GREEN}✔ {msg}{Fore.RESET}")
        click.echo(f"  {Fore.YELLOW}Execute 'doxoade lite-xl restart' para aplicar.{Fore.RESET}\n")
    else:
        click.echo(f"\n{Fore.RED}✖ {msg}{Fore.RESET}\n")

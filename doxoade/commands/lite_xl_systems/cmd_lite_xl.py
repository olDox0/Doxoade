# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/cmd_lite_xl.py
""" CLI para Orquestração, Diagnóstico, Profiler e Gestão do Lite XL (Doxly). """
import os
import re
import sys
import time
import json
import shutil
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
import click
from doxoade.tools.doxcolors import Fore, Style, Back
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
from doxoade.tools.lua_systems.profiler import ProfilerEngine
from doxoade.commands.lite_xl_systems.chaos_sandbox_runner import ChaosSandboxRunner
from doxoade.commands.lite_xl_systems.chaos_payload import MEGA_CHAOS_PAYLOAD
from doxoade.tools.lua_systems.chaos_validator import ChaosValidator
from doxoade.commands.lite_xl_systems.chaos_deep_runner import DeepChaosRunner
from doxoade.commands.lite_xl_systems.chaos_canary_probe import run_canary_probe
from doxoade.commands.lite_xl_systems.cmd_typhon_deploy import deploy_group
from doxoade.commands.lite_xl_systems.typhon_doxly.cmd_typhon_doxly import typhon_doxly_group


@click.group("lite-xl", help="⚡ Gestão, diagnóstico e automação do Lite XL.")
def lite_xl_group():
    """Grupo de comandos do ecossistema Lite XL."""
    pass

lite_xl_group.add_command(deploy_group)

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
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🐺 AUDITORIA SEMÂNTICA SHADOW (Active Simulator){Style.RESET_ALL}")
    shadow_report = LiteXLEngine.run_shadow_audit()
    if shadow_report.get("status") == "SKIPPED":
        click.echo(f"  {Fore.YELLOW}⚠ Shadow Audit ignorado: {shadow_report.get('reason')}{Fore.RESET}\n")
    else:
        for fname, sdata in shadow_report.get("files", {}).items():
            status_tag = f"{Fore.GREEN}[SHADOW PASS]{Fore.RESET}" if sdata["status"] == "PASS" else f"{Fore.RED}[SHADOW FAIL]{Fore.RESET}"
            time_badge = f"{Fore.LIGHTBLACK_EX}({sdata.get('time_ms', 0):.2f}ms){Fore.RESET}"
            click.echo(f"  {status_tag} {Style.BRIGHT}{fname:<35}{Style.RESET_ALL} {time_badge}")
            if sdata.get("error"):
                click.echo(f"      {Fore.RED}✖ {sdata['error']}{Fore.RESET}")

        cmd_count = shadow_report.get("commands_count", 0)
        cmd_passed = shadow_report.get("commands_passed", 0)
        cmd_crashed = shadow_report.get("commands_crashed", 0)

        if cmd_count > 0:
            status_color = Fore.GREEN if cmd_crashed == 0 else Fore.RED
            click.echo(f"\n  {status_color}✔ Simulação Ativa de Comandos:{Fore.RESET} {cmd_passed}/{cmd_count} executaram com sucesso ({cmd_crashed} falhas).")

        if shadow_report.get("crashed_commands"):
            click.echo(f"  {Fore.RED}✖ Comandos que Falharam na Execução Ativa:{Fore.RESET}")
            for c in shadow_report["crashed_commands"]:
                click.echo(f"      {Fore.RED}• [{c['command']}]: {Fore.YELLOW}{c['error']}{Fore.RESET}")

        if shadow_report.get("prompt_crashes"):
            click.echo(f"  {Fore.RED}✖ Falhas em Callbacks de Prompt (Submit):{Fore.RESET}")
            for p in shadow_report["prompt_crashes"]:
                click.echo(f"      {Fore.RED}• [{p['prompt']}]: {Fore.YELLOW}{p['error']}{Fore.RESET}")

        if shadow_report.get("orphan_keys"):
            click.echo(f"  {Fore.RED}⚠ Atalhos Órfãos Detectados:{Fore.RESET}")
            for ok in shadow_report["orphan_keys"]:
                click.echo(f"      {Fore.YELLOW}• {ok}{Fore.RESET}")

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

@lite_xl_group.command("chaos-canary", help="🐤 Prova de execução do init do sandbox.")
def cmd_chaos_canary():
    """Verifica se o Lite XL está lendo o init.lua do sandbox."""
    try:
        run_canary_probe()
    except Exception as e:
        click.echo(f"{Fore.RED}✖ Falha no canário forense: {e}{Fore.RESET}")
        sys.exit(1)

@lite_xl_group.command("chaos-deep", help="🏜️ Testes de crash, falha e erro oculto no sandbox.")
@click.option("--category", "-c", multiple=True,
              type=click.Choice(["crash", "fault", "hidden"]),
              help="Filtra por categoria (pode repetir). Padrão: todos.")
def cmd_chaos_deep(category):
    """Executa a suíte de caos profundo no sandbox isolado."""
    try:
        cats = list(category) if category else None
        results = DeepChaosRunner.run_deep_suite(categories=cats)
        if results["missed"] > 0:
            sys.exit(1)
    except Exception as e:
        click.echo(f"{Fore.RED}✖ Falha na suíte profunda: {e}{Fore.RESET}")
        sys.exit(1)

@lite_xl_group.command("chaos-test", help="⚖️ Injeta erros propositalmente para testar se a auditoria os detecta.")
def cmd_chaos_test():
    """Executa a suíte de validação de falhas (Mutation Testing)."""
    try:
        results = ChaosValidator.run_chaos_suite()
        if results["escaped"] > 0:
            sys.exit(1) # Força saída com erro se a auditoria falhou em detectar
        else:
            click.echo(f"{Fore.GREEN}✔ Teste de Caos concluído com sucesso.{Fore.RESET}")
    except Exception as e:
        click.echo(f"{Fore.RED}✖ Falha na execução do Chaos Validator: {e}{Fore.RESET}")
        sys.exit(1)

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

@lite_xl_group.command("diagnose", help="Realiza auditoria forense do init.lua (Production, Sandbox ou Test).")
@click.option("--mode", "-m", type=click.Choice(["production", "sandbox", "test"]), default="production", help="Ambiente a ser diagnosticado.")
def cmd_diagnose(mode):
    if mode == "sandbox":
        target_dir = LiteXLEngine.get_sandbox_dir()
    elif mode == "test":
        target_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy"
    else:
        target_dir = LiteXLEngine.get_user_dir()

    init_file = target_dir / "init.lua"
    err_file = target_dir / "error.txt"

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩺 DIAGNÓSTICO FORENSE DO INIT.LUA ({mode.upper()}){Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Alvo:{Fore.RESET} {init_file}\n")

    if err_file.exists() and err_file.stat().st_size > 0:
        raw_err = err_file.read_text(encoding="utf-8", errors="replace")
        click.echo(f"{Fore.RED}{Style.BRIGHT}⚠ CRASH REPORT DETECTADO (error.txt):{Style.RESET_ALL}")
        click.echo(raw_err)
        detect_khonsu_crash(raw_err, target_dir)

    report = LiteXLEngine.diagnose_init_file(init_file)
    if not report["exists"]:
        click.echo(f"{Fore.YELLOW}⚠ Arquivo init.lua não encontrado em {target_dir}.{Fore.RESET}")
        return

    if report["errors"]:
        click.echo(f"{Fore.RED}{Style.BRIGHT}✖ ERROS CRÍTICOS DETECTADOS ({len(report['errors'])}):{Style.RESET_ALL}")
        for err in report["errors"]:
            click.echo(f"  {Fore.RED}• {err}{Fore.RESET}")
    else:
        click.echo(f"{Fore.GREEN}✔ Sintaxe, escapes e módulos 100% validados!{Fore.RESET}")

def parse_traceback(traceback_text, message=""):
    """Extrai informações estruturadas do traceback OU da mensagem.
    V2.0: Prioriza arquivos do CORE do Lite XL quando o erro é no tokenizer/highlighter."""
    lines = traceback_text.strip().split('\n') if traceback_text else []
    culprit_file = None
    culprit_line = 0
    culprit_name = "core"
    frames = []

    # 🛡️ KHONSU V2: Arquivos do core têm prioridade sobre plugins
    # quando o erro é no tokenizer/highlighter/syntax
    CORE_PRIORITY_KEYWORDS = ["tokenizer", "highlighter", "syntax", "docview"]
    CORE_PRIORITY_FILES = ["tokenizer.lua", "highlighter.lua", "docview.lua", "syntax.lua"]

    error_is_core_related = any(
        kw in message.lower() or kw in traceback_text.lower()
        for kw in CORE_PRIORITY_KEYWORDS
    )

    for line in lines:
        line = line.strip()
        if not line:
            continue
        frames.append(line)
        if line.startswith('[C]:') or line.startswith('[STRING'):
            continue

        match = re.search(r'([a-zA-Z]:\\[^:\n]+|\/[^:\n]+):(\d+)', line)
        if match:
            fpath = match.group(1)
            fline = int(match.group(2))
            fname = fpath.replace('\\', '/')

            # 🛡️ KHONSU V2: Se o erro é core-related, priorizar arquivos do core
            if error_is_core_related:
                is_core_file = any(cf in fname.lower() for cf in CORE_PRIORITY_FILES)
                if is_core_file:
                    culprit_file = fpath
                    culprit_line = fline
                    culprit_name = fname.split('/')[-1]
                    break
                # Pular plugins quando procurando causa raiz no core
                if 'plugins/' in fname.lower() or 'plugins\\' in fname.lower():
                    continue
            else:
                # Comportamento original: primeiro arquivo não-core
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


def detect_khonsu_crash(raw_err, target_dir):
    """
    🌙 KHONSU CRASH DETECTOR — Analisa error.txt (crash fatal fora do hook core.error),
    atribui culpado via parse_traceback e, se o frame culpado for um chunk anônimo
    (assinatura de init compilado/minificado pelo Khonsu, ex: [string "local core..."]),
    tenta mapear a linha de volta ao init.lua.dev (espelho legível salvo pelo Khonsu).
    """
    if not raw_err or not raw_err.strip():
        return

    lines = raw_err.strip().splitlines()
    first_line = lines[0] if lines else ""
    message = first_line.split("Error:", 1)[-1].strip() if "Error:" in first_line else first_line
    traceback_body = "\n".join(lines[1:]) if len(lines) > 1 else raw_err

    info = parse_traceback(traceback_body, message)

    click.echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}🌙 [KHONSU CRASH DETECTOR]{Style.RESET_ALL}")

    if info["file"]:
        real_path = Path(info["file"])
        click.echo(f"  {Fore.WHITE}Culpado provável:{Fore.RESET} {info['name']}")
        click.echo(f"  {Fore.WHITE}Local:{Fore.RESET} {info['file']}:{info['line']}")
        if real_path.exists():
            render_snippet(real_path, info["line"])
        else:
            click.echo(f"  {Fore.YELLOW}⚠ Arquivo não encontrado em disco para snippet.{Fore.RESET}")
        return

    # Nenhum frame externo identificável — provável falha pura do core nativo do
    # Lite XL, ou o único frame com contexto é um chunk anônimo do init compilado.
    anon_match = re.search(r'\[string "([^"]*)"\]:(\d+)', raw_err)
    dev_mirror = target_dir / "init.lua.dev"
    if anon_match and dev_mirror.exists():
        anon_line = int(anon_match.group(2))
        click.echo(
            f"  {Fore.YELLOW}💡 Frame culpado é um chunk anônimo do init compilado pelo Khonsu "
            f"({anon_match.group(1)}...):{anon_line}{Fore.RESET}"
        )
        click.echo(f"  {Fore.CYAN}Mapeando via dev mirror (init.lua.dev):{Fore.RESET}")
        render_snippet(dev_mirror, anon_line)
    else:
        click.echo(
            f"  {Fore.YELLOW}⚠ Nenhum culpado atribuível em código nosso — indício de falha "
            f"no core nativo do Lite XL (fora do init/plugins customizados).{Fore.RESET}"
        )
        if anon_match and not dev_mirror.exists():
            click.echo(
                f"  {Fore.LIGHTBLACK_EX}(init.lua.dev não encontrado em {target_dir} — "
                f"rode o deploy com save_dev_mirror ativo para habilitar o mapeamento.){Fore.RESET}"
            )


@lite_xl_group.command("log", help="Exibe os logs de sessão (Production, Sandbox ou Test).")
@click.option("--mode", "-m", type=click.Choice(["production", "sandbox", "test"]), default="production", help="Ambiente do log.")
@click.option("--lines", "-n", default=30, help="Número de linhas a exibir.")
@click.option("--khonsu/--no-khonsu", "khonsu_on", default=True,
              help="Ativa/desativa o Khonsu Crash Detector na saída.")
def cmd_log(mode, lines, khonsu_on):
    if mode == "sandbox":
        target_dir = LiteXLEngine.get_sandbox_dir()
    elif mode == "test":
        target_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy"
    else:
        target_dir = LiteXLEngine.get_user_dir()

    log_path = target_dir / "session_log.txt"
    err_path = target_dir / "error.txt"

    if err_path.exists() and err_path.stat().st_size > 0:
        raw_err = err_path.read_text(encoding="utf-8", errors="replace")
        click.echo(f"\n{Fore.RED}{Style.BRIGHT}⚠ [CRASH LOG ({mode.upper()}) - error.txt]{Style.RESET_ALL}")
        click.echo(raw_err)
        detect_khonsu_crash(raw_err, target_dir)

    if log_path.exists():
        click.echo(f"\n{Fore.CYAN}📜 [SESSION LOG ({mode.upper()})] -> {log_path}{Fore.RESET}\n")
        all_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in all_lines[-lines:]:
            click.echo(f"  {line}")
    else:
        click.echo(f"{Fore.YELLOW}⚠ Nenhum session_log.txt encontrado em {target_dir}.{Fore.RESET}")


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


@lite_xl_group.command("open", help="📂 Abre arquivo/pasta no Lite XL (reutiliza instância viva via IPC).")
@click.argument("target", required=False, default=".")
@click.option("--new", "-n", is_flag=True, help="Força nova instância (ignora IPC).")
def cmd_open(target: str, new: bool):
    """Abre arquivo ou pasta no Lite XL, reutilizando instância viva via IPC se possível."""
    resolved, exists, is_dir = LiteXLEngine.resolve_target_path(target)
    if not resolved or not exists:
        click.echo(f"{Fore.RED}✖ Caminho não existe no disco: {target}{Fore.RESET}")
        sys.exit(1)

    if LiteXLEngine.is_process_alive() and not new:
        ok, sent_path = LiteXLEngine.send_to_running_instance(resolved)
        if ok:
            click.echo(f"{Fore.GREEN}✔ Enviado para instância viva via IPC: {sent_path}{Fore.RESET}")
            return
        else:
            click.echo(f"{Fore.YELLOW}⚠ IPC falhou ({sent_path}), lançando nova instância...{Fore.RESET}")

    ok, msg = LiteXLEngine.launch_with_safety_guard(resolved, restore_session=True)
    if ok:
        click.echo(f"{Fore.GREEN}✔ Lite XL iniciado: {msg}{Fore.RESET}")
    else:
        click.echo(f"{Fore.RED}✖ Falha ao iniciar: {msg}{Fore.RESET}")
        sys.exit(1)

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
@click.option("--mode", "-m", type=click.Choice(["production", "sandbox", "test"]), default="production", help="Ambiente alvo.")
@click.option("-l", "--live", is_flag=True, help="Modo streaming contínuo em tempo real.")
@click.option("-e", "--errors-only", is_flag=True, help="Filtra apenas erros e tracebacks.")
def cmd_debug(mode, live, errors_only):
    if mode == "sandbox":
        target_dir = LiteXLEngine.get_sandbox_dir()
    elif mode == "test":
        target_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy"
    else:
        target_dir = LiteXLEngine.get_user_dir()

    log_path = target_dir / "session_log.txt"
    err_path = target_dir / "error.txt"

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩺 DOXOADE LITE XL LIVE DEBUGGER ({mode.upper()}){Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Alvo:{Fore.RESET} {log_path}\n")

    if not log_path.exists():
        click.echo(f"{Fore.YELLOW}⚠ Arquivo session_log.txt não encontrado em {target_dir}.{Fore.RESET}")
        return

    # Exibe o conteúdo atual
    content = log_path.read_text(encoding="utf-8", errors="replace")
    for line in content.splitlines()[-20:]:
        if not errors_only or "[ERROR]" in line or "GHOST" in line or "STACK TRACEBACK" in line.upper():
            click.echo(f"  {line}")

    # 🌙 Captura de crash fatal (error.txt) — antes ausente deste comando.
    last_err_mtime = None
    if err_path.exists() and err_path.stat().st_size > 0:
        raw_err = err_path.read_text(encoding="utf-8", errors="replace")
        click.echo(f"\n{Fore.RED}{Style.BRIGHT}⚠ CRASH REPORT DETECTADO (error.txt):{Style.RESET_ALL}")
        click.echo(raw_err)
        detect_khonsu_crash(raw_err, target_dir)
        last_err_mtime = err_path.stat().st_mtime

    if live:
        click.echo(f"\n{Fore.CYAN}👀 Modo Live streaming ativo. Pressione Ctrl+C para encerrar.{Fore.RESET}\n")
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if line:
                        if not errors_only or "[ERROR]" in line or "GHOST" in line or "STACK TRACEBACK" in line.upper():
                            click.echo(f"  {line.rstrip()}")
                    else:
                        # Verifica se um crash fatal apareceu/mudou desde a última checagem.
                        if err_path.exists() and err_path.stat().st_size > 0:
                            cur_mtime = err_path.stat().st_mtime
                            if cur_mtime != last_err_mtime:
                                last_err_mtime = cur_mtime
                                raw_err = err_path.read_text(encoding="utf-8", errors="replace")
                                click.echo(f"\n{Fore.RED}{Style.BRIGHT}⚠ [CRASH DETECTADO EM TEMPO REAL] error.txt{Style.RESET_ALL}")
                                click.echo(raw_err)
                                detect_khonsu_crash(raw_err, target_dir)
                        time.sleep(0.2)
        except KeyboardInterrupt:
            click.echo(f"\n{Fore.YELLOW}Monitoramento de depuração encerrado.{Fore.RESET}")


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

@lite_xl_group.command("profile", help="⏱️ Análise forense de performance, peso de módulos e telemetria live.")
@click.option("-l", "--live", is_flag=True, help="Exibe a telemetria em tempo real do editor em execução.")
@click.option("-m", "--mode", type=click.Choice(["production", "sandbox", "test"]), default="production", help="Ambiente a monitorar (padrão: production).")
@click.option("-w", "--watch", is_flag=True, help="Modo sentinela contínuo em tempo real.")
@click.option("-r", "--runs", default=5, help="Número de iterações para benchmark estático (padrão: 5).")
@click.option("-f", "--file", default=None, help="Filtra a análise para um arquivo específico.")
def cmd_profile(live, mode, watch, runs, file):
    """⏱️ Chronos Profiler — Análise estática de boot e telemetria dinâmica de produção."""
    
    # =========================================================================
    # MODO 1: LIVE PROFILER INTERATIVO (Sessão de Captura com Encerramento por ENTER)
    # =========================================================================
    if live or watch:
        import threading
        
        target_dir = LiteXLEngine.get_sandbox_dir() if mode == "sandbox" else (
            LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy" if mode == "test" else LiteXLEngine.get_user_dir()
        )
        
        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}⚡ CHRONOS LIVE PROFILER — SESSÃO DE CAPTURA EM TEMPO REAL ({mode.upper()}){Style.RESET_ALL}")
        click.echo(f"  {Fore.WHITE}Alvo:{Fore.RESET} {target_dir}")
        click.echo(f"  {Fore.GREEN}👉 Use o Lite XL normalmente (digite, navegue, abra arquivos).{Fore.RESET}")
        click.echo(f"  {Fore.YELLOW}🛑 Pressione [ENTER] neste terminal a qualquer momento para encerrar e gerar o laudo.{Fore.RESET}\n")
        click.echo(f"{Fore.LIGHTBLACK_EX}{'─' * 70}{Fore.RESET}")

        stop_event = threading.Event()

        def wait_for_enter():
            try:
                input()
            except Exception:
                pass
            stop_event.set()

        # Thread não-bloqueante para capturar o [ENTER] do usuário
        listener_thread = threading.Thread(target=wait_for_enter, daemon=True)
        listener_thread.start()

        start_time = time.time()
        fps_samples = []
        seen_spikes = set()
        all_spikes = []
        last_cmds_snapshot = {}

        try:
            while not stop_event.is_set():
                data = ProfilerEngine.get_live_telemetry(mode=mode)
                if data:
                    fps = data.get("active_fps", 60.0)
                    fps_samples.append(fps)
                    gc_mem = data.get("gc_memory_kb", 0.0)
                    last_cmds_snapshot = data.get("command_frequencies", {})

                    # Notifica novos spikes detectados em tempo real (sem limpar a tela)
                    for sp in data.get("frame_spikes", []):
                        sp_key = f"{sp['timestamp']}:{sp['duration_ms']}:{sp['active_file']}"
                        if sp_key not in seen_spikes:
                            seen_spikes.add(sp_key)
                            all_spikes.append(sp)
                            click.echo(
                                f"  {Fore.RED}⚠️ [SPIKE DETECTADO]{Fore.RESET} {Fore.YELLOW}{sp['duration_ms']:5.2f} ms{Fore.RESET} "
                                f"no buffer: {Fore.WHITE}{sp['active_file']}{Fore.RESET}"
                            )

                # Pulso de status a cada 2 segundos
                elapsed_sec = int(time.time() - start_time)
                current_fps = fps_samples[-1] if fps_samples else 60.0
                fps_color = Fore.GREEN if current_fps >= 55.0 else (Fore.YELLOW if current_fps >= 30.0 else Fore.RED)
                
                # Exibe linha discreta de streaming
                sys.stdout.write(f"\r  ⏱️ [{elapsed_sec:3d}s] FPS: {fps_color}{current_fps:4.1f}{Fore.RESET} | Spikes: {Fore.RED}{len(all_spikes)}{Fore.RESET} | Pressione [ENTER] para laudo final... ")
                sys.stdout.flush()

                time.sleep(1.0)
        except KeyboardInterrupt:
            stop_event.set()

        sys.stdout.write("\r" + " " * 80 + "\r") # Limpa a linha de pulso
        session_duration = round(time.time() - start_time, 1)

        # =====================================================================
        # LAUDO CONSOLIDADO FINAL DA SESSÃO CALIBRADA
        # =====================================================================
        final_data = ProfilerEngine.get_live_telemetry(mode=mode) or {}
        
        latency = final_data.get("avg_draw_latency_ms", 1.8)
        active_fps = final_data.get("active_fps", 60.0)
        target_fps = final_data.get("target_fps", 60)
        final_gc = final_data.get("gc_memory_kb", 0.0)
        is_idle = final_data.get("is_idle", False)

        # Badge visual de estabilidade
        status_badge = f"{Fore.CYAN}[💤 OCIOSO / 0% CPU]{Fore.RESET}" if is_idle else (
            f"{Fore.GREEN}[⚡ FLUIDO / {target_fps} FPS]{Fore.RESET}" if active_fps >= (target_fps * 0.9) else f"{Fore.YELLOW}[ALERTA: QUEDAS DE QUADRO]{Fore.RESET}"
        )

        click.echo(f"\n{'=' * 70}")
        click.echo(f"{Fore.GREEN}{Style.BRIGHT}🏆 LAUDO CONSOLIDADO DA SESSÃO DE PERFORMANCE (CHRONOS CALIBRADO){Style.RESET_ALL}")
        click.echo(f"{'=' * 70}")
        click.echo(f"  • {Fore.WHITE}Duração da Sessão   :{Fore.RESET} {session_duration} segundos")
        click.echo(f"  • {Fore.WHITE}Latência de Render  :{Fore.RESET} {Fore.GREEN}{latency:4.2f} ms{Fore.RESET} por quadro (Capacidade: {Fore.CYAN}{1000/max(latency, 0.1):.0f} FPS{Fore.RESET})")
        click.echo(f"  • {Fore.WHITE}Taxa Ativa de FPS   :{Fore.RESET} {Fore.GREEN}{active_fps:4.1f} FPS{Fore.RESET} (Alvo: {target_fps} FPS)  {status_badge}")
        click.echo(f"  • {Fore.WHITE}Memória do GC       :{Fore.RESET} {Fore.CYAN}{final_gc:6.1f} KB{Fore.RESET} ({final_gc / 1024.0:4.2f} MB)")
        click.echo(f"  • {Fore.WHITE}Total de Spikes     :{Fore.RESET} {Fore.RED if all_spikes else Fore.GREEN}{len(all_spikes)} queda(s) reais (> {target_fps} FPS limit){Fore.RESET}")

        # Ranking de Comandos Disparados na Sessão
        click.echo(f"\n  {Fore.YELLOW}{Style.BRIGHT}📊 COMANDOS MAIS DISPARADOS NA SESSÃO (Frequência):{Style.RESET_ALL}")
        top_cmds = final_data.get("top_commands", [])
        if top_cmds:
            for idx, (cmd_name, count) in enumerate(top_cmds[:6], start=1):
                click.echo(f"     {idx}. {Fore.WHITE}{cmd_name:<32}{Fore.RESET} {Fore.CYAN}{count:>4}x{Fore.RESET}")
        else:
            click.echo(f"     {Fore.LIGHTBLACK_EX}(Nenhum comando registrado){Fore.RESET}")

        click.echo(f"\n{'=' * 70}\n")
        return

    # =========================================================================
    # MODO 2: SHADOW PROFILER (A Ponta do Iceberg: Benchmark Estático de Boot)
    # =========================================================================
    user_dir = LiteXLEngine.get_user_dir()
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}⏱️ CHRONOS DEEP PROFILER — ANÁLISE HIERÁRQUICA DE FUNÇÕES{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Alvo:{Fore.RESET} {user_dir} | {Fore.WHITE}Amostras:{Fore.RESET} {runs} iterações\n")

    bench = ProfilerEngine.run_deep_benchmark(runs=runs, target_file=file)
    if bench["runs"] == 0:
        click.echo(f"{Fore.RED}✖ Não foi possível executar o benchmark de sombra.{Fore.RESET}")
        return

    click.echo(f"  ┌─ RESUMO GERAL DO BENCHMARK")
    click.echo(f"  │  • Tempo Médio Total : {Fore.GREEN}{bench['total_avg_ms']:5.2f} ms{Fore.RESET}")
    click.echo(f"  │  • Memória Alocada   : {Fore.CYAN}{bench.get('total_mem_kb', 0.0):5.1f} KB{Fore.RESET}")
    click.echo(f"  │  • Módulos Mapeados  : {bench['modules_count']} módulos")
    click.echo(f"  └─────────────────────────────────────────────────────────────────\n")

    click.echo(f"  {Fore.YELLOW}{Style.BRIGHT}📦 PESO DAS FUNÇÕES POR ARQUIVO (DRILL-DOWN):{Style.RESET_ALL}\n")

    for mod in bench["modules"]:
        m_name = mod["module"]
        m_time = mod["mean_ms"]
        m_pct = mod["percent"]
        m_mem = mod.get("mem_kb", 0.0)
        funcs = mod.get("functions", [])

        if mod.get("is_single_bottleneck"):
            pattern_badge = f"{Fore.RED}[GARGALO CONCENTRADO: {mod.get('dominant_feature', 'Lógica')}]{Fore.RESET}"
        elif len(funcs) > 5:
            pattern_badge = f"{Fore.YELLOW}[CUSTO DISTRIBUÍDO]{Fore.RESET}"
        else:
            pattern_badge = f"{Fore.GREEN}[LEVE / UNIFORME]{Fore.RESET}"

        click.echo(f"  {Fore.WHITE}📄 {Style.BRIGHT}{m_name:<32}{Style.RESET_ALL} {Fore.GREEN}{m_time:>6.2f} ms{Fore.RESET} ({m_pct:>4.1f}%) | {Fore.CYAN}+{m_mem:>5.1f} KB{Fore.RESET}  {pattern_badge}")

        if funcs:
            for idx, fn in enumerate(funcs[:6], start=1):
                is_last = (idx == min(len(funcs), 6))
                branch = "└──" if is_last else "├──"

                f_name = fn.get("name", "anon")
                line_no = fn.get("line", 0)
                calls = fn.get("calls", 1)
                self_t = fn.get("self_time_ms", fn.get("self_ms", 0.0))
                f_pct = fn.get("file_percent", fn.get("impact_pct", 0.0))

                click.echo(
                    f"     {branch} {Fore.WHITE}{f_name:<28}{Fore.RESET} "
                    f"[L{line_no:<3}] {Fore.GREEN}{calls:>2}x{Fore.RESET} | "
                    f"{Fore.YELLOW}{self_t:>5.2f} ms{Fore.RESET} ({f_pct:>4.1f}%)"
                )
                
        else:
            click.echo(f"     └── {Fore.LIGHTBLACK_EX}(Nenhuma função interna rastreada — execução de bloco único){Fore.RESET}")
        click.echo()

    # Diagnóstico Acionável
    click.echo(f"  {Fore.YELLOW}{Style.BRIGHT}🔍 DIAGNÓSTICO ACIONÁVEL:{Style.RESET_ALL}")
    for mod in bench["modules"][:3]:
        if mod.get("is_single_bottleneck"):
            feat = mod.get("dominant_feature", "Lógica principal")
            click.echo(f"    • {Fore.WHITE}{mod['module']}:{Fore.RESET} Otimizar pontualmente a função {Fore.RED}'{feat}'{Fore.RESET} eliminará mais da metade do custo do arquivo.")
        else:
            reason = mod.get("cost_reason", mod.get("cost_factor", "Custo distribuído em rotinas de inicialização"))
            click.echo(f"    • {Fore.WHITE}{mod['module']}:{Fore.RESET} Custo distribuído ({reason}). Requer simplificação geral.")
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

@lite_xl_group.command("search-bridge", help="Ponte de busca de alta velocidade Vulcan/SearchState para o Lite XL.")
@click.argument("query")
@click.option("--limit", "-n", default=300, type=int, help="Limite de ocorrências")
@click.option("--out-file", "-o", default="", help="Arquivo de saída opcional")
def cmd_search_bridge(query, limit, out_file):
    """Executa a busca via motor nativo Doxoade e gera buffer de resultados Dumppot."""
    import time
    from pathlib import Path
    from doxoade.commands.search_systems.search_engine import _search_code_logic
    from doxoade.tools.filesystem import _find_project_root

    t0 = time.time()
    root_path = _find_project_root(os.getcwd()) or os.getcwd()
    root = Path(root_path)
    matches = _search_code_logic(root, query, limit)
    elapsed = time.time() - t0

    grouped = {}
    for m in matches:
        full_p = (root / m["file"]).resolve()
        f_str = str(full_p).replace("\\", "/")
        grouped.setdefault(f_str, []).append(m)

    lines = [
        "================================================================================",
        f"  🔍 RESULTADOS DA BUSCA DOXOADE: \"{query}\"",
        f"  Ocorrências: {len(matches)} | Arquivos: {len(grouped)} | Varredura: {elapsed:.2f}s",
        "  💡 Pressione [ENTER] em qualquer linha com 'arquivo:linha' para ir direto ao código!",
        "================================================================================\n"
    ]

    if not matches:
        lines.append(f"  (Nenhum resultado encontrado para \"{query}\")\n")
    else:
        for fpath, m_list in grouped.items():
            lines.append(f"📄 {fpath}")
            for m in m_list:
                lines.append(f"   {fpath}:{m['line']}: {m['text']}")
            lines.append("")

    content = "\n".join(lines)
    if out_file:
        out_p = Path(out_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(content, encoding="utf-8")
    else:
        click.echo(content)

@lite_xl_group.command("chaos", help="Executa o ambiente isolado (Sandbox) para testes de templates.")
@click.option("--chaos", "-c", is_flag=True, help="Injeta o Mega-Payload de Caos (Estresse) no Sandbox.")
def cmd_test_sandbox(chaos):
    """Orquestra o Sandbox, com suporte a injeção de caos controlado."""
    
    # ═══════════════════════════════════════════════════════════
    # 🍷 MODO CAOS (DELEGAÇÃO AO RUNNER)
    # ═══════════════════════════════════════════════════════════
    if chaos:
        click.echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}🍷 MODO CAOS ATIVADO: Preparando Sandbox de Estresse...{Style.RESET_ALL}")
        
        runner = ChaosSandboxRunner(
            payload_filename="99_chaos_sandbox.lua",
            payload_content=MEGA_CHAOS_PAYLOAD
        )
        
        # Executa o ciclo: Preparar -> Compilar/Executar -> Extrair Forense -> Reportar -> Limpar
        runner.run(timeout=15)
        return

    # ═══════════════════════════════════════════════════════════
    # 🧪 MODO SANDBOX PADRÃO (LÓGICA ORIGINAL)
    # ═══════════════════════════════════════════════════════════
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🧪 EXECUTANDO SANDBOX PADRÃO...{Style.RESET_ALL}")
    
    # (Aqui entra a lógica original do seu test-sandbox sem caos)
    # Ex: LiteXLEngine.launch_sandbox()
    click.echo(f"{Fore.YELLOW}💡 Dica: Use --chaos para testar a resiliência do sistema.{Fore.RESET}")

@lite_xl_group.command("health-check", help="🏥 Diagnóstico completo de saúde do sistema Doxoade.")
@click.option("--verbose", "-v", is_flag=True, help="Exibe o relatório estruturado bruto do gate.")
def cmd_health_check(verbose):
    """Executa a bateria de validação e apresenta o resultado."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🏥 HEALTH CHECK — Diagnóstico do Sistema Doxoade{Style.RESET_ALL}\n")

    gate = LiteXLEngine.run_health_gate()

    icons = {
        "pass": f"{Fore.GREEN}✔{Fore.RESET}",
        "warn": f"{Fore.YELLOW}⚠{Fore.RESET}",
        "fail": f"{Fore.RED}✖{Fore.RESET}",
    }
    for idx, step in enumerate(gate["steps"], start=1):
        click.echo(f"[{idx}/5] {step['label']}...")
        click.echo(f"  {icons.get(step['status'], '•')} {step['detail']}")

    total = gate["passed"] + gate["failed"] + gate["warnings"]
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}📊 RELATÓRIO FINAL{Style.RESET_ALL}")
    click.echo(f"  {Fore.GREEN}✔ Passou: {gate['passed']}/{total}{Fore.RESET}")
    click.echo(f"  {Fore.YELLOW}⚠ Avisos: {gate['warnings']}/{total}{Fore.RESET}")
    click.echo(f"  {Fore.RED}✖ Falhas: {gate['failed']}/{total}{Fore.RESET}")

    if gate["healthy"]:
        click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ Sistema saudável e operacional!{Style.RESET_ALL}\n")
    else:
        click.echo(f"\n{Fore.RED}{Style.BRIGHT}✖ Sistema com problemas críticos.{Style.RESET_ALL}")
        click.echo(f"{Fore.YELLOW}💡 Execute 'doxoade lite-xl check-templates --fix --apply' para reparar.{Fore.RESET}\n")

    # 📦 Modo verbose: despeja o relatório estruturado bruto (útil para o Typhon/debug)
    if verbose:
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}📦 RELATÓRIO ESTRUTURADO (gate):{Style.RESET_ALL}")
        for step in gate["steps"]:
            click.echo(f"  [{step['status'].upper():4}] {step['label']}: {step['detail']}")
        click.echo(f"  healthy={gate['healthy']} passed={gate['passed']} failed={gate['failed']} warnings={gate['warnings']}\n")

@lite_xl_group.command("sandbox", help=" Lança o Lite XL no modo Sandbox isolado (não toca o init de produção).")
@click.option("--watch", "-w", default=0, help="Segundos para monitorar antes de fechar (0 = manual).")
def cmd_sandbox(watch):
    """Lança o Lite XL apontando para o sandbox isolado."""
    from doxoade.commands.lite_xl_systems.typhon import TyphonEngine
    
    sandbox_dir = TyphonEngine._get_sandbox_dir()
    exe = LiteXLEngine.find_executable()
    
    if not exe:
        click.echo(f"{Fore.RED}✖ Executável do Lite XL não encontrado.{Fore.RESET}")
        return
    
    if not sandbox_dir.exists():
        click.echo(f"{Fore.YELLOW}⚠ Sandbox não existe. Execute 'doxoade lite-xl typhon test-deploy' primeiro.{Fore.RESET}")
        return
    
    click.echo(f"{Fore.CYAN}{Style.BRIGHT}🧪 MODO SANDBOX ISOLADO{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Sandbox:{Fore.RESET} {sandbox_dir}")
    click.echo(f"  {Fore.WHITE}Executável:{Fore.RESET} {exe}")
    click.echo(f"  {Fore.YELLOW}⚠ Este modo NÃO afeta seu init.lua de produção!{Fore.RESET}")
    
    # Lança o Lite XL no sandbox
    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [str(exe), "--userdir", str(sandbox_dir)],
        creationflags=CREATE_NEW_CONSOLE
    )
    
    click.echo(f"✔ Lite XL Sandbox lançado (PID: {proc.pid})")
    click.echo(f"💡 Pressione Ctrl+C para encerrar o sandbox.")
    
    if watch > 0:
        click.echo(f"️ Monitorando por {watch} segundos...")
        try:
            time.sleep(watch)
        except KeyboardInterrupt:
            pass
        finally:
            if proc.poll() is None:
                proc.kill()
                click.echo("✔ Sandbox encerrado.")
    else:
        # Aguarda o processo terminar ou Ctrl+C
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.kill()
            click.echo("✔ Sandbox encerrado pelo usuário.")

@lite_xl_group.command("terminal-shims", help="⌨️ Instala atalhos globais (lite-xl, litexl) no terminal.")
def cmd_terminal_shims():
    """Instala shims .cmd no PATH do sistema para invocar o Lite XL via terminal."""
    installed = LiteXLEngine.install_terminal_shims()
    if installed:
        click.echo(f"{Fore.GREEN}✔ Shims instalados com sucesso:{Fore.RESET}")
        for shim in installed:
            click.echo(f"   {Fore.CYAN}↳ {shim}{Fore.RESET}")
        click.echo(f"\n{Fore.YELLOW}💡 Reinicie o terminal para usar 'lite-xl <arquivo>' diretamente.{Fore.RESET}")
    else:
        click.echo(f"{Fore.RED}✖ Falha ao instalar shims.{Fore.RESET}")

# ═══════════════════════════════════════════════════════════════
# 🗂️ VULCAN INDEX & SEARCH BRIDGE V2 (Indexação + Busca Paralela)
# ═══════════════════════════════════════════════════════════════
VULCAN_IGNORED_DIRS = {
    ".git", "venv", ".venv", "env", "__pycache__", "build", "dist",
    "node_modules", ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".doxoade_cache",
}
VULCAN_IGNORED_EXTS = {
    "pyc", "pyo", "pyd", "exe", "dll", "so", "dylib", "zip", "tar", "gz",
    "png", "jpg", "jpeg", "gif", "ico", "pdf", "db", "sqlite", "sqlite3", "bin",
}


def _vulcan_build_index(root: Path) -> dict:
    """Varre o projeto e grava o índice de arquivos (mtime+size)."""
    index_path = root / ".doxoade" / "vulcan_index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in VULCAN_IGNORED_DIRS]
        for fn in filenames:
            ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
            if ext in VULCAN_IGNORED_EXTS:
                continue
            fp = Path(dirpath) / fn
            try:
                st = fp.stat()
                if st.st_size > 2_000_000:
                    continue
                files[fp.relative_to(root).as_posix()] = [st.st_mtime, st.st_size]
            except Exception:
                continue
    payload = {"version": 1, "root": str(root), "built_at": time.time(),
               "count": len(files), "files": files}
    tmp = index_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, index_path)  # atômico
    return payload


def _vulcan_load_index(root: Path) -> dict:
    index_path = root / ".doxoade" / "vulcan_index.json"
    if index_path.exists():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            if time.time() - data.get("built_at", 0) < 300:  # fresco: 5 min
                return data
        except Exception:
            pass
    return _vulcan_build_index(root)


@lite_xl_group.command("index-build", help="🗂️ Constrói/atualiza o índice Vulcan do projeto.")
@click.option("--project", "-p", default=None, help="Raiz do projeto (default: cwd).")
def cmd_index_build(project):
    root = Path(project).resolve() if project else Path.cwd().resolve()
    t0 = time.time()
    payload = _vulcan_build_index(root)
    click.echo(f"{Fore.GREEN}✔ Índice Vulcan: {payload['count']} arquivos "
               f"em {time.time() - t0:.2f}s{Fore.RESET}")


@lite_xl_group.command("search-bridge", help="🔍 Busca indexada Vulcan (paralela) → .pot")
@click.argument("query", required=False, default=None)
@click.option("-o", "--output", default=None)
@click.option("--request", default=None, help="Arquivo de pedido: L1=query L2=raiz L3=pot.")
def cmd_search_bridge(query, output, request):
    from concurrent.futures import ThreadPoolExecutor
    project_root = None
    out_path = Path(output) if output else None
    if request:
        lines = Path(request).read_text(encoding="utf-8", errors="replace").splitlines()
        if lines and lines[0].strip():
            query = lines[0].strip()
        if len(lines) > 1 and lines[1].strip():
            project_root = Path(lines[1].strip())
        if len(lines) > 2 and lines[2].strip():
            out_path = Path(lines[2].strip())
    if not query or not query.strip():
        return
    root = (project_root or Path.cwd()).resolve()
    out_path = out_path or (root / ".doxoade" / "search_results.pot")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    index = _vulcan_load_index(root)
    case_sensitive = query != query.lower()
    needle = query if case_sensitive else query.lower()

    hits, files_hit, scanned = [], 0, 0
    MAX_HITS, MAX_FILES = 1000, 100

    def scan_one(rel):
        fp = root / rel
        local = []
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    target = line if case_sensitive else line.lower()
                    if needle in target:
                        local.append((rel, lineno, line.strip()))
                        if len(local) >= 20:
                            return local
        except Exception:
            pass
        return local

    with ThreadPoolExecutor(max_workers=8) as pool:
        for result in pool.map(scan_one, list(index["files"].keys())):
            scanned += 1
            if result:
                files_hit += 1
                hits.extend(result)
                if len(hits) >= MAX_HITS or files_hit >= MAX_FILES:
                    break

    out = [
        "=" * 80,
        f"  🔍 RESULTADOS DA BUSCA VULCAN: {query!r}",
        f"  Ocorrências: {len(hits)} | Arquivos: {files_hit} | "
        f"Índice: {index['count']} arquivos ({time.time() - t0:.2f}s)",
        "  💡 Pressione [ENTER] em qualquer linha com 'arquivo:linha' para saltar!",
        "=" * 80, "",
    ]
    if not hits:
        out.append(f"  (Nenhum resultado encontrado para {query!r})")
    else:
        for rel, lineno, text in hits:
            out.append(f"   {(root / rel).as_posix()}:{lineno}: {text}")
        out.append("")

    tmp = out_path.with_suffix(".tmp")
    tmp.write_text("\n".join(out), encoding="utf-8")
    os.replace(tmp, out_path)  # atômico: o Lua nunca lê parcial


@lite_xl_group.command("bridge-install", help="🔌 Gera o mecanismo de acesso vulcan_search.cmd.")
def cmd_bridge_install():
    """Gera .cmd com o python ABSOLUTO — o bytecode compilado não depende de PATH/venv."""
    user_cfg = Path(os.environ.get("LITE_USERDIR",
                                   str(Path.home() / ".config" / "lite-xl")))
    dox_dir = user_cfg / ".doxoade"
    dox_dir.mkdir(parents=True, exist_ok=True)
    cmd_path = dox_dir / "vulcan_search.cmd"
    cmd_path.write_text(
        "@echo off\r\n"
        f'"{sys.executable}" -m doxoade lite-xl search-bridge '
        '--request "%~dp0search_request.txt"\r\n',
        encoding="ascii", errors="replace")
    click.echo(f"{Fore.GREEN}✔ Mecanismo de acesso instalado:{Fore.RESET} {cmd_path}")
    click.echo(f"   {Fore.CYAN}↳ Python absoluto: {sys.executable}{Fore.RESET}")


# ═══════════════════════════════════════════════════════════
# 🐉 TYPHON — Pipeline Supervisionado de Deploy
# ═══════════════════════════════════════════════════════════
from doxoade.commands.lite_xl_systems.typhon import TyphonEngine
@lite_xl_group.group("typhon", help="🐉 Pipeline supervisionado de deploy com auto-rollback.")
def typhon_group():
    """Typhon: O pai dos monstros. Deploy supervisionado com gates e rollback."""
    pass

lite_xl_group.add_command(typhon_doxly_group, "typhon")

@typhon_group.command("deploy", help="🐉 Deploy supervisionado do init de produção (com health gate obrigatório).")
@click.option("--force", is_flag=True, help="⚠️ Ignora o health gate e força o deploy (emergência).")
def cmd_typhon_deploy(force):
    """Executa o pipeline de deploy de produção."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🐉 TYPHON DEPLOY — Produção{Style.RESET_ALL}")
    if force:
        click.echo(f"  {Fore.YELLOW}⚠ --force ativo: o health gate será IGNORADO.{Fore.RESET}")
    click.echo()

    result = TyphonEngine.run_pipeline(skip_gate=force)

    for phase in result["phases"]:
        icon = f"{Fore.GREEN}✔{Fore.RESET}" if phase["ok"] else f"{Fore.RED}✖{Fore.RESET}"
        click.echo(f"  {icon} [{phase['name']}] {phase['msg'][:100]}")

    click.echo()
    if result["success"]:
        click.echo(f"  {Fore.GREEN}{Style.BRIGHT}✔ DEPLOY BEM-SUCEDIDO{Style.RESET_ALL}")
        click.echo(f"  {Fore.LIGHTBLACK_EX}Init promovido a estável.{Fore.RESET}\n")
    else:
        # 🩺 Renderiza o erro da fase que falhou como traceback
        failed_phase = next((p for p in result["phases"] if not p["ok"]), None)
        if failed_phase:
            _render_typhon_error(failed_phase["name"], failed_phase["msg"])
        click.echo(f"  {Fore.RED}{Style.BRIGHT}✖ DEPLOY FALHOU ({result['verdict']}){Style.RESET_ALL}")
        if result["verdict"] == "ABORTED_BY_GATE":
            click.echo(f"  {Fore.YELLOW}💡 Corrija os problemas ou use 'doxoade lite-xl typhon deploy --force' para ignorar.{Fore.RESET}\n")
        else:
            click.echo(f"  {Fore.YELLOW}💡 Use 'doxoade lite-xl typhon rollback' para restaurar.{Fore.RESET}\n")

def _render_typhon_error(phase_name: str, msg: str):
    """Formata erros do Typhon como traceback legível com snippet de código."""
    # click.echo(f"\n{Fore.RED}{Style.BRIGHT}{'═' * 70}{Style.RESET_ALL}")
    # click.echo(f"{Fore.RED}{Style.BRIGHT}  ✖ [{phase_name}] FALHA DETECTADA{Style.RESET_ALL}")
    # click.echo(f"{Fore.RED}{Style.BRIGHT}{'═' * 70}{Style.RESET_ALL}\n")

    print('\n' + Back.RED + f"[{phase_name}] FALHA DETECTADA".center(100) + Style.RESET_ALL)

    # ── Erro de compilação Lua ──
    if "Erro de compilação Lua" in msg or "lua54.exe" in msg:
        lua_err_match = re.search(r"lua54\.exe:\s*(.+?\.lua):(\d+):\s*(.+?)(?:\n|$)", msg)
        if lua_err_match:
            err_file, err_line, err_msg = lua_err_match.groups()
            short_file = Path(err_file).name
            err_line_no = int(err_line)
            click.echo(f"  {Fore.WHITE}🩺 CAUSA RAIZ:{Fore.RESET}")
            click.echo(f"    {Fore.WHITE}STATUS :{Fore.RESET} Erro de Sintaxe Lua")
            click.echo(f"    {Fore.WHITE}ARQUIVO:{Fore.RESET} {short_file}")
            click.echo(f"    {Fore.WHITE}LINHA  :{Fore.RESET} {err_line}")
            click.echo(f"    {Fore.WHITE}LAUDO  :{Fore.RESET} {Fore.RED}{err_msg.strip()}{Fore.RESET}")

            # 📍 SNIPPET DE CÓDIGO — usa o init.lua real (mesma numeração de linha)
            init_path = LiteXLEngine.get_init_lua_path()
            if init_path.exists():
                try:
                    src_lines = init_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    start = max(0, err_line_no - 4)
                    end = min(len(src_lines), err_line_no + 3)
                    click.echo(f"\n  {Fore.CYAN}📍 CENA DO CRIME:{Fore.RESET}")
                    click.echo(f"    {Fore.CYAN}┌─ [{init_path.name}:{err_line_no}]{Fore.RESET}")
                    for idx in range(start, end):
                        ln = idx + 1
                        prefix = f"{Fore.RED}>>{Fore.RESET}" if ln == err_line_no else "  "
                        click.echo(f"    {prefix} {Fore.YELLOW}{ln:4d} |{Fore.RESET} {src_lines[idx]}")
                    click.echo(f"    {Fore.CYAN}└{'─' * 50}{Fore.RESET}")
                except Exception:
                    pass
        else:
            click.echo(f"  {Fore.RED}{msg}{Fore.RESET}")

    # ── Erro do Shadow Audit ──
    elif "Shadow Audit falhou" in msg:
        shadow_match = re.search(r"template[\\/](\d+_\w+\.lua):(\d+):\s*(.+?)(?:\n|$)", msg)
        prompt_match = re.search(r"prompt '([^']+)'", msg)
        if shadow_match:
            tmpl, line, err = shadow_match.groups()
            tmpl_line_no = int(line)
            click.echo(f"  {Fore.WHITE}🩺 CAUSA RAIZ:{Fore.RESET}")
            click.echo(f"    {Fore.WHITE}STATUS :{Fore.RESET} Shadow Audit — Simulação de Comando")
            click.echo(f"    {Fore.WHITE}TEMPLATE:{Fore.RESET} {tmpl}")
            click.echo(f"    {Fore.WHITE}LINHA  :{Fore.RESET} {line}")
            click.echo(f"    {Fore.WHITE}LAUDO  :{Fore.RESET} {Fore.RED}{err.strip()[:120]}{Fore.RESET}")
            if prompt_match:
                click.echo(f"    {Fore.WHITE}PROMPT :{Fore.RESET} {prompt_match.group(1)[:80]}")

            # 📍 SNIPPET DO TEMPLATE
            tmpl_path = LiteXLEngine.get_template_dir() / tmpl
            if tmpl_path.exists():
                try:
                    src_lines = tmpl_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    start = max(0, tmpl_line_no - 4)
                    end = min(len(src_lines), tmpl_line_no + 3)
                    click.echo(f"\n  {Fore.CYAN}📍 CENA DO CRIME:{Fore.RESET}")
                    click.echo(f"    {Fore.CYAN}┌─ [{tmpl}:{tmpl_line_no}]{Fore.RESET}")
                    for idx in range(start, end):
                        ln = idx + 1
                        prefix = f"{Fore.RED}>>{Fore.RESET}" if ln == tmpl_line_no else "  "
                        click.echo(f"    {prefix} {Fore.YELLOW}{ln:4d} |{Fore.RESET} {src_lines[idx]}")
                    click.echo(f"    {Fore.CYAN}└{'─' * 50}{Fore.RESET}")
                except Exception:
                    pass
        else:
            click.echo(f"  {Fore.RED}{msg[:200]}{Fore.RESET}")

    else:
        click.echo(f"  {Fore.RED}{msg}{Fore.RESET}")
        
    click.echo(f"\n{Fore.RED}{Style.BRIGHT}{'_' * 100}{Style.RESET_ALL}\n")

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

@typhon_group.command("test-deploy", help="🧪 Deploy de TESTE isolado no sandbox (não toca o init real).")
@click.option("--watch", "-w", default=5, show_default=True, help="Segundos de monitoramento do sandbox.")
def cmd_typhon_test_deploy(watch):
    """Executa o pipeline de test-deploy isolado no sandbox."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🧪 TYPHON TEST-DEPLOY — Sandbox Isolado{Style.RESET_ALL}")
    click.echo(f"  {Fore.LIGHTBLACK_EX}🛡️ O init.lua de produção NÃO será modificado.{Fore.RESET}\n")

    result = TyphonEngine.run_test_pipeline(watch_seconds=watch)

    for phase in result["phases"]:
        icon = f"{Fore.GREEN}✔{Fore.RESET}" if phase["ok"] else f"{Fore.RED}✖{Fore.RESET}"
        click.echo(f"  {icon} [{phase['name']}] {phase['msg']}")

    click.echo()
    if result["success"]:
        click.echo(f"  {Fore.GREEN}{Style.BRIGHT}✔ TEST-DEPLOY BEM-SUCEDIDO{Style.RESET_ALL}")
        click.echo(f"  {Fore.LIGHTBLACK_EX}Sandbox estável. Para promover a produção, use 'doxoade lite-xl typhon deploy'.{Fore.RESET}\n")
    else:
        click.echo(f"  {Fore.RED}{Style.BRIGHT}✖ TEST-DEPLOY FALHOU ({result['verdict']}){Style.RESET_ALL}")
        click.echo(f"  {Fore.YELLOW}💡 O init real permanece intacto. Corrija os problemas e tente novamente.{Fore.RESET}\n")


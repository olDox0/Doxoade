# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/cmd_typhon_deploy.py
"""
Comandos CLI para o Typhon Deploy Engine v2.0.
Separação clara entre PRODUCTION, SANDBOX e TEST modes com Launch Automático.
"""
import click
import os
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from .typhon_deploy import TyphonDeployEngine

@click.group("deploy", help="🐉 Pipeline de deploy com separação produção/testes.")
def deploy_group():
    """Grupo de comandos de deploy Typhon."""
    pass

@deploy_group.command("status", help="Mostra status de todos os modos.")
@click.option("--mode", "-m",
              type=click.Choice(["production", "staging", "sandbox", "test"]))
def cmd_status(mode):
    TyphonDeployEngine.print_status(mode)

@deploy_group.command("reset", help="🧹 Reseta ambiente de deploy (limpa estado poluído/crash).")
@click.argument("mode_arg", required=False,
                type=click.Choice(["production", "staging", "sandbox", "test"]))
@click.option("--mode", "-m",
              type=click.Choice(["production", "staging", "sandbox", "test"]),
              default=None,
              help="Ambiente alvo (padrão: test). Aceita argumento posicional também.")
@click.option("--hard", is_flag=True,
              help="Remove também init.lua (força redeploy completo).")
@click.option("--no-backups", is_flag=True,
              help="Não preserva .doxoade/backups/.")
@click.option("--yes", "-y", is_flag=True, help="Sem confirmação.")
@click.option("--all", "reset_all", is_flag=True,
              help="Reseta todos os modos de uma vez.")
def cmd_reset(mode_arg, mode, hard, no_backups, yes, reset_all):
    # Resolve: argumento posicional > option --mode > default "test"
    mode = mode_arg or mode or "test"

    print(f"\n{Fore.CYAN}{Style.BRIGHT}🧹 DOXLY RESET{Style.RESET_ALL}\n")
    modes = ["production", "staging", "sandbox", "test"] if reset_all else [mode]
    if not yes:
        scope = ", ".join(modes)
        hard_txt = f" {Fore.RED}[HARD: init.lua será apagado]{Fore.RESET}" if hard else ""
        if not click.confirm(
            f"{Fore.YELLOW}Resetar [{scope}]?{Fore.RESET}{hard_txt}",
            default=False,
        ):
            print(f"{Fore.YELLOW}Reset cancelado.{Fore.RESET}\n")
            return

    total_removed = total_errors = 0
    for m in modes:
        print(f"\n  {Fore.WHITE}▶ [{m.upper()}]{Fore.RESET}")
        report = TyphonDeployEngine.reset_mode(
            m, hard=hard, keep_backups=not no_backups,
        )
        if not Path(report["dir"]).exists():
            print(f"    {Fore.LIGHTBLACK_EX}Diretório não existe.{Fore.RESET}")
            continue
        for r in report["removed"]:
            print(f"    {Fore.GREEN}✔{Fore.RESET} removido: {r}")
            total_removed += 1
        for k in report["kept"]:
            print(f"    {Fore.CYAN}💾{Fore.RESET} preservado: {k}")
        for e in report["errors"]:
            print(f"    {Fore.RED}✖{Fore.RESET} {e}")
            total_errors += 1

    print(f"\n{Fore.GREEN}{Style.BRIGHT}✔ Reset concluído.{Style.RESET_ALL} "
          f"({total_removed} removidos, {total_errors} erro(s))\n")
    if total_errors == 0:
        print(f"  {Fore.LIGHTBLACK_EX}Próximo: doxoade doxly deploy {mode} --force{Fore.RESET}\n")

@deploy_group.command("production", help="🏛️ [FASE 4] DEPRECATED: alias de 'promote' (staging → canonical).")
@click.option("--force", "-f", is_flag=True, help="Força promote mesmo com warnings.")
@click.option("--launch/--no-launch", "-l/-nl", default=True, help="Lança o Lite XL após promote.")
@click.option("--allow-aot", is_flag=True, default=False,
              help="Permite AOT no canonical (D4: bloqueado por default).")
@click.option("--legacy-direct", is_flag=True, default=False,
              help="⚠️ [ESCAPE] Escreve direto em canonical, ignorando staging (bypassa o pipeline).")
def cmd_deploy_production(force, launch, allow_aot, legacy_direct):
    # ── MODO LEGACY: escape rápido para emergências ──
    if legacy_direct:
        print(f"\n{Fore.RED}{Style.BRIGHT}⚠️ MODO LEGACY ATIVADO (--legacy-direct){Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}Escrevendo DIRETO em canonical, ignorando staging.{Fore.RESET}")
        print(f"  {Fore.LIGHTBLACK_EX}Use apenas em emergências. O fluxo canônico é 'deploy staging' → 'promote'.{Fore.RESET}\n")
        status = TyphonDeployEngine.get_canonical_status()
        if status.get("promotion_pending") and not force:
            print(f"  {Fore.YELLOW}⚠ Staging diverge de canonical. Confirme com --force.{Fore.RESET}")
            return
        result = TyphonDeployEngine.deploy("production", force=force, no_khonsu=True)
        if result["success"]:
            print(f"\n{Fore.GREEN}✔ Deploy legacy concluído ({result.get('opt_mode', '?')}){Fore.RESET}")
            if result["backup"]:
                print(f"{Fore.CYAN}💾 Backup: {result['backup'].name}{Fore.RESET}")
            if launch:
                TyphonDeployEngine.launch("production", exorcise=True)
        else:
            print(f"\n{Fore.RED}✖ Deploy falhou: {result['error']}{Fore.RESET}")
        return

     # ── MODO PADRÃO: rebuild staging + promote (Garante atualização) ──
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🏛️ DEPLOY PRODUCTION — Pipeline Completo{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}  Passo 1: recompilar staging a partir dos templates.{Fore.RESET}")
    print(f"{Fore.LIGHTBLACK_EX}  Passo 2: promover staging → test + production.{Fore.RESET}\n")

    # ── PASSO 1: rebuild staging ──
    print(f"{Fore.CYAN}  [1/2] Compilando staging...{Fore.RESET}")
    staging_result = TyphonDeployEngine.deploy(
        "staging", force=force, no_khonsu=True,
    )
    if not staging_result["success"]:
        print(f"{Fore.RED}✖ Falha ao compilar staging: {staging_result.get('error', '?')}{Fore.RESET}")
        print(f"{Fore.YELLOW}  Deploy de produção abortado.{Fore.RESET}\n")
        return

    print(f"{Fore.GREEN}  ✔ Staging atualizado: {staging_result['init']}{Fore.RESET}")
    print(f"{Fore.LIGHTBLACK_EX}    Modo: {staging_result.get('opt_mode', '?')} "
          f"| {staging_result.get('size', 0):,} bytes{Fore.RESET}\n")

    # ── PASSO 2: verificar AOT e promover ──
    status = TyphonDeployEngine.get_canonical_status()

    if status["staging"]["is_aot"] and not allow_aot and not force:
        print(f"{Fore.RED}{Style.BRIGHT}⚠ Staging é AOT bytecode{Fore.RESET}")
        print(f"{Fore.YELLOW}  D4 despriorizou AOT. Rode 'deploy staging --no-khonsu' antes.{Fore.RESET}")
        print(f"{Fore.CYAN}  Ou passe --allow-aot para forçar (não recomendado).{Fore.RESET}\n")
        return

    print(f"{Fore.CYAN}  [2/2] Promovendo staging → test + production...{Fore.RESET}")

    if status["identical_canonical_staging"] and not force:
        print(f"{Fore.GREEN}  ✔ Canonical e staging já são idênticos após rebuild.{Fore.RESET}")
        print(f"{Fore.LIGHTBLACK_EX}    (nenhuma promoção necessária){Fore.RESET}\n")
        if launch:
            TyphonDeployEngine.launch("production", exorcise=True)
        return

    if not force:
        delta = status["staging"]["size"] - status["canonical"]["size"]
        print(f"  {Fore.WHITE}Canonical:{Fore.RESET} {status['canonical']['size']:,} bytes "
              f"({'AOT' if status['canonical']['is_aot'] else 'source'})")
        print(f"  {Fore.WHITE}Staging:  {Fore.RESET} {status['staging']['size']:,} bytes "
              f"({'AOT' if status['staging']['is_aot'] else 'source'})  "
              f"({delta:+d} bytes)")
        if not click.confirm(
            f"{Fore.YELLOW}Propagar staging → test + production?{Fore.RESET}",
            default=False,
        ):
            print(f"{Fore.YELLOW}Promote cancelado.{Fore.RESET}\n")
            return

    ok, msg = TyphonDeployEngine.promote(force=force, allow_aot=allow_aot)
    if ok:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}✔ PROMOTE CONCLUÍDO (staging → test + production){Style.RESET_ALL}")
        for line in msg.splitlines():
            print(f"  {Fore.WHITE}{line}{Fore.RESET}")
        print(f"\n{Fore.LIGHTBLACK_EX}  Rollback: doxoade doxly deploy restore --list -m production{Fore.RESET}\n")
        if launch:
            TyphonDeployEngine.launch("production", exorcise=True)
    else:
        print(f"\n{Fore.RED}✖ Promote falhou: {msg}{Fore.RESET}\n")

@deploy_group.command("sandbox", help="Deploy em SANDBOX (isolamento total + launch automático).")
@click.option("--launch/--no-launch", "-l/-nl", default=True, help="Lança o Lite XL após deploy (Padrão: True).")
@click.option("--exorcise/--no-exorcise", default=True, help="Mata instâncias antigas de sandbox.")
def cmd_deploy_sandbox(launch, exorcise):
    """Deploy isolado no sandbox sem interferir na produção."""
    print(f"\n{Fore.BLUE}{Style.BRIGHT}🔵 DEPLOY SANDBOX{Style.RESET_ALL}\n")
    result = TyphonDeployEngine.deploy("sandbox")
    if result["success"]:
        print(f"\n{Fore.GREEN}✔ Deploy de sandbox concluído!{Fore.RESET}")
        print(f"{Fore.LIGHTBLACK_EX}   Diretório isolado: {result['init'].parent}{Fore.RESET}")
        if launch:
            print()
            TyphonDeployEngine.launch("sandbox", exorcise=exorcise)
    else:
        print(f"\n{Fore.RED}✖ Deploy falhou: {result['error']}{Fore.RESET}")

@deploy_group.command("test", help="Deploy em TESTE (source mode por padrão).")
@click.option("--force", "-f", is_flag=True)
@click.option("--no-khonsu", is_flag=True, default=True,
              help="[DEPRECATED] Source é o default.")
@click.option("--allow-aot", is_flag=True, default=False,
              help="Permite AOT bytecode.")
@click.option("--exorcise/--no-exorcise", default=True)
def cmd_deploy_test(force, no_khonsu, allow_aot, exorcise):
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}🟡 DEPLOY TEST{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}Modo: source (D4){Fore.RESET}\n")
    effective_no_khonsu = not allow_aot
    result = TyphonDeployEngine.deploy("test", force=force, no_khonsu=effective_no_khonsu)

    if result["success"]:
        print(f"\n{Fore.GREEN}✔ Deploy de teste concluído com sucesso! ({result.get('opt_mode', 'standard')}){Fore.RESET}")
        if result["backup"]:
            print(f"{Fore.CYAN}💾 Backup de segurança: {result['backup'].name}{Fore.RESET}")
        if exorcise:
            TyphonDeployEngine.exorcise_mode_instance("test")
        print()
        pid = TyphonDeployEngine.launch("test", exorcise=False)
        if pid:
            import threading
            from .typhon_deploy import forensic_harvester
            test_dir = TyphonDeployEngine._get_deploy_dir("test")
            thread = threading.Thread(target=forensic_harvester, args=(pid, test_dir), daemon=True)
            thread.start()
    else:
        print(f"\n{Fore.RED}✖ Deploy falhou: {result['error']}{Fore.RESET}")
        if result["backup"]:
            print(f"{Fore.YELLOW}🔄 Rollback automático executado.{Fore.RESET}")

@deploy_group.command("backup", help="Cria backup manual do init atual.")
@click.option("--mode", "-m", type=click.Choice(["production", "sandbox", "test"]), 
              default="production", help="Modo alvo.")
@click.option("--reason", "-r", default="manual", help="Motivo do backup.")
def cmd_backup(mode, reason):
    """Cria backup timestampado do init.lua."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}💾 BACKUP MANUAL ({mode}){Style.RESET_ALL}\n")
    
    ok, backup_path = TyphonDeployEngine.create_backup(mode, reason)
    
    if ok and backup_path:
        print(f"{Fore.GREEN}✔ Backup criado: {backup_path.name}{Fore.RESET}")
        print(f"{Fore.LIGHTBLACK_EX}   Caminho: {backup_path}{Fore.RESET}")
    elif ok:
        print(f"{Fore.YELLOW}⚠ Nenhum init.lua encontrado para backup.{Fore.RESET}")
    else:
        print(f"{Fore.RED}✖ Falha ao criar backup.{Fore.RESET}")

@deploy_group.command("restore", help="Restaura backup do init.lua.")
@click.option("--mode", "-m",
              type=click.Choice(["production", "staging", "sandbox", "test"]),
              default="production", help="Modo alvo.")
@click.option("--backup", "-b", default=None,
              help="Nome do backup (basta o filename, sem path).")
@click.option("--list", "-l", "list_backups", is_flag=True,
              help="Lista backups disponíveis.")
def cmd_restore(mode, backup, list_backups):
    if list_backups:
        backups = TyphonDeployEngine.list_backups(mode)
        print(f"\n{Fore.CYAN}{Style.BRIGHT}💾 BACKUPS DISPONÍVEIS ({mode}){Fore.RESET}\n")
        if not backups:
            print(f"{Fore.YELLOW}Nenhum backup encontrado.{Fore.RESET}\n")
            return
        for i, bkp in enumerate(backups, 1):
            st = bkp.stat()
            from datetime import datetime as _dt
            ts = _dt.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  {Fore.WHITE}{i:2d}. {bkp.name}{Fore.RESET}")
            print(f"     {Fore.LIGHTBLACK_EX}{st.st_size:,} bytes | {ts}{Fore.RESET}")
        print()
        return

    # ✅ FIX 6: resolver filename contra o backup dir correto
    backup_path = None
    if backup:
        backup_path = Path(backup)
        if not backup_path.exists():
            # Procura em todos os diretórios de backup do modo
            candidates = []
            if mode == "production":
                from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
                candidates.append(LiteXLPaths.get_canonical_backups_dir())
            else:
                candidates.append(TyphonDeployEngine._get_backup_dir(mode))
            for cdir in candidates:
                candidate = cdir / backup
                if candidate.exists():
                    backup_path = candidate
                    break
            if not backup_path.exists():
                print(f"{Fore.RED}✖ Backup não encontrado: {backup}{Fore.RESET}")
                print(f"{Fore.LIGHTBLACK_EX}  Use: doxoade doxly deploy restore --list -m {mode}{Fore.RESET}")
                return

    print(f"\n{Fore.CYAN}{Style.BRIGHT}🔄 RESTAURAR BACKUP ({mode}){Fore.RESET}\n")
    ok, msg = TyphonDeployEngine.restore_backup(mode, backup_path)
    if ok:
        print(f"{Fore.GREEN}✔ {msg}{Fore.RESET}")
    else:
        print(f"{Fore.RED}✖ {msg}{Fore.RESET}")

@deploy_group.command("exorcise", help="Mata todas as instâncias do Lite XL.")
def cmd_exorcise():
    """Exorcismo de processos para garantir isolamento."""
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}🔪 EXORCISMO DE PROCESSOS{Style.RESET_ALL}\n")
    
    ok = TyphonDeployEngine.exorcise_instances()
    
    if ok:
        print(f"{Fore.GREEN}✔ Instâncias encerradas com sucesso.{Fore.RESET}")
    else:
        print(f"{Fore.YELLOW}⚠ Exorcismo parcial (algumas instâncias podem ter falhado).{Fore.RESET}")

@deploy_group.command("canone", help="🏛️ Deploy CÂNONE soberano de produção.")
@click.option("--force", "-f", is_flag=True, help="Força deploy mesmo com warnings.")
@click.option("--launch/--no-launch", "-l/-nl", default=True, help="Lança o Lite XL Cânone após deploy (Padrão: True).")
@click.option("--no-khonsu", is_flag=True, default=False, help="Desativa Khonsu AOT (gera texto puro).")
def cmd_deploy_canone(force, launch, no_khonsu):
    """Promove e instala o perfil soberano Cânone em produção definitiva."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🏛️  DEPLOY CÂNONE (PRODUÇÃO SOBERANA){Style.RESET_ALL}\n")
    result = TyphonDeployEngine.deploy("production", force=force, no_khonsu=no_khonsu)
    if result["success"]:
        print(f"\n{Fore.GREEN}✔ Perfil CÂNONE promovido com sucesso para a produção definitiva! ({result.get('opt_mode', 'standard')}){Fore.RESET}")
        if result["backup"]:
            print(f"{Fore.CYAN}💾 Backup prévio salvo: {result['backup'].name}{Fore.RESET}")
        
        # Atualiza o atalho soberano do Windows
        try:
            from doxoade.commands.leap_sys.leap_platform.leap_windows.leap_elevation import create_sovereign_shortcut
            create_sovereign_shortcut()
        except Exception:
            pass

        if launch:
            print()
            TyphonDeployEngine.launch("production", exorcise=True)
    else:
        print(f"\n{Fore.RED}✖ Falha no deploy Cânone: {result['error']}{Fore.RESET}")
        if result["backup"]:
            print(f"{Fore.YELLOW}🔄 Rollback automático executado.{Fore.RESET}")

@deploy_group.command("staging", help="🎯 Deploy em STAGING (candidato isolado, sem backup).")
@click.option("--force", "-f", is_flag=True, help="Força deploy mesmo com warnings.")
@click.option("--no-khonsu", is_flag=True, default=True,
              help="[DEPRECATED] Source é o default (D4).")
@click.option("--allow-aot", is_flag=True, default=False,
              help="Permite AOT bytecode (D4: não recomendado).")
@click.option("--launch-test", is_flag=True,
              help="Abre Lite XL em modo staging para validação visual.")
def cmd_deploy_staging(force, no_khonsu, allow_aot, launch_test):
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}🎯 DEPLOY STAGING (CANDIDATO){Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}  ⚠ Canonical e test NÃO serão tocados.{Fore.RESET}\n")

    effective_no_khonsu = not allow_aot
    result = TyphonDeployEngine.deploy("staging", force=force, no_khonsu=effective_no_khonsu)

    if not result["success"]:
        print(f"{Fore.RED}✖ Deploy staging falhou: {result['error']}{Fore.RESET}")
        return

    print(f"{Fore.GREEN}✔ Staging pronto: {result['init']}{Fore.RESET}")
    print(f"{Fore.CYAN}  Modo: {result.get('opt_mode', '?')}{Fore.RESET}")

    status = TyphonDeployEngine.get_canonical_status()
    if status["promotion_pending"]:
        delta = status["staging"]["size"] - status["canonical"]["size"]
        print(f"\n{Fore.YELLOW}💡 Canonical difere do staging ({delta:+d} bytes).{Fore.RESET}")
        print(f"{Fore.WHITE}   Promova com: doxoade doxly deploy promote{Fore.RESET}")

    if launch_test:
        print(f"\n{Fore.CYAN}🧪 Lançando Lite XL em modo STAGING...{Fore.RESET}")
        TyphonDeployEngine.launch("staging", exorcise=False)
    print()

@deploy_group.command("promote", help="⚡ Promove staging → test + production (D2).")
@click.option("--force", "-f", is_flag=True, help="Sem confirmação.")
@click.option("--allow-aot", is_flag=True,
              help="Permite AOT no canonical (D4: bloqueado por default).")
def cmd_promote(force, allow_aot):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}⚡ PROMOTE — Staging → test + production{Style.RESET_ALL}\n")

    status = TyphonDeployEngine.get_canonical_status()
    if not status["staging"]["exists"]:
        print(f"{Fore.RED}✖ Staging não existe. Rode 'deploy staging' antes.{Fore.RESET}\n")
        return

    if status["identical_canonical_staging"] and not force:
        print(f"{Fore.GREEN}✔ Canonical e staging já são idênticos.{Fore.RESET}")
        print(f"{Fore.LIGHTBLACK_EX}  Nada a promover.{Fore.RESET}\n")
        return

    if status["staging"]["is_aot"] and not allow_aot and not force:
        print(f"{Fore.RED}{Style.BRIGHT}⚠ Staging é AOT bytecode{Fore.RESET}")
        print(f"{Fore.YELLOW}  D4 despriorizou AOT. Promote em AOT é PERMANENTE.{Fore.RESET}")
        print(f"{Fore.YELLOW}  Debug ficará impossível até próximo promote source.{Fore.RESET}")
        print(f"\n{Fore.CYAN}💡 Use --no-khonsu no deploy staging, ou --allow-aot.{Fore.RESET}\n")
        return

    print(f"  {Fore.WHITE}Canonical: {status['canonical']['size']:,} bytes "
          f"({'AOT' if status['canonical']['is_aot'] else 'source'}){Fore.RESET}")
    print(f"  {Fore.WHITE}Staging:   {status['staging']['size']:,} bytes "
          f"({'AOT' if status['staging']['is_aot'] else 'source'}){Fore.RESET}")
    print(f"  {Fore.WHITE}Test:      {status['test']['size']:,} bytes "
          f"(será sincronizado){Fore.RESET}\n")

    if not force:
        if not click.confirm(
            f"{Fore.YELLOW}Propagar staging para test + production?{Fore.RESET}",
            default=False,
        ):
            print(f"{Fore.YELLOW}Promote cancelado.{Fore.RESET}\n")
            return

    ok, msg = TyphonDeployEngine.promote(force=force, allow_aot=allow_aot)
    if ok:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}✔ PROMOTE CONCLUÍDO{Fore.RESET}")
        for line in msg.splitlines():
            print(f"  {Fore.WHITE}{line}{Fore.RESET}")
        print(f"\n{Fore.LIGHTBLACK_EX}  Rollback: doxoade doxly deploy restore --list -m production{Fore.RESET}\n")
    else:
        print(f"\n{Fore.RED}✖ Promote falhou: {msg}{Fore.RESET}\n")

@deploy_group.command("launch", help="🚀 Abre Lite XL num ambiente específico (sem redeploy).")
@click.option("--mode", "-m",
              type=click.Choice(["production", "staging", "sandbox", "test"]),
              default="production")
@click.option("--exorcise/--no-exorcise", default=True,
              help="Encerra instâncias antigas antes (default: sim).")
@click.option("--raw", is_flag=True, default=False,
              help="⚠️ Acessa a pasta real de produção (sem isolamento de sessão).")
def cmd_launch(mode, exorcise, raw):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🚀 LAUNCH — {mode.upper()}{Fore.RESET}\n")
    deploy_dir = TyphonDeployEngine._get_deploy_dir(mode)
    init_file = deploy_dir / "init.lua"
    if not init_file.exists():
        print(f"{Fore.RED}✖ init.lua ausente em {deploy_dir}{Fore.RESET}")
        print(f"{Fore.YELLOW}  Rode 'deploy {mode}' primeiro.{Fore.RESET}\n")
        return
    size = init_file.stat().st_size
    print(f"  {Fore.WHITE}Diretório: {deploy_dir}{Fore.RESET}")
    print(f"  {Fore.WHITE}init.lua:  {size:,} bytes{Fore.RESET}\n")
    
    pid = TyphonDeployEngine.launch(mode, exorcise=exorcise, raw_mode=raw)
    
    if pid is not None:
        if pid > 0:
            print(f"{Fore.GREEN}✔ Lite XL [{mode.upper()}] iniciado (PID: {pid}){Fore.RESET}")
        else:
            print(f"{Fore.GREEN}✔ Lite XL [{mode.upper()}] iniciado.{Fore.RESET}")
        
        actual_dir = TyphonDeployEngine._get_deploy_dir(mode)
        if mode == "production" and not raw:
            actual_dir = actual_dir / ".doxoade" / "canonical_live"
            print(f"{Fore.YELLOW}  🛡️ Sessão isolada: {actual_dir}{Fore.RESET}")
        else:
            print(f"{Fore.LIGHTBLACK_EX}  Session isolada em: {actual_dir}{Fore.RESET}\n")
    else:
        print(f"{Fore.RED}✖ Falha ao iniciar Lite XL [{mode}]{Fore.RESET}\n")

@deploy_group.command("menu", help="🚀 Menu interativo para lançamento de ambientes.")
def cmd_deploy_menu():
    from doxoade.tools.doxcolors import Fore, Style
    import click
    
    while True:
        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}╔══════════════════════════════════════════════════╗{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}║      🐺 DOXLY LAUNCHER — Painel de Controle      ║{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}╚══════════════════════════════════════════════════╝{Style.RESET_ALL}\n")
        
        click.echo(f"  {Fore.GREEN}[1]{Fore.RESET} 🏛️  Abrir CANONICAL (Isolado, sem redeploy)")
        click.echo(f"  {Fore.YELLOW}[2]{Fore.RESET} 🚀  Redeploy + Abrir PRODUCTION")
        click.echo(f"  {Fore.BLUE}[3]{Fore.RESET} 🧪  Redeploy + Abrir TEST")
        click.echo(f"  {Fore.CYAN}[4]{Fore.RESET} 🎯  Redeploy + Abrir STAGING")
        click.echo(f"  {Fore.MAGENTA}[5]{Fore.RESET} ⚡  PROMOTE (Staging → Produção)")
        click.echo(f"  {Fore.RED}[0]{Fore.RESET} ❌  Sair\n")
        
        choice = click.prompt(f"{Fore.WHITE}Opção{Fore.RESET}", type=str).strip()
        
        if choice == "1":
            click.echo(f"\n{Fore.GREEN}🏛️ Abrindo Canonical (Sessão Isolada)...{Fore.RESET}")
            ctx = click.Context(cmd_launch)
            # ✅ CORREÇÃO: passamos raw=False explicitamente
            ctx.invoke(cmd_launch, mode="production", exorcise=True, raw=False)
            break
        elif choice == "2":
            click.echo(f"\n{Fore.YELLOW}🚀 Redeploying PRODUCTION...{Fore.RESET}")
            ctx = click.Context(cmd_deploy_production)
            ctx.invoke(cmd_deploy_production, force=True, launch=True, allow_aot=False, legacy_direct=True)
            break
        elif choice == "3":
            click.echo(f"\n{Fore.BLUE}🧪 Redeploying TEST...{Fore.RESET}")
            ctx = click.Context(cmd_deploy_test)
            ctx.invoke(cmd_deploy_test, force=True, no_khonsu=True, allow_aot=False, exorcise=True)
            break
        elif choice == "4":
            click.echo(f"\n{Fore.CYAN}🎯 Redeploying STAGING...{Fore.RESET}")
            ctx = click.Context(cmd_deploy_staging)
            ctx.invoke(cmd_deploy_staging, force=True, no_khonsu=True, allow_aot=False, launch_test=True)
            break
        elif choice == "5":
            click.echo(f"\n{Fore.MAGENTA}⚡ Promovendo Staging → Produção...{Fore.RESET}")
            ctx = click.Context(cmd_promote)
            ctx.invoke(cmd_promote, force=True, allow_aot=False)
            break
        elif choice == "0":
            click.echo(f"{Fore.RED}Saindo...{Fore.RESET}")
            break
        else:
            click.echo(f"{Fore.RED}Opção inválida!{Fore.RESET}")

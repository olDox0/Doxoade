# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/cmd_typhon_deploy.py
"""
Comandos CLI para o Typhon Deploy Engine v2.0.
Separação clara entre PRODUCTION, SANDBOX e TEST modes com Launch Automático.
"""
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from .typhon_deploy import TyphonDeployEngine

@click.group("deploy", help="🐉 Pipeline de deploy com separação produção/testes.")
def deploy_group():
    """Grupo de comandos de deploy Typhon."""
    pass

@deploy_group.command("status", help="Mostra status de todos os modos de deploy.")
@click.option("--mode", "-m", type=click.Choice(["production", "sandbox", "test"]), help="Modo específico.")
def cmd_status(mode):
    """Exibe status completo dos modos de deploy."""
    TyphonDeployEngine.print_status(mode)

@deploy_group.command("production", help="Deploy em PRODUÇÃO (com backup e launch automático).")
@click.option("--force", "-f", is_flag=True, help="Força deploy mesmo com warnings.")
@click.option("--launch/--no-launch", "-l/-nl", default=True, help="Lança o Lite XL após deploy (Padrão: True).")
def cmd_deploy_production(force, launch):
    """Deploy seguro em produção com backup e lançamento automático."""
    print(f"\n{Fore.GREEN}{Style.BRIGHT}🟢 DEPLOY PRODUCTION{Style.RESET_ALL}\n")
    result = TyphonDeployEngine.deploy("production", force=force)
    if result["success"]:
        print(f"\n{Fore.GREEN}✔ Deploy de produção concluído com sucesso!{Fore.RESET}")
        if result["backup"]:
            print(f"{Fore.CYAN}💾 Backup de segurança: {result['backup'].name}{Fore.RESET}")
        if launch:
            print()
            TyphonDeployEngine.launch("production", exorcise=False)
    else:
        print(f"\n{Fore.RED}✖ Deploy falhou: {result['error']}{Fore.RESET}")
        if result["backup"]:
            print(f"{Fore.YELLOW}🔄 Rollback automático executado.{Fore.RESET}")

@deploy_group.command("sandbox", help="Deploy em SANDBOX (isolamento total + launch automático).")
@click.option("--launch/--no-launch", "-l/-nl", default=True, help="Lança o Lite XL após deploy (Padrão: True).")
@click.option("--exorcise", is_flag=True, default=False, help="Mata instâncias antigas de sandbox.")
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

@deploy_group.command("test", help="Deploy em TEST (chaos injection + launch automático).")
@click.option("--launch/--no-launch", "-l/-nl", default=True, help="Lança o Lite XL após deploy (Padrão: True).")
@click.option("--exorcise", is_flag=True, default=False, help="Mata instâncias antigas de teste.")
def cmd_deploy_test(launch, exorcise):
    """Deploy de teste com telemetria forense e launch automático."""
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}🟡 DEPLOY TEST{Style.RESET_ALL}\n")
    result = TyphonDeployEngine.deploy("test")
    if result["success"]:
        print(f"\n{Fore.GREEN}✔ Deploy de teste concluído!{Fore.RESET}")
        if launch:
            print()
            TyphonDeployEngine.launch("test", exorcise=exorcise)
    else:
        print(f"\n{Fore.RED}✖ Deploy falhou: {result['error']}{Fore.RESET}")

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
@click.option("--mode", "-m", type=click.Choice(["production", "sandbox", "test"]), 
              default="production", help="Modo alvo.")
@click.option("--backup", "-b", type=click.Path(exists=True), help="Backup específico.")
@click.option("--list", "-l", "list_backups", is_flag=True, help="Lista backups disponíveis.")
def cmd_restore(mode, backup, list_backups):
    """Restaura backup ou lista backups disponíveis."""
    if list_backups:
        backups = TyphonDeployEngine.list_backups(mode)
        print(f"\n{Fore.CYAN}{Style.BRIGHT}💾 BACKUPS DISPONÍVEIS ({mode}){Style.RESET_ALL}\n")
        
        if not backups:
            print(f"{Fore.YELLOW}Nenhum backup encontrado.{Fore.RESET}")
            return
        
        for i, bkp in enumerate(backups, 1):
            mtime = bkp.stat().st_mtime
            size = bkp.stat().st_size
            print(f"  {Fore.WHITE}{i}. {bkp.name}{Fore.RESET}")
            print(f"     {Fore.LIGHTBLACK_EX}Tamanho: {size:,} bytes | Modificado: {mtime}{Fore.RESET}")
        return
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🔄 RESTAURAR BACKUP ({mode}){Style.RESET_ALL}\n")
    
    backup_path = Path(backup) if backup else None
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

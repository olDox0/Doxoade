# -*- coding: utf-8 -*-
"""
NEXUS-GIT - Comando Unificado de Gestão Profissional v1.0.
Gerencia Branches, Issues e Saúde de Dependências.
"""
import click
import os
from .git_systems.git_flow import GitFlowManager
from .git_systems.git_bridge import GitHubBridge
from .git_systems.git_health import DependencyGuard
# [DOX-UNUSED] from ..shared_tools import ExecutionLogger

@click.group('git')
def git_group():
    """🛠  NEXUS-GIT: Gestão profissional de fluxo e segurança."""
    pass

@git_group.command('branch')
@click.option('--new', '-n', help="Cria uma nova branch (feature/nome ou bugfix/nome).")
@click.option('--list', '-l', is_flag=True, help="Lista branches com status de merge.")
@click.option('--done', '-d', help="Finaliza uma branch e volta para a main.")
def branch_cmd(new, list, done):
    """Organiza a árvore genealógica do código (Osíris)."""
    flow = GitFlowManager(os.getcwd())
    if new: flow.create_branch(new)
    elif list: flow.list_branches()
    elif done: flow.finish_branch(done)

@git_group.command('issues')
@click.option('--sync', '-s', is_flag=True, help="Sincroniza issues do GitHub com o banco local.")
def issues_cmd(sync):
    """Conecta com Hermes para buscar ordens do Olimpo (GitHub Issues)."""
    bridge = GitHubBridge(os.getcwd())
    bridge.display_issues()

@git_group.command('audit-deps')
@click.option('--fix', is_flag=True, help="Tenta atualizar dependências inseguras automaticamente.")
def audit_deps(fix):
    """O Dependabot do Doxoade: Vigilância de Vulns e Versões."""
    guard = DependencyGuard(os.getcwd())
    guard.check_health(auto_fix=fix)
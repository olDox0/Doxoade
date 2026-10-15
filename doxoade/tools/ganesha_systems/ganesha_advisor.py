# -*- coding: utf-8 -*-
# doxoade/tools/ganesha_systems/ganesha_advisor.py
"""
Ganesha Advisor - Sistema de Apoio Inteligente para Desenvolvedores.
Remove o atrito de erros de digitação e audita rotas do CLI automaticamente.
"""
from __future__ import annotations
import difflib
import click
from typing import Optional, List
from collections import Counter
from importlib import import_module
from doxoade.tools.doxcolors import Fore, Style


class GaneshaAdvisor:
    """Advisor que intercepta erros de CLI e sugere correções."""

    COMMON_ALIASES = {
        '-h': '--help',
        '-?': '--help',
        '--h': '--help',
        '-help': '--help',
        '-V': '--version',
        '--v': '--version',
        '-v': '--version',
        '--f': '--force',
        '-f': '--force',
    }

    @staticmethod
    def suggest_option(command: click.Command, wrong_option: str) -> Optional[str]:
        if not command:
            return None

        if wrong_option in GaneshaAdvisor.COMMON_ALIASES:
            return GaneshaAdvisor.COMMON_ALIASES[wrong_option]

        available_options = []
        for param in command.params:
            if isinstance(param, click.Option):
                available_options.extend(param.opts)
                available_options.extend(param.secondary_opts)

        available_options = sorted(set(available_options))
        matches = difflib.get_close_matches(wrong_option, available_options, n=1, cutoff=0.6)
        return matches[0] if matches else None

    @staticmethod
    def _get_bigrams(text: str) -> List[str]:
        return [text[i:i+2] for i in range(len(text) - 1)]

    @staticmethod
    def _calculate_similarity_score(wrong: str, candidate: str) -> float:
        if not wrong or not candidate:
            return 0.0

        wrong_lower = wrong.lower()
        candidate_lower = candidate.lower()

        len_diff = abs(len(wrong) - len(candidate))
        len_score = max(0, 1 - (len_diff / max(len(wrong), len(candidate))))

        wrong_chars = Counter(wrong_lower)
        candidate_chars = Counter(candidate_lower)
        common_chars = sum((wrong_chars & candidate_chars).values())
        char_score = common_chars / max(len(wrong), len(candidate))

        wrong_bigrams = set(GaneshaAdvisor._get_bigrams(wrong_lower))
        candidate_bigrams = set(GaneshaAdvisor._get_bigrams(candidate_lower))
        bigram_score = len(wrong_bigrams & candidate_bigrams) / max(len(wrong_bigrams), len(candidate_bigrams)) if wrong_bigrams and candidate_bigrams else 0.0

        position_score = sum(1 for a, b in zip(wrong_lower, candidate_lower) if a == b) / max(len(wrong), len(candidate))

        return (len_score * 0.15) + (char_score * 0.30) + (bigram_score * 0.35) + (position_score * 0.20)

    @staticmethod
    def _advanced_suggest_command(wrong_command: str, available_commands: List[str]) -> Optional[str]:
        matches = difflib.get_close_matches(wrong_command, available_commands, n=1, cutoff=0.6)
        if matches:
            return matches[0]

        candidates_with_scores = []
        for cmd in available_commands:
            score = GaneshaAdvisor._calculate_similarity_score(wrong_command, cmd)
            if score > 0.3:
                candidates_with_scores.append((cmd, score))

        if not candidates_with_scores:
            return None

        candidates_with_scores.sort(key=lambda x: x[1], reverse=True)
        return candidates_with_scores[0][0]

    @staticmethod
    def suggest_command(group: click.Group, wrong_command: str) -> Optional[str]:
        if not group:
            return None
        try:
            available_commands = list(group.list_commands(click.Context(group)))
        except Exception:
            return None
        return GaneshaAdvisor._advanced_suggest_command(wrong_command, available_commands)

    @staticmethod
    def inspect_lazy_route(group: click.Group, cmd_name: str) -> Optional[Tuple[str, str]]:
        """
        Verifica se o comando consta no mapa lazy e se sua rota está quebrada.
        Retorna (rota, erro) se houver falha, ou None se estiver saudável.
        """
        lazy_map = getattr(group, '_lazy_map', None) or getattr(group, '_doxoade_commands', None)
        if not isinstance(lazy_map, dict):
            return None

        route = lazy_map.get(cmd_name)
        if not route:
            return None

        if ":" not in route:
            return (route, "Sintaxe da rota inválida (sem ':')")

        mod_path, attr_name = route.split(":")
        try:
            mod = import_module(mod_path)
            if not hasattr(mod, attr_name):
                return (route, f"Atributo '{attr_name}' não encontrado no módulo")
        except Exception as e:
            return (route, str(e))

        return None

    @staticmethod
    def show_option_suggestion(ctx: click.Context, command: click.Command, wrong_option: str):
        suggestion = GaneshaAdvisor.suggest_option(command, wrong_option)
        if suggestion:
            click.secho(
                f"\n🐘 [Ganesha] Você escreveu '{wrong_option}', "
                f"mas provavelmente quis dizer '{suggestion}'?",
                fg='cyan', bold=True
            )
            click.echo("\nVeja o help abaixo:\n")
            click.echo(ctx.get_help())
        else:
            click.secho(f"\n⚠️  Opção '{wrong_option}' não existe.", fg='red')
            click.echo(f"Use '{ctx.command_path} --help' para ver as opções disponíveis.\n")

    @staticmethod
    def show_usage_suggestion(command: click.Command, wrong_args: list):
        if not command:
            return
        ctx = click.Context(command, info_name=command.name)
        usage_pieces = command.collect_usage_pieces(ctx)
        usage_str = f"doxoade {command.name} " + " ".join(usage_pieces)

        click.secho(f"\n📖 [SINTAXE CORRETA PARA '{command.name.upper()}']", fg='cyan', bold=True)
        click.secho(f"   Usage: {Fore.YELLOW}{usage_str}{Style.RESET_ALL}", bold=True)

        args = [p for p in command.params if isinstance(p, click.Argument)]
        if args:
            click.secho("\n   📦 Argumentos:", fg='green', bold=True)
            for i, arg in enumerate(args, 1):
                required = "obrigatório" if arg.required else "opcional"
                nargs_desc = " (múltiplos)" if arg.nargs == -1 else (f" ({arg.nargs} valores)" if arg.nargs != 1 else "")
                click.echo(f"      {i}. {Fore.CYAN}{arg.human_readable_name}{Style.RESET_ALL} [{required}]{nargs_desc}")

        opts = [p for p in command.params if isinstance(p, click.Option)]
        if opts:
            click.secho("\n   🚩 Opções disponíveis:", fg='magenta', bold=True)
            for opt in opts[:10]:
                opt_str = " / ".join(opt.opts)
                help_txt = opt.help or "Sem descrição"
                click.echo(f"      {Fore.YELLOW}{opt_str:<22}{Style.RESET_ALL} {Style.DIM}{help_txt[:50]}{Style.RESET_ALL}")
            if len(opts) > 10:
                click.echo(f"      {Style.DIM}... e mais {len(opts) - 10} opções. Use --help para ver todas.{Style.RESET_ALL}")
        click.echo()

    @staticmethod
    def show_command_suggestion(ctx: click.Context, group: click.Group, wrong_command: str):
        # 1. Auditoria preventiva: O comando existe no mapa lazy mas falhou ao importar?
        broken = GaneshaAdvisor.inspect_lazy_route(group, wrong_command)
        if broken:
            route, err = broken
            click.secho(f"\n🐘 [GANESHA AUDITOR] O comando '{wrong_command}' está registrado, mas sua rota está corrompida!", fg='yellow', bold=True)
            click.echo(f"   ↳ Rota definida:  {Fore.CYAN}{route}{Style.RESET_ALL}")
            click.echo(f"   ↳ Erro no import: {Fore.RED}{err}{Style.RESET_ALL}")
            click.echo(f"   💡 Dica: Verifique o mapeamento em cli.py ou execute a auditoria de integridade.\n")
            return

        # 2. Busca por similaridade
        suggestion = GaneshaAdvisor.suggest_command(group, wrong_command)
        click.secho(f"\n🐘 [GANESHA ADVISOR] Comando '{wrong_command}' não encontrado.", fg='red', bold=True)

        if suggestion:
            click.secho(f"   ✨ Você quis dizer: {Fore.GREEN}{suggestion}{Style.RESET_ALL}?", fg='cyan', bold=True)
            # Verifica se o comando sugerido está íntegro antes de tentar puxá-lo
            broken_suggested = GaneshaAdvisor.inspect_lazy_route(group, suggestion)
            if not broken_suggested:
                try:
                    correct_cmd = group.get_command(ctx, suggestion)
                    if correct_cmd:
                        GaneshaAdvisor.show_usage_suggestion(correct_cmd, [])
                except Exception:
                    pass
        else:
            click.secho("   ✨ Nenhum comando similar encontrado. Use 'doxoade --help' para ver a lista.", fg='yellow')

        click.echo()


def install_ganesha_hook():
    original_show = click.exceptions.UsageError.show

    def patched_show(self, file=None):
        error_msg = str(self)
        ctx = click.get_current_context(silent=True)
        if not ctx:
            return original_show(self, file)

        if "No such option:" in error_msg:
            wrong_option = error_msg.split("No such option:")[-1].strip()
            command = ctx.command if ctx.command else (ctx.parent.command if ctx.parent else None)
            if command:
                GaneshaAdvisor.show_option_suggestion(ctx, command, wrong_option)
                return

        if "No such command" in error_msg:
            wrong_cmd = error_msg.split("No such command")[-1].strip().strip("'\".")
            group = None
            if isinstance(ctx.command, click.Group):
                group = ctx.command
            elif ctx.parent and isinstance(ctx.parent.command, click.Group):
                group = ctx.parent.command

            if group:
                GaneshaAdvisor.show_command_suggestion(ctx, group, wrong_cmd)
                return

        original_show(self, file)

    click.exceptions.UsageError.show = patched_show

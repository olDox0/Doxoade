# -*- coding: utf-8 -*-
# doxoade/tools/ganesha_systems/ganesha_advisor.py
"""
Ganesha Advisor - Sistema de Apoio Inteligente para Desenvolvedores.
Remove o atrito de erros de digitação e sugere correções automaticamente.
"""
import difflib
import click
from typing import Optional, List, Tuple
from collections import Counter
from doxoade.tools.doxcolors import Fore, Style


class GaneshaAdvisor:
    """Advisor que intercepta erros de CLI e sugere correções."""
    
    @staticmethod
    def suggest_option(command: click.Command, wrong_option: str) -> Optional[str]:
        """Sugere a opção mais próxima da digitada incorretamente."""
        if not command:
            return None
        
        # 1. Mapeamento de aliases comuns (prioridade máxima)
        COMMON_ALIASES = {
            '-h': '--help',
            '-?': '--help',
            '--h': '--help',
            '-help': '--help',
            '-V': '--version',
            '--v': '--version',
            '-v': '--version',
        }
        
        if wrong_option in COMMON_ALIASES:
            return COMMON_ALIASES[wrong_option]
        
        # 2. Coleta todas as opções disponíveis
        available_options = []
        for param in command.params:
            if isinstance(param, click.Option):
                available_options.extend(param.opts)
                available_options.extend(param.secondary_opts)
        
        available_options = sorted(set(available_options))
        
        # 3. Busca por similaridade (fallback)
        matches = difflib.get_close_matches(wrong_option, available_options, n=1, cutoff=0.6)
        return matches[0] if matches else None
    
    @staticmethod
    def _get_bigrams(text: str) -> List[str]:
        """Extrai bigramas (pares de letras consecutivas) de uma string."""
        return [text[i:i+2] for i in range(len(text) - 1)]
    
    @staticmethod
    def _calculate_similarity_score(wrong: str, candidate: str) -> float:
        """
        Calcula score de similaridade multi-fator.
        Retorna float entre 0.0 e 1.0
        """
        if not wrong or not candidate:
            return 0.0
        
        wrong_lower = wrong.lower()
        candidate_lower = candidate.lower()
        
        # Fator 1: Diferença de tamanho (penaliza diferenças grandes)
        len_diff = abs(len(wrong) - len(candidate))
        len_score = max(0, 1 - (len_diff / max(len(wrong), len(candidate))))
        
        # Fator 2: Caracteres em comum (frequência)
        wrong_chars = Counter(wrong_lower)
        candidate_chars = Counter(candidate_lower)
        common_chars = sum((wrong_chars & candidate_chars).values())
        char_score = common_chars / max(len(wrong), len(candidate))
        
        # Fator 3: Bigramas em comum (pares de letras consecutivas)
        wrong_bigrams = set(GaneshaAdvisor._get_bigrams(wrong_lower))
        candidate_bigrams = set(GaneshaAdvisor._get_bigrams(candidate_lower))
        
        if wrong_bigrams and candidate_bigrams:
            common_bigrams = wrong_bigrams & candidate_bigrams
            bigram_score = len(common_bigrams) / max(len(wrong_bigrams), len(candidate_bigrams))
        else:
            bigram_score = 0.0
        
        # Fator 4: Letras em posições corretas
        position_score = sum(1 for a, b in zip(wrong_lower, candidate_lower) if a == b)
        position_score /= max(len(wrong), len(candidate))
        
        # Score final ponderado
        final_score = (
            len_score * 0.15 +
            char_score * 0.30 +
            bigram_score * 0.35 +
            position_score * 0.20
        )
        
        return final_score
    
    @staticmethod
    def _advanced_suggest_command(wrong_command: str, available_commands: List[str]) -> Optional[str]:
        """
        Sistema de sugestão avançado multi-camadas.
        Camada 1: difflib (cutoff 0.6)
        Camada 2: Análise de tamanho + caracteres em comum + bigramas
        """
        # Camada 1: difflib normal
        matches = difflib.get_close_matches(wrong_command, available_commands, n=1, cutoff=0.6)
        if matches:
            return matches[0]
        
        # Camada 2: Análise avançada
        candidates_with_scores = []
        for cmd in available_commands:
            score = GaneshaAdvisor._calculate_similarity_score(wrong_command, cmd)
            if score > 0.3:  # Threshold mínimo
                candidates_with_scores.append((cmd, score))
        
        if not candidates_with_scores:
            return None
        
        # Ordena por score (maior primeiro)
        candidates_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Retorna o melhor candidato
        best_match, best_score = candidates_with_scores[0]
        return best_match
    
    @staticmethod
    def suggest_command(group: click.Group, wrong_command: str) -> Optional[str]:
        """Sugere o comando mais próximo do digitado incorretamente."""
        if not group:
            return None
        
        try:
            available_commands = list(group.list_commands(click.Context(group)))
        except Exception:
            return None
        
        # Usa o sistema avançado multi-camadas
        return GaneshaAdvisor._advanced_suggest_command(wrong_command, available_commands)
    
    @staticmethod
    def show_option_suggestion(ctx: click.Context, command: click.Command, wrong_option: str):
        """Mostra sugestão amigável para opção errada."""
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
        """
        Explica a ordem correta de escrita do comando quando há erro de sintaxe/ordem.
        (PASC 8.24 - Ganesha Syntax Teacher)
        """
        if not command:
            return
        
        # 1. Extrai o Usage nativo do Click
        ctx = click.Context(command, info_name=command.name)
        usage_pieces = command.collect_usage_pieces(ctx)
        usage_str = f"doxoade {command.name} " + " ".join(usage_pieces)
        
        click.secho(f"\n📖 [SINTAXE CORRETA PARA '{command.name.upper()}']", fg='cyan', bold=True)
        click.secho(f"   Usage: {Fore.YELLOW}{usage_str}{Style.RESET_ALL}", bold=True)
        
        # 2. Explica os Argumentos (ordem importa!)
        args = [p for p in command.params if isinstance(p, click.Argument)]
        if args:
            click.secho("\n   📦 Argumentos (ordem obrigatória):", fg='green', bold=True)
            for i, arg in enumerate(args, 1):
                required = "obrigatório" if arg.required else "opcional"
                # 🆕 Melhorar a descrição de nargs
                if arg.nargs == -1:
                    nargs_desc = " (múltiplos valores)"
                elif arg.nargs != 1:
                    nargs_desc = f" ({arg.nargs} valores)"
                else:
                    nargs_desc = ""
                click.echo(f"      {i}. {Fore.CYAN}{arg.human_readable_name}{Style.RESET_ALL} "
                          f"[{required}]{nargs_desc}")
        
        # 3. Explica as Opções (flags)
        opts = [p for p in command.params if isinstance(p, click.Option)]
        if opts:
            click.secho("\n   🚩 Opções (podem vir em qualquer ordem):", fg='magenta', bold=True)
            for opt in opts[:10]:  # Limita a 10 para não poluir
                opt_str = " / ".join(opt.opts)
                help_txt = opt.help or "Sem descrição"
                click.echo(f"      {Fore.YELLOW}{opt_str:<20}{Style.RESET_ALL} {Style.DIM}{help_txt[:50]}{Style.RESET_ALL}")
            if len(opts) > 10:
                click.echo(f"      {Style.DIM}... e mais {len(opts) - 10} opções. Use --help para ver todas.{Style.RESET_ALL}")
        
        # 4. Dica sobre o erro específico
        if wrong_args:
            click.secho(f"\n   💡 Você digitou: {Fore.RED}{' '.join(wrong_args)}{Style.RESET_ALL}", bold=True)
            click.secho("      Dica: Verifique se os caminhos vêm antes das flags, ou use -- para separar.", 
                       fg='yellow', dim=True)
        
        click.echo()
    
    @staticmethod
    def show_command_suggestion(ctx: click.Context, group: click.Group, wrong_command: str):
        """Sugere o comando correto e mostra o usage se for um comando válido."""
        suggestion = GaneshaAdvisor.suggest_command(group, wrong_command)
        
        click.secho(f"\n🤖 [GANESHA ADVISOR] Comando '{wrong_command}' não encontrado.", fg='red', bold=True)
        
        if suggestion:
            click.secho(f"   ✨ Você quis dizer: {Fore.GREEN}{suggestion}{Style.RESET_ALL}?", fg='cyan', bold=True)
            # 🆕 Mostra o usage do comando sugerido
            correct_cmd = group.get_command(ctx, suggestion)
            if correct_cmd:
                GaneshaAdvisor.show_usage_suggestion(correct_cmd, [])
        else:
            click.secho("   ✨ Nenhum comando similar encontrado. Use 'doxoade --help' para ver a lista.", fg='yellow')
        
        click.echo()


def install_ganesha_hook():
    """
    Instala o hook do Ganesha no Click globalmente.
    Intercepta UsageError em qualquer nível (grupo ou subcomando).
    """
    # Salva o método original
    original_show = click.exceptions.UsageError.show
    
    def patched_show(self, file=None):
        """Intercepta a exibição de UsageError e aciona o Ganesha."""
        error_msg = str(self)
        
        # Tenta obter o contexto atual
        ctx = click.get_current_context(silent=True)
        if not ctx:
            return original_show(self, file)
        
        # Caso 1: Opção inexistente (ex: "No such option: -h")
        if "No such option:" in error_msg:
            wrong_option = error_msg.split("No such option:")[-1].strip()
            command = None
            if ctx.command:
                command = ctx.command
            elif ctx.parent and ctx.parent.command:
                command = ctx.parent.command
            
            if command:
                GaneshaAdvisor.show_option_suggestion(ctx, command, wrong_option)
                return
        
        # Caso 2: Comando inexistente (ex: "No such command 'chek'")
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
        
        # Caso 3: Erro genérico - comportamento padrão do Click
        original_show(self, file)
    
    # Aplica o monkey-patch
    click.exceptions.UsageError.show = patched_show
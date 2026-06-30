# doxoade\tools\ganesha_systems\ganesha_advisor.py
"""
Ganesha Advisor - Sistema de Apoio Inteligente para Desenvolvedores.
Remove o atrito de erros de digitação e sugere correções automaticamente.
"""
import difflib
import click
from typing import Optional, List, Tuple
from collections import Counter


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
    def show_command_suggestion(ctx: click.Context, group: click.Group, wrong_command: str):
        """Mostra sugestão amigável para comando errado."""
        suggestion = GaneshaAdvisor.suggest_command(group, wrong_command)
        
        if suggestion:
            click.secho(
                f"\n🐘 [Ganesha] Comando '{wrong_command}' não existe. "
                f"Você quis dizer '{suggestion}'?",
                fg='cyan', bold=True
            )
            click.echo(f"\nUse 'doxoade {suggestion} --help' para ver as opções.\n")
        else:
            click.secho(f"\n⚠️  Comando '{wrong_command}' não existe.", fg='red')
            click.echo("Use 'doxoade --help' para ver os comandos disponíveis.\n")


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
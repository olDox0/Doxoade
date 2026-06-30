# -*- coding: utf-8 -*-
"""
🐘 GANESHA UX ADVISOR - v1.0 Chief-Gold
Sistema de Apoio Inteligente para Desenvolvedores Doxoade.

Remove o atrito de erros de digitação na CLI, sugerindo correções
automaticamente através de análise multi-camadas:
  • Camada 1: Aliases comuns (-h → --help)
  • Camada 2: difflib (similaridade clássica)
  • Camada 3: Análise de bigramas + caracteres em comum + tamanho
  • Camada 4: Fallback reverso (padrão invertido)

Honraria: Batizado em homenagem a Ganesha, o removedor de obstáculos
da tradição hindu — patrono dos desenvolvedores que enfrentam erros
de digitação em terminais.

Autor: olDox222 | Doxoade Chief-Gold
Compliance: PASC-UX-1.0
"""
import difflib
import click
from typing import Optional, List
from collections import Counter


class GaneshaAdvisor:
    """
    🐘 Advisor que intercepta erros de CLI e sugere correções.

    Arquitetura Multi-Camadas:
    ─────────────────────────
    1. ALIASES   → Mapeamento direto (prioridade máxima)
    2. DIFFLIB   → Similaridade clássica (cutoff 0.6)
    3. ANALYTICS → Bigramas + chars + tamanho + posição
    4. REVERSE   → Padrão invertido (último recurso)
    """

    # ═══════════════════════════════════════════════════════════
    #  CAMADA 1: ALIASES COMUNS (Prioridade Máxima)
    # ═══════════════════════════════════════════════════════════
    COMMON_ALIASES = {
        # Help
        '-h': '--help',
        '-?': '--help',
        '--h': '--help',
        '-help': '--help',
        # Version
        '-V': '--version',
        '--v': '--version',
        '-v': '--version',
        # Force
        '--f': '--force',
        '-frc': '--force',
        # Quiet
        '--q': '--quiet',
        '-q': '--quiet',
        # Verbose
        '--verb': '--verbose',
    }

    @staticmethod
    def suggest_option(command: click.Command, wrong_option: str) -> Optional[str]:
        """Sugere a opção mais próxima da digitada incorretamente."""
        if not command:
            return None

        # Camada 1: Aliases diretos
        if wrong_option in GaneshaAdvisor.COMMON_ALIASES:
            return GaneshaAdvisor.COMMON_ALIASES[wrong_option]

        # Coleta opções disponíveis
        available_options = []
        for param in command.params:
            if isinstance(param, click.Option):
                available_options.extend(param.opts)
                available_options.extend(param.secondary_opts)

        available_options = sorted(set(available_options))

        # Camada 2: difflib clássico
        matches = difflib.get_close_matches(wrong_option, available_options, n=1, cutoff=0.6)
        if matches:
            return matches[0]

        # Camada 3: Análise avançada
        return GaneshaAdvisor._advanced_option_match(wrong_option, available_options)

    @staticmethod
    def _advanced_option_match(wrong: str, candidates: List[str]) -> Optional[str]:
        """Match avançado para opções usando bigramas e caracteres."""
        if len(wrong) < 2:
            return None

        best_match = None
        best_score = 0.0

        for candidate in candidates:
            score = GaneshaAdvisor._calculate_similarity_score(wrong, candidate)
            if score > best_score and score > 0.4:
                best_score = score
                best_match = candidate

        return best_match

    # ═══════════════════════════════════════════════════════════
    #  CAMADA 2 + 3 + 4: SUGESTÃO DE COMANDOS
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def suggest_command(group: click.Group, wrong_command: str) -> Optional[str]:
        """Sugere o comando mais próximo do digitado incorretamente."""
        if not group:
            return None

        try:
            available_commands = list(group.list_commands(click.Context(group)))
        except Exception:
            return None

        # Camada 2: difflib normal
        matches = difflib.get_close_matches(wrong_command, available_commands, n=1, cutoff=0.6)
        if matches:
            return matches[0]

        # Camada 3: Análise multi-fator
        advanced = GaneshaAdvisor._advanced_suggest_command(wrong_command, available_commands)
        if advanced:
            return advanced

        # Camada 4: Fallback reverso
        return GaneshaAdvisor._reverse_pattern_match(wrong_command, available_commands)

    @staticmethod
    def _advanced_suggest_command(wrong_command: str, available_commands: List[str]) -> Optional[str]:
        """Sistema de sugestão avançado multi-camadas."""
        candidates_with_scores = []

        for cmd in available_commands:
            score = GaneshaAdvisor._calculate_similarity_score(wrong_command, cmd)
            if score > 0.3:  # Threshold mínimo
                candidates_with_scores.append((cmd, score))

        if not candidates_with_scores:
            return None

        candidates_with_scores.sort(key=lambda x: x[1], reverse=True)
        best_match, best_score = candidates_with_scores[0]
        return best_match

    @staticmethod
    def _calculate_similarity_score(wrong: str, candidate: str) -> float:
        """
        Calcula score de similaridade multi-fator.
        Retorna float entre 0.0 e 1.0

        Fatores ponderados:
          • Tamanho (15%)
          • Caracteres em comum (30%)
          • Bigramas (35%)
          • Posição correta (20%)
        """
        if not wrong or not candidate:
            return 0.0

        wrong_lower = wrong.lower()
        candidate_lower = candidate.lower()

        # Fator 1: Diferença de tamanho
        len_diff = abs(len(wrong) - len(candidate))
        len_score = max(0, 1 - (len_diff / max(len(wrong), len(candidate))))

        # Fator 2: Caracteres em comum (frequência)
        wrong_chars = Counter(wrong_lower)
        candidate_chars = Counter(candidate_lower)
        common_chars = sum((wrong_chars & candidate_chars).values())
        char_score = common_chars / max(len(wrong), len(candidate))

        # Fator 3: Bigramas em comum
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
    def _get_bigrams(text: str) -> List[str]:
        """Extrai bigramas (pares de letras consecutivas) de uma string."""
        return [text[i:i+2] for i in range(len(text) - 1)]

    @staticmethod
    def _reverse_pattern_match(wrong_command: str, available_commands: List[str]) -> Optional[str]:
        """
        Fallback de padrão reverso: analisa a palavra ao contrário
        para encontrar padrões parciais.

        Exemplo: 'kulkam' → 'makluk' → contém 'ulk' → similar a 'ulc' de 'vulcan'
        """
        if len(wrong_command) < 3:
            return None

        reversed_wrong = wrong_command[::-1]
        best_match = None
        best_score = 0

        for cmd in available_commands:
            for i in range(len(cmd) - 2):
                for j in range(i + 3, len(cmd) + 1):
                    substring = cmd[i:j]
                    reversed_substring = substring[::-1]
                    if reversed_substring in reversed_wrong:
                        score = len(substring) / max(len(cmd), len(wrong_command))
                        if score > best_score:
                            best_score = score
                            best_match = cmd

        return best_match if best_score > 0.3 else None

    # ═══════════════════════════════════════════════════════════
    #  UI / EXIBIÇÃO
    # ═══════════════════════════════════════════════════════════
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
    original_show = click.exceptions.UsageError.show

    def patched_show(self, file=None):
        """Intercepta a exibição de UsageError e aciona o Ganesha."""
        error_msg = str(self)

        ctx = click.get_current_context(silent=True)
        if not ctx:
            return original_show(self, file)

        # Caso 1: Opção inexistente
        if "No such option:" in error_msg:
            wrong_option = error_msg.split("No such option:")[-1].strip()
            command = ctx.command if ctx.command else (ctx.parent.command if ctx.parent else None)
            if command:
                GaneshaAdvisor.show_option_suggestion(ctx, command, wrong_option)
                return

        # Caso 2: Comando inexistente
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

        # Caso 3: Erro genérico
        original_show(self, file)

    click.exceptions.UsageError.show = patched_show


# ═══════════════════════════════════════════════════════════
#  ENTRY POINT (Teste Standalone)
# ═══════════════════════════════════════════════════════════
if __name__ == '__main__':
    # Teste rápido do algoritmo de similaridade
    test_cases = [
        ('kulkam', ['vulcan', 'check', 'doctor', 'metal', 'webcheck']),
        ('web', ['debug', 'webcheck', 'vulcan']),
        ('dozto', ['doctor', 'debug', 'dashboard']),
        ('-h', ['--help', '--host', '--hash']),
    ]

    print("🐘 GANESHA UX ADVISOR - Teste de Similaridade\n")
    for wrong, candidates in test_cases:
        result = GaneshaAdvisor._advanced_suggest_command(wrong, candidates)
        rev = GaneshaAdvisor._reverse_pattern_match(wrong, candidates)
        print(f"  '{wrong}' → difflib+analytics: {result}")
        print(f"  '{wrong}' → reverse_pattern:    {rev}")
        print()

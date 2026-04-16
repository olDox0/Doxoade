# doxoade/doxoade/commands/pedia_systems/pedia_json.py
"""
Pedia JSON Render - Visualizador Semântico (v1.0).
Transforma estruturas de dados brutas em Dashboards de Engenharia elegantes.
Responsabilidade: Detecção automática de JSON e formatação rica.
"""
import json
import textwrap
import click
from doxoade.tools.doxcolors import Fore, Style
STYLE_MAP = {'SEVERITY': (Fore.RED + Style.BRIGHT, '🔥'), 'ROOT_CAUSE': (Fore.MAGENTA + Style.BRIGHT, '🎯'), 'CRITICAL': (Fore.RED + Style.BRIGHT, '☠️'), 'FIX': (Fore.GREEN + Style.BRIGHT, '🛠️'), 'SOLUTION': (Fore.GREEN + Style.BRIGHT, '✅'), 'WORKAROUND': (Fore.YELLOW, '⚠️'), 'SYMPTOM': (Fore.CYAN, '🤒'), 'CONTEXT': (Fore.BLUE, '🔍'), 'IMPACT': (Fore.YELLOW + Style.BRIGHT, '💥'), 'DESCRIPTION': (Fore.WHITE, '📝')}

class SemanticJSONRenderer:

    def try_render(self, content: str) -> bool:
        """
        Tenta parsear e renderizar como JSON rico.
        Retorna True se foi renderizado com sucesso, False se for texto comum.
        """
        stripped = content.strip()
        if not (stripped.startswith('{') or stripped.startswith('[')):
            return False
        try:
            data = json.loads(content)
            self._render_semantic_card(data)
            return True
        except json.JSONDecodeError:
            return False

    def _render_semantic_card(self, data):
        """Renderiza o objeto JSON como um Card de Interface."""
        if isinstance(data, list):
            for item in data:
                self._render_semantic_card(item)
                click.echo(Fore.CYAN + '─' * 40 + Fore.RESET)
            return
        if not isinstance(data, dict):
            click.echo(data)
            return
        click.echo('')
        priority_keys = ['severity', 'status', 'type']
        for key in priority_keys:
            if key in data:
                self._render_field(key, data.pop(key))
        for key, value in data.items():
            self._render_field(key, value)
        click.echo('')

    def _render_field(self, key, value):
        upper_key = key.upper()
        style_cfg = STYLE_MAP.get(upper_key, (Fore.CYAN, '•'))
        color, icon = style_cfg
        click.echo(f' {icon} {color}{upper_key.replace('_', ' ')}:{Style.RESET_ALL}')
        if isinstance(value, list):
            for item in value:
                click.echo(f'    {Fore.WHITE}- {item}{Fore.RESET}')
        elif isinstance(value, dict):
            for k, v in value.items():
                click.echo(f'    {Fore.WHITE}{k}: {Style.DIM}{v}{Style.RESET_ALL}')
        else:
            val_str = str(value)
            wrapped = textwrap.fill(val_str, width=80, initial_indent='    ', subsequent_indent='    ')
            if upper_key == 'SEVERITY':
                val_color = Fore.RED if 'HIGH' in val_str.upper() or 'CRIT' in val_str.upper() else Fore.YELLOW
                click.echo(f'    {val_color}{Style.BRIGHT}{val_str}{Style.RESET_ALL}')
            else:
                click.echo(f'{Fore.WHITE}{wrapped}{Fore.RESET}')
        click.echo('')
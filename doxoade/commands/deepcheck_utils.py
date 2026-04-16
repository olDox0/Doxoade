# doxoade/doxoade/commands/deepcheck_utils.py
import ast
import os
import sys
from doxoade.tools.doxcolors import Fore, Style
from click import echo
P_IO, P_CALC, P_OPER, P_CONST = (f'{Fore.MAGENTA}IO{Fore.RESET}', f'{Fore.YELLOW}CALC{Fore.RESET}', f'{Fore.CYAN}OPER{Fore.RESET}', f'{Fore.WHITE}CONST{Fore.RESET}')
UI_KEYWORDS = {'click', 'echo', 'print', 'Fore', 'Console', 'rich', 'progressbar', 'input'}
SYS_KEYWORDS = {'os', 'sys', 'path', 'shutil', 'subprocess', 'glob', 'pathlib', 'environ'}

class DeepAnalyzer(ast.NodeVisitor):

    def __init__(self, module_imports=None):
        self.module_imports = module_imports or set()
        self.params, self.returns, self.calls, self.vars_meta = ({}, [], [], {})
        self.flow_map, self.read_vars, self.assigned_vars, self.try_blocks = ([], set(), set(), [])

    def _get_static_addr(self, name: str) -> str:
        """Gera endereço virtual para inspeção visual (Fix: Bandit HIGH)."""
        import hashlib
        h = hashlib.sha256(name.encode()).hexdigest()[:8].upper()
        return f'0x{h}'

    def _detect_purpose(self, node):
        p = getattr(node, 'parent', None)
        if isinstance(p, (ast.BinOp, ast.UnaryOp, ast.AugAssign)):
            return 'CALC'
        if isinstance(p, ast.Call):
            return 'IO'
        if isinstance(p, (ast.For, ast.While, ast.If, ast.Compare)):
            return 'OPER'
        if isinstance(p, ast.Constant):
            return 'CONST'
        return 'OPER'

    def visit_Name(self, node):
        if not node.id.startswith('__'):
            name = node.id
            if isinstance(node.ctx, ast.Load):
                self.read_vars.add(name)
            elif isinstance(node.ctx, ast.Store):
                self.assigned_vars.add(name)
            if name not in self.vars_meta:
                scope = 'GLOBAL' if name in self.module_imports else 'LOCAL'
                self.vars_meta[name] = {'type': 'Inferred', 'purpose': set(), 'scope': scope, 'addr': self._get_static_addr(name), 'lines': set()}
            self.vars_meta[name]['purpose'].add(self._detect_purpose(node))
            self.vars_meta[name]['lines'].add(node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node):
        try:
            full_name = ast.unparse(node.func)
            self.calls.append({'line': node.lineno, 'name': full_name, 'is_ui': any((x in full_name for x in UI_KEYWORDS)), 'is_sys': any((x in full_name for x in SYS_KEYWORDS))})
        except Exception as e:
            _, exc_val, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else 'unknown'
            line_n = exc_tb.tb_lineno if exc_tb else 0
            echo(f'\x1b[31m ■ Erro AST em {fname}:{line_n} | {e}\x1b[0m')
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        try:
            for arg in node.args.args:
                name = arg.arg
                addr = self._get_static_addr(name)
                self.params[name] = {'type': ast.unparse(arg.annotation) if arg.annotation else 'Any', 'addr': addr}
                self.flow_map.append(('ENTRY', 'recebe', name))
            self.declared_return = ast.unparse(node.returns) if node.returns else 'Any'
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            print(f'\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n')
            exc_trace(exc_tb)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                value_repr = ast.unparse(node.value)
                self.flow_map.append((value_repr, 'processa ➔', target.id))
        self.generic_visit(node)

    def visit_Return(self, node):
        val = ast.unparse(node.value) if node.value else 'None'
        self.returns.append({'line': node.lineno, 'value': val})
        self.flow_map.append((val, 'finaliza ➔', 'EXIT'))
        self.generic_visit(node)

    def visit_Try(self, node):
        for handler in node.handlers:
            self.try_blocks.append({'line': handler.lineno, 'is_bare': handler.type is None, 'is_silent': any((isinstance(s, ast.Pass) for s in handler.body))})
        self.generic_visit(node)

def _render_variable_analysis(visitor):
    """Renderiza a tabela de variáveis com a nova estética Chief-Gold."""
    echo(f'\n   {Fore.BLUE}[ INSPEÇÃO DE VARIÁVEIS E MEMÓRIA ST ]{Style.RESET_ALL}')
    echo(f'      {Style.RESET_ALL}{'NOME':<27} │ {'TIPO':<10} │ {'ENDEREÇO':<12} │ {'ESCOPO':<8} │ {'PROPÓSITO'}{Style.RESET_ALL}')
    echo(f'      {Style.RESET_ALL}{'─' * 28}┼{'─' * 12}┼{'─' * 14}┼{'─' * 10}┼{'─' * 15}{Style.RESET_ALL}')
    for n, m in sorted(visitor.vars_meta.items()):
        p_str = ' '.join([globals().get(f'P_{p}', p) for p in m['purpose']])
        echo(f'      {Fore.WHITE}{n:<27} {Style.RESET_ALL}│{Style.NORMAL} {Fore.GREEN}{m['type']:<10} {Style.RESET_ALL}│{Style.NORMAL} {Fore.YELLOW}{m['addr']:<12} {Style.RESET_ALL}│{Style.NORMAL} {Fore.CYAN}{m['scope']:<8} {Style.RESET_ALL}│{Style.NORMAL} {p_str}')

def calculate_architectural_score(visitor, cc):
    score, penalties = (100, [])
    if cc > 12:
        p = (cc - 12) * 4
        score -= p
        penalties.append(f'CC alta (-{p})')
    if any((c['is_ui'] for c in visitor.calls)) and any((c['is_sys'] for c in visitor.calls)):
        score -= 20
        penalties.append('Hibridismo UI/SYS (-20)')
    dead_params = [p for p in visitor.params if p not in visitor.read_vars and p != 'self']
    if dead_params:
        p = len(dead_params) * 5
        score -= p
        penalties.append(f'Parâmetros não lidos (-{p})')
    return (max(0, score), penalties)

def _render_comparison(old_rep: dict, new_rep: dict):
    echo(f'\n   {Fore.YELLOW}{Style.BRIGHT}[ 📊 SEMANTIC DIFF / COMPARAÇÃO ]{Style.RESET_ALL}')

    def echo_delta(label, old, new, reverse=False):
        delta = new - old
        color = (Fore.GREEN if delta <= 0 else Fore.RED) if reverse else Fore.GREEN if delta >= 0 else Fore.RED
        echo(f'      {label:<25} : {old} ➔ {new} {color}({delta:+}){Style.RESET_ALL}')
    echo_delta('Score Arquitetural', old_rep['score'], new_rep['score'])
    echo_delta('Complexidade Ciclomática', old_rep['cc'], new_rep['cc'], reverse=True)

def _render_deep_report(visitor, name, cc, as_json=False, show_vars=False, show_flow=False, compare_to=None):
    """Orquestrador de Exibição (Fix: Argumentos Explícitos)."""
    score, penalties = calculate_architectural_score(visitor, cc)
    serializable_vars = {k: {**v, 'purpose': list(v['purpose']), 'lines': sorted(list(v['lines']))} for k, v in visitor.vars_meta.items()}
    current_report = {'function': name, 'score': score, 'cc': cc, 'variables': serializable_vars, 'flow': visitor.flow_map, 'issues': penalties}
    if as_json:
        return current_report
    if compare_to:
        _render_comparison(compare_to, current_report)
    echo(f"\n{Fore.CYAN}{Style.BRIGHT}🔍 EXAME DE FLUXO: '{name}'{Style.RESET_ALL}")
    score_color = Fore.GREEN if score > 80 else Fore.YELLOW if score > 50 else Fore.RED
    echo(f'   Score Arquitetural       : {score_color}{score}/100{Style.RESET_ALL}')
    echo(f'   Complexidade Ciclomática : {cc} {Style.RESET_ALL}(Limite: 12){Style.RESET_ALL}')
    if show_vars:
        echo(f'\n   {Fore.BLUE}[ INSPEÇÃO DE VARIÁVEIS E MEMÓRIA ST ]{Style.RESET_ALL}')
        echo(f'      {Style.RESET_ALL}{'NOME':<27} │ {'TIPO':<10} │ {'ENDEREÇO':<12} │ {'ESCOPO':<8} │ {'PROPÓSITO'}{Style.RESET_ALL}')
        echo(f'      {Style.RESET_ALL}{Style.RESET_ALL}{'─' * 28}┼{'─' * 12}┼{'─' * 14}┼{'─' * 10}┼{'─' * 15}{Style.RESET_ALL}')
        for n, m in sorted(visitor.vars_meta.items()):
            p_str = ' '.join([globals().get(f'P_{p}', p) for p in m['purpose']])
            echo(f'      {Fore.WHITE}{n:<27} {Style.RESET_ALL}{Style.RESET_ALL}{Style.RESET_ALL}│{Style.NORMAL} {Fore.GREEN}{m['type']:<10} {Style.RESET_ALL}│{Style.NORMAL} {Fore.YELLOW}{m['addr']:<12} {Style.RESET_ALL}│{Style.NORMAL} {Fore.CYAN}{m['scope']:<8} {Style.RESET_ALL}│{Style.NORMAL} {p_str:>2}')
    if show_flow:
        echo(f'\n   {Fore.BLUE}[ RASTREIO DE TRANSFORMAÇÕES SEQUENCIAIS ]{Style.RESET_ALL}')
        for orig, action, dest in visitor.flow_map:
            c_o, c_d = (Fore.MAGENTA, Fore.WHITE) if orig == 'ENTRY' else (Fore.WHITE, Fore.GREEN if dest == 'EXIT' else Fore.WHITE)
            echo(f'      {c_o}{str(orig):<28} {Fore.CYAN}{action:<12} {c_d}{dest}')
    echo(f'\n   {Fore.MAGENTA}{Style.BRIGHT}[ INTELIGÊNCIA ARQUITETURAL ]{Style.RESET_ALL}')
    if not penalties:
        echo(f'      · {Fore.GREEN}ESTADO: Função em conformidade máxima.')
    else:
        for p in penalties:
            echo(f'      · {Fore.WHITE}{p}')
    for n, m in visitor.vars_meta.items():
        if 'CALC' in m['purpose'] and 'IO' in m['purpose']:
            echo(f"      · {Fore.YELLOW}RECOMENDAÇÃO: Variável '{n}' é híbrida. Separe cálculo de E/S.")
        if n in visitor.assigned_vars and n not in visitor.read_vars and (n not in visitor.params):
            echo(f"      · {Fore.RED}AVISO: Variável '{n}' é atribuída mas nunca lida (Dead Store).")
    echo(f'{Fore.CYAN}{Style.RESET_ALL}─' * 78 + Style.RESET_ALL)
    return current_report
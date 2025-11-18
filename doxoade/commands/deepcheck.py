# doxoade/commands/deepcheck.py
import ast
import sys
import click
from colorama import Fore, Style

class FunctionDataVisitor(ast.NodeVisitor):
    """
    Um NodeVisitor avançado para extrair um dossiê completo de uma função.
    Coleta parâmetros, retornos, chamadas externas e atribuições de variáveis.
    """
    def __init__(self):
        self.params = []
        self.returns = []
        self.function_calls = []
        self.assignments = []
        self.risks = []

    def visit_FunctionDef(self, node):
        # Extrai os parâmetros da função
        for arg in node.args.args:
            param_type = ast.unparse(arg.annotation) if arg.annotation else "não anotado"
            self.params.append({'name': arg.arg, 'type': param_type})
        # Continua a visita apenas dentro do corpo da função
        self.generic_visit(node)

    def visit_Return(self, node):
        if node.value:
            return_type = "literal"
            value_str = ast.unparse(node.value)
            if isinstance(node.value, ast.Name):
                return_type = "variável"
            elif not isinstance(node.value, ast.Constant):
                return_type = "expressão"
            
            self.returns.append({'lineno': node.lineno, 'type': return_type, 'value': value_str})

    def visit_Call(self, node):
        # Captura o nome da função chamada
        func_name = ast.unparse(node.func)
        self.function_calls.append({'lineno': node.lineno, 'name': func_name})
        self.generic_visit(node)

    def visit_Assign(self, node):
        # Captura nomes de variáveis que estão sendo atribuídas
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.assignments.append({'lineno': node.lineno, 'name': target.id})
        self.generic_visit(node)

    def visit_Subscript(self, node):
        # A mesma lógica de risco de antes
        self.risks.append({
            'lineno': node.lineno,
            'message': "Acesso a dicionário/lista sem tratamento.",
            'details': f"Acesso direto a '{ast.unparse(node)}' pode causar 'KeyError' ou 'IndexError'."
        })
        self.generic_visit(node)


def _get_complexity(content):
    """Calcula a complexidade ciclomática usando radon."""
    try:
        from radon.visitors import ComplexityVisitor
        return {f.name: f.complexity for f in ComplexityVisitor.from_code(content).functions}
    except ImportError:
        return {}

def _get_complexity_rank(complexity):
    """Classifica a complexidade."""
    if complexity > 20: return ("Altíssima", Fore.MAGENTA)
    if complexity > 15: return ("Alta", Fore.RED)
    if complexity > 10: return ("Média", Fore.YELLOW)
    if complexity > 5: return ("Baixa", Fore.GREEN)
    return ("Baixíssima", Fore.CYAN)

def _present_dossier(dossier, verbose=False):
    """(Versão Corrigida) Apresenta o relatório de forma segura usando .get()."""
    rank, color = dossier.get('complexity_rank', ('Desconhecida', Fore.WHITE))
    
    # Usa .get() com valores padrão para evitar KeyError
    name = dossier.get('name', 'Nome Desconhecido')
    lineno = dossier.get('lineno', '?')
    complexity = dossier.get('complexity', '?')
    
    click.echo(color + Style.BRIGHT + f"\n\n--- Função: '{name}' (linha {lineno}) ---")
    click.echo(f"  [Complexidade]: {complexity} ({rank})")

    click.echo(Style.DIM + "  [Entradas (Parâmetros)]")
    params = dossier.get('params', [])
    if not params: click.echo("    - Nenhum parâmetro.")
    for p in params: 
        click.echo(f"    - Nome: {p.get('name', '?')} (Tipo: {p.get('type', '?')})")

    click.echo(Style.DIM + "  [Saídas (Pontos de Retorno)]")
    returns = dossier.get('returns', [])
    if not returns: click.echo("    - Nenhum retorno explícito.")
    for r in returns: 
        click.echo(f"    - Linha {r.get('lineno', '?')}: Retorna {r.get('type', '?')} '{r.get('value', '?')}'")

    click.echo(Fore.YELLOW + "  [Pontos de Risco (Análise de Erros)]")
    risks = dossier.get('risks', [])
    if not risks: click.echo("    - Nenhum ponto de risco óbvio detectado.")
    for risk in risks:
        click.echo(Fore.YELLOW + f"    - AVISO (Linha {risk.get('lineno', '?')}): {risk.get('message', '?')}")
        click.echo(Fore.WHITE + f"      > Detalhe: {risk.get('details', '?')}")
    
    if verbose:
        click.echo(Style.DIM + "  [Atividade Interna (Verbose)]")
        
        assignments = sorted(list(set(a.get('name') for a in dossier.get('assignments', []) if a.get('name'))))
        if not assignments: click.echo("    - Nenhuma variável local principal definida.")
        else: click.echo("    - Variáveis definidas: " + ", ".join(assignments))
        
        calls = sorted(list(set(c.get('name') for c in dossier.get('function_calls', []) if c.get('name'))))
        if not calls: click.echo("    - Nenhuma chamada a outra função detectada.")
        else: click.echo("    - Funções externas chamadas: " + ", ".join(calls))

@click.command('deepcheck')
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--func', '-f', 'func_name', default=None, help="Analisa profundamente uma função específica.")
@click.option('--verbose', '-v', is_flag=True, help="Exibe um relatório ainda mais detalhado.")
def deepcheck(file_path, func_name, verbose):
    """Executa uma análise profunda do fluxo de dados e pontos de risco em um arquivo Python."""
    click.echo(Fore.CYAN + Style.BRIGHT + f"--- [DEEPCHECK] Analisando fluxo de '{file_path}' ---")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content, filename=file_path)
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] Falha ao ler ou analisar o arquivo: {e}"); sys.exit(1)

    complexity_map = _get_complexity(content)
    function_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    
    if func_name:
        function_nodes = [node for node in function_nodes if node.name == func_name]

    if not function_nodes:
        click.echo(Fore.YELLOW + (f"A função '{func_name}' não foi encontrada." if func_name else "Nenhuma função encontrada."))
        return

    for func_node in function_nodes:
        visitor = FunctionDataVisitor()
        visitor.visit_FunctionDef(func_node)
        
        complexity = complexity_map.get(func_node.name, 0)
        rank, _ = _get_complexity_rank(complexity)
        
        dossier = {
            'name': func_node.name,
            'lineno': func_node.lineno,
            'complexity': complexity,
            'complexity_rank': (rank, _),
            'params': visitor.params,
            'returns': visitor.returns,
            'risks': visitor.risks,
            'assignments': visitor.assignments,
            'function_calls': visitor.function_calls,
        }
        _present_dossier(dossier, verbose)
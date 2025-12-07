# doxoade/commands/deepcheck.py
import ast
import sys
import click
from colorama import Fore, Style

class AdvancedFunctionVisitor(ast.NodeVisitor):
    """
    NodeVisitor V2: Rastreia fluxo, tipos e contratos.
    """
    def __init__(self):
        self.params = {} # {nome: tipo}
        self.returns = [] # [{line, type, value, is_none}]
        self.calls = []
        self.assignments = {} # {nome: [linhas]}
        self.used_vars = set()
        self.raised_exceptions = []
        
        # Estado
        self.current_scope_vars = set()

    def visit_FunctionDef(self, node):
        # 1. Análise de Contrato (Input)
        for arg in node.args.args:
            p_type = ast.unparse(arg.annotation) if arg.annotation else "Any"
            self.params[arg.arg] = p_type
            self.current_scope_vars.add(arg.arg)
            
        # 2. Análise de Contrato (Output Declarado)
        self.declared_return = ast.unparse(node.returns) if node.returns else "Any"
        
        # Visita corpo
        self.generic_visit(node)

    def visit_Return(self, node):
        ret_info = {'lineno': node.lineno}
        
        if node.value is None:
            ret_info['type'] = 'NoneType'
            ret_info['value'] = 'None'
            ret_info['is_none'] = True
        else:
            # Tenta inferir tipo básico
            if isinstance(node.value, ast.Constant):
                ret_info['type'] = type(node.value.value).__name__
                ret_info['value'] = str(node.value.value)
                ret_info['is_none'] = node.value.value is None
            elif isinstance(node.value, ast.Name):
                ret_info['type'] = 'Variable' # Difícil saber o tipo estaticamente
                ret_info['value'] = node.value.id
                self.used_vars.add(node.value.id)
                ret_info['is_none'] = False
            else:
                ret_info['type'] = 'Expression'
                ret_info['value'] = ast.unparse(node.value)
                ret_info['is_none'] = False
                
        self.returns.append(ret_info)

    def visit_Call(self, node):
        func_name = ast.unparse(node.func)
        args = [ast.unparse(a) for a in node.args]
        keywords = [k.arg for k in node.keywords if k.arg]
        
        self.calls.append({
            'lineno': node.lineno,
            'name': func_name,
            'args': args,
            'kwargs': keywords
        })
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_vars.add(node.id)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                if name not in self.assignments:
                    self.assignments[name] = []
                self.assignments[name].append(node.lineno)
                self.current_scope_vars.add(name)
        self.generic_visit(node)
        
    def visit_Raise(self, node):
        exc = ast.unparse(node.exc) if node.exc else "Unknown"
        self.raised_exceptions.append({'lineno': node.lineno, 'exc': exc})

def _analyze_contract_consistency(visitor):
    """Verifica se o código obedece aos contratos de tipo."""
    issues = []
    
    # 1. Parâmetros não usados
    for param in visitor.params:
        if param not in visitor.used_vars:
            issues.append(f"Parâmetro '{param}' declarado mas nunca usado (Dead Param).")
            
    # 2. Inconsistência de Retorno
    return_types = set()
    has_value_return = False
    has_none_return = False
    
    for r in visitor.returns:
        return_types.add(r['type'])
        if r['is_none']: has_none_return = True
        else: has_value_return = True
        
    # Mistura de retorno com valor e sem valor (ex: return 1 e return None implícito)
    # Nota: Em Python é válido, mas muitas vezes é bug.
    if has_value_return and has_none_return:
        issues.append("Função retorna valores mistos (Valor e None). Verifique se todos os caminhos retornam algo.")

    # Contrato Declarado vs Real
    declared = visitor.declared_return
    if declared != "Any":
        # Validação simples
        if declared == "bool" and any(t not in ['bool', 'Constant', 'Expression', 'Variable'] for t in return_types):
             # Heurística fraca, mas ajuda
             pass 

    return issues

def _present_deep_analysis(visitor, name, lineno, complexity):
    click.echo(Fore.CYAN + Style.BRIGHT + f"\n=== ANÁLISE PROFUNDA: '{name}' (Linha {lineno}) ===")
    click.echo(f"Complexidade: {complexity}")
    
    # 1. Contrato (IO)
    click.echo(Fore.YELLOW + "\n[CONTRATO IO]")
    if not visitor.params:
        click.echo("  Entrada: (Nenhuma)")
    else:
        for p, t in visitor.params.items():
            status = Fore.RED + "(Não Usado)" if p not in visitor.used_vars else Fore.GREEN + "(Usado)"
            click.echo(f"  Entrada: {p}: {t} {status}{Fore.RESET}")
            
    click.echo(f"  Saída Declarada: {visitor.declared_return}")
    
    # 2. Fluxo de Saída Real
    click.echo(Fore.YELLOW + "\n[FLUXO DE SAÍDA REAL]")
    if not visitor.returns:
        click.echo("  (Implícito) Retorna None no final.")
    else:
        for r in visitor.returns:
            click.echo(f"  Linha {r['lineno']}: Retorna {r['type']} -> {Fore.WHITE}{r['value']}{Fore.YELLOW}")

    # 3. Trabalho (Calls)
    if visitor.calls:
        click.echo(Fore.YELLOW + "\n[TRABALHO REALIZADO (Chamadas)]")
        for c in visitor.calls:
            args_str = ", ".join(c['args'] + [f"{k}=..." for k in c['kwargs']])
            click.echo(f"  Linha {c['lineno']}: {c['name']}({args_str})")

    # 4. Diagnóstico de Problemas
    issues = _analyze_contract_consistency(visitor)
    if issues or visitor.raised_exceptions:
        click.echo(Fore.RED + "\n[PROBLEMAS DETECTADOS]")
        for i in issues:
            click.echo(f"  [!] {i}")
        for exc in visitor.raised_exceptions:
            click.echo(f"  [!] Levanta Exceção: {exc['exc']} (Linha {exc['lineno']})")
    else:
        click.echo(Fore.GREEN + "\n[OK] Nenhum problema de contrato óbvio detectado.")
        
    click.echo(Fore.CYAN + "="*50)

# ... (Manter _get_complexity_rank e outras auxiliares se necessário) ...

@click.command('deepcheck')
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--func', '-f', 'func_name', default=None, help="Analisa profundamente uma função específica.")
@click.option('--verbose', '-v', is_flag=True, help="Exibe um relatório ainda mais detalhado.")
def deepcheck(file_path, func_name, verbose):
    """Executa uma análise profunda semântica."""
    
    # ... (Leitura do arquivo igual) ...
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content, filename=file_path)
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] {e}"); sys.exit(1)
        
    # Encontra função
    target_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if func_name and node.name == func_name:
                target_node = node
                break
            # Se não especificou nome, pega a primeira? Ou lista todas?
            # O comportamento antigo listava todas. Vamos manter se func_name for None.
    
    # Se pediu uma especifica e não achou
    if func_name and not target_node:
        click.echo(Fore.RED + f"Função '{func_name}' não encontrada.")
        return

    # Lista de nós a analisar
    nodes_to_analyze = [target_node] if target_node else [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    
    from ..shared_tools import _get_complexity_rank
    # Precisamos recalcular complexidade aqui ou importar se já tiver
    # Vou usar uma simplificação ou importar se shared_tools tiver
    
    for node in nodes_to_analyze:
        visitor = AdvancedFunctionVisitor()
        visitor.visit(node)
        
        # Complexidade (Placeholder ou real)
        complexity = "N/A" 
        
        _present_deep_analysis(visitor, node.name, node.lineno, complexity)
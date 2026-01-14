# doxoade/commands/deepcheck.py
"""
Módulo de Análise Profunda (Deepcheck).
Responsável por análise semântica, fluxo de dados e validação de contratos.
"""
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
        self.current_scope_vars = set()

    def visit_FunctionDef(self, node):
        """Analisa assinatura da função."""
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
        """Registra pontos de retorno e tipos."""
        ret_info = {'lineno': node.lineno}
        
        if node.value is None:
            ret_info['type'] = 'NoneType'
            ret_info['value'] = 'None'
            ret_info['is_none'] = True
        else:
            if isinstance(node.value, ast.Constant):
                ret_info['type'] = type(node.value.value).__name__
                ret_info['value'] = str(node.value.value)
                ret_info['is_none'] = node.value.value is None
            elif isinstance(node.value, ast.Name):
                ret_info['type'] = 'Variable' 
                ret_info['value'] = node.value.id
                self.used_vars.add(node.value.id)
                ret_info['is_none'] = False
            else:
                ret_info['type'] = 'Expression'
                try:
                    ret_info['value'] = ast.unparse(node.value)
                except Exception:
                    ret_info['value'] = "Complex Expr"
                ret_info['is_none'] = False
                
        self.returns.append(ret_info)
        # Importante: Visitar o valor de retorno para marcar variáveis usadas nele!
        if node.value:
            self.visit(node.value)

    def visit_Call(self, node):
        """Registra chamadas de função."""
        # CORREÇÃO: Removido assert quebrado
        try:
            func_name = ast.unparse(node.func)
            args = [ast.unparse(a) for a in node.args]
            keywords = [k.arg for k in node.keywords if k.arg]
            
            self.calls.append({
                'lineno': node.lineno,
                'name': func_name,
                'args': args,
                'kwargs': keywords
            })
        except Exception:
            pass # Parsing seguro
            
        self.generic_visit(node)

    def visit_Name(self, node):
        """Rastreia uso de variáveis."""
        if isinstance(node.ctx, ast.Load):
            self.used_vars.add(node.id)
        self.generic_visit(node)

    def visit_Assign(self, node):
        """Rastreia atribuições."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                if name not in self.assignments:
                    self.assignments[name] = []
                self.assignments[name].append(node.lineno)
                self.current_scope_vars.add(name)
        self.generic_visit(node)
        
    def visit_Raise(self, node):
        """Registra exceções levantadas."""
        exc = ast.unparse(node.exc) if node.exc else "Unknown"
        self.raised_exceptions.append({'lineno': node.lineno, 'exc': exc})
        self.generic_visit(node)

def _analyze_contract_consistency(visitor):
    """Verifica se o código obedece aos contratos de tipo."""
    issues = []
    
    # 1. Parâmetros não usados
    for param in visitor.params:
        if param not in visitor.used_vars:
            # Filtro para ignorar 'self' em métodos
            if param != 'self':
                issues.append(f"Parâmetro '{param}' declarado mas nunca usado (Dead Param).")
            
    # 2. Inconsistência de Retorno
    return_types = set()
    has_value_return = False
    has_none_return = False
    
    for r in visitor.returns:
        return_types.add(r['type'])
        if r['is_none']: has_none_return = True
        else: has_value_return = True
        
    if has_value_return and has_none_return:
        # Verifica se o None é explícito ou implícito (fundo da função)
        issues.append("Função retorna valores mistos (Valor e None). Risco de TypeError.")

    return issues

def _analyze_function_nodes(self, node):
    """
    Analisa os nós da função para distinguir contratos de erros.
    """
    for i, child in enumerate(node.body):
        # MPoT-Aware: Identifica 'raise' nas primeiras linhas como Contrato
        if isinstance(child, ast.Raise) and i < 3:
            self.contracts.append({
                'line': child.lineno,
                'type': ast.unparse(child.exc).split('(')[0],
                'message': ast.unparse(child.exc)
            })
            continue # Não trata como erro de fluxo não-planejado

def _present_deep_analysis(visitor, name, lineno, complexity):
    """Apresenta os resultados da análise no terminal."""
    
    click.echo(Fore.CYAN + Style.BRIGHT + f"\n=== ANÁLISE PROFUNDA: '{name}' (Linha {lineno}) ===")
    click.echo(f"Complexidade: {complexity}")
    
    # 1. Contrato (IO)
    click.echo(Fore.YELLOW + "\n[CONTRATO IO]")
    if not visitor.params:
        click.echo("  Entrada: (Nenhuma)")
    else:
        for p, t in visitor.params.items():
            status = Fore.RED + "(Não Usado)" if p not in visitor.used_vars and p != 'self' else Fore.GREEN + "(Usado)"
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
        # Limita visualização para não poluir
        for c in visitor.calls[:10]:
            args_str = ", ".join(c['args'][:3])
            if len(c['args']) > 3: args_str += "..."
            click.echo(f"  Linha {c['lineno']}: {c['name']}({args_str})")
#        if len(visitor.calls) > 10:
#             click.echo(f"  ... e mais {len(visitor.calls)-10} chamadas.")

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
        
    if hasattr(visitor, 'contracts') and visitor.contracts:
        console.print("[bold cyan][CONTRATOS ATIVOS (MPoT-5)][/bold cyan]")
        for c in visitor.contracts:
            console.print(f"  Line {c['line']}: {c['type']} -> Proteção de entrada validada.")
            
    click.echo(Fore.CYAN + "="*50)

@click.command('deepcheck')
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--func', '-f', 'func_name', default=None, help="Analisa profundamente uma função específica.")
@click.option('--verbose', '-v', is_flag=True, help="Exibe um relatório ainda mais detalhado.")
def deepcheck(file_path, func_name, verbose):
    """Executa uma análise profunda semântica."""
    assert file_path, "Caminho do arquivo é obrigatório"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content, filename=file_path)
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] {e}"); sys.exit(1)
        
    # Encontra função
    target_node = None
    all_funcs = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            all_funcs.append(node)
            if func_name and node.name == func_name:
                target_node = node
                break
    
    nodes_to_analyze = [target_node] if target_node else all_funcs
    
    if not nodes_to_analyze:
        click.echo(Fore.YELLOW + "Nenhuma função encontrada para análise.")
        return
    
    from ..shared_tools import _get_complexity_rank
    
    for node in nodes_to_analyze:
        visitor = AdvancedFunctionVisitor()
        visitor.visit(node)
        
        # Placeholder de complexidade (futuro: usar Radon)
        complexity = "N/A" 
        
        _present_deep_analysis(visitor, node.name, node.lineno, complexity)
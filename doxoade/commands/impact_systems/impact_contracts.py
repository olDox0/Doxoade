# -*- coding: utf-8 -*-
# doxoade/commands/impact_systems/impact_contracts.py
"""
Impact Contracts — Extração e validação de contratos públicos.

Camada 1 do "Flow de Contrato": assinaturas declaradas vs uso real.

Um contrato é composto por:
  - Nome do símbolo (função/classe/método público)
  - Parâmetros (nome, tipo, default)
  - Tipo de retorno
  - Exceções declaradas (raises)
  - Flag de async
  - Linha de definição

A validação compara a assinatura declarada com os argumentos
realmente passados pelos consumidores (via AST + ImpactVisitor estendido).
"""
from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────
# Extração de contratos
# ─────────────────────────────────────────────────────────────

def _has_public_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Decorators que promovem a função a contrato público."""
    PUBLIC_DECORATORS = {
        'command', 'group', 'option', 'argument',     # Click
        'fixture', 'task',                            # Pytest, Celery
        'route', 'get', 'post', 'put', 'delete',      # Flask/FastAPI
        'public', 'api',                              # Custom
    }
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr in PUBLIC_DECORATORS:
            return True
        if isinstance(target, ast.Name) and target.id in PUBLIC_DECORATORS:
            return True
    return False


def _has_return_annotation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return node.returns is not None


def _is_public(
    name: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef | None = None,
    promote_typed: bool = True,
) -> bool:
    """
    Regras:
      1. Dunder → público
      2. Sem '_' inicial → público
      3. Com '_' inicial, MAS:
         - tem decorator Click/API → público
         - tem anotação de retorno (promote_typed) → público
    """
    if name.startswith('__') and name.endswith('__'):
        return True
    if not name.startswith('_'):
        return True
    if node is None:
        return False
    if _has_public_decorator(node):
        return True
    if promote_typed and _has_return_annotation(node):
        return True
    return False


def _annotation_to_str(node: Optional[ast.AST]) -> Optional[str]:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None

def _has_public_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Decorators que promovem a função a contrato público."""
    PUBLIC_DECORATORS = {
        'command', 'group', 'option', 'argument',     # Click
        'fixture', 'task',                            # Pytest, Celery
        'route', 'get', 'post', 'put', 'delete',      # Flask/FastAPI
        'public', 'api',                              # Custom
    }
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr in PUBLIC_DECORATORS:
            return True
        if isinstance(target, ast.Name) and target.id in PUBLIC_DECORATORS:
            return True
    return False


def _is_public(
    name: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef | None = None,
    promote_typed: bool = True,
) -> bool:
    """
    Regras:
      1. Dunder → público
      2. Sem '_' inicial → público
      3. Com '_' inicial, MAS:
         - tem decorator Click/API → público
         - tem anotação de retorno (promote_typed) → público
    """
    if name.startswith('__') and name.endswith('__'):
        return True
    if not name.startswith('_'):
        return True
    if node is None:
        return False
    if _has_public_decorator(node):
        return True
    if promote_typed and node.returns is not None:
        return True
    return False

def _extract_param_info(
    args: ast.arguments, param: ast.arg, arg_index: int
) -> Dict[str, Any]:
    """Extrai info de um parâmetro (nome, tipo, default)."""
    default_expr = None
    # Calcula offset dos defaults
    positional = args.args
    defaults = args.defaults
    n_defaults = len(defaults)
    n_positional = len(positional)
    defaults_offset = n_positional - n_defaults
    if arg_index >= defaults_offset and arg_index < n_positional:
        default_node = defaults[arg_index - defaults_offset]
        default_expr = _annotation_to_str(default_node)
    return {
        'name': param.arg,
        'type': _annotation_to_str(param.annotation),
        'default': default_expr,
    }



def extract_contracts(tree: ast.AST, module: str) -> Dict[str, Dict[str, Any]]:
    """
    Extrai contratos públicos de funções e métodos de classes.

    Retorna dict: {qualname: contract_dict}
    """
    contracts: Dict[str, Dict[str, Any]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        if not _is_public(node.name, node=node):
            continue

        # Parâmetros
        params: List[Dict[str, Any]] = []
        all_positional = list(node.args.args)
        for i, p in enumerate(all_positional):
            params.append(_extract_param_info(node.args, p, i))

        for p in node.args.kwonlyargs:
            params.append({
                'name': p.arg,
                'type': _annotation_to_str(p.annotation),
                'default': 'kwonly',
            })

        if node.args.vararg:
            params.append({
                'name': f'*{node.args.vararg.arg}',
                'type': _annotation_to_str(node.args.vararg.annotation),
                'default': 'variadic',
            })
        if node.args.kwarg:
            params.append({
                'name': f'**{node.args.kwarg.arg}',
                'type': _annotation_to_str(node.args.kwarg.annotation),
                'default': 'variadic',
            })

        # Retorno
        returns = _annotation_to_str(node.returns)

        # Raises (procura por raise X() no corpo, não recursivo em defs aninhados)
        raises: List[str] = []
        for child in ast.iter_child_nodes(node):
            for sub in ast.walk(child):
                if isinstance(sub, ast.Raise) and isinstance(sub.exc, ast.Call):
                    if isinstance(sub.exc.func, ast.Name):
                        exc_name = sub.exc.func.id
                        if exc_name not in raises:
                            raises.append(exc_name)
                elif isinstance(sub, ast.Raise) and isinstance(sub.exc, ast.Name):
                    exc_name = sub.exc.id
                    if exc_name not in raises:
                        raises.append(exc_name)

        contracts[node.name] = {
            'module': module,
            'line': node.lineno,
            'params': params,
            'returns': returns,
            'raises': raises,
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'required_args': sum(
                1 for p in params
                if p['default'] is None or p['default'] == 'kwonly'
            ),
        }

    return contracts


# ─────────────────────────────────────────────────────────────
# Índice de chamadores (para detectar violação de contrato)
# ─────────────────────────────────────────────────────────────

class CallerExtractor(ast.NodeVisitor):
    """
    Rastreia chamadas no nível de função do módulo-alvo.

    Detecta:
      - nome da função chamadora (ou '<module>' se top-level)
      - nome da função chamada
      - número de args posicionais passados
      - número de kwargs passados
      - linha da chamada
    """

    def __init__(self, module: str):
        self.module = module
        self.current_func: Optional[str] = None
        self.callers: Dict[str, List[Dict[str, Any]]] = {}
        self._func_stack: List[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._func_stack.append(node.name)
        prev = self.current_func
        self.current_func = node.name
        self.generic_visit(node)
        self.current_func = prev
        self._func_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_Call(self, node: ast.Call) -> None:
        callee_name: Optional[str] = None
        is_self_call = False
        is_super_call = False

        if isinstance(node.func, ast.Name):
            callee_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            callee_name = node.func.attr
            # Detecta self.X / cls.X
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id in ('self', 'cls'):
                    is_self_call = True
            # Detecta super().X
            if isinstance(node.func.value, ast.Call):
                if isinstance(node.func.value.func, ast.Name):
                    if node.func.value.func.id == 'super':
                        is_super_call = True

        if callee_name:
            caller = self.current_func or '<module>'
            self.callers.setdefault(callee_name, []).append({
                'caller': caller,
                'module': self.module,
                'line': node.lineno,
                'args_passed': len(node.args),
                'kwargs_passed': [kw.arg for kw in node.keywords if kw.arg],
                'has_star_args': any(isinstance(a, ast.Starred) for a in node.args),
                'has_star_kwargs': any(kw.arg is None for kw in node.keywords),
                'is_self_call': is_self_call,      # ⭐ NOVO
                'is_super_call': is_super_call,    # ⭐ NOVO
            })
        self.generic_visit(node)


def index_callers(tree: ast.AST, module: str) -> Dict[str, List[Dict[str, Any]]]:
    """Retorna índice {callee_name: [calls...]}."""
    extractor = CallerExtractor(module)
    extractor.visit(tree)
    return extractor.callers


# ─────────────────────────────────────────────────────────────
# Detecção de violações
# ─────────────────────────────────────────────────────────────

def detect_contract_violations(
    contracts: Dict[str, Dict[str, Any]],
    callers: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []

    for callee_name, contract in contracts.items():
        # Click gerencia a assinatura — não validamos chamadas diretas
        if contract.get('is_click_invoked'):
            continue

        declared_params = contract['params']
        declared_names = {p['name'] for p in declared_params}
        required_positional = contract['required_args']
        has_injected_ctx = contract.get('has_injected_ctx', False)

        for call in callers.get(callee_name, []):
            # Ignora chamadas com *args/**kwargs
            if call['has_star_args'] or call['has_star_kwargs']:
                continue
            # Ignora self.X() e super().X() — método/bound
            if call.get('is_self_call') or call.get('is_super_call'):
                continue

            n_pos = call['args_passed']
            n_kw = len(call['kwargs_passed'])
            n_total = n_pos + n_kw
            n_req = required_positional

            # Ajusta: se ctx injetado, conta 1 a mais no "recebido"
            effective_total = n_total + (1 if has_injected_ctx else 0)

            # Argumentos obrigatórios: se a soma (pos + kw) < required → falta
            if n_total < n_req:
                violations.append({
                    'type': 'MISSING_ARGS',
                    'callee': callee_name,
                    'caller': call['caller'],
                    'module': call['module'],
                    'line': call['line'],
                    'expected': f'>={n_req}',
                    'got': n_total,
                    'detail': f"Faltam {n_req - n_total} argumento(s) obrigatório(s) "
                              f"(pos={n_pos}, kw={n_kw}, esperado>={n_req})",
                })
            elif n_total > len(declared_params):
                violations.append({
                    'type': 'EXTRA_ARGS',
                    'callee': callee_name,
                    'caller': call['caller'],
                    'module': call['module'],
                    'line': call['line'],
                    'expected': f'<={len(declared_params)}',
                    'got': n_total,
                    'detail': f"Excesso de {n_total - len(declared_params)} argumento(s)",
                })

            # Kwargs não declarados
            for kw_name in call['kwargs_passed']:
                if kw_name not in declared_names:
                    violations.append({
                        'type': 'UNEXPECTED_KWARG',
                        'callee': callee_name,
                        'caller': call['caller'],
                        'module': call['module'],
                        'line': call['line'],
                        'expected': 'kwarg declarado',
                        'got': kw_name,
                        'detail': f"kwarg '{kw_name}' não existe na assinatura",
                    })

    return violations


# ─────────────────────────────────────────────────────────────
# Conveniência: pipeline completo
# ─────────────────────────────────────────────────────────────

def analyze_contracts_from_file(
    file_path: str, module_name: str
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """
    Pipeline completo: lê arquivo → extrai contratos + callers → violações.

    Retorna (contracts, callers, violations).
    """
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as e:
        return {}, {}, [{
            'type': 'SYNTAX_ERROR',
            'callee': '-',
            'caller': '-',
            'module': module_name,
            'line': e.lineno or 0,
            'expected': '-',
            'got': '-',
            'detail': f'Sintaxe inválida: {e.msg}',
        }]

    contracts = extract_contracts(tree, module_name)
    callers = index_callers(tree, module_name)
    violations = detect_contract_violations(contracts, callers)
    return contracts, callers, violations


# ─────────────────────────────────────────────────────────────
# Renderização (para uso no CLI)
# ─────────────────────────────────────────────────────────────

def render_contracts_cli(
    contracts: Dict[str, Dict[str, Any]],
    violations: List[Dict[str, Any]],
    module: str,
    verbose: bool = False,
) -> None:
    """Imprime contratos e violações no terminal com doxcolors."""
    from doxoade.tools.doxcolors import Fore, Style

    if not contracts:
        print(Fore.YELLOW + f"  (nenhum contrato público em '{module}')" + Style.RESET_ALL)
        return

    # Cabeçalho
    print(Fore.CYAN + f"  Módulo: {Fore.WHITE}{module}" + Style.RESET_ALL)
    print(Fore.CYAN + f"  Contratos públicos: {Fore.WHITE}{len(contracts)}{Style.RESET_ALL}")
    print()

    for name, c in sorted(contracts.items()):
        # Parâmetros
        param_parts = []
        for p in c['params']:
            ptype = p['type'] or 'Any'
            pdef = f" = {p['default']}" if p['default'] else ''
            param_parts.append(f"{Fore.WHITE}{p['name']}{Style.RESET_ALL}: {Fore.CYAN}{ptype}{Style.RESET_ALL}{pdef}")
        params_str = ', '.join(param_parts)

        # Retorno
        ret_str = c['returns'] or 'Any'
        ret_colored = f"{Fore.YELLOW}{ret_str}{Style.RESET_ALL}"

        # Async
        async_prefix = f"{Fore.MAGENTA}async {Style.RESET_ALL}" if c['is_async'] else ''

        # Raises
        raises_str = ''
        if c['raises']:
            raises_list = ', '.join(c['raises'])
            raises_str = f" {Fore.RED}raises ({raises_list}){Style.RESET_ALL}"

        print(f"  {Fore.GREEN}ƒ {async_prefix}{name}{Style.RESET_ALL}({params_str}) -> {ret_colored}{raises_str}")
        if verbose:
            print(f"     {Style.DIM}Linha {c['line']} | required_args={c['required_args']}{Style.RESET_ALL}")

    # Violações
    if violations:
        print()
        print(Fore.RED + f"  ⚠ {len(violations)} violação(ões) de contrato:" + Style.RESET_ALL)
        for v in violations:
            sev_color = Fore.RED if v['type'] in ('MISSING_ARGS', 'UNEXPECTED_KWARG') else Fore.YELLOW
            print(
                f"    {sev_color}✘ [{v['type']}]{Style.RESET_ALL} "
                f"{Fore.WHITE}{v['caller']}{Style.RESET_ALL}:{v['line']} → "
                f"{Fore.CYAN}{v['callee']}{Style.RESET_ALL} "
                f"({v['detail']})"
            )
    else:
        print()
        print(Fore.GREEN + "  ✔ Nenhuma violação de contrato detectada." + Style.RESET_ALL)


# ─────────────────────────────────────────────────────────────
# Exportação: para Mermaid (contratos como labels)
# ─────────────────────────────────────────────────────────────

def contracts_to_mermaid(
    contracts: Dict[str, Dict[str, Any]],
    callers: Dict[str, List[Dict[str, Any]]],
    module: str,
) -> str:
    """
    Gera Mermaid com funções como nós e chamadas como arestas.

    Labels dos nós incluem assinatura resumida.
    """
    def _node_id(name: str) -> str:
        return 'c_' + name.replace('.', '_').replace('-', '_')

    def _short_sig(name: str, c: Dict[str, Any]) -> str:
        n_params = len(c['params'])
        ret = (c['returns'] or 'Any')[:20]
        return f"{name}({n_params} args)<br/>→ {ret}"

    lines = ['flowchart LR']
    lines.append('  classDef publicFunc fill:#1e395c,stroke:#4D91E8,stroke-width:2px,rx:6,ry:6')
    lines.append('  classDef callerFunc fill:#5a3821,stroke:#E38D53,stroke-width:2px,rx:6,ry:6')

    # Nós: contratos
    for name, c in contracts.items():
        nid = _node_id(name)
        label = _short_sig(name, c)
        lines.append(f'  {nid}["{label}"]:::publicFunc')

    # Arestas: chamadas
    seen_edges = set()
    for callee, calls in callers.items():
        if callee not in contracts:
            continue
        for call in calls:
            caller = call['caller']
            if caller == '<module>':
                caller_nid = 'c_module'
                if caller_nid not in seen_edges:
                    lines.append(f'  {caller_nid}(["📦 {module}"])')
                    seen_edges.add(caller_nid)
            else:
                caller_nid = _node_id(caller)
                if caller_nid not in seen_edges:
                    lines.append(f'  {caller_nid}["{caller}()"]:::callerFunc')
                    seen_edges.add(caller_nid)

            callee_nid = _node_id(callee)
            args_label = f"{call['args_passed']} args"
            edge_key = (caller_nid, callee_nid, call['line'])
            if edge_key not in seen_edges:
                lines.append(f'  {caller_nid} -- "{args_label}" --> {callee_nid}')
                seen_edges.add(edge_key)

    return '\n'.join(lines)

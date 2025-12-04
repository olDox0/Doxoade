# doxoade/commands/impact_analysis.py
import os
import ast
import click
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger, _get_project_config

def _resolve_relative_import(module_name, level, current_file_module):
    if level == 0: return module_name
    base_path = current_file_module.split('.')
    climb_from = base_path[:-1]
    ascended_path = climb_from[:-(level - 1)]
    if module_name:
        full_module = ascended_path + module_name.split('.')
    else:
        full_module = ascended_path
    return ".".join(full_module)

class DetailedAnalysisVisitor(ast.NodeVisitor):
    def __init__(self, current_module):
        self.imports = set()
        self.usages = set()
        self.defined_functions = set()
        self.current_module = current_module

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.level > 0:
            resolved = _resolve_relative_import(node.module, node.level, self.current_module)
            self.imports.add(resolved)
        elif node.module:
            self.imports.add(node.module)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.usages.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Load):
            self.usages.add(node.attr)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.defined_functions.add(node.name)
        self.generic_visit(node)

def _path_to_module_name(file_path, root_path):
    try:
        rel_path = os.path.relpath(file_path, root_path)
    except ValueError:
        rel_path = os.path.basename(file_path)
    base = os.path.splitext(rel_path)[0]
    normalized = base.replace('\\', '.').replace('/', '.')
    if normalized.startswith('.'):
        normalized = normalized[1:]
    return normalized

def _build_advanced_index(search_path, ignore_patterns, logger):
    click.echo(Fore.WHITE + "Mapeando estrutura do projeto...")
    index = {}
    
    for root, dirs, files in os.walk(search_path):
        dirs[:] = [d for d in dirs if d not in ignore_patterns and not d.startswith('.')]
        
        for file in files:
            if not file.endswith('.py'): continue
            
            file_path = os.path.join(root, file)
            module_name = _path_to_module_name(file_path, search_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if not content: continue
                    tree = ast.parse(content)
                
                visitor = DetailedAnalysisVisitor(module_name)
                visitor.visit(tree)
                
                index[module_name] = {
                    "path": os.path.relpath(file_path, search_path),
                    "imports": visitor.imports,
                    "calls": visitor.usages,
                    "defines": visitor.defined_functions
                }
            except Exception: continue
            
    return index

def _calculate_metrics(target_module, inbound, outbound):
    """Calcula métricas de acoplamento."""
    fan_in = len(inbound)
    fan_out = len(outbound)
    total = fan_in + fan_out
    
    instability = fan_out / total if total > 0 else 0.0
    
    # Classificação
    if instability < 0.3: status = (Fore.GREEN, "Estável (Core)")
    elif instability > 0.7: status = (Fore.YELLOW, "Instável (Orquestrador)")
    else: status = (Fore.WHITE, "Híbrido")
    
    return {
        'fan_in': fan_in,
        'fan_out': fan_out,
        'instability': instability,
        'status': status
    }

def _present_tracking_results(target_module, index):
    """Apresenta análise detalhada com métricas e visualização rica."""
    target_data = index.get(target_module)
    if not target_data: return

    defined_funcs = target_data.get("defines", set())
    
    # Recalcula dependências para métricas
    inbound_paths = set()
    for mod, data in index.items():
        if target_module in data.get("imports", set()):
            inbound_paths.add(data["path"])
            
    outbound_deps = target_data.get("imports", set())
    
    metrics = _calculate_metrics(target_module, inbound_paths, outbound_deps)
    color, status_text = metrics['status']
    
    # 1. DASHBOARD
    click.echo(Fore.CYAN + Style.BRIGHT + f"\n=== RELATÓRIO DE IMPACTO: {target_module} ===")
    click.echo("Métricas de Acoplamento:")
    click.echo(f"  • Fan-In (Quem usa):  {metrics['fan_in']}")
    click.echo(f"  • Fan-Out (O que usa): {metrics['fan_out']}")
    click.echo(f"  • Instabilidade:      {metrics['instability']:.2f} -> {color}{status_text}{Style.RESET_ALL}")
    
    click.echo(Fore.YELLOW + "\n[+] MAPA DE USO (Quem chama o quê?):")
    
    used_funcs = set()
    has_usage = False
    
    for mod, data in index.items():
        if target_module in data.get("imports", set()):
            calls = data.get("calls", set())
            intersection = calls.intersection(defined_funcs)
            
            if intersection:
                has_usage = True
                path = data.get("path")
                # Exibe agrupado
                click.echo(Fore.GREEN + f"  ▼ {path}")
                for func in sorted(intersection):
                    click.echo(Fore.WHITE + f"    └── {func}()")
                    used_funcs.update([func])
    
    if not has_usage:
        click.echo(Fore.WHITE + "    (Nenhum uso explícito de funções detectado via análise estática)")

    # 2. DEAD CODE
    unused = defined_funcs - used_funcs
    # Filtra funções privadas (_func) se a flag --public-only for usada? 
    # Por padrão, mostra tudo, mas com cor diferente se for privada
    
    if unused:
        click.echo(Fore.RED + "\n[!] FUNÇÕES NÃO REFERENCIADAS EXTERNAMENTE:")
        public_unused = [f for f in unused if not f.startswith('_')]
        private_unused = [f for f in unused if f.startswith('_')]
        
        if public_unused:
            click.echo(Fore.RED + "  Públicas (Risco Alto de Dead Code):")
            click.echo(Fore.WHITE + f"    {', '.join(sorted(public_unused))}")
            
        if private_unused:
            click.echo(Style.DIM + "  Privadas (Provavelmente uso interno):")
            click.echo(Style.DIM + f"    {', '.join(sorted(private_unused))}")

    # 3. DEPENDÊNCIAS EXTERNAS
    click.echo(Fore.YELLOW + "\n[+] CONSUMO DE RECURSOS (Chamadas):")
    calls = target_data.get("calls", set())
    external_calls = calls - defined_funcs
    builtins = {'print', 'len', 'str', 'int', 'list', 'dict', 'set', 'open', 'range', 'super', 'type', 'isinstance'}
    interesting_calls = external_calls - builtins
    
    if interesting_calls:
        # Tenta categorizar (Doxoade vs Python)
#        doxoade_calls = [c for c in interesting_calls if 'doxoade' in str(c)] # Difícil saber só pelo nome
        # Lista simples melhorada
        sorted_calls = sorted(list(interesting_calls))
        click.echo(Fore.WHITE + f"    Total: {len(sorted_calls)} chamadas únicas.")
        click.echo(Style.DIM + f"    Exemplos: {', '.join(sorted_calls[:10])}...")
    else:
        click.echo(Fore.WHITE + "    Nenhuma chamada externa relevante.")
        
    click.echo(Fore.CYAN + "="*50)

def _generate_mermaid_graph(target_module, index):
    """Gera um diagrama Mermaid baseado nas relações de chamada."""
    
    click.echo(Fore.WHITE + "\n Copie o código abaixo para um visualizador Mermaid (ex: mermaid.live):")
    click.echo(Fore.CYAN + "-" * 40)
    
    # Cabeçalho do Gráfico (TD = Top-Down)
    lines = ["graph TD"]
    
    # Estilos
    lines.append("    classDef target fill:#f9f,stroke:#333,stroke-width:2px;")
    lines.append("    classDef dependency fill:#ccf,stroke:#333,stroke-width:1px;")
    
    # Identificar nós relevantes (Quem chama e Quem é chamado)
    relevant_modules = set()
    relevant_modules.add(target_module)
    
    # Adiciona quem o alvo chama
    target_data = index.get(target_module)
    if target_data:
        for mod, data in index.items():
            if mod in target_data.get("imports", set()):
                relevant_modules.add(mod)
    
    # Adiciona quem chama o alvo
    for mod, data in index.items():
        if target_module in data.get("imports", set()):
            relevant_modules.add(mod)

    # Gera Subgraphs (Clusters por arquivo)
    for mod in relevant_modules:
        data = index.get(mod)
        if not data: continue
        
        path = data.get("path")
        clean_name = mod.replace('.', '_')
        
        lines.append(f"    subgraph {clean_name} [{path}]")
        
        # Adiciona funções definidas como nós
        funcs = data.get("defines", set())
        if not funcs:
            # Se não detectou funções, cria um nó genérico para o arquivo
            lines.append(f"        {clean_name}_mod({mod})")
        else:
            for f in funcs:
                node_id = f"{clean_name}_{f}"
                # Destaque para o alvo
                style_class = ":::target" if mod == target_module else ":::dependency"
                lines.append(f"        {node_id}({f}){style_class}")
                
        lines.append("    end")

    # Gera Arestas (Conexões) baseadas na Heurística
    # A -> B se A importa B e A usa uma função definida em B
    for mod_a in relevant_modules:
        data_a = index.get(mod_a)
        if not data_a: continue
        
        # Calls feitas por A
        calls_in_a = data_a.get("calls", set())
        
        # Verifica dependências
        imports = data_a.get("imports", set())
        
        for mod_b in relevant_modules:
            if mod_b == mod_a: continue # Ignora recursão interna por enquanto para limpar o gráfico
            
            if mod_b in imports:
                data_b = index.get(mod_b)
                if not data_b: continue
                
                defines_in_b = data_b.get("defines", set())
                
                # Interseção: A chama algo que B define
                links = calls_in_a.intersection(defines_in_b)
                
                clean_a = mod_a.replace('.', '_')
                clean_b = mod_b.replace('.', '_')
                
                for func in links:
                    # Tenta achar QUEM em A chamou (difícil estaticamente sem CFG completo)
                    # Por simplificação, ligamos o módulo A (ou uma função 'main' se houver) à função B
                    # Melhoria: Ligar nó genérico do módulo A à função B
                    
                    # Se A definiu funções, tenta ver se alguma delas contem a chamada? 
                    # (Isso exigiria um visitor mais complexo que mapeia Call -> Escopo Pai)
                    # Padrão atual: Nó do Arquivo A -> Função B
                    
                    if not data_a.get("defines"):
                        source_node = f"{clean_a}_mod"
                    else:
                        # Se não sabemos qual função chamou, usamos um nó "fictício" ou a primeira função pública
                        # Para ficar limpo, vamos ligar do subgrafo A (invisível) ou criar um nó 'import'
                        source_node = f"{clean_a}_call" 
                        # Hack_visual: criamos um nó de chamada
                        if f"{clean_a}_call(Calls)" not in lines: # Evita duplicar no loop
                             lines.append(f"    {clean_a}_call(Calls) --> {clean_b}_{func}")
                        continue

                    lines.append(f"    {source_node} --> {clean_b}_{func}")

    click.echo(Fore.WHITE + "\n".join(lines))
    click.echo(Fore.CYAN + "-" * 40)


@click.command('impact-analysis')
@click.pass_context
@click.argument('file_path_arg', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--path', 'project_path', type=click.Path(exists=True), default='.')
@click.option('--tracking', '-t', is_flag=True, help="Ativa rastreamento profundo.")
@click.option('--graph', '-g', is_flag=True, help="Gera código de diagrama Mermaid.") # <--- NOVA FLAG
def impact_analysis(ctx, file_path_arg, project_path, tracking, graph):
    """Analisa dependências e rastreia uso de código."""
    with ExecutionLogger('impact-analysis', project_path, ctx.params) as logger:
        config = _get_project_config(logger, start_path=project_path)
        search_path = config.get('search_path', '.')
        ignore_patterns = {item.strip('/\\') for item in config.get('ignore', [])}
        project_index = _build_advanced_index(search_path, ignore_patterns, logger)
        target_module = _path_to_module_name(file_path_arg, search_path)
        
        if target_module not in project_index:
            click.echo(Fore.RED + "Arquivo não indexado."); return

        # Se pediu gráfico, gera SÓ o gráfico e sai (ou mostra ambos?)
        if graph:
            _generate_mermaid_graph(target_module, project_index)
            return
            
        # Análise Padrão (Imports)
        # CORRIGIDO: usa 'project_index' em vez de 'index'
        data = project_index[target_module]
        inbound = data.get("imports", set())
        outbound = [idx_data["path"] for mod, idx_data in project_index.items() if target_module in idx_data.get("imports", set())]

        click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- Impacto: {target_module} ---")
        click.echo(Fore.YELLOW + f"\n[IN] Depende de ({len(inbound)}):")
        for dep in sorted(inbound): click.echo(f"  - {dep}")
        
        click.echo(Fore.YELLOW + f"\n[OUT] Usado por ({len(outbound)}):")
        for dep in sorted(outbound): click.echo(f"  - {dep}")

        if tracking:
            _present_tracking_results(target_module, project_index)
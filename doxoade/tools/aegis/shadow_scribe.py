# doxoade/doxoade/tools/vulcan/shadow_scribe.py
import ast
import textwrap

class NexusShadowReturnScribe(ast.NodeTransformer):
    """Intercepta instruções de retorno para capturar as saídas (I/O) de dados no Sombra."""
    def __init__(self, func_name, filename):
        self.func_name = func_name
        self.filename = filename

    def visit_Return(self, node):
        if node.value is None:
            # Retorno vazio/implícito
            log_stmt = (
                f"_dox_logged_exit = True\n"
                f"chief_heartbeat('SHADOW', 'EXIT', {{'f': '{self.func_name}', 'status': 'COMPLETE', 'snapshot': 'None'}})"
            )
            parsed_nodes = ast.parse(log_stmt).body
            return [
                parsed_nodes[0],  # Atribuição da flag de controle
                parsed_nodes[1],  # Execução do heartbeat de saída explícita
                node
            ]

        # Retorno com expressão (return <expr>)
        # Transforma em:
        # _dox_ret_val = <expr>
        # _dox_logged_exit = True
        # chief_heartbeat('SHADOW', 'EXIT', {'f': func_name, 'status': 'COMPLETE', 'snapshot': str(_dox_ret_val)[:200]})
        # return _dox_ret_val
        log_stmt = (
            f"_dox_logged_exit = True\n"
            f"chief_heartbeat('SHADOW', 'EXIT', {{'f': '{self.func_name}', 'status': 'COMPLETE', 'snapshot': str(_dox_ret_val)[:200]}})"
        )
        
        assign_node = ast.Assign(
            targets=[ast.Name(id='_dox_ret_val', ctx=ast.Store())],
            value=node.value
        )
        
        parsed_nodes = ast.parse(log_stmt).body
        return [
            assign_node,
            parsed_nodes[0],  # Atribuição da flag de controle
            parsed_nodes[1],  # Execução do heartbeat
            ast.Return(value=ast.Name(id='_dox_ret_val', ctx=ast.Load()))
        ]

    def visit_FunctionDef(self, node):
        return node

    def visit_AsyncFunctionDef(self, node):
        return node


class NexusShadowScribe(ast.NodeTransformer):
    def __init__(self, filename):
        self.filename = filename

    def visit_FunctionDef(self, node):
        if node.name.startswith('_') or node.name in ['chief_heartbeat', 'activate_protocol']:
            return node

        # 1. ENTER: Rastro de entrada com argumentos
        arg_names = [arg.arg for arg in node.args.args if arg.arg != 'self']
        arg_capture = ", ".join([f"'{n}': {n}" for n in arg_names])
        
        # 2. Transforma retornos explícitos do corpo da função para capturar o I/O
        ret_scribe = NexusShadowReturnScribe(node.name, self.filename)
        node.body = ret_scribe.visit(ast.Module(body=node.body)).body

        # 3. Cirurgia de Veredito: Diferencia Sucesso de Colapso e injeta o bloco try-except-finally
        # Inclui o controle de redundância via _dox_logged_exit
        telemetry_payload = textwrap.dedent(f"""
            chief_heartbeat('SHADOW', 'ENTER', {{'f': '{node.name}', 'file': '{self.filename}', 'args': {{{arg_capture}}}}})
            _dox_status = 'SUCCESS'
            _dox_logged_exit = False
            try:
                pass
            except Exception as _dox_err:
                _dox_status = 'CRASHED'
                if type(_dox_err).__name__ not in ('Exit', 'Abort'):
                    import traceback as _tb
                    from doxoade.rescue import activate_protocol as _ap
                    _ap(_tb.format_exc(), context=locals())
                raise _dox_err
            finally:
                if not _dox_logged_exit:
                    chief_heartbeat('SHADOW', 'EXIT', {{'f': '{node.name}', 'status': _dox_status}})
        """).strip()

        vax_nodes = ast.parse(telemetry_payload).body

        # Injeta o corpo original dentro do try (quarto nó da lista vax_nodes, índice 3)
        # vax_nodes[0] -> heartbeat de ENTER
        # vax_nodes[1] -> inicialização do status
        # vax_nodes[2] -> inicialização da flag de bypass
        # vax_nodes[3] -> estrutura try-except-finally
        vax_nodes[3].body = node.body
        node.body = vax_nodes
        return node
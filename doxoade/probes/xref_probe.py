# doxoade/probes/xref_probe.py
import ast
import sys
import os
import json

class ProjectIndexer(ast.NodeVisitor):
    """
    Passo 1: Cria um índice de definições (Funções, Classes e Variáveis Globais).
    """
    def __init__(self):
        self.index = {}
        self.current_file = None

    def index_file(self, file_path):
        self.current_file = os.path.abspath(file_path)
        self.index[self.current_file] = {'defs': {}}
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            tree = ast.parse(content, filename=file_path)
            self.visit(tree)
        except Exception:
            pass 

    def visit_FunctionDef(self, node):
        # Detecta se é comando Click
        is_click = False
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in ['command', 'group']:
                is_click = True
            elif isinstance(dec, ast.Attribute) and dec.attr in ['command', 'group']:
                is_click = True

        args_count = len(node.args.args)
        defaults_count = len(node.args.defaults)
        min_args = args_count - defaults_count
        
        self.index[self.current_file]['defs'][node.name] = {
            'type': 'function',
            'min_args': min_args,
            'max_args': args_count,
            'has_varargs': node.args.vararg is not None,
            'is_click': is_click,
            'lineno': node.lineno
        }

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node):
        self.index[self.current_file]['defs'][node.name] = {
            'type': 'class',
            'lineno': node.lineno
        }

    def visit_Assign(self, node):
        if node.col_offset == 0:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.index[self.current_file]['defs'][target.id] = {
                        'type': 'variable',
                        'lineno': node.lineno
                    }

class IntegrityChecker(ast.NodeVisitor):
    def __init__(self, index, project_root):
        self.index = index
        self.project_root = os.path.abspath(project_root)
        self.current_file = None
        self.findings = []
        self.imports_map = {} 

    def check_file(self, file_path):
        self.current_file = os.path.abspath(file_path)
        self.imports_map = {} 
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            tree = ast.parse(content, filename=file_path)
            self.visit(tree)
        except Exception:
            pass

    def _resolve_module_path(self, module_name, level=0):
        if not module_name and level == 0: return None
        start_dir = self.project_root
        if level > 0:
            start_dir = os.path.dirname(self.current_file)
            
        parts = module_name.split('.') if module_name else []
        
        candidate = os.path.join(start_dir, *parts) + ".py"
        if os.path.abspath(candidate) in self.index: 
            return os.path.abspath(candidate)
        
        candidate_pkg = os.path.join(start_dir, *parts, "__init__.py")
        if os.path.abspath(candidate_pkg) in self.index:
            return os.path.abspath(candidate_pkg)

        candidate_root = os.path.join(self.project_root, *parts) + ".py"
        if os.path.abspath(candidate_root) in self.index:
            return os.path.abspath(candidate_root)
            
        return None

    def visit_ImportFrom(self, node):
        target_file = self._resolve_module_path(node.module, node.level)
        if not target_file: return

        target_defs = self.index[target_file]['defs']

        for alias in node.names:
            if alias.name == '*': continue
            
            if alias.name not in target_defs:
                self.findings.append({
                    'severity': 'ERROR',
                    'category': 'BROKEN-LINK',
                    'message': f"Import quebrado: '{alias.name}' não foi encontrado em '{node.module}'.",
                    'line': node.lineno,
                    'file': self.current_file
                })
            else:
                local_name = alias.asname or alias.name
                self.imports_map[local_name] = target_defs[alias.name]

    def visit_Call(self, node):
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        
        if not func_name: return

        def_info = None
        
        # 1. Tenta resolver via Imports (Módulos externos indexados)
        if func_name in self.imports_map:
            def_info = self.imports_map[func_name]
        # 2. Tenta resolver localmente (No mesmo arquivo)
        elif self.current_file in self.index and func_name in self.index[self.current_file]['defs']:
            def_info = self.index[self.current_file]['defs'][func_name]
            
        if def_info:
            if def_info.get('type') == 'function':
                if def_info.get('is_click'):
                    self.generic_visit(node)
                    return

                args_passed = len(node.args) + len(node.keywords)
                min_req = def_info['min_args']
                max_req = def_info['max_args']
                
                if not def_info['has_varargs']:
                    if args_passed < min_req:
                        self.findings.append({
                            'severity': 'WARNING',
                            'category': 'SIGNATURE-MISMATCH',
                            'message': f"Chamada para '{func_name}' com poucos argumentos (passou {args_passed}, exige {min_req}).",
                            'line': node.lineno,
                            'file': self.current_file
                        })
                    elif len(node.keywords) == 0 and args_passed > max_req:
                        self.findings.append({
                            'severity': 'WARNING',
                            'category': 'SIGNATURE-MISMATCH',
                            'message': f"Chamada para '{func_name}' com muitos argumentos (passou {args_passed}, máx {max_req}).",
                            'line': node.lineno,
                            'file': self.current_file
                        })
        
        # Continua visitando os argumentos
        self.generic_visit(node)

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print("[]"); sys.exit(0)
        project_root = sys.argv[1]
        input_data = sys.stdin.read()
        if not input_data:
            print("[]"); sys.exit(0)
        files = json.loads(input_data)
        
        indexer = ProjectIndexer()
        for f in files: indexer.index_file(f)
            
        checker = IntegrityChecker(indexer.index, project_root)
        for f in files: checker.check_file(f)
            
        print(json.dumps(checker.findings))
    except Exception:
        print("[]")
# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_utils.py
"""
Support_Utils para Intelligence (PASC 1.2 / MPoT 17).
Foco: Extração de Metadados de Documentação e Análise de Fluxo de IO.
"""
import os
import ast
import re
import sys
import json
from typing import List, Dict, Any
# Padrões de IO para busca via AST
IO_KEYWORDS = {'open', 'read', 'write', 'load', 'dump', 'print', 'input', 'get', 'post', 'request'}
IO_MODULES = {'os', 'sys', 'pathlib', 'shutil', 'subprocess', 'socket', 'requests', 'json', 'toml'}

def get_ignore_spec(root: str):
    """
    Carrega especificações de ignorar do pyproject.toml ou defaults (PASC 8.13/10).
    """
    import toml
    import pathspec
    
    # Padrões obrigatórios de sobrevivência (Sempre ignorar)
    default_patterns = [
        '.git/', '__pycache__/', 'venv/', '.venv/', 
        '*.pyc', '.vscode/', '.idea/', 'dist/', 'build/',
        '*.bak', 'recovery_zone/', 'chief_dossier.json'
    ]
    
    config_path = os.path.join(root, "pyproject.toml")
    patterns = default_patterns.copy()
    if os.path.exists(config_path):
        try:
            config = toml.load(config_path)
            # Busca em tool.doxoade.ignore
            toml_patterns = config.get("tool", {}).get("doxoade", {}).get("ignore", [])
            if toml_patterns:
                patterns.extend(toml_patterns)
        except Exception as e:
            _print_forensic("get_ignore_spec_toml", e)
    return pathspec.PathSpec.from_lines('gitwildmatch', patterns)

class ChiefInsightVisitor(ast.NodeVisitor):
    def __init__(self):
        self.stats = {
            "classes":      [], "functions": [], 
            "imports":      {"stdlib": [], "external": []},
            "complexities": [], "mpot_4_violations": 0, "docstrings": {}
        }
    def _detect_io_calls(self, node: ast.AST) -> List[str]:
        """Rastreia chamadas de IO dentro da função (PASC 8.2)."""
        io_found = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                # Detecta chamadas diretas (ex: print())
                if isinstance(child.func, ast.Name) and child.func.id in IO_KEYWORDS:
                    io_found.add(child.func.id)
                # Detecta chamadas de módulo (ex: os.path.join())
                elif isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name) and child.func.value.id in IO_MODULES:
                        io_found.add(f"{child.func.value.id}.{child.func.attr}")
        return list(io_found)
    def _analyze_func(self, node):
        line_count = (node.end_lineno - node.lineno) if node.end_lineno else 0
        if line_count > 60: self.stats["mpot_4_violations"] += 1
        
        complexity = 1 + sum(1 for child in ast.walk(node) if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)))
        self.stats["complexities"].append(complexity)
        
        self.stats["functions"].append({
            "name":      node.name, 
            "lines":     line_count, 
            "complexity":complexity, 
            "args":      len(node.args.args),
            "io_flow":   self._detect_io_calls(node) # Novo: Rastreio de Fluxo
        })
def visit_FunctionDef(self, node):
    doc = ast.get_docstring(node) or ""
    if doc:
        self.stats["docstrings"][node.name] = doc
    self._analyze_func(node)   # delega — salva dict consistente, conta mpot corretamente
    self.generic_visit(node)
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._analyze_func(node)
        self.generic_visit(node)
    # REINTEGRANDO LOGICA RESGATADA DO DOSSIER (22/01)
    def visit_ClassDef(self, node):
        methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.stats['classes'].append({'name': node.name, 'methods_count': len(methods)})
        self.generic_visit(node)
    def visit_Import(self, node):
        for alias in node.names:
            self._sort_import(alias.name)
    def visit_ImportFrom(self, node):
        if node.module:
            self._sort_import(node.module)
    def _sort_import(self, name):
        """Separa stdlib de externos (PASC 6.1)."""
        root_mod = name.split('.')[0]
        if root_mod in sys.builtin_module_names or root_mod in ['os', 'sys', 'ast', 'json', 're', 'time']:
            self.stats["imports"]["stdlib"].append(name)
        else:
            self.stats["imports"]["external"].append(name)
def analyze_document(file_path: str, ext: str) -> Dict[str, Any]:
    """Extrai dados ricos de documentação (PASC 3.2 / 8.3)."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if ext == '.json':
                data = json.loads(content)
                # Retorna chaves principais para não sobrecarregar se for gigante
                return {"doc_type": "structured_data", "keys": list(data.keys())[:20], "raw": data if len(content) < 5000 else "truncated"}
            elif ext == '.md':
                headers = re.findall(r'^#+\s+(.*)', content, re.MULTILINE)
                return {"doc_type": "markdown", "headers": headers[:10], "brief": content[:500]}
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
        return {"error": str(e)}
    return {}
def find_debt_tags(content: str) -> List[Dict[str, Any]]:
    debt = []
    patterns = r'#\s*(TODO|FIXME|BUG|HACK|ADTI)\b[:\s]*(.*)'
    for i, line in enumerate(content.splitlines(), 1):
        m = re.search(patterns, line, re.IGNORECASE)
        if m: debt.append({"line": i, "tag": m.group(1).upper(), "msg": m.group(2).strip()})
    return debt
def _print_forensic(func_name: str, e: Exception):
    import os as _dox_os
    _, _, exc_tb = sys.exc_info()
    f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "unknown"
    line_n = exc_tb.tb_lineno if exc_tb else 0
    print(f"\033[1;34m\n[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: {func_name}\033[0m")
    print(f"\033[31m    ■ Type: {type(e).__name__} | Value: {e}\033[0m")
    
class SemanticAnalyzer:
    """Extrai a estrutura lógica para tokens de IA (OSL 4 / PASC 8.10)."""
    def __init__(self, code):
        self.code = code
        try:
            self.tree = ast.parse(code)
        except Exception as e:
            import sys as _dox_sys, os as _dox_os
            exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
            f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_n = exc_tb.tb_lineno
            print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: __init__\033[0m")
            print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
            self.tree = None

    def get_map(self):
        if not self.tree: return {"role": "CORRUPT_SOURCE"}
        
        # Identifica o papel do arquivo (God Assignment)
        imports = [n.names[0].name for n in ast.walk(self.tree) if isinstance(n, ast.Import)]
        
        return {
            "role":             self._infer_role(imports),
            "classes":          [n.name for n in ast.walk(self.tree) if isinstance(n, ast.ClassDef)],
            "exported_symbols": [n.name for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) if not n.name.startswith('_')],
            "complexity_index":  len([n for n in ast.walk(self.tree) if isinstance(n, (ast.If, ast.For, ast.While))])
        }

    def _infer_role(self, imports):
        if 'click'   in imports: return "ZEUS_CLI"
        if 'socket'  in imports  or 'requests' in imports: return "POSEIDON_NET"
        if 'sqlite3' in imports: return "HADES_DB"
        return "GENERIC_LOGIC"

    def get_summary(self):
        """Retorna um mapa simplificado da 'alma' do arquivo."""
        if not self.tree: 
            return {"status": "corrupt", "classes": [], "functions": [], "complexity": 0}
        
        return {
            "status": "stable",
            "classes":    [n.name for n in ast.walk(self.tree) if isinstance(n, ast.ClassDef)],
            "functions":  [n.name for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)],
            "complexity":  len([n for n in ast.walk(self.tree) if isinstance(n, (ast.If, ast.For, ast.While))])
        }

    def get_docstrings(self):
        """Mapeia docstrings a símbolos para entendimento contextual."""
        docs = {}
        if not self.tree: return docs
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                doc = ast.get_docstring(node)
                if doc:
                    name = getattr(node, 'name', 'module_root')
                    docs[name] = {"intent": doc.split('\n')[0], "full_doc": doc}
        return docs
        
class NexusThothMapper:
    """Mapeia a topologia do código para o panteão Doxoade (AI-Ready)."""
    GOD_MAP = {
        "Zeus":    {"keywords":["cli",   "main",        "orchestrator"],"imports":["click", "getopt.h", "argparse.hpp"]},
        "Poseidon":{"keywords":["stream","socket",      "io", "flow"  ],"imports":["asyncio","socket", "sys/socket.h", "curl/curl.h", "arpa/inet.h"]},
        "Hades":   {"keywords":["db",    "storage",     "cache"       ],"imports":["sqlite3","json", "sqlite3.h", "mysql.h", "pqxx"]},
        "Atena":   {"keywords":["logic", "architecture","nexus"       ],"imports": ["abc", "memory", "algorithm", "vector"]},
        "Anúbis":  {"keywords": ["check", "security",    "audit"       ],"imports":["hashlib", "re", "openssl/sha.h", "openssl/md5.h", "regex.h"]}
    }
    
    @classmethod
    def identify(cls, file_path, imports):
        name = file_path.lower()
        for god, criteria in cls.GOD_MAP.items():
            if any(k in name for k in criteria["keywords"]) or \
               any(imp in imports for imp in criteria["imports"]):
                return god
        return "Dionísio"


class CSemanticAnalyzer:
    """Extrai a estrutura lógica para tokens de IA de arquivos C/C++ via Regex (PASC 8.15)."""
    def __init__(self, code):
        self.code = code
        self.classes = []
        self.functions = []
        self.includes =[]
        self.complexity = 1
        self._parse()

    def _parse(self):
        # 1. Mapeamento de Includes
        self.includes = re.findall(r'#include\s*[<"]([^>"]+)[>"]', self.code)
        
        # 2. Mapeamento de Classes e Structs
        self.classes = re.findall(r'\b(?:class|struct)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', self.code)
        
        # 3. Mapeamento de Funções (Heurística)
        # Captura: Tipo Retorno + Nome Função + (Args) + {
        func_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_*:&<>\s]+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^;]*\)\s*\{'
        funcs = re.findall(func_pattern, self.code)
        
        # Filtra palavras reservadas capturadas acidentalmente como funções
        reserved = {'if', 'for', 'while', 'switch', 'catch', 'return'}
        self.functions = list(set([f for f in funcs if f not in reserved]))
        
        # 4. Mapeamento de Complexidade (Ramos lógicos)
        logic_branches = re.findall(r'\b(?:if|for|while|catch|case)\b', self.code)
        self.complexity = len(logic_branches) + 1

    def get_summary(self):
        """Retorna um mapa simplificado da 'alma' do arquivo C/C++."""
        return {
            "status": "stable_c_cpp",
            "classes": self.classes,
            "functions": self.functions,
            "complexity": self.complexity
        }

    def get_docstrings(self):
        """Extração simplificada de blocos de comentários."""
        docs = {}
        blocks = re.findall(r'/\*\*?(.*?)\*/', self.code, re.DOTALL)
        if blocks:
            docs["c_cpp_comments"] = {"intent": "Extracted block comments", "full_doc": "\n".join(blocks[:3])}
        return docs
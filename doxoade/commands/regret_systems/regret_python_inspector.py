# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_python_inspector.py
"""
🐍 Inspetor Semântico de Símbolos, Comandos Click e Assinaturas em Código Python.
Utiliza a AST nativa do Python 3.12 para auditar a perda de funções, classes, opções CLI
e salvaguardas com suporte a inteligência de relocação.
"""

from __future__ import annotations
import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional

try:
    from doxoade.commands.regret_systems.regret_lua_inspector import RegretFinding
except ImportError:
    from .regret_lua_inspector import RegretFinding


@dataclass
class PythonFunctionMeta:
    name: str
    args: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    click_options: List[str] = field(default_factory=list)
    click_command_name: Optional[str] = None
    calls: Set[str] = field(default_factory=set)
    has_try_except: bool = False
    start_line: int = 1
    end_line: int = 1
    raw_code: str = ""


@dataclass
class PythonInventory:
    functions: Dict[str, PythonFunctionMeta] = field(default_factory=dict)
    classes: Dict[str, List[str]] = field(default_factory=dict)  # Class -> [methods]
    click_commands: Dict[str, str] = field(default_factory=dict) # cmd_name -> func_name
    all_calls: Set[str] = field(default_factory=set)


class PythonASTVisitor(ast.NodeVisitor):
    """Varre a AST extraindo inventário completo de funções, classes e decorators Click."""

    def __init__(self, source_code: str):
        self.source_lines = source_code.splitlines()
        self.inventory = PythonInventory()
        self.current_class = None

    def visit_ClassDef(self, node: ast.ClassDef):
        prev_class = self.current_class
        self.current_class = node.name
        self.inventory.classes[node.name] = []
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_func(node)

    def _process_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        func_name = f"{self.current_class}.{node.name}" if self.current_class else node.name
        if self.current_class:
            self.inventory.classes[self.current_class].append(node.name)

        args_list = [a.arg for a in node.args.args]
        decorators_list = []
        click_opts = []
        click_cmd = None

        for d in node.decorator_list:
            d_str = ast.unparse(d) if hasattr(ast, "unparse") else ""
            decorators_list.append(d_str)

            # Detector de Click Command / Group
            if "command(" in d_str or "group(" in d_str:
                m = re.search(r'["\']([^"\']+)["\']', d_str)
                click_cmd = m.group(1) if m else node.name
                self.inventory.click_commands[click_cmd] = func_name

            # Detector de Click Options
            if "option(" in d_str or "argument(" in d_str:
                m = re.search(r'["\'](--[A-Za-z0-9_\-]+|-[A-Za-z0-9_\-]+)["\']', d_str)
                if m:
                    click_opts.append(m.group(1))

        # Coleta chamadas de função internas e blocos try
        calls = set()
        has_try = False
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                if isinstance(sub.func, ast.Name):
                    calls.add(sub.func.id)
                    self.inventory.all_calls.add(sub.func.id)
                elif isinstance(sub.func, ast.Attribute):
                    calls.add(sub.func.attr)
                    self.inventory.all_calls.add(sub.func.attr)
            elif isinstance(sub, (ast.Try, ast.TryStar)):
                has_try = True

        start_l = node.lineno
        end_l = getattr(node, "end_lineno", start_l + 10)
        raw_lines = self.source_lines[start_l - 1:end_l]
        raw_code = "\n".join(raw_lines)

        self.inventory.functions[func_name] = PythonFunctionMeta(
            name=func_name,
            args=args_list,
            decorators=decorators_list,
            click_options=click_opts,
            click_command_name=click_cmd,
            calls=calls,
            has_try_except=has_try,
            start_line=start_l,
            end_line=end_l,
            raw_code=raw_code,
        )

        self.generic_visit(node)


class RegretPythonInspector:
    """Inspetor Semântico Diferencial para Python com inteligência de relocação."""

    @classmethod
    def extract_inventory(cls, source_code: str) -> Optional[PythonInventory]:
        try:
            tree = ast.parse(source_code)
            visitor = PythonASTVisitor(source_code)
            visitor.visit(tree)
            return visitor.inventory
        except Exception:
            return None

    @classmethod
    def compare(
        cls, old_code: str, new_code: str, file_name: str = ""
    ) -> List[RegretFinding]:
        findings: List[RegretFinding] = []

        old_inv = cls.extract_inventory(old_code)
        new_inv = cls.extract_inventory(new_code)

        if not old_inv or not new_inv:
            return findings

        # 1. Comandos CLI Click Perdidos
        for cmd_name, func_name in old_inv.click_commands.items():
            if cmd_name not in new_inv.click_commands:
                # Checa se o comando foi apenas renomeado ou a função ainda existe
                if func_name in new_inv.functions:
                    findings.append(RegretFinding(
                        category="CLI_COMMAND_MUTATED",
                        identifier=f"click.command({cmd_name})",
                        severity="high",
                        old_line_approx=old_inv.functions[func_name].start_line,
                        snippet_lost=f"@click.command('{cmd_name}')",
                        impact_description=f"O comando CLI '{cmd_name}' foi desregistrado da função '{func_name}'.",
                        mitigation_hint=f"Restaurar decorator @click.command('{cmd_name}') em {func_name}."
                    ))
                else:
                    findings.append(RegretFinding(
                        category="CLI_COMMAND_LOST",
                        identifier=f"click.command({cmd_name})",
                        severity="critical",
                        old_line_approx=old_inv.functions[func_name].start_line,
                        snippet_lost=old_inv.functions[func_name].raw_code,
                        impact_description=f"O comando CLI '{cmd_name}' e sua função de execução foram extirpados.",
                        mitigation_hint=f"Restaurar o comando '{cmd_name}' e sua implementação."
                    ))

        # 2. Funções e Métodos Perdidos
        for func_name, meta in old_inv.functions.items():
            if func_name not in new_inv.functions:
                # Checa se foi uma Relocação de método entre classes
                short_name = func_name.split(".")[-1]
                relocated_target = None
                for new_f in new_inv.functions.keys():
                    if new_f.split(".")[-1] == short_name:
                        relocated_target = new_f
                        break

                if relocated_target:
                    findings.append(RegretFinding(
                        category="FUNCTION_RELOCATED",
                        identifier=f"{func_name} -> {relocated_target}",
                        severity="low",
                        old_line_approx=meta.start_line,
                        snippet_lost=meta.raw_code,
                        impact_description=f"A função '{func_name}' foi refatorada e movida para '{relocated_target}'. A capacidade foi preservada no arquivo.",
                        mitigation_hint="Confirmar se todos os pontos de chamada foram atualizados."
                    ))
                else:
                    findings.append(RegretFinding(
                        category="FUNCTION_DROPPED",
                        identifier=func_name,
                        severity="high",
                        old_line_approx=meta.start_line,
                        snippet_lost=meta.raw_code,
                        impact_description=f"A função/método '{func_name}' foi excluído do arquivo Python.",
                        mitigation_hint=f"Verificar se {func_name} ainda é consumido por outros módulos do sistema."
                    ))
            else:
                # Função existe em ambos: checa mutação de argumentos
                new_meta = new_inv.functions[func_name]
                lost_args = [a for a in meta.args if a not in new_meta.args and a != "self" and a != "cls"]
                if lost_args:
                    # Comandos Click sofrem evolução natural de flags CLI
                    if meta.click_command_name or new_meta.click_command_name:
                        cmd_name = new_meta.click_command_name or meta.click_command_name
                        findings.append(RegretFinding(
                            category="CLI_OPTION_REFACTORED",
                            identifier=f"{func_name}(removido {', '.join(lost_args)})",
                            severity="low",
                            old_line_approx=meta.start_line,
                            snippet_lost=f"def {func_name}({', '.join(meta.args)})",
                            impact_description=f"Opções/parâmetros do comando CLI '{cmd_name}' foram modernizados: {', '.join(lost_args)}.",
                            mitigation_hint=f"Confirmar se as novas flags de CLI suprem o comando '{cmd_name}'."
                        ))
                    else:
                        findings.append(RegretFinding(
                            category="SIGNATURE_BREAK",
                            identifier=f"{func_name}(removido {', '.join(lost_args)})",
                            severity="high",
                            old_line_approx=meta.start_line,
                            snippet_lost=f"def {func_name}({', '.join(meta.args)})",
                            impact_description=f"A assinatura de '{func_name}' perdeu parâmetros essenciais: {', '.join(lost_args)}.",
                            mitigation_hint="Manter parâmetros antigos com valores padrão (default) para evitar quebra de compatibilidade."
                        ))

        # 3. Classes Deletadas
        for cls_name, methods in old_inv.classes.items():
            if cls_name not in new_inv.classes:
                findings.append(RegretFinding(
                    category="CLASS_DROPPED",
                    identifier=cls_name,
                    severity="critical",
                    old_line_approx=1,
                    snippet_lost=f"class {cls_name} ({len(methods)} métodos)",
                    impact_description=f"A classe '{cls_name}' inteira foi removida.",
                    mitigation_hint=f"Verificar instâncias dependentes de {cls_name} no Doxoade."
                ))

        return findings

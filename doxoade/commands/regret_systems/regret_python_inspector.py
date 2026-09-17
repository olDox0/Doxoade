# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_python_inspector.py
"""
🐍 Inspetor Semântico de Símbolos, Comandos Click, Assinaturas e Orfandade em Código Python.
Fase 3: Detecção de Funções Privadas Zumbis, Handlers Desconectados e Métodos Órfãos via AST (Python 3.12).
Compliance: ProDeNov 1.2.1 | PASC-6.1
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
    is_method: bool = False
    class_name: Optional[str] = None


@dataclass
class PythonInventory:
    functions: Dict[str, PythonFunctionMeta] = field(default_factory=dict)
    classes: Dict[str, List[str]] = field(default_factory=dict)
    click_commands: Dict[str, str] = field(default_factory=dict)
    all_calls: Set[str] = field(default_factory=set)
    exported_symbols: Set[str] = field(default_factory=set)  # Símbolos definidos em __all__


class PythonASTVisitor(ast.NodeVisitor):
    """Varre a AST extraindo inventário completo de funções, classes, decorators e chamadas."""

    def __init__(self, source_code: str):
        self.source_lines = source_code.splitlines()
        self.inventory = PythonInventory()
        self.current_class = None

    def visit_Assign(self, node: ast.Assign):
        # Detecta __all__ = ["foo", "bar"]
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            self.inventory.exported_symbols.add(elt.value)
        self.generic_visit(node)

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
            if "command(" in d_str or "group(" in d_str:
                m = re.search(r'["\']([^"\']+)["\']', d_str)
                click_cmd = m.group(1) if m else node.name
                self.inventory.click_commands[click_cmd] = func_name
            if "option(" in d_str or "argument(" in d_str:
                m = re.search(r'["\'](--[A-Za-z0-9_\-]+|-[A-Za-z0-9_\-]+)["\']', d_str)
                if m:
                    click_opts.append(m.group(1))

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
            is_method=self.current_class is not None,
            class_name=self.current_class,
        )
        self.generic_visit(node)


class RegretPythonInspector:
    """Inspetor Semântico Diferencial e de Orfandade para Python."""

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
    def audit_orphans(
        cls,
        inventory: PythonInventory,
        source_code: str,
        file_name: str = ""
    ) -> List[RegretFinding]:
        """
        Detecta funções privadas e métodos auxiliares zumbis (call_count == 0 no próprio arquivo).
        """
        findings: List[RegretFinding] = []
        lines = source_code.splitlines()

        # Métodos de protocolo/mágicos padrão que não são chamados diretamente
        MAGIC_METHODS = {
            "__init__", "__new__", "__str__", "__repr__", "__call__",
            "__enter__", "__exit__", "__getitem__", "__setitem__",
            "__delitem__", "__iter__", "__next__", "__len__", "__eq__",
            "__hash__", "__post_init__"
        }

        for func_name, meta in inventory.functions.items():
            base_name = func_name.split(".")[-1]

            # 1. Ignora métodos mágicos e especiais do Python
            if base_name in MAGIC_METHODS:
                continue

            # 2. Ignora se for comando ou grupo Click registrado
            # if meta.click_command_name or any("command" in d or "group" in d for d in meta.decorators):
            #     continue

            if (
                meta.click_command_name
                or any("command" in d or "group" in d or "injector" in d or "register" in d for d in meta.decorators)
                or len(meta.decorators) > 0  # Qualquer função com decorator de registro é consumida em import-time
            ):
                continue

            # 3. Ignora se o símbolo estiver exportado explicitamente em __all__
            if base_name in inventory.exported_symbols or func_name in inventory.exported_symbols:
                continue

            # 4. Ignora métodos com decorators públicos (ex: @property, @classmethod, @staticmethod)
            # se a classe for pública (eles podem ser consumidos externamente)
            is_public_api = False
            for d in meta.decorators:
                if d in ("property", "classmethod", "staticmethod") and not base_name.startswith("_"):
                    is_public_api = True
                    break
            if is_public_api and not base_name.startswith("_"):
                continue

            # 5. Para funções privadas/internas (prefixadas com '_'):
            # Elas obrigatoriamente devem ser chamadas no próprio arquivo!
            if base_name.startswith("_") and not base_name.startswith("__"):
                if base_name not in inventory.all_calls:
                    snippet = lines[meta.start_line - 1].strip() if meta.start_line <= len(lines) else f"def {base_name}(...)"
                    findings.append(RegretFinding(
                        category="ORPHAN_PYTHON_FUNCTION",
                        identifier=func_name,
                        severity="medium",
                        old_line_approx=meta.start_line,
                        snippet_lost=snippet,
                        impact_description=(
                            f"A função/método interno '{func_name}' foi definido na linha {meta.start_line}, "
                            f"mas NUNCA é chamado em nenhum ponto do arquivo (função zumbi)."
                        ),
                        mitigation_hint=f"Conecte '{func_name}' aos fluxos de execução ou remova o código morto.",
                        mutation_pct=0.0
                    ))

        return findings

    @classmethod
    def compare(
        cls, old_code: str, new_code: str, file_name: str = ""
    ) -> List[RegretFinding]:
        findings: List[RegretFinding] = []
        old_inv = cls.extract_inventory(old_code)
        new_inv = cls.extract_inventory(new_code)
        if not old_inv or not new_inv:
            return findings

        # 1. Comandos Click perdidos
        for cmd_name, func_name in old_inv.click_commands.items():
            if cmd_name not in new_inv.click_commands:
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

        # 2. Funções extirpadas ou relocadas
        for func_name, meta in old_inv.functions.items():
            if func_name not in new_inv.functions:
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
                new_meta = new_inv.functions[func_name]
                lost_args = [a for a in meta.args if a not in new_meta.args and a != "self" and a != "cls"]
                if lost_args:
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
                            impact_description=f"A assinatura de '{func_name}' perdeu parâmetros obrigatórios: {', '.join(lost_args)}.",
                            mitigation_hint=f"Restaurar compatibilidade de parâmetros em {func_name}."
                        ))

        return findings

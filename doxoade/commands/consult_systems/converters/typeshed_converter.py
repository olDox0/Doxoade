# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/typeshed_converter.py
from __future__ import annotations
import ast, io, sys, urllib.request, zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional

_converters_dir = Path(__file__).resolve().parent
if str(_converters_dir) not in sys.path:
    sys.path.insert(0, str(_converters_dir))

try:
    from .base_converter import BaseCanonicalConverter
except (ImportError, ValueError):
    from base_converter import BaseCanonicalConverter


class TypeshedConverter(BaseCanonicalConverter):
    category = "python_typeshed"
    canonical_filename = "typeshed_stdlib.jsonl"
    default_source_url = (
        "https://github.com/python/typeshed/archive/refs/heads/main.zip"
    )

    TARGET_DIR = "stdlib/"
    SKIP_TOKENS = ("__pycache__",)

    def _detect_root_prefix(self, names: List[str]) -> str:
        for n in names:
            parts = n.split("/", 1)
            if len(parts) == 2 and parts[1]:
                return parts[0] + "/"
        return ""

    @staticmethod
    def _format_stub_signature(node) -> str:
        """Assinatura compacta para .pyi — só o que importa."""
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            return f"class {node.name}({bases})" if bases else f"class {node.name}"
        args = node.args
        parts = []

        def _arg(a: ast.arg) -> str:
            return f"{a.arg}: {ast.unparse(a.annotation)}" if a.annotation else a.arg

        pos = [_arg(a) for a in args.posonlyargs]
        if pos:
            parts.extend(pos)
            parts.append("/")
        parts.extend(_arg(a) for a in args.args)
        if args.vararg:
            parts.append(f"*{_arg(args.vararg)}")
        elif args.kwonlyargs:
            parts.append("*")
        for a, default in zip(args.kwonlyargs, args.kw_defaults):
            if default is not None:
                parts.append(f"{_arg(a)} = {ast.unparse(default)}")
            else:
                parts.append(_arg(a))
        if args.kwarg:
            parts.append(f"**{_arg(args.kwarg)}")
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return f"def {node.name}({', '.join(parts)}){ret}"

    def _extract_from_pyi(self, source: str, rel_path: str) -> Optional[Dict[str, Any]]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None

        module_doc = (ast.get_docstring(tree) or "").strip()

        # Em .pyi, o interesse principal são classes e funções top-level.
        # Não descemos em métodos — o objetivo é referência rápida de assinatura.
        lines: List[str] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                sig = self._format_stub_signature(node)
                doc = (ast.get_docstring(node) or "").strip()
                entry = f"### `{sig}`"
                if doc:
                    entry += f"\n\n{doc.splitlines()[0]}"  # só a 1ª linha
                lines.append(entry)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = self._format_stub_signature(node)
                doc = (ast.get_docstring(node) or "").strip()
                entry = f"### `{sig}`"
                if doc:
                    entry += f"\n\n{doc.splitlines()[0]}"
                lines.append(entry)

        if not lines and not module_doc:
            return None

        # Nome do módulo = path sem .pyi, sem barra
        rel = rel_path.replace(".pyi", "")
        module_name = rel.replace("/", ".")
        if module_name.endswith(".__init__"):
            module_name = module_name[:-9]

        body_parts = [f"# Stubs: {module_name}", ""]
        if module_doc:
            body_parts.extend([module_doc, ""])
        body_parts.append("## Assinaturas tipadas")
        body_parts.append("")
        body_parts.extend(lines)

        content = "\n\n".join(body_parts).strip()
        if len(content) < 60:
            return None

        slug = self.slugify(rel)
        uid = f"python/typeshed/{slug}"

        return {
            "uid": uid,
            "path": uid,
            "category": self.category,
            "title": f"Typeshed: {module_name}",
            "keywords": self.extract_keywords(module_name, content, max_words=40),
            "content": content,
        }

    def convert(self, source_url: Optional[str] = None) -> Path:
        url = source_url or self.default_source_url
        print(f"\n[*] 📥 Baixando ZIP do typeshed...")

        req = urllib.request.Request(
            url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (Typeshed)"}
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            zip_bytes = resp.read()
        print(f"[*] ZIP recebido ({len(zip_bytes) / (1024*1024):.2f} MB).")

        records: List[Dict[str, Any]] = []
        skipped = 0
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            all_names = zf.namelist()
            root = self._detect_root_prefix(all_names)
            print(f"[*] Prefixo raiz: {root!r}")

            for member in all_names:
                if not member.endswith(".pyi"):
                    continue
                if not member.startswith(root):
                    continue
                rel = member[len(root):]
                if not rel.startswith(self.TARGET_DIR):
                    continue
                if any(tok in member for tok in self.SKIP_TOKENS):
                    continue

                try:
                    source = zf.read(member).decode("utf-8", errors="replace")
                except Exception:
                    skipped += 1
                    continue

                rec = self._extract_from_pyi(source, rel)
                if rec:
                    records.append(rec)
                else:
                    skipped += 1

                if len(records) % 50 == 0 and len(records) > 0:
                    print(f"  ↳ {len(records)} módulos processados...")

        print(f"\n[*] Total: {len(records)} stubs válidos ({skipped} ignorados).")
        return self.save_canonical(records)


def run_converter():
    converter = TypeshedConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

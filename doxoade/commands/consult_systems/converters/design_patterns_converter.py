# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/design_patterns_converter.py
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


class DesignPatternsConverter(BaseCanonicalConverter):
    category = "python_patterns"
    canonical_filename = "python_design_patterns.jsonl"
    default_source_url = (
        "https://github.com/faif/python-patterns/archive/refs/heads/master.zip"
    )

    TARGET_DIR = "patterns/"
    SKIP_TOKENS = ("__pycache__", "/test_", "_test.py")

    def _detect_root_prefix(self, names: List[str]) -> str:
        for n in names:
            parts = n.split("/", 1)
            if len(parts) == 2 and parts[1]:
                return parts[0] + "/"
        return ""

    @staticmethod
    def _format_signature(node) -> str:
        """Reconstrói a assinatura de função/classe a partir do AST."""
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            return f"class {node.name}({bases})" if bases else f"class {node.name}"
        args = node.args
        parts = []

        def _arg(a: ast.arg) -> str:
            if a.annotation:
                return f"{a.arg}: {ast.unparse(a.annotation)}"
            return a.arg

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
                parts.append(f"{_arg(a)}={ast.unparse(default)}")
            else:
                parts.append(_arg(a))
        if args.kwarg:
            parts.append(f"**{_arg(args.kwarg)}")
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(parts)}){ret}"

    def _extract_from_py(self, source: str, rel_path: str) -> Optional[Dict[str, Any]]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None

        module_doc = (ast.get_docstring(tree) or "").strip()
        symbols: List[str] = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = (ast.get_docstring(node) or "").strip()
                sig = self._format_signature(node)
                entry = f"### `{sig}`"
                if doc:
                    entry += f"\n\n{doc}"
                symbols.append(entry)

        if not symbols and not module_doc:
            return None

        stem = Path(rel_path).stem
        friendly = stem.replace("_", " ").title()
        category_dir = Path(rel_path).parent.name.replace("_", " ").title()

        body_parts = [f"# {friendly}", "", f"**Padrão:** {category_dir}", ""]
        if module_doc:
            body_parts.extend([module_doc, ""])
        body_parts.extend(symbols)

        content = "\n\n".join(body_parts).strip()
        if len(content) < 80:
            return None

        slug = self.slugify(rel_path.replace("/", "_").replace(".py", ""))
        uid = f"python/patterns/{slug}"

        return {
            "uid": uid,
            "path": uid,
            "category": self.category,
            "title": f"Padrão: {friendly} ({category_dir})",
            "keywords": self.extract_keywords(f"{friendly} {category_dir} {stem}", content, max_words=50),
            "content": content,
        }

    def convert(self, source_url: Optional[str] = None) -> Path:
        url = source_url or self.default_source_url
        print(f"\n[*] 📥 Baixando ZIP do python-patterns...")

        req = urllib.request.Request(
            url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (DesignPatterns)"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            zip_bytes = resp.read()
        print(f"[*] ZIP recebido ({len(zip_bytes) / (1024*1024):.2f} MB).")

        records: List[Dict[str, Any]] = []
        skipped = 0
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            all_names = zf.namelist()
            root = self._detect_root_prefix(all_names)
            print(f"[*] Prefixo raiz: {root!r}")

            for member in all_names:
                if not member.endswith(".py"):
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

                rec = self._extract_from_py(source, rel)
                if rec:
                    records.append(rec)
                else:
                    skipped += 1

        print(f"\n[*] Total: {len(records)} padrões válidos ({skipped} ignorados).")
        return self.save_canonical(records)


def run_converter():
    converter = DesignPatternsConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

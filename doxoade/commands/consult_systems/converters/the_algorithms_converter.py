# -*- coding: utf-8 -*-
# doxoade\commands\consult_systems\converters\the_algorithms_converter.py
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

class TheAlgorithmsConverter(BaseCanonicalConverter):
    category = "python_algorithms"
    canonical_filename = "the_algorithms.jsonl"
    default_source_url = (
        "https://github.com/TheAlgorithms/Python/archive/refs/heads/master.zip"
    )

    # Diretórios cirúrgicos — Blitzplan §2.1 (evita inchaço do banco)
    TARGET_DIRS = (
        "data_structures/",
        "searches/",
        "sorts/",
        "ciphers/",
        "hashes/",
    )

    # Ignora testes e caches dentro dos diretórios alvo
    SKIP_TOKENS = ("__pycache__", "/test_", "/tests/", "_test.py")

    # def _should_include(self, name: str) -> bool:
    #     if not name.endswith(".py"):
    #         return False
    #     if "TheAlgorithms-Python-master/" not in name:
    #         return False
    #     rel = name.split("TheAlgorithms-Python-master/", 1)[1]
    #     if not any(rel.startswith(d) for d in self.TARGET_DIRS):
    #         return False
    #     return not any(tok in name for tok in self.SKIP_TOKENS)

    def _detect_root_prefix(self, names: List[str]) -> str:
        """Detecta o prefixo raiz do ZIP (ex: 'TheAlgorithms-Python-master/')."""
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
        # FunctionDef / AsyncFunctionDef
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
        if len(module_doc) < 20 and not module_doc:
            # Alguns arquivos só têm a docstring dentro das funções; aceitamos
            pass

        symbols: List[str] = []
        for node in tree.body:  # só top-level — evita ruído de métodos internos
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = (ast.get_docstring(node) or "").strip()
                sig = self._format_signature(node)
                entry = f"### `{sig}`"
                if doc:
                    entry += f"\n\n{doc}"
                symbols.append(entry)
            elif isinstance(node, ast.Assign) and len(symbols) < 5:
                # Captura constantes top-level úteis (LIMITS, TABLES, etc.)
                try:
                    if isinstance(node.value, (ast.Dict, ast.List, ast.Tuple, ast.Constant)):
                        target = ast.unparse(node.targets[0])
                        if target.isupper() and len(target) > 1:
                            val_repr = ast.unparse(node.value)
                            if len(val_repr) < 200:
                                symbols.append(f"### `{target} = {val_repr}`")
                except Exception:
                    pass

        try:
            tree = ast.parse(source)
        except SyntaxError:
            print(f"  [ast] SyntaxError em {rel_path}")
            return None

        if not symbols and not module_doc:
            return None

        # Nome amigável a partir do path
        stem = Path(rel_path).stem
        friendly = stem.replace("_", " ").title()
        subdir = Path(rel_path).parent.name.replace("_", " ").title()

        body_parts = [f"# {friendly}", "", f"**Categoria:** {subdir}", ""]
        if module_doc:
            body_parts.extend([module_doc, ""])
        body_parts.extend(symbols)

        content = "\n\n".join(body_parts).strip()
        if len(content) < 80:
            return None

        slug = self.slugify(rel_path.replace("/", "_").replace(".py", ""))
        uid = f"python/algorithms/{slug}"

        return {
            "uid": uid,
            "path": uid,
            "category": self.category,
            "title": f"Algoritmo: {friendly} ({subdir})",
            "keywords": self.extract_keywords(f"{friendly} {subdir} {stem}", content, max_words=50),
            "content": content,
        }

    def convert(self, source_url: Optional[str] = None) -> Path:
        url = source_url or self.default_source_url
        print(f"\n[*] 📥 Baixando ZIP do TheAlgorithms/Python...")
        print(f"    {url}")
        req = urllib.request.Request(
            url, headers={"User-Agent": "Doxoade-Ingestor/1.0 (TheAlgorithms)"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            zip_bytes = resp.read()
        print(f"[*] ZIP recebido ({len(zip_bytes) / (1024*1024):.1f} MB).")

        records: List[Dict[str, Any]] = []
        skipped = 0
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            all_names = zf.namelist()
            root_prefix = self._detect_root_prefix(all_names)
            print(f"[*] Prefixo raiz detectado: {root_prefix!r}")

            total_py_in_targets = 0
            for member in all_names:
                if not member.endswith(".py"):
                    continue
                if not member.startswith(root_prefix):
                    continue
                rel = member[len(root_prefix):]
                if not any(rel.startswith(d) for d in self.TARGET_DIRS):
                    continue
                if any(tok in member for tok in self.SKIP_TOKENS):
                    continue
                total_py_in_targets += 1

                try:
                    source = zf.read(member).decode("utf-8", errors="replace")
                except Exception:
                    skipped += 1
                    continue

                rec = self._extract_from_py(source, rel)
                if rec:
                    records.append(rec)
                    if len(records) % 50 == 0:
                        print(f"  ↳ {len(records)} arquivos processados...")
                else:
                    skipped += 1

            print(f"[*] .py nos diretórios alvo: {total_py_in_targets}")

        print(f"\n[*] Total: {len(records)} algoritmos válidos ({skipped} ignorados/vazios).")

        from collections import Counter
        dir_counts = Counter(r["path"].split("/")[2].split("_")[0] if "/" in r["path"] else "?" for r in records)
        print(f"[*] Distribuição: {dict(dir_counts)}")

        # Distribuição por diretório alvo (debug útil)
        from collections import Counter
        dist = Counter()
        for r in records:
            # path exemplo: python/algorithms/data_structures_arrays_...
            for d in self.TARGET_DIRS:
                if f"algorithms/{d.replace('/', '_')}" in r["path"] or f"algorithms_{d.replace('/', '_')}" in r["path"]:
                    dist[d] += 1
                    break
            else:
                dist["?"] += 1
        if dist:
            print(f"[*] Distribuição: {dict(dist)}")

        return self.save_canonical(records)

def run_converter():
    converter = TheAlgorithmsConverter()
    converter.convert()


if __name__ == "__main__":
    run_converter()

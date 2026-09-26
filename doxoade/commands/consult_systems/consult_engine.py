# doxoade/commands/consult_systems/consult_engine.py
import pydoc
import inspect
import io
import sys
from typing import Any, List, Tuple, Optional

class ConsultEngine:
    def resolve_object(self, term: str) -> Optional[Any]:
        try:
            obj = pydoc.locate(term)
            if obj:
                return obj
        except Exception:
            pass
        try:
            import importlib
            return importlib.import_module(term)
        except ImportError:
            return None

    def get_docstring(self, obj: Any) -> str:
        try:
            # CORREÇÃO: pydoc.plaintext já é a instância do renderizador no Python 3
            doc_text = pydoc.render_doc(obj, renderer=pydoc.plaintext)
            return doc_text
        except Exception as e:
            raw_doc = inspect.getdoc(obj)
            return f"Erro ao renderizar via pydoc: {e}\n\nDocstring bruta:\n{raw_doc or 'Sem docstring disponível.'}"

    def get_source(self, obj: Any) -> Optional[str]:
        try:
            return inspect.getsource(obj)
        except (TypeError, OSError):
            return None

    def search_modules(self, keyword: str) -> List[Tuple[str, str]]:
        old_stdout = sys.stdout
        sys.stdout = mystdout = io.StringIO()
        try:
            pydoc.apropos(keyword)
        finally:
            sys.stdout = old_stdout
            
        output = mystdout.getvalue().strip()
        if not output:
            return []
            
        results = []
        for line in output.split('\n'):
            if line.strip():
                parts = line.split(' - ', 1)
                if len(parts) == 2:
                    results.append((parts[0].strip(), parts[1].strip()))
                else:
                    results.append((line.strip(), ""))
        return results

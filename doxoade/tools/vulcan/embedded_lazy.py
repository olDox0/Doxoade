# doxoade/doxoade/tools/vulcan/embedded_lazy.py
"""
EmbeddedDoxoadeLazy — Lazy bootstrap de doxoade para projetos que o embarcam.
==============================================================================

Por que este módulo existe
--------------------------
O ``VulcanLazyFinder`` (lazy_loader.py) exclui ``doxoade.*`` via
``_NEVER_LAZY_PREFIXES`` para evitar ciclos durante o boot do próprio Vulcan.
Isso é correto para uso interno — mas o efeito colateral é que projetos HOST
que embarcam doxoade não conseguem diferir seu import.

Este módulo resolve o problema no sentido oposto:

  ┌─────────────────────────────────────────────────────────────────┐
  │  VulcanLazyFinder  →  lazy para módulos DO projeto host         │
  │  EmbeddedDoxoadeLazy → lazy para DOXOADE em si no projeto host  │
  └─────────────────────────────────────────────────────────────────┘

Como funciona
-------------
1. ``install()`` chama ``importlib.util.find_spec("doxoade")`` sem importar.
2. Envolve o loader real com ``importlib.util.LazyLoader`` (stdlib).
   → O ``LazyLoader`` substitui ``module.__class__`` por ``_LazyModule``.
   → O primeiro acesso a qualquer atributo não-dunder dispara ``exec_module``.
3. Opcionalmente envolve também com ``_PostExecLoader`` para instalar o
   ``VulcanMetaFinder`` logo após ``doxoade/__init__.py`` executar.
4. O módulo proxy é registrado em ``sys.modules["doxoade"]`` imediatamente.
   Subimports (``doxoade.tools.*``) funcionam porque ``__path__`` já está
   preenchido pelo ``ModuleSpec`` antes de qualquer exec.

Uso no projeto host
-------------------
Coloque a chamada **antes de qualquer** ``import doxoade`` no entry-point::

    # host_project/main.py  (ou __init__.py do topo)
    from doxoade.tools.vulcan.embedded_lazy import install as lazy_doxoade
    lazy_doxoade(project_root=__file__)     # doxoade não carregou ainda

    # ... resto do startup ...

    import doxoade               # ainda lazy — só resolve o spec
    doxoade.cli.main()           # ← AQUI o import real acontece

Compatibilidade
---------------
- Thread-safe: ``LazyLoader`` usa lock interno; ``_PostExecLoader`` tem
  seu próprio lock para o callback.
- ``_LoadGuard`` de lazy_loader.py não interfere (diferente caminho de exec).
- Idempotente: ``install()`` é no-op se doxoade já estiver em sys.modules.
- ``uninstall()`` remove o proxy se ainda não foi resolvido (útil em testes).
"""
from __future__ import annotations
import importlib.abc
import importlib.util
import sys
import threading
from pathlib import Path
from typing import Callable, Optional, Union

class _PostExecLoader(importlib.abc.Loader):
    """
    Wraps um loader existente e dispara um callback após exec_module.

    Usado para instalar VulcanMetaFinder logo após doxoade/__init__.py rodar,
    antes que qualquer código do host acesse atributos do pacote.

    O lock garante que o callback execute exatamente uma vez mesmo se
    exec_module for chamado por threads concorrentes (improvável, mas seguro).
    """

    def __init__(self, inner: importlib.abc.Loader, callback: Callable) -> None:
        self._inner = inner
        self._cb = callback
        self._cb_done = False
        self._lock = threading.Lock()

    def create_module(self, spec):
        return self._inner.create_module(spec)

    def exec_module(self, module) -> None:
        self._inner.exec_module(module)
        with self._lock:
            if not self._cb_done:
                self._cb_done = True
                try:
                    self._cb(module)
                except Exception:
                    pass

def _make_vulcan_callback(project_root: str) -> Callable:
    """
    Retorna callback que instala VulcanMetaFinder para project_root.

    Chamado por _PostExecLoader.exec_module() logo após doxoade carregar.
    Silencia qualquer exceção — se o VulcanMetaFinder não estiver disponível
    (ambiente sem compilação), o import de doxoade ainda funciona normalmente.
    """

    def _cb(_module) -> None:
        try:
            from doxoade.tools.vulcan import meta_finder
            if meta_finder._VULCAN_FINDER_INSTANCE is None:
                meta_finder.install(project_root)
        except Exception:
            pass
    return _cb

def install(project_root: Optional[Union[str, Path]]=None, *, install_vulcan: bool=True) -> bool:
    """
    Registra doxoade como módulo lazy em sys.modules.

    Deve ser chamado **antes** de qualquer ``import doxoade`` no projeto host.
    Depois de instalado, ``import doxoade`` e subimports são no-op até o
    primeiro acesso real a um atributo do pacote.

    Parâmetros
    ----------
    project_root : str | Path | None
        Raiz do projeto host. Usado para instalar o VulcanMetaFinder após
        doxoade carregar. Se None, VulcanMetaFinder não é instalado
        automaticamente (você pode instalá-lo depois com meta_finder.install()).
    install_vulcan : bool
        Se True (padrão) e project_root não for None, instala VulcanMetaFinder
        como callback pós-load de doxoade.

    Retorna
    -------
    bool
        True   → proxy lazy instalado com sucesso.
        False  → doxoade já estava em sys.modules (no-op seguro).

    Levanta
    -------
    ImportError
        Se doxoade não for localizável no ambiente (não instalado, não no path).
    """
    if 'doxoade' in sys.modules:
        return False
    spec = importlib.util.find_spec('doxoade')
    if spec is None or spec.loader is None:
        raise ImportError("[EmbeddedDoxoadeLazy] 'doxoade' não encontrado. Verifique se o pacote está instalado ou no sys.path do projeto host.")
    loader = spec.loader
    if install_vulcan and project_root is not None:
        root_str = str(Path(project_root).resolve() if not Path(project_root).is_dir() else Path(project_root).resolve())
        loader = _PostExecLoader(loader, _make_vulcan_callback(root_str))
    if not hasattr(loader, 'exec_module'):
        raise ImportError("[EmbeddedDoxoadeLazy] O loader de 'doxoade' não suporta exec_module — lazy loading não é possível para extensões C puras.")
    spec.loader = importlib.util.LazyLoader(loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules['doxoade'] = module
    spec.loader.exec_module(module)
    return True

def uninstall() -> bool:
    """
    Remove o proxy lazy de sys.modules SE ainda não foi resolvido.

    Útil em testes de integração que precisam resetar o estado de import.
    Se doxoade já foi carregado, esta função é no-op e retorna False.

    Retorna
    -------
    bool
        True  → proxy removido.
        False → doxoade não era lazy (já carregado) ou não estava em sys.modules.
    """
    if not is_lazy():
        return False
    sys.modules.pop('doxoade', None)
    return True

def is_lazy() -> bool:
    """
    Retorna True se doxoade está registrado como proxy lazy e ainda não carregou.

    Usa ``type(mod).__name__ == '_LazyModule'`` em vez de acessar ``mod.__spec__``.

    IMPORTANTE — por que não ``getattr(mod, '__spec__')``:
        ``_LazyModule.__getattribute__`` intercepta TODO acesso a atributos do
        módulo proxy, incluindo ``__spec__``, e dispara ``exec_module`` antes
        de retornar o valor.  Chamar ``getattr(mod, '__spec__')`` destruiria
        exatamente o estado que estamos verificando.

    ``type(mod)`` usa a API C de tipos (``Py_TYPE``), não passa por
    ``__getattribute__``.  ``type(mod).__name__`` acessa o nome da *classe*,
    não um atributo do módulo — portanto é seguro.
    """
    mod = sys.modules.get('doxoade')
    if mod is None:
        return False
    return type(mod).__name__ == '_LazyModule'

def force_load() -> None:
    """
    Força o carregamento imediato de doxoade se ainda estiver lazy.

    Útil quando você precisa garantir que doxoade (e VulcanMetaFinder) estejam
    prontos antes de um ponto crítico, sem depender de um acesso implícito.

    Se doxoade não estiver em sys.modules ou já estiver carregado, é no-op.
    """
    mod = sys.modules.get('doxoade')
    if mod is None or not is_lazy():
        return
    try:
        _ = mod._embedded_lazy_force_trigger
    except AttributeError:
        pass
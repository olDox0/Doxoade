# doxoade/doxoade/tools/vulcan/lazy_loader.py
"""
VulcanLazyLoader — redirecionamento com lazy import, cache e fail-safe.

Componentes
-----------
  AccessPolicy          — whitelist | blacklist com padrões glob/prefix
                          + validate() que avisa sobre módulos protegidos
  _LoadGuard            — proteção de reentrada por thread (evita exec_module 2×)
  _SafetyAnalyzer       — análise estática do .py antes de permitir lazy
  analyze_module_safety — API pública de análise por nome de módulo
  VulcanLazyFinder      — MetaPathFinder que wraps loaders com LazyLoader
  install / uninstall   — API de ativação (idempotente, thread-safe)
  load_policy / save_policy — persistência em lazy_policy.json

Segurança
---------
  _NEVER_LAZY           — nomes críticos nunca interceptados (O(1) frozenset)
  _NEVER_LAZY_PREFIXES  — prefixos proibidos (tuple de startswith)
  whitelist por padrão  — política vazia = zero módulos interceptados
  _LoadGuard            — impede exec_module 2× no mesmo thread
                          (profiler multi-pass, import circular via proxy)
  _SafetyAnalyzer       — detecta atexit/signal/thread/monkey-patch
                          antes de adicionar à política
"""
from __future__ import annotations
import ast
import fnmatch
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import threading
import time
from pathlib import Path
from typing import Optional

class _LoadGuard:
    """
    Proteção de reentrada por thread para exec_module.

    Problema que resolve
    --------------------
    importlib.util.LazyLoader substitui sys.modules[name] por um proxy.
    Quando o proxy tem seu primeiro atributo acessado, chama exec_module().

    Em dois cenários isso pode acontecer 2× no mesmo thread:

    1. Profiler com múltiplos passes (line-timer + cProfile na mesma sessão):
       cada passe reinstrumenta o frame e acessa __dict__ do proxy — dispara
       o load.  O stdlib LazyLoader não tem proteção aqui.

    2. Import circular acessa o proxy durante sua própria carga:
       A importa B (lazy) → exec_module de B importa C → C importa B →
       proxy de B ainda existe em sys.modules → segundo exec_module.

    Solução
    -------
    _local é threading.local().  acquire(name) retorna False se o mesmo
    thread já está carregando name → exec_module retorna imediatamente.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    def _set(self) -> set[str]:
        if not hasattr(self._local, 'loading'):
            self._local.loading = set()
        return self._local.loading

    def acquire(self, name: str) -> bool:
        """True = primeira carga (ok). False = reentrada (bloquear)."""
        s = self._set()
        if name in s:
            return False
        s.add(name)
        return True

    def release(self, name: str) -> None:
        self._set().discard(name)

    def is_loading(self, name: str) -> bool:
        return name in self._set()
_load_guard = _LoadGuard()

class SafetyResult:
    SAFE = 'safe'
    WARNING = 'warning'
    UNSAFE = 'unsafe'

    def __init__(self, level: str, reasons: list[str]) -> None:
        self.level = level
        self.reasons = reasons
        self.safe = level == self.SAFE

    def __bool__(self) -> bool:
        return self.safe

    def __repr__(self) -> str:
        return f'SafetyResult({self.level!r}, {self.reasons!r})'

class _SafetyAnalyzer:
    """
    Análise estática (AST) para determinar se um módulo é seguro para lazy-load.

    Riscos detectados
    -----------------
    UNSAFE — efeitos colaterais em import-time que mudam de comportamento
             quando diferidos:
      atexit.register, signal.signal, sys.setprofile/settrace,
      faulthandler.enable, sys.modules[...] = ..., sys.meta_path.insert/append

    WARNING — pode ser problemático dependendo do contexto:
      threading.Thread(...).start() ou multiprocessing.Process(...).start()
      chamados em nível de módulo

    SAFE — nenhum padrão acima detectado.

    Limitações
    ----------
    Análise puramente sintática.  Efeitos colaterais dentro de funções
    chamadas no import-time não são detectados.  Cobre os padrões mais comuns.
    """
    _UNSAFE_CALLS: frozenset[tuple[str, str]] = frozenset({('atexit', 'register'), ('signal', 'signal'), ('signal', 'set_wakeup_fd'), ('sys', 'setprofile'), ('sys', 'settrace'), ('faulthandler', 'enable'), ('faulthandler', 'register')})
    _WARNING_CALLS: frozenset[tuple[str, str]] = frozenset({('threading', 'Thread'), ('threading', 'Timer'), ('multiprocessing', 'Process'), ('concurrent.futures', 'ThreadPoolExecutor'), ('concurrent.futures', 'ProcessPoolExecutor')})

    def analyze_source(self, source: str, filename: str='<unknown>') -> SafetyResult:
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as e:
            return SafetyResult(SafetyResult.WARNING, [f'SyntaxError ao parsear ({e}) — análise incompleta'])
        reasons: list[str] = []
        for node in ast.iter_child_nodes(tree):
            self._check_stmt(node, reasons)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Attribute) and isinstance(target.value.value, ast.Name) and (target.value.value.id == 'sys') and (target.value.attr == 'modules'):
                        reasons.append(f'L{node.lineno}: sys.modules[...] = ... [UNSAFE — monkey-patch direto]')
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                fn = node.func
                if fn.attr in ('insert', 'append', 'remove') and isinstance(fn.value, ast.Attribute) and isinstance(fn.value.value, ast.Name) and (fn.value.value.id == 'sys') and (fn.value.attr == 'meta_path'):
                    reasons.append(f'L{node.lineno}: sys.meta_path.{fn.attr}() [UNSAFE — modifica import machinery]')
        level = SafetyResult.SAFE
        for r in reasons:
            if 'UNSAFE' in r:
                level = SafetyResult.UNSAFE
                break
            if 'WARNING' in r and level == SafetyResult.SAFE:
                level = SafetyResult.WARNING
        return SafetyResult(level, reasons)

    def analyze_file(self, path: Path) -> SafetyResult:
        try:
            source = path.read_text(encoding='utf-8', errors='replace')
        except OSError as e:
            return SafetyResult(SafetyResult.WARNING, [f'Não foi possível ler {path}: {e}'])
        return self.analyze_source(source, str(path))

    def _check_stmt(self, node: ast.AST, reasons: list[str]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            self._check_call(node.value, node.lineno, reasons)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = getattr(node, 'value', None)
            if value and isinstance(value, ast.Call):
                self._check_call(value, getattr(node, 'lineno', 0), reasons)
        if isinstance(node, ast.If):
            if not self._is_main_guard(node.test):
                for child in ast.iter_child_nodes(node):
                    self._check_stmt(child, reasons)
        if isinstance(node, (ast.Try, ast.With)):
            for child in ast.iter_child_nodes(node):
                self._check_stmt(child, reasons)

    def _check_call(self, call: ast.Call, lineno: int, reasons: list[str]) -> None:
        func = call.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            pair = (func.value.id, func.attr)
            if pair in self._UNSAFE_CALLS:
                reasons.append(f'L{lineno}: {func.value.id}.{func.attr}() [UNSAFE]')
                return
            if pair in self._WARNING_CALLS:
                reasons.append(f'L{lineno}: {func.value.id}.{func.attr}() [WARNING — objeto criado em módulo level]')
        if isinstance(func, ast.Attribute) and func.attr == 'start' and isinstance(func.value, ast.Call):
            inner = func.value.func
            if isinstance(inner, ast.Attribute) and isinstance(inner.value, ast.Name):
                if (inner.value.id, inner.attr) in self._WARNING_CALLS:
                    reasons.append(f'L{lineno}: {inner.value.id}.{inner.attr}(...).start() [WARNING — thread iniciada em módulo level]')

    @staticmethod
    def _is_main_guard(node: ast.expr) -> bool:
        return isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq) and isinstance(node.left, ast.Name) and (node.left.id == '__name__') and (len(node.comparators) == 1) and isinstance(node.comparators[0], ast.Constant) and (node.comparators[0].value == '__main__')
_safety_analyzer = _SafetyAnalyzer()

def analyze_module_safety(module_name: str, search_paths: list[Path] | None=None, project_root: Path | None=None) -> SafetyResult:
    if project_root and (module_name.endswith('.py') or '/' in module_name or '\\' in module_name):
        candidate = (project_root / module_name).resolve()
        if candidate.exists():
            return _safety_analyzer.analyze_file(candidate)
        return SafetyResult(SafetyResult.WARNING, [f'Arquivo não encontrado: {candidate}'])
    try:
        spec = importlib.util.find_spec(module_name)
        if spec and spec.origin:
            if spec.origin.endswith('.py'):
                return _safety_analyzer.analyze_file(Path(spec.origin))
            if spec.origin.endswith(('.pyd', '.so', '.dll')):
                return SafetyResult(SafetyResult.SAFE, ['Extensão C — LazyLoader não intercepta (sem exec_module).'])
    except (ModuleNotFoundError, ValueError, AttributeError):
        pass
    parts = module_name.split('.')
    rel = Path(*parts[:-1]) / (parts[-1] + '.py') if len(parts) > 1 else Path(parts[0] + '.py')
    roots = []
    if project_root:
        roots.append(project_root)
    roots.extend(search_paths or [Path(p) for p in sys.path if p])
    for base in roots:
        candidate = base / rel
        if candidate.exists():
            return _safety_analyzer.analyze_file(candidate)
    return SafetyResult(SafetyResult.WARNING, ['Arquivo .py não encontrado — análise impossível'])

class ValidationResult:
    STATUS_OK = 'ok'
    STATUS_PROTECTED = 'protected'
    STATUS_INACTIVE = 'inactive'

    def __init__(self, status: str, reason: str='') -> None:
        self.status = status
        self.reason = reason
        self.ok = status == self.STATUS_OK

    def __repr__(self) -> str:
        return f'ValidationResult({self.status!r}, {self.reason!r})'

class AccessPolicy:
    """
    Determina quais módulos entram no pipeline lazy.

    Modos
    -----
    whitelist (padrão) — apenas padrões listados são interceptados.
    blacklist          — tudo interceptado exceto padrões listados.

    Padrões
    -------
    "numpy"    → "numpy" + "numpy.*"
    "myapp.*"  → apenas subpacotes (não "myapp" em si)
    """
    MODE_WHITELIST = 'whitelist'
    MODE_BLACKLIST = 'blacklist'

    def __init__(self, mode: str=MODE_WHITELIST, patterns: list[str] | None=None) -> None:
        self.mode = mode
        self.patterns = list(patterns or [])
        self._lock = threading.Lock()

    def add(self, pattern: str) -> bool:
        with self._lock:
            if pattern not in self.patterns:
                self.patterns.append(pattern)
                return True
            return False

    def remove(self, pattern: str) -> bool:
        with self._lock:
            before = len(self.patterns)
            self.patterns = [p for p in self.patterns if p != pattern]
            return len(self.patterns) < before

    def validate(self, pattern: str) -> ValidationResult:
        """
        Verifica se o padrão SERÁ de fato interceptado pelo VulcanLazyFinder.

        Retorna STATUS_PROTECTED quando o módulo está em _NEVER_LAZY ou
        _NEVER_LAZY_PREFIXES — o finder o ignora mesmo que esteja na política.
        """
        if pattern in _NEVER_LAZY:
            return ValidationResult(ValidationResult.STATUS_PROTECTED, f"'{pattern}' está em _NEVER_LAZY (módulo crítico). O finder ignora este módulo independentemente da política.")
        for prefix in _NEVER_LAZY_PREFIXES:
            if pattern == prefix or pattern.startswith(prefix + '.') or pattern.startswith(prefix + '_'):
                return ValidationResult(ValidationResult.STATUS_PROTECTED, f"'{pattern}' tem prefixo protegido '{prefix}'. O finder ignora este módulo independentemente da política.")
        return ValidationResult(ValidationResult.STATUS_OK)

    def allows(self, module_name: str) -> bool:
        with self._lock:
            patterns = self.patterns
        matched = any((module_name == p or module_name.startswith(p + '.') or fnmatch.fnmatchcase(module_name, p) for p in patterns))
        return matched if self.mode == self.MODE_WHITELIST else not matched

    def to_dict(self) -> dict:
        return {'mode': self.mode, 'patterns': list(self.patterns)}

    @classmethod
    def from_dict(cls, d: dict) -> 'AccessPolicy':
        return cls(mode=d.get('mode', cls.MODE_WHITELIST), patterns=d.get('patterns', []))
_NEVER_LAZY: frozenset[str] = frozenset({'sys', 'builtins', '_thread', '_io', '_abc', '_warnings', '_codecs', '_signal', '_collections', '_functools', '_operator', '_heapq', '_bisect', '_random', '_struct', '_datetime', '_weakref', '_weakrefset', '_sre', '_locale', 'importlib', 'importlib.abc', 'importlib.machinery', 'importlib.util', 'importlib._bootstrap', 'importlib._bootstrap_external', '_frozen_importlib', '_frozen_importlib_external', 'abc', 'types', 'warnings', 'codecs', 'io', 'os', 'os.path', 'posixpath', 'ntpath', 'genericpath', 'pathlib', 'threading', 'functools', 'operator', 'contextlib', 'collections', 'collections.abc', 'fnmatch', 'json', 're', 'ast', 'dis', '_doxoade_vulcan_runtime', '_doxoade_vulcan_embedded', '_doxoade_vulcan_lazy', 'click', 'click.core', 'click.decorators', 'click.exceptions', 'click.formatting', 'click.globals', 'click.termui', 'click.types', 'click.utils', 'logging', 'logging.handlers'})
_NEVER_LAZY_PREFIXES: tuple[str, ...] = ('_frozen', 'encodings', 'importlib', '_doxoade', 'doxoade', '_collections_abc')

class _LoadGuardedLoader(importlib.abc.Loader):
    """
    Wrapper sobre importlib.util.LazyLoader que integra _LoadGuard.
    Impede que exec_module seja chamado 2× no mesmo thread.
    """

    def __init__(self, lazy_loader: importlib.util.LazyLoader, name: str) -> None:
        self._lazy = lazy_loader
        self._name = name

    def create_module(self, spec):
        return self._lazy.create_module(spec)

    def exec_module(self, module) -> None:
        if not _load_guard.acquire(self._name):
            return
        try:
            self._lazy.exec_module(module)
        finally:
            _load_guard.release(self._name)

class VulcanLazyFinder(importlib.abc.MetaPathFinder):
    """
    MetaPathFinder instalado no início de sys.meta_path.

    Para cada import:
      1. _should_lazy()     — _NEVER_LAZY + prefixes + AccessPolicy + reentrada
      2. cache nativo       — se já em sys.modules → None
      3. _delegate()        — encontra ModuleSpec nos finders subsequentes
      4. wraps com _LoadGuardedLoader(LazyLoader(...))
      5. retorna spec       → Python registra proxy em sys.modules
    """

    def __init__(self, policy: AccessPolicy) -> None:
        self.policy = policy
        self._active = True
        self._lock = threading.Lock()
        self._stats: dict[str, dict] = {}

    def _should_lazy(self, fullname: str) -> bool:
        if not self._active:
            return False
        if fullname in _NEVER_LAZY:
            return False
        for prefix in _NEVER_LAZY_PREFIXES:
            if fullname == prefix or fullname.startswith(prefix + '.') or fullname.startswith(prefix + '_'):
                return False
        if _load_guard.is_loading(fullname):
            return False
        return self.policy.allows(fullname)

    def find_spec(self, fullname, path, target=None):
        if fullname in sys.modules:
            return None
        if not self._should_lazy(fullname):
            return None
        t0 = time.monotonic()
        spec = self._delegate(fullname, path, target)
        dt = (time.monotonic() - t0) * 1000
        if spec is None or spec.loader is None:
            return None
        if not hasattr(spec.loader, 'exec_module'):
            return None
        try:
            inner = importlib.util.LazyLoader(spec.loader)
            spec.loader = _LoadGuardedLoader(inner, fullname)
        except Exception:
            return None
        with self._lock:
            e = self._stats.setdefault(fullname, {'hits': 0, 'loaded': False, 'defer_ms': 0.0, 'load_ms': 0.0})
            e['hits'] += 1
            e['defer_ms'] += dt
        return spec

    def invalidate_caches(self) -> None:
        for f in sys.meta_path:
            if f is not self:
                fn = getattr(f, 'invalidate_caches', None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass

    def _delegate(self, fullname, path, target):
        for finder in sys.meta_path:
            if finder is self:
                continue
            fn = getattr(finder, 'find_spec', None)
            if not callable(fn):
                continue
            try:
                spec = fn(fullname, path, target)
                if spec is not None:
                    return spec
            except Exception:
                continue
        return None

    def pause(self) -> None:
        self._active = False

    def resume(self) -> None:
        self._active = True

    def mark_loaded(self, module_name: str, load_ms: float=0.0) -> None:
        with self._lock:
            if module_name in self._stats:
                self._stats[module_name]['loaded'] = True
                self._stats[module_name]['load_ms'] += load_ms

    def get_stats(self) -> dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._stats.items()}
_installed_finder: Optional[VulcanLazyFinder] = None
_install_lock = threading.Lock()

def install(policy: Optional[AccessPolicy]=None, position: int=0) -> VulcanLazyFinder:
    global _installed_finder
    with _install_lock:
        if _installed_finder is not None and _installed_finder in sys.meta_path:
            return _installed_finder
        finder = VulcanLazyFinder(policy or AccessPolicy())
        sys.meta_path.insert(position, finder)
        _installed_finder = finder
        return finder

def uninstall() -> bool:
    global _installed_finder
    with _install_lock:
        if _installed_finder is None:
            return False
        try:
            sys.meta_path.remove(_installed_finder)
        except ValueError:
            pass
        _installed_finder = None
        return True

def get_finder() -> Optional[VulcanLazyFinder]:
    return _installed_finder

def load_policy(config_path: Path) -> AccessPolicy:
    import json
    try:
        if config_path.exists():
            return AccessPolicy.from_dict(json.loads(config_path.read_text(encoding='utf-8')))
    except Exception:
        pass
    return AccessPolicy()

def save_policy(policy: AccessPolicy, config_path: Path) -> bool:
    import json
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(policy.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')
        return True
    except Exception:
        return False
# doxoade/doxoade/tools/vulcan/simd_compiler.py
"""
──────────────────────────────────────────────────────────────────────────────
Compilação SIMD-aware para o pipeline Vulcan.

Responsabilidades:
  • Injetar flags SIMD no ambiente de compilação (CFLAGS, extra_compile_args)
  • Envolver compilações existentes (PitstopEngine, HybridForge, LibForge)
  • Gerar relatório de ganho estimado por nível SIMD
  • Produzir `.pyx` enriquecido com typed memoryviews para acesso vetorizável

Classes:
    SIMDContext        — configuração de uma sessão SIMD
    SIMDEnvironment    — injeta flags no os.environ para subprocessos de build
    SIMDForge          — wrapper de alto nível para compilação SIMD
    SIMDPyxEnricher    — transforma .pyx gerados pelo HybridForge em SIMD-friendly

Funções de conveniência:
    compile_with_simd(module_path, project_root, ...)  → (ok, msg)
    enrich_pyx(pyx_path, caps)                         → Path
    estimate_gain(caps)                                → str
"""
from __future__ import annotations
import os
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from doxoade.tools.vulcan.cpu_flags import simd_compile_flags
from .simd_detector import SIMDCapabilities, detect as detect_simd
_BEST_TO_CPU_LEVEL: dict[str, str] = {'avx512f': 'AVX512', 'avx2': 'AVX2', 'avx': 'AVX', 'sse4.2': 'SSE4', 'sse4.1': 'SSE4', 'sse2': 'SSE2', 'neon': 'SCALAR', 'none': 'SCALAR'}

@dataclass
class SIMDContext:
    """
    Configuração de uma sessão de compilação SIMD.

    Parâmetros:
        caps        — capacidades detectadas (None = auto-detectar)
        level_cap   — nível máximo permitido: 'sse2'|'avx'|'avx2'|'avx512f'|'native'|'auto'
        enrich_pyx  — se True, enriquece .pyx com typed memoryviews
        verbose     — log extra durante compilação
    """
    caps: SIMDCapabilities = field(default_factory=detect_simd)
    level_cap: str = 'auto'
    enrich_pyx: bool = True
    verbose: bool = False
    _LEVEL_ORDER = ['none', 'sse2', 'sse4.1', 'sse4.2', 'avx', 'avx2', 'avx512f']

    def effective_caps(self) -> SIMDCapabilities:
        """Retorna caps limitadas por level_cap."""
        if self.level_cap in ('auto', 'native'):
            return self.caps
        cap_idx = self._LEVEL_ORDER.index(self.level_cap) if self.level_cap in self._LEVEL_ORDER else 99
        from dataclasses import replace
        kwargs = {}
        pairs = [('sse2', 1), ('sse4_1', 2), ('sse4_2', 3), ('avx', 4), ('avx2', 5), ('avx512f', 6)]
        for attr, idx in pairs:
            kwargs[attr] = getattr(self.caps, attr) and idx <= cap_idx
        return replace(self.caps, **kwargs)

    def gcc_flags(self) -> list[str]:
        eff = self.effective_caps()
        if self.level_cap == 'native':
            return eff.native_flags
        return eff.gcc_flags

    def msvc_flags(self) -> list[str]:
        return self.effective_caps().msvc_flags

    def cflags(self) -> list[str]:
        """
        Flags de compilação para a plataforma atual.

        Pipeline:
          1. cpu_flags.simd_compile_flags  — fonte primária (lê suporte real da CPU)
          2. SIMDCapabilities.{gcc,msvc}_flags — acrescenta extras finos:
               GCC: -funroll-loops, -mpopcnt, -mbmi/-mbmi2 condicionais
               MSVC: /GL (whole-program opt), /Gy (function-level linking)
          Flags já presentes na base não são duplicadas.
        """
        eff = self.effective_caps()
        if self.level_cap == 'native':
            return eff.native_flags
        level_str = _BEST_TO_CPU_LEVEL.get(eff.best, 'SCALAR')
        base: list[str] = list(simd_compile_flags(level_str))
        caps_flags = eff.msvc_flags if os.name == 'nt' else eff.gcc_flags
        seen = set(base)
        for f in caps_flags:
            if f not in seen:
                base.append(f)
                seen.add(f)
        return base

class SIMDEnvironment:
    """
    Context manager que injeta flags SIMD nas variáveis de ambiente
    usadas pelos subprocessos de compilação (Cython + GCC/MSVC).

    Uso:
        with SIMDEnvironment(ctx) as env:
            engine.compile(...)
    """

    def __init__(self, ctx: SIMDContext):
        self._ctx = ctx
        self._backup: dict[str, str | None] = {}

    def __enter__(self) -> 'SIMDEnvironment':
        flags = ' '.join(self._ctx.cflags())
        env_keys = ['CFLAGS', 'CXXFLAGS']
        for key in env_keys:
            self._backup[key] = os.environ.get(key)
            existing = os.environ.get(key, '')
            new_val = (existing + ' ' + flags).strip()
            os.environ[key] = new_val
        os.environ['VULCAN_SIMD_LEVEL'] = self._ctx.effective_caps().best
        os.environ['VULCAN_SIMD_FLAGS'] = flags
        return self

    def __exit__(self, *_):
        for key, val in self._backup.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        os.environ.pop('VULCAN_SIMD_LEVEL', None)
        os.environ.pop('VULCAN_SIMD_FLAGS', None)

class SIMDPyxEnricher:
    """
    Transforma arquivos .pyx gerados pelo HybridForge para maximizar
    benefícios SIMD via:

    1. Typed memoryviews contíguas  (float[:] → double[::1])
    2. nogil blocks em loops sobre arrays
    3. Diretivas de compilador no header
    4. Uso de libc.math em vez de Python math
    """
    _HEADER_TMPL = textwrap.dedent('    # cython: boundscheck=False\n    # cython: wraparound=False\n    # cython: cdivision=True\n    # cython: nonecheck=False\n    # cython: language_level=3\n    # [VULCAN-SIMD] level={level} flags={flags}\n    from libc.math cimport sqrt, fabs, floor, ceil, pow as c_pow\n    from libc.stdlib cimport malloc, free\n    import numpy as np\n    cimport numpy as np\n\n    ')
    _REPLACEMENTS = [('\\blist\\b(\\s+\\w+)\\b', 'double[::1]\\1'), ('np\\.ndarray\\s+(\\w+)', 'np.ndarray[np.float64_t, ndim=1] \\1'), ('for\\s+(\\w+)\\s+in\\s+range\\s*\\(\\s*len\\s*\\((\\w+)\\)\\s*\\):', 'for \\1 in range(len(\\2)):  # SIMD-candidate')]

    def __init__(self, caps: SIMDCapabilities):
        self._caps = caps

    def enrich(self, pyx_path: Path) -> Path:
        """
        Lê pyx_path, aplica transformações e sobrescreve o arquivo.
        Retorna o caminho (mesmo arquivo, enriquecido).
        """
        try:
            source = pyx_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return pyx_path
        if '[VULCAN-SIMD]' in source:
            return pyx_path
        source = re.sub('^# cython:.*\\n', '', source, flags=re.MULTILINE)
        flags_str = ' '.join(self._caps.gcc_flags) if os.name != 'nt' else ' '.join(self._caps.msvc_flags)
        header = self._HEADER_TMPL.format(level=self._caps.best, flags=flags_str)
        source = header + source
        for pattern, repl in self._REPLACEMENTS:
            try:
                source = re.sub(pattern, repl, source)
            except Exception:
                pass
        source = self._inject_nogil_hints(source)
        pyx_path.write_text(source, encoding='utf-8')
        return pyx_path

    def _inject_nogil_hints(self, source: str) -> str:
        """
        Adiciona comentário SIMD-candidate em funções cpdef/cdef com loops numéricos.
        Não modifica assinaturas para não quebrar API.
        """
        lines = source.splitlines(keepends=True)
        result = []
        for i, line in enumerate(lines):
            result.append(line)
            if re.match('\\s*(cpdef|cdef)\\s+\\w.*\\(.*\\[.*\\].*\\):', line):
                indent = len(line) - len(line.lstrip())
                result.append(' ' * indent + '    # TODO(SIMD): considere nogil + prange para loops internos\n')
        return ''.join(result)

@dataclass
class CompileResult:
    module_name: str
    ok: bool
    error: str = ''
    simd_level: str = 'none'
    flags_used: list[str] = field(default_factory=list)
    pyx_enriched: bool = False
    bin_path: str = ''
    duration_ms: int = 0

class SIMDForge:
    """
    Wrapper de alto nível que compila módulos/libs com flags SIMD.

    Uso básico:
        forge = SIMDForge(project_root)
        result = forge.compile_module("mymodule", Path("mymodule.pyx"))

    Integração com pipeline existente:
        forge = SIMDForge(project_root, ctx=SIMDContext(level_cap="avx2"))
        with forge.env_context():
            pitstop_engine.scan_and_optimize(...)
    """

    def __init__(self, project_root: str | Path, ctx: SIMDContext | None=None):
        self._root = Path(project_root).resolve()
        self._ctx = ctx or SIMDContext()
        self._enricher = SIMDPyxEnricher(self._ctx.effective_caps())

    @property
    def caps(self) -> SIMDCapabilities:
        return self._ctx.effective_caps()

    def env_context(self) -> SIMDEnvironment:
        """Retorna context manager para injetar flags no ambiente."""
        return SIMDEnvironment(self._ctx)

    def enrich_pyx(self, pyx_path: Path) -> Path:
        """Enriquece um .pyx com typed memoryviews e diretivas SIMD."""
        if self._ctx.enrich_pyx:
            return self._enricher.enrich(pyx_path)
        return pyx_path

    def compile_module(self, module_name: str, pyx_path: Path, bin_dir: Path | None=None, extra_flags: list[str] | None=None) -> CompileResult:
        """
        Compila um único .pyx com flags SIMD.

        Tenta usar o mecanismo interno do Vulcan (HybridForge._compile)
        com flags injetadas via ambiente. Fallback: subprocess direto.
        """
        import time
        t0 = time.monotonic()
        bin_dir = bin_dir or self._root / '.doxoade' / 'vulcan' / 'bin'
        bin_dir.mkdir(parents=True, exist_ok=True)
        enriched = False
        if self._ctx.enrich_pyx:
            try:
                self.enrich_pyx(pyx_path)
                enriched = True
            except Exception:
                pass
        flags = self.caps.cflags() + (extra_flags or [])
        ok, err = self._compile_internal(module_name, pyx_path, bin_dir, flags)
        if not ok:
            ok, err = self._compile_subprocess(module_name, pyx_path, bin_dir, flags)
        duration = int((time.monotonic() - t0) * 1000)
        ext = '.pyd' if os.name == 'nt' else '.so'
        candidates = list(bin_dir.glob(f'*{module_name}*{ext}'))
        bin_path = str(candidates[0]) if candidates else ''
        return CompileResult(module_name=module_name, ok=ok, error=err, simd_level=self.caps.best, flags_used=flags, pyx_enriched=enriched, bin_path=bin_path, duration_ms=duration)

    def _compile_internal(self, module_name: str, pyx_path: Path, bin_dir: Path, flags: list[str]) -> tuple[bool, str]:
        """Tenta usar HybridIgnite._compile com env SIMD."""
        try:
            from .hybrid_forge import HybridIgnite
            ignite = HybridIgnite(str(self._root))
            with SIMDEnvironment(self._ctx):
                ok, err = ignite._compile(module_name)
            return (ok, str(err) if err else '')
        except Exception as e:
            return (False, str(e))

    def _compile_subprocess(self, module_name: str, pyx_path: Path, bin_dir: Path, flags: list[str]) -> tuple[bool, str]:
        """
        Compilação direta via subprocess: cythonize + gcc.
        Usado como fallback quando o pipeline interno não está disponível.
        """
        try:
            import tempfile
            setup_content = textwrap.dedent(f'            from setuptools import setup, Extension\n            from Cython.Build import cythonize\n            import os\n\n            extra = {flags!r}\n            ext = Extension(\n                name="{module_name}",\n                sources=[r"{pyx_path}"],\n                extra_compile_args=extra,\n                extra_link_args=[],\n            )\n            setup(\n                name="{module_name}",\n                ext_modules=cythonize(\n                    [ext],\n                    compiler_directives={self.caps.cython_directives!r},\n                    quiet=True,\n                ),\n                script_args=["build_ext", "--inplace",\n                             "--build-lib", r"{bin_dir}"],\n            )\n            ')
            with tempfile.TemporaryDirectory() as tmp:
                setup_py = Path(tmp) / 'setup.py'
                setup_py.write_text(setup_content, encoding='utf-8')
                env = os.environ.copy()
                env['CFLAGS'] = ' '.join(flags)
                proc = subprocess.run([sys.executable, str(setup_py)], capture_output=True, text=True, timeout=120, cwd=str(pyx_path.parent), env=env)
                if proc.returncode != 0:
                    return (False, (proc.stderr or proc.stdout)[-500:])
                ext_suffix = '.pyd' if os.name == 'nt' else '.so'
                for built in Path(pyx_path.parent).glob(f'*{module_name}*{ext_suffix}'):
                    dest = bin_dir / built.name
                    shutil.copy2(built, dest)
                    return (True, '')
            return (False, 'binário não encontrado após compilação')
        except Exception as e:
            return (False, str(e))

    def compile_batch(self, targets: list[tuple[str, Path]], bin_dir: Path | None=None, max_workers: int | None=None) -> list[CompileResult]:
        """
        Compila múltiplos módulos com flags SIMD.
        Usa ThreadPoolExecutor para paralelismo.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        workers = max_workers or min(8, os.cpu_count() or 2)
        results: list[CompileResult] = []
        with SIMDEnvironment(self._ctx):
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(self.compile_module, name, path, bin_dir): name for name, path in targets}
                for fut in as_completed(futures):
                    try:
                        results.append(fut.result())
                    except Exception as e:
                        name = futures[fut]
                        results.append(CompileResult(module_name=name, ok=False, error=str(e)))
        return results

    def compile_library(self, lib_name: str) -> tuple[bool, str]:
        """
        Compila uma lib do venv com flags SIMD injetadas via CFLAGS.
        Delega para LibForge internamente.
        """
        try:
            from .lib_forge import LibForge
            forge = LibForge(str(self._root))
            with SIMDEnvironment(self._ctx):
                ok, msg = forge.compile_library(lib_name)
            simd_tag = f' [SIMD:{self.caps.best}]'
            return (ok, msg + (simd_tag if ok else ''))
        except Exception as e:
            return (False, str(e))

def compile_with_simd(module_path: str | Path, project_root: str | Path, level_cap: str='auto', enrich: bool=True) -> tuple[bool, str]:
    """
    Compila um único arquivo Python/Cython com otimizações SIMD.

    Retorna (ok, mensagem).
    """
    path = Path(module_path).resolve()
    forge = SIMDForge(project_root, SIMDContext(level_cap=level_cap, enrich_pyx=enrich))
    result = forge.compile_module(path.stem, path)
    return (result.ok, result.error or f'OK [SIMD:{result.simd_level}]')

def enrich_pyx(pyx_path: Path, caps: SIMDCapabilities | None=None) -> Path:
    """Enriquece .pyx com typed memoryviews e diretivas SIMD."""
    caps = caps or detect_simd()
    enricher = SIMDPyxEnricher(caps)
    return enricher.enrich(pyx_path)

def estimate_gain(caps: SIMDCapabilities | None=None) -> str:
    """Retorna estimativa textual de ganho SIMD para a CPU atual."""
    caps = caps or detect_simd()
    gains = {'avx512f': '30–60% em operações vetorizadas (512-bit lanes)', 'avx2': '20–45% em operações vetorizadas (256-bit lanes)', 'avx': '15–30% em operações vetorizadas (256-bit float)', 'sse4.2': '10–20% em operações escalares e comparação de strings', 'sse4.1': '8–15% em operações de ponto flutuante', 'sse2': '5–10% vs código escalar base', 'neon': '20–40% em operações vetorizadas ARM (128-bit)', 'none': '0% — nenhuma extensão vetorial disponível'}
    return gains.get(caps.best, 'ganho desconhecido')

def get_simd_report(caps: SIMDCapabilities | None=None) -> dict:
    """Retorna relatório completo para uso em CLI ou JSON."""
    caps = caps or detect_simd()
    return {**caps.to_dict(), 'estimated_gain': estimate_gain(caps), 'cython_directives': caps.cython_directives, 'define_macros': caps.define_macros}
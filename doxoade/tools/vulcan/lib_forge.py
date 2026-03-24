# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/lib_forge.py
"""
LibForge — Compilação de bibliotecas de terceiros já instaladas no venv.

Fluxo Harmonioso (Industrial Pipeline):
  1. Localiza a biblioteca no site-packages do Python atual.
  2. Matriz de Evasão: Impede a compilação de bibliotecas que já possuem
     núcleo nativo (C/C++/Fortran) para evitar o 'Paradoxo Cython'.
  3. Copia SOMENTE os fontes .py para um diretório temporário.
  4. LibOptimizer: aplica dead code elimination, remoção de imports, etc.
  5. HybridIgnite + Harmonia Paralela nos fontes já otimizados.
  6. Move os binários aprovados para .doxoade/vulcan/lib_bin/.

Segurança:
  - Trabalha sempre com a cópia temporária.
  - O venv original NUNCA é modificado.
  - Binários só chegam ao lib_bin após compilação bem-sucedida.
"""

import shutil
import sys
# [DOX-UNUSED] import site
import tempfile
import os
import concurrent.futures
import threading
from pathlib import Path

# ── Pool de instâncias HybridIgnite por thread ────────────────────────────────
# Em vez de criar uma nova instância por arquivo (O(N) instâncias),
# cada worker-thread reutiliza a mesma instância durante toda a compilação.
# Com max_workers = cpu_count(), isso reduz de ~150k instâncias → N_CPU instâncias.
_thread_local = threading.local()


class LibForge:
    """
    Orquestrador de compilação de bibliotecas do venv.
    Nunca altera o ambiente Python original.
    """

    # ── MATRIZ DE EVASÃO (Anti-Paradoxo Cython) ────────────────────────────────
    # Bibliotecas que já são hiper-otimizadas nativamente. Compilá-las com
    # Cython adiciona overhead de conversão (C-API) e destrói a performance.
    _NATIVE_HEAVY_LIBS = frozenset({
        "numpy", "pandas", "scipy", "torch", "tensorflow", "cv2", "opencv-python",
        "matplotlib", "pygame", "kivy", "pyqt5", "pyside2", "pyside6",
        "grpcio", "cryptography", "pillow", "pil", "lxml", "sqlalchemy"
    })

    def __init__(self, project_root: str):
        self.root = Path(project_root)
        self.lib_bin_dir = self.root / ".doxoade" / "vulcan" / "lib_bin"
        self.lib_bin_dir.mkdir(parents=True, exist_ok=True)

    # ── Entry-point público ────────────────────────────────────────────────────

    def compile_library(
        self,
        lib_name: str,
        run_optimizer: bool = True,
        simd_ctx=None,
    ) -> tuple[bool, str]:
        """
        Localiza, copia, otimiza e compila funções elegíveis da biblioteca.
        """
        
        # ── Fase 0: Verificação de Evasão ──────────────────────────────────────
        if lib_name.lower() in self._NATIVE_HEAVY_LIBS:
            return False, (
                f"[EVASÃO DE RISCO] A biblioteca '{lib_name}' possui núcleo nativo (C/C++).\n"
                f"   O Vulcan bloqueou a forja desta biblioteca para evitar degradação\n"
                f"   de performance causada pelo overhead da C-API (Paradoxo Cython)."
            )

        with tempfile.TemporaryDirectory(prefix=f"vulcan_lib_{lib_name}_") as temp_dir:
            work_dir = Path(temp_dir)

            # Resolve os extra_cflags SIMD uma vez, fora das threads
            _simd_cflags: list[str] =[]
            _simd_label  = ""
            if simd_ctx is not None:
                try:
                    caps         = simd_ctx.effective_caps()
                    _simd_cflags = list(caps.cflags)
                    _simd_label  = caps.best.upper()
                    print(f"   > [SIMD] {_simd_label} — flags: {' '.join(_simd_cflags)}")
                except Exception as exc:
                    print(f"   > [SIMD] Falha ao resolver caps ({exc}) — compilando sem SIMD.")
                    _simd_cflags =[]

            # ── Fase 1: Localizar no venv ──────────────────────────────────────
            print(f"   > Localizando '{lib_name}' no site-packages...")
            source_path = self._find_in_venv(lib_name)

            if not source_path:
                return False, f"Biblioteca '{lib_name}' não encontrada no site-packages."

            print(f"   > Encontrada em: {source_path}")

            # ── Fase 2: Copiar fontes para área isolada ────────────────────────
            print("   > Copiando fontes .py para área temporária de trabalho...")
            try:
                work_copy = self._copy_sources(source_path, work_dir)
            except Exception as e:
                return False, f"Falha ao copiar fontes: {e}"

            py_count = sum(1 for _ in work_copy.rglob("*.py"))
            print(f"   > {py_count} arquivo(s) .py copiado(s) para análise.")

            if py_count == 0:
                return False, f"'{lib_name}' não possui arquivos .py copiáveis."

            # ── Fase 3: LibOptimizer nos fontes da cópia ──────────────────────
            opt_stats: dict = {
                'files_processed': 0, 'files_optimized': 0, 'files_skipped': 0,
                'bytes_saved': 0, 'docstrings_removed': 0, 'dead_branches': 0,
                'imports_removed': 0, 'locals_minified': 0,
            }

            if run_optimizer:
                print("   > [OPT] Otimizando fontes (dead code, imports, docstrings, locals)...")
                opt_stats = self._optimize_sources(work_copy)
                self._print_opt_summary(opt_stats)
            else:
                print("   > [OPT] Otimização de fontes ignorada (run_optimizer=False).")

            # ── Fase 4: HybridIgnite em paralelo nos fontes otimizados ─────────
            from .hybrid_forge import HybridIgnite
            from .object_reduction import reduce_source
            from .hybrid_optimizer import optimize_pyx_file

            # Instância global APENAS para listagem de arquivos
            base_ignite = HybridIgnite(self.root)
            files       = base_ignite._collect_files(work_copy)

            modules_generated  =[]
            functions_compiled = 0
            functions_skipped  = 0
            errors: list[str]  =[]

            # Lock para proteger o _compile contra race conditions
            compile_lock = threading.Lock()

            max_workers = os.cpu_count() or 3
            simd_suffix = f" + SIMD {_simd_label}" if _simd_label else ""
            print(f"   > Forjando candidatos em PARALELO ({max_workers} workers{simd_suffix})...")

            def process_file(py_file: Path):
                """Processamento isolado por arquivo — executa em thread.

                Otimizações aplicadas:
                  1. Thread-Local Pool: HybridIgnite é criado uma única vez por
                     worker-thread e reutilizado para todos os arquivos daquela thread.
                     Reduz de O(N_arquivos) instâncias para O(N_CPU) instâncias.
                  2. sys.intern nos nomes de módulo: garante que strings repetidas
                     (ex: nomes de funções candidatas) compartilhem o mesmo endereço
                     de memória — comparações futuras viram checagem de ponteiro O(1).
                """
                # Cirurgia 1: Thread-Local Pool — reutiliza a instância da thread
                if not hasattr(_thread_local, 'ignite'):
                    _thread_local.ignite = HybridIgnite(self.root)
                local_ignite = _thread_local.ignite

                try:
                    scan = local_ignite._scanner.scan(str(py_file))
                except Exception as e:
                    return False, None, 0, f"{py_file.name}: Falha no scanner ({e})"

                skipped_list = getattr(scan, "skipped",[])

                if not getattr(scan, "candidates", None):
                    return False, None, len(skipped_list), None

                # Cirurgia 2: sys.intern nos nomes dos candidatos
                # Nomes de funções se repetem massivamente entre arquivos da mesma lib.
                # intern() garante uma única cópia em RAM — comparações futuras são O(1).
                try:
                    for candidate in scan.candidates:
                        if hasattr(candidate, 'name') and isinstance(candidate.name, str):
                            candidate.name = sys.intern(candidate.name)
                except Exception:
                    pass  # intern é otimização — falha silenciosa é aceitável

                # Gera .pyx a partir do fonte já otimizado pelo LibOptimizer
                try:
                    pyx_path = local_ignite._forge.generate(scan)
                except Exception as e:
                    return False, None, 0, f"{py_file.name}: Falha ao gerar .pyx ({e})"

                if not pyx_path:
                    return False, None, 0, f"{py_file.name}: Arquivo .pyx não retornou"

                # 1. Obj-Reduce: elimina alocações temporárias no .pyx
                try:
                    source     = pyx_path.read_text(encoding="utf-8")
                    red_result = reduce_source(source, pyx_path, level=1, is_pyx=True)
                    if getattr(red_result, "has_changes", False):
                        pyx_path.write_text(red_result.transformed, encoding="utf-8")
                except Exception:
                    pass

                # 2. Hybrid-Optimizer: injeta cdef com AST Hoisting
                try:
                    optimized_pyx_path, _ = optimize_pyx_file(pyx_path)
                    if optimized_pyx_path:
                        pyx_path = optimized_pyx_path
                except Exception:
                    pass

                # 3. Compilação com Lock
                with compile_lock:
                    if _simd_cflags:
                        try:
                            ok, err = local_ignite._compile(pyx_path.stem, extra_cflags=_simd_cflags)
                        except TypeError:
                            ok, err = local_ignite._compile(pyx_path.stem)
                    else:
                        ok, err = local_ignite._compile(pyx_path.stem)

                if ok:
                    return True, pyx_path.stem, len(scan.candidates), py_file.name
                else:
                    return False, None, 0, f"{py_file.name}: {err}"

            # ── Motor de execução paralela ─────────────────────────────────────
            # Cirurgia 1 aplicada: _thread_local garante que cada worker-thread
            # crie exatamente UMA instância de HybridIgnite e a reutilize para
            # todos os arquivos daquela thread. O loop as_completed abaixo não
            # instancia mais nada — apenas coleta resultados já prontos.
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_file, f): f for f in files}

                for future in concurrent.futures.as_completed(futures):
                    try:
                        success, mod_stem, count, extra = future.result()
                        if success:
                            modules_generated.append(mod_stem)
                            functions_compiled += count
                            print(f"     ✔ {extra} compilado ({count} funções otimizadas)")
                        else:
                            if extra:
                                errors.append(extra)
                            else:
                                functions_skipped += count
                    except Exception as e:
                        errors.append(f"Erro crítico na thread: {e}")

            if not modules_generated:
                if errors:
                    return False, (
                        f"Compilação falhou em todos os módulos.\n"
                        f"Erros ({len(errors)}):\n" + "\n".join(errors[:3])
                    )
                return False, (
                    f"Nenhuma função elegível encontrada em '{lib_name}' "
                    f"({functions_skipped} descartadas por I/O ou estado mutável)."
                )

            # ── Fase 5: Mover binários aprovados para lib_bin/ ────────────────
            print(f"   > Promovendo {len(modules_generated)} binários para lib_bin...")
            bin_dir = self.root / ".doxoade" / "vulcan" / "bin"
            moved, failed = self._promote_to_lib_bin(bin_dir, modules_generated)

            bytes_saved = opt_stats.get('bytes_saved', 0)
            simd_line   = f"\n   SIMD aplicado    : {_simd_label}" if _simd_label else ""
            summary = (
                f"Biblioteca '{lib_name}' forjada com sucesso!\n"
                f"   Binários gerados : {len(moved)}\n"
                f"   Funções nativas  : {functions_compiled}\n"
                f"   Falhas no link   : {len(failed)}\n"
                f"   Fontes otimizados: {opt_stats.get('files_optimized', 0)}"
                f"/{opt_stats.get('files_processed', 0)} arquivos"
                f" ({bytes_saved:,} bytes economizados)"
                f"{simd_line}"
            )
            return True, summary

    # ── Localização no venv ───────────────────────────────────────────────────

    def _find_in_venv(self, lib_name: str) -> Path | None:
        import sys
        import importlib.util
        from pathlib import Path

        site_dirs = self._get_site_packages_dirs()

        # 1. GOD MODE: Injeta o site-packages do venv ativo no sys.path do Doxoade global
        old_path = list(sys.path)
        
        # Insere em ordem reversa para que o primeiro da lista fique no topo (índice 0)
        for d in reversed(site_dirs):
            if d not in sys.path:
                sys.path.insert(0, d)

        try:
            # 2. Usa o motor nativo do Python agora que ele está ciente do venv
            variants_to_try =[
                lib_name, 
                lib_name.replace("-", "_"), 
                lib_name.replace("_", "-")
            ]
            
            for variant in variants_to_try:
                try:
                    spec = importlib.util.find_spec(variant)
                    if spec is not None:
                        if spec.submodule_search_locations:
                            return Path(next(iter(spec.submodule_search_locations)))
                        elif spec.origin:
                            return Path(spec.origin).parent
                except Exception:
                    pass
        finally:
            # Restaura o sys.path original para não causar efeitos colaterais globais
            sys.path = old_path

        # 3. FALLBACK CLÁSSICO: Varredura manual
        base = lib_name.lower()
        name_variants = {
            lib_name, base,
            base.replace("-", "_"), base.replace("_", "-"),
            lib_name.replace("-", "_"), lib_name.replace("_", "-"),
        }

        for sp in site_dirs:
            sp_path = Path(sp)
            if not sp_path.is_dir():
                continue

            for variant in name_variants:
                candidate = sp_path / variant
                if candidate.is_dir() and (candidate / "__init__.py").exists():
                    return candidate

            try:
                for item in sp_path.iterdir():
                    if not item.is_dir(): continue
                    if item.name.lower() not in {v.lower() for v in name_variants}: continue
                    if (item / "__init__.py").exists():
                        return item
            except PermissionError:
                continue

        return None

    @staticmethod
    def _get_site_packages_dirs() -> list[str]:
        import os
        import site
        from pathlib import Path
        import sys
        
        dirs: list[str] =[]
        
        # 1. ESPIONAGEM: Lê a variável do venv que o terminal atual ativou
        venv = os.environ.get("VIRTUAL_ENV")
        if venv:
            venv_path = Path(venv)
            # Estrutura do Windows (venv\Lib\site-packages)
            win_site = venv_path / "Lib" / "site-packages"
            if win_site.exists(): dirs.append(str(win_site))
            
            # Estrutura do Linux/Mac (venv/lib/python3.X/site-packages)
            lib_path = venv_path / "lib"
            if lib_path.exists():
                for p in lib_path.glob("python*/site-packages"):
                    if p.is_dir(): dirs.append(str(p))

        # 2. Caminhos originais do Python do próprio Doxoade
        try: dirs.extend(site.getsitepackages())
        except AttributeError: pass
        
        try:
            user_sp = site.getusersitepackages()
            if user_sp and user_sp not in dirs: dirs.append(user_sp)
        except AttributeError: pass
        
        for p in sys.path:
            if ("site-packages" in p or "dist-packages" in p) and p not in dirs:
                dirs.append(p)
                
        # Remove duplicatas garantindo que a pasta do venv fique com prioridade 0
        seen = set()
        return[x for x in dirs if not (x in seen or seen.add(x))]

    # ── Cópia segura dos fontes ───────────────────────────────────────────────

    @staticmethod
    def _copy_sources(source_path: Path, work_dir: Path) -> Path:
        dest = work_dir / source_path.name
        _SKIP_DIRS = frozenset({"__pycache__", "tests", "test", "testing", "docs", "doc", "examples", "benchmarks"})
        _SKIP_SUFFIXES = frozenset({".pyc", ".pyo", ".pyd", ".so", ".pyx", ".pxd", ".c", ".h", ".cpp"})

        def _ignore(dir_: str, names: list[str]) -> set[str]:
            ignored: set[str] = set()
            for name in names:
                p = Path(dir_) / name
                if p.is_dir() and (name in _SKIP_DIRS or name.startswith("test_") or name.endswith("_test")):
                    ignored.add(name)
                elif p.is_file() and p.suffix in _SKIP_SUFFIXES:
                    ignored.add(name)
            return ignored

        shutil.copytree(str(source_path), str(dest), ignore=_ignore)
        return dest

    # ── Otimização dos fontes da cópia ────────────────────────────────────────

    @staticmethod
    def _optimize_sources(work_copy: Path) -> dict:
        try:
            from .lib_optimizer import LibOptimizer
            optimizer = LibOptimizer()
            return optimizer.optimize_directory(work_copy)
        except Exception as exc:
            print(f"   > [OPT] Optimizer falhou ({exc}) — compilando fontes não-otimizados.")
            return {
                'files_processed': 0, 'files_optimized': 0, 'files_skipped': 0,
                'bytes_saved': 0, 'docstrings_removed': 0, 'dead_branches': 0,
                'imports_removed': 0, 'locals_minified': 0,
            }

    @staticmethod
    def _print_opt_summary(stats: dict) -> None:
        if stats['files_optimized'] == 0:
            print(f"   > [OPT] Sem transformações aplicadas ({stats['files_skipped']} arquivo(s) sem ganho).")
            return
        parts = []
        if stats['docstrings_removed']: parts.append(f"{stats['docstrings_removed']} docstrings")
        if stats['dead_branches']: parts.append(f"{stats['dead_branches']} dead branches")
        if stats['imports_removed']: parts.append(f"{stats['imports_removed']} imports não usados")
        if stats['locals_minified']: parts.append(f"{stats['locals_minified']} vars locais")

        detail   = f"({', '.join(parts)})" if parts else ""
        saved_kb = stats['bytes_saved'] / 1024
        print(f"   > [OPT] {stats['files_optimized']}/{stats['files_processed']} arquivo(s) otimizados — {saved_kb:.1f} KB economizados {detail}")

    # ── Promoção para lib_bin/ ────────────────────────────────────────────────

    def _promote_to_lib_bin(self, bin_dir: Path, modules: list[str]) -> tuple[list, list]:
        moved, failed = [],[]
        ext = ".pyd" if sys.platform == "win32" else ".so"

        for mod in modules:
            candidates = list(bin_dir.glob(f"{mod}*{ext}"))
            if candidates:
                src = candidates[0]
                dst = self.lib_bin_dir / src.name
                try:
                    shutil.move(str(src), str(dst))
                    moved.append(dst)
                    print(f"   > ✔ {src.name} instalado em lib_bin/")
                except Exception as e:
                    failed.append(f"{mod}: {e}")
            else:
                failed.append(f"{mod}: binário não encontrado em {bin_dir}")

        return moved, failed
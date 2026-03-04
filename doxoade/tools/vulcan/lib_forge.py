# doxoade/tools/vulcan/lib_forge.py
"""
LibForge — Compilação de bibliotecas de terceiros já instaladas no venv.

Fluxo:
  1. Localiza a biblioteca no site-packages do Python atual (nunca baixa).
  2. Copia SOMENTE os fontes .py para um diretório temporário de trabalho.
     O original no venv nunca é tocado.
  3. [NOVO] LibOptimizer: aplica dead code elimination, remoção de imports
     não usados, remoção de docstrings e minificação de variáveis locais
     na cópia. Transformações revertidas por arquivo em caso de falha.
  4. HybridIgnite na cópia otimizada — só compila funções com score >= limiar
     e que passem em todas as verificações de elegibilidade.
  5. Move os binários aprovados para .doxoade/vulcan/lib_bin/.
     Arquivos não compilados permanecem otimizados na cópia (que é descartada
     com o tempdir — apenas os binários persistem).

Segurança:
  - Trabalha sempre com a cópia temporária (tempfile.TemporaryDirectory).
  - O venv original NUNCA é modificado.
  - Cada arquivo da cópia tem revert independente se a otimização falhar.
  - HybridIgnite filtra arquivos e funções inelegíveis antes de compilar.
  - Binários só chegam ao lib_bin após compilação bem-sucedida.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path


class LibForge:
    """
    Orquestrador de compilação + otimização de bibliotecas do venv.

    Nunca altera o ambiente Python original — trabalha com uma cópia isolada
    dos fontes .py da biblioteca alvo.
    """

    def __init__(self, project_root: str):
        self.root = Path(project_root)
        self.lib_bin_dir = self.root / ".doxoade" / "vulcan" / "lib_bin"
        self.lib_bin_dir.mkdir(parents=True, exist_ok=True)

    # ── Entry-point público ────────────────────────────────────────────────────

    def compile_library(self, lib_name: str) -> tuple[bool, str]:
        """
        Localiza, copia, otimiza e compila funções elegíveis da biblioteca.

        Retorna (sucesso, mensagem).
        """
        with tempfile.TemporaryDirectory(prefix=f"vulcan_lib_{lib_name}_") as temp_dir:
            work_dir = Path(temp_dir)

            # ── Fase 1: Localizar no venv ──────────────────────────────────────
            print(f"   > Localizando '{lib_name}' no site-packages...")
            source_path = self._find_in_venv(lib_name)

            if not source_path:
                return False, (
                    f"Biblioteca '{lib_name}' não encontrada no site-packages. "
                    f"Instale primeiro com: pip install {lib_name}"
                )

            print(f"   > Encontrada em: {source_path}")

            # ── Fase 2: Copiar fontes para área isolada ────────────────────────
            print(f"   > Copiando fontes .py para área temporária de trabalho...")
            try:
                work_copy = self._copy_sources(source_path, work_dir)
            except Exception as e:
                return False, f"Falha ao copiar fontes: {e}"

            py_count = sum(1 for _ in work_copy.rglob("*.py"))
            print(f"   > {py_count} arquivo(s) .py copiado(s) para análise.")

            if py_count == 0:
                return False, (
                    f"'{lib_name}' não possui arquivos .py copiáveis "
                    f"(pode ser uma extensão C pura)."
                )

            # ── Fase 3: Otimizar fontes da cópia ──────────────────────────────
            print(f"   > Otimizando fontes (dead code, imports, minificação local)...")
            opt_stats = self._optimize_sources(work_copy)
            self._print_opt_summary(opt_stats)

            # ── Fase 4: HybridIgnite na cópia otimizada ────────────────────────
            print(f"   > Analisando candidatos com HybridScanner...")
            from .hybrid_forge import HybridIgnite

            ignite = HybridIgnite(self.root)
            report = ignite.run(target=work_copy, on_progress=print)

            if not report.get("modules_generated"):
                skipped = report.get("functions_skipped", 0)
                errors  = report.get("errors", [])

                if errors:
                    return False, (
                        f"Compilação falhou em todos os módulos. "
                        f"Erros ({len(errors)}): {errors[:3]}"
                    )
                return False, (
                    f"Nenhuma função elegível encontrada em '{lib_name}' "
                    f"({skipped} função(ões) descartada(s) pelo scanner). "
                    f"A biblioteca pode ser C-only, usar I/O intensivo ou "
                    f"não ter loops computacionais suficientes para ganho real."
                )

            # ── Fase 5: Mover binários aprovados para lib_bin/ ────────────────
            bin_dir = self.root / ".doxoade" / "vulcan" / "bin"
            moved, failed = self._promote_to_lib_bin(bin_dir, report["modules_generated"])

            func_count = report.get("functions_compiled", 0)
            summary = (
                f"{moved} módulo(s) de '{lib_name}' instalados em lib_bin/ "
                f"({func_count} função(ões) otimizadas, "
                f"{report.get('functions_skipped', 0)} descartadas pelo scanner, "
                f"{opt_stats['bytes_saved']:,} bytes economizados pelo optimizer)."
            )
            if failed:
                summary += f" Falhas ao mover: {'; '.join(failed[:3])}"

            return True, summary

    # ── Localização no venv ───────────────────────────────────────────────────

    def _find_in_venv(self, lib_name: str) -> Path | None:
        """
        Busca a pasta da biblioteca no site-packages do Python atual.

        Tenta variações comuns de nome (hífens ↔ underscores, capitalização)
        e verifica se é um pacote real (possui __init__.py).
        """
        site_dirs = self._get_site_packages_dirs()

        base = lib_name.lower()
        name_variants = {
            lib_name,
            base,
            base.replace("-", "_"),
            base.replace("_", "-"),
            lib_name.replace("-", "_"),
            lib_name.replace("_", "-"),
        }

        for sp in site_dirs:
            sp_path = Path(sp)
            if not sp_path.is_dir():
                continue

            # 1. Tentativa direta
            for variant in name_variants:
                candidate = sp_path / variant
                if candidate.is_dir() and (candidate / "__init__.py").exists():
                    return candidate

            # 2. Varredura case-insensitive (Pillow → PIL, SQLAlchemy → sqlalchemy)
            try:
                for item in sp_path.iterdir():
                    if not item.is_dir():
                        continue
                    if item.name.lower() not in {v.lower() for v in name_variants}:
                        continue
                    if (item / "__init__.py").exists():
                        return item
            except PermissionError:
                continue

        return None

    @staticmethod
    def _get_site_packages_dirs() -> list[str]:
        """Coleta todos os diretórios site-packages acessíveis pelo Python atual."""
        import site

        dirs: list[str] = []

        try:
            dirs.extend(site.getsitepackages())
        except AttributeError:
            pass

        try:
            user_sp = site.getusersitepackages()
            if user_sp and user_sp not in dirs:
                dirs.append(user_sp)
        except AttributeError:
            pass

        for p in sys.path:
            if ("site-packages" in p or "dist-packages" in p) and p not in dirs:
                dirs.append(p)

        return dirs

    # ── Cópia segura dos fontes ───────────────────────────────────────────────

    @staticmethod
    def _copy_sources(source_path: Path, work_dir: Path) -> Path:
        """
        Copia apenas os .py da biblioteca para o diretório de trabalho.

        Exclui:
          - __pycache__/ e *.pyc/.pyo
          - *.pyd / *.so  (binários já compilados)
          - tests/ / test_*/ (suítes de teste)
          - *.pyx / *.pxd / *.c / *.h (código C/Cython — não misturar com forge)
        """
        dest = work_dir / source_path.name

        _SKIP_DIRS = frozenset({
            "__pycache__", "tests", "test", "testing",
            "docs", "doc", "examples", "benchmarks",
        })
        _SKIP_SUFFIXES = frozenset({
            ".pyc", ".pyo", ".pyd", ".so",
            ".pyx", ".pxd", ".c", ".h", ".cpp",
        })

        def _ignore(dir_: str, names: list[str]) -> set[str]:
            ignored: set[str] = set()
            for name in names:
                p = Path(dir_) / name
                if p.is_dir() and (name in _SKIP_DIRS
                                   or name.startswith("test_")
                                   or name.endswith("_test")):
                    ignored.add(name)
                elif p.is_file() and p.suffix in _SKIP_SUFFIXES:
                    ignored.add(name)
            return ignored

        shutil.copytree(str(source_path), str(dest), ignore=_ignore)
        return dest

    # ── Otimização dos fontes da cópia ────────────────────────────────────────

    @staticmethod
    def _optimize_sources(work_copy: Path) -> dict:
        """
        Aplica LibOptimizer em todos os .py da cópia.
        Cada arquivo tem revert independente — falhas são silenciosas.
        """
        try:
            from .lib_optimizer import LibOptimizer
            optimizer = LibOptimizer()
            return optimizer.optimize_directory(work_copy)
        except Exception as exc:
            # Nunca quebra o fluxo principal
            print(f"   > [WARN] Optimizer falhou ({exc}) — continuando sem otimização de fonte.")
            return {
                'files_processed': 0, 'files_optimized': 0, 'files_skipped': 0,
                'bytes_saved': 0, 'docstrings_removed': 0, 'dead_branches': 0,
                'imports_removed': 0, 'locals_minified': 0,
            }

    @staticmethod
    def _print_opt_summary(stats: dict):
        """Exibe resumo da otimização de forma compacta."""
        if stats['files_optimized'] == 0 and stats['files_skipped'] == stats['files_processed']:
            print(f"   > [OPT] Sem transformações aplicadas ({stats['files_skipped']} arquivo(s) ignorados).")
            return

        parts = []
        if stats['docstrings_removed']:
            parts.append(f"{stats['docstrings_removed']} docstrings")
        if stats['dead_branches']:
            parts.append(f"{stats['dead_branches']} dead branches")
        if stats['imports_removed']:
            parts.append(f"{stats['imports_removed']} imports não usados")
        if stats['locals_minified']:
            parts.append(f"{stats['locals_minified']} vars locais minificadas")

        detail = f"({', '.join(parts)})" if parts else ""
        saved_kb = stats['bytes_saved'] / 1024

        print(
            f"   > [OPT] {stats['files_optimized']}/{stats['files_processed']} arquivo(s) "
            f"otimizados — {saved_kb:.1f} KB economizados {detail}"
        )
        if stats['files_skipped']:
            print(f"   > [OPT] {stats['files_skipped']} arquivo(s) ignorado(s) (parse error / revertido).")

    # ── Promoção para lib_bin/ ────────────────────────────────────────────────

    def _promote_to_lib_bin(
        self,
        bin_dir: Path,
        module_names: list[str],
    ) -> tuple[int, list[str]]:
        """
        Move os binários gerados de bin/ para lib_bin/.
        Retorna (qtd_movidos, lista_de_erros).
        """
        moved   = 0
        failed: list[str] = []

        for module_name in module_names:
            for binary in list(bin_dir.glob(f"{module_name}*")):
                if binary.suffix not in (".pyd", ".so"):
                    continue
                try:
                    dst = self.lib_bin_dir / binary.name
                    shutil.move(str(binary), str(dst))
                    print(f"   > ✔ {binary.name} instalado em lib_bin/")
                    moved += 1
                except Exception as e:
                    failed.append(f"{binary.name}: {e}")

        return moved, failed
# doxoade/tools/vulcan/lib_forge.py
import json
import statistics
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


_PACKAGE_RE = re.compile(r"^[A-Za-z0-9_.-]+([<>=!~]=[^\s,;]+)?$")


class LibForge:
    """
    Orquestrador para compilação de bibliotecas de terceiros.
    Fases:
    1. Download do código-fonte (sdist).
    2. Compilação seletiva via HybridIgnite.
    3. Mover o binário para o diretório de bibliotecas do Vulcan.
    """

    def __init__(self, project_root):
        self.root = Path(project_root)
        self.lib_bin_dir = self.root / ".doxoade" / "vulcan" / "lib_bin"
        self.lib_bin_dir.mkdir(parents=True, exist_ok=True)

    def compile_library(self, lib_name: str) -> (bool, str):
        lib_name = (lib_name or "").strip()
        if not self._is_safe_requirement(lib_name):
            return False, (
                "Nome de biblioteca inválido/inseguro. Use formato simples, "
                "ex: pacote ou pacote==1.2.3"
            )

        with tempfile.TemporaryDirectory(prefix=f"vulcan_lib_build_{lib_name.split('=')[0]}_") as temp_dir:
            build_zone = Path(temp_dir)

            # Fase 1: Aquisição da Fonte
            print(f"   > Baixando código-fonte para '{lib_name}'...")
            source_path = self._download_source(lib_name, build_zone)
            if not source_path:
                return False, "Falha ao baixar o código-fonte (sdist)."

            print(f"   > Código-fonte extraído em: {source_path}")

            # Fase 2: Forja Híbrida
            print("   > Analisando e compilando funções 'quentes'...")
            from .hybrid_forge import HybridIgnite

            ignite = HybridIgnite(self.root)

            bin_dir = self.root / ".doxoade" / "vulcan" / "bin"
            ext = ".pyd" if os.name == "nt" else ".so"
            before = {p.name for p in bin_dir.glob(f"*{ext}")}

            report = ignite.run(target=source_path)

            if not report.get("modules_generated"):
                if report.get("errors"):
                    return False, f"Compilação falhou. Erros: {report['errors']}"
                return False, "Nenhuma função elegível para compilação foi encontrada na biblioteca."

            # Fase 3: mover apenas artefatos novos para lib_bin
            produced = [p for p in bin_dir.glob(f"*{ext}") if p.name not in before]
            moved_count = 0
            moved_files = []
            for binary in produced:
                if not self._is_binary_valid_for_host(binary):
                    continue
                dst = self.lib_bin_dir / binary.name
                try:
                    shutil.move(str(binary), str(dst))
                    print(f"   > Binário otimizado '{binary.name}' instalado com sucesso.")
                    moved_count += 1
                    moved_files.append(binary.name)
                except Exception as e:
                    return False, f"Falha ao mover o binário '{binary.name}': {e}"

            if moved_count > 0:
                self._write_manifest(lib_name, moved_files)
                return True, (
                    f"{moved_count} módulo(s) da biblioteca '{lib_name}' foram compilados "
                    "e instalados com validação de arquitetura."
                )

            return False, (
                "Compilação ocorreu, mas nenhum binário novo/compatível foi encontrado para instalar."
            )

    def integrity_report(self, lib_name: str | None = None) -> dict:
        manifest = self._load_manifest()
        libs = manifest.get("libraries", {})
        if lib_name:
            norm = self._extract_package_name(lib_name)
            libs = {k: v for k, v in libs.items() if self._extract_package_name(k) == norm}

        report = {
            "library": lib_name or "*",
            "libraries_checked": len(libs),
            "entries": [],
            "missing_files": 0,
            "invalid_host": 0,
            "ok": True,
        }

        for l_name, info in libs.items():
            binaries = info.get("binaries", []) if isinstance(info, dict) else []
            for bname in binaries:
                p = self.lib_bin_dir / bname
                exists = p.exists()
                valid_host = exists and self._is_binary_valid_for_host(p)
                entry = {
                    "library": l_name,
                    "binary": bname,
                    "exists": exists,
                    "valid_host": valid_host,
                    "size_kb": round(p.stat().st_size / 1024, 1) if exists else 0,
                }
                report["entries"].append(entry)
                if not exists:
                    report["missing_files"] += 1
                    report["ok"] = False
                elif not valid_host:
                    report["invalid_host"] += 1
                    report["ok"] = False

        return report

    def benchmark_library(self, lib_name: str, runs: int = 8) -> dict:
        self._last_bench_error_base = None
        self._last_bench_error_vulcan = None
        package = self._extract_package_name(lib_name)
        if not package:
            return {"ok": False, "error": "Nome de biblioteca inválido para benchmark."}

        base_samples = self._run_bench_samples(package, runs, disable_lib_bin=True)
        vulcan_samples = self._run_bench_samples(package, runs, disable_lib_bin=False)

        if not base_samples or not vulcan_samples:
            return {
                "ok": False,
                "error": "Falha ao executar benchmark de importação para a biblioteca.",
                "library": package,
                "details": {
                    "python_baseline_error": getattr(self, "_last_bench_error_base", None),
                    "vulcan_error": getattr(self, "_last_bench_error_vulcan", None),
                },
            }

        base = statistics.mean([s["elapsed"] for s in base_samples])
        vulcan = statistics.mean([s["elapsed"] for s in vulcan_samples])
        redirected = max([s.get("redirected", 0) for s in vulcan_samples])

        speedup = (base / vulcan) if vulcan > 0 else 0.0
        return {
            "ok": True,
            "library": package,
            "runs": runs,
            "mean_import_seconds_python": base,
            "mean_import_seconds_vulcan": vulcan,
            "speedup": speedup,
            "redirected_modules": redirected,
        }

    def _run_bench_samples(self, package: str, runs: int, disable_lib_bin: bool) -> list[dict]:
        samples: list[dict] = []
        for _ in range(max(1, runs)):
            row = self._run_bench_subprocess(package, disable_lib_bin=disable_lib_bin)
            if row is None:
                return []
            samples.append(row)
        return samples

    def _run_bench_subprocess(self, package: str, disable_lib_bin: bool) -> dict | None:
        env = os.environ.copy()
        env["VULCAN_DISABLE_LIB_BIN"] = "1" if disable_lib_bin else "0"
        script = (
            "import importlib, json, sys, time\n"
            "from doxoade.tools.vulcan.meta_finder import install\n"
            "root = sys.argv[1]\n"
            "pkg = sys.argv[2]\n"
            "install(root)\n"
            "t0 = time.perf_counter()\n"
            "importlib.import_module(pkg)\n"
            "elapsed = time.perf_counter() - t0\n"
            "lib_bin = (root + '/.doxoade/vulcan/lib_bin').replace('\\\\','/')\n"
            "redirected = 0\n"
            "for m in list(sys.modules.values()):\n"
            "  f = getattr(m, '__file__', '') or ''\n"
            "  if f and lib_bin in f.replace('\\\\','/'):\n"
            "    redirected += 1\n"
            "print(json.dumps({'elapsed': elapsed, 'redirected': redirected}))\n"
        )
        cmd = [sys.executable, "-c", script, str(self.root), package]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False, cwd=str(self.root))
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "").strip()
                if disable_lib_bin:
                    self._last_bench_error_base = err
                else:
                    self._last_bench_error_vulcan = err
                return None
            line = (proc.stdout or "").strip().splitlines()[-1]
            payload = json.loads(line)
            return {
                "elapsed": float(payload.get("elapsed", 0.0)),
                "redirected": int(payload.get("redirected", 0)),
            }
        except Exception:
            return None

    @staticmethod
    def _extract_package_name(requirement: str) -> str:
        requirement = (requirement or "").strip()
        return re.split(r"[<>=!~]", requirement, maxsplit=1)[0].strip().lower()

    @staticmethod
    def _is_safe_requirement(lib_name: str) -> bool:
        if not lib_name or len(lib_name) > 128:
            return False
        return bool(_PACKAGE_RE.fullmatch(lib_name))

    @staticmethod
    def _is_binary_valid_for_host(bin_path: Path) -> bool:
        # Reuso do guardião de integridade/arquitetura já existente no runtime.
        try:
            from .runtime import _is_binary_valid_for_host as _runtime_is_valid

            return _runtime_is_valid(bin_path)
        except Exception:
            return False

    def _load_manifest(self) -> dict:
        manifest = self.lib_bin_dir / "manifest.json"
        if not manifest.exists():
            return {"libraries": {}}
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"libraries": {}}
            return data
        except Exception:
            return {"libraries": {}}

    def _write_manifest(self, lib_name: str, binaries: list[str]) -> None:
        manifest = self.lib_bin_dir / "manifest.json"
        data = self._load_manifest()
        data.setdefault("libraries", {})[lib_name] = {
            "compiled_at": int(time.time()),
            "binaries": sorted(binaries),
        }
        manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _download_source(self, lib_name: str, dest: Path) -> Path | None:
        """Baixa o sdist de uma biblioteca usando pip."""
        try:
            cmd = [
                sys.executable,
                "-m",
                "pip",
                "download",
                lib_name,
                "--no-binary",
                ":all:",
                "--no-deps",
                "--dest",
                str(dest),
            ]
            proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if proc.stderr:
                print(proc.stderr.strip())

            for archive in dest.iterdir():
                if archive.name.endswith((".tar.gz", ".zip", ".tar", ".tgz")):
                    shutil.unpack_archive(archive, dest)

            candidates = [
                item
                for item in dest.iterdir()
                if item.is_dir() and ((item / "pyproject.toml").exists() or (item / "setup.py").exists())
            ]
            if not candidates:
                # fallback: retorna primeiro diretório extraído
                candidates = [item for item in dest.iterdir() if item.is_dir()]

            for item in sorted(candidates):
                try:
                    item.resolve().relative_to(dest.resolve())
                    return item
                except Exception:
                    continue
            return None
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

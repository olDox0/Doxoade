# doxoade/tools/vulcan/lib_forge.py
import json
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

    def _write_manifest(self, lib_name: str, binaries: list[str]) -> None:
        manifest = self.lib_bin_dir / "manifest.json"
        data = {"libraries": {}}
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                data = {"libraries": {}}
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

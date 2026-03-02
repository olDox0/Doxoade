# doxoade/tools/vulcan/lib_forge.py
import os, sys
import shutil
import subprocess
import tempfile
from pathlib import Path

class LibForge:
    """
    Orquestrador para compilação de bibliotecas de terceiros.
    Fases:
    1. Download do código-fonte (sdist).
    2. Compilação seletiva via HybridIgnite.
    3. Mover o binário para o diretório de bibliotecas do Vulcano.
    """
    def __init__(self, project_root):
        self.root = Path(project_root)
        self.lib_bin_dir = self.root / ".doxoade" / "vulcan" / "lib_bin"
        self.lib_bin_dir.mkdir(parents=True, exist_ok=True)

    def compile_library(self, lib_name: str) -> (bool, str):
        with tempfile.TemporaryDirectory(prefix=f"vulcan_lib_build_{lib_name}_") as temp_dir:
            build_zone = Path(temp_dir)
            
            # Fase 1: Aquisição da Fonte
            print(f"   > Baixando código-fonte para '{lib_name}'...")
            source_path = self._download_source(lib_name, build_zone)
            if not source_path:
                return False, "Falha ao baixar o código-fonte (sdist)."
            
            print(f"   > Código-fonte extraído em: {source_path}")

            # Fase 2: Forja Híbrida
            print(f"   > Analisando e compilando funções 'quentes'...")
            from .hybrid_forge import HybridIgnite
            
            ignite = HybridIgnite(self.root)
            # Aponta o HybridIgnite para o código-fonte baixado
            report = ignite.run(target=source_path)

            if not report.get("modules_generated"):
                if report.get("errors"):
                    return False, f"Compilação falhou. Erros: {report['errors']}"
                return False, "Nenhuma função elegível para compilação foi encontrada na biblioteca."
            
            # Fase 3: Mover o Binário para o Local Correto
            # O HybridIgnite já salva no bin_dir principal, precisamos mover para lib_bin
            bin_dir = self.root / ".doxoade" / "vulcan" / "bin"
            
            moved_count = 0
            for module_name in report["modules_generated"]:
                # O nome do binário pode ter tags de versão (ex: .cp312-win_amd64.pyd)
                for binary in bin_dir.glob(f"{module_name}*"):
                    try:
                        shutil.move(str(binary), self.lib_bin_dir)
                        print(f"   > Binário otimizado '{binary.name}' instalado com sucesso.")
                        moved_count += 1
                    except Exception as e:
                        return False, f"Falha ao mover o binário '{binary.name}': {e}"

            if moved_count > 0:
                return True, f"{moved_count} módulo(s) da biblioteca '{lib_name}' foram compilados e instalados."
            else:
                return False, "Compilação parece ter ocorrido, mas nenhum binário foi encontrado para instalar."


    def _download_source(self, lib_name: str, dest: Path) -> Path | None:
        """Baixa o sdist de uma biblioteca usando pip."""
        try:
            cmd = [
                sys.executable, "-m", "pip", "download",
                lib_name,
                "--no-binary", ":all:",
                "--no-deps",
                "--dest", str(dest)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Encontra e descompacta o arquivo baixado (.tar.gz)
            for archive in dest.iterdir():
                if archive.name.startswith(lib_name) and (archive.name.endswith(".tar.gz") or archive.name.endswith(".zip")):
                    shutil.unpack_archive(archive, dest)
                    # Encontra a pasta descompactada
                    for item in dest.iterdir():
                        if item.is_dir() and item.name.startswith(lib_name):
                            return item
            return None
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
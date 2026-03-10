# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic.py (v82.4 Gold)
import os
import shutil
import sys
from pathlib import Path
import importlib.util

class VulcanDiagnostic:
    def __init__(self, project_root):
        self.root = Path(project_root).resolve()
        # Âncora do Core: sobe 3 níveis do arquivo atual
        # doxoade/doxoade/tools/vulcan/diagnostic.py -> doxoade/ (raiz do projeto)
        self.core_dir = Path(__file__).resolve().parents[3]
        self.issues = []

    def check_environment(self):
        """Check-up focando na infraestrutura interna do Doxoade."""
        # 1. Tenta injetar o venv do Doxoade no sys.path preventivamente
        self._bootstrap_core_venv()
        
        compiler_ok = self._check_compiler()
        cython_ok = self._check_internal_dependency("cython")
        
        results = {
            "compiler": compiler_ok,
            "cython": cython_ok,
            "foundry": self._check_directory(".doxoade/vulcan/foundry"),
            "disk_space": self._check_disk_free()
        }
        return all(results.values()), results

    def _bootstrap_core_venv(self):
        """Injeta o site-packages do próprio Doxoade no sys.path (MPoT-19)."""
        # Caminho do site-packages do VENV do Doxoade
        if os.name == 'nt':
            sp = self.core_dir / "venv" / "Lib" / "site-packages"
        else:
            sp = self.core_dir / "venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
        
        if sp.exists() and str(sp) not in sys.path:
            # Insere no início para garantir prioridade total às ferramentas do Core
            sys.path.insert(0, str(sp))

    def _check_compiler(self):
        """Busca compilador no PATH ou na pasta 'opt' do Doxoade."""
        if shutil.which("gcc") or shutil.which("cl.exe"):
            return True
            
        internal_gcc = self.core_dir / "thirdparty" / "w64devkit" / "bin" / "gcc.exe"
        if internal_gcc.exists():
            bin_path = str(internal_gcc.parent)
            if bin_path not in os.environ["PATH"]:
                os.environ["PATH"] = bin_path + os.pathsep + os.environ["PATH"]
            return True
            
        self.issues.append(f"Compilador não encontrado. Instale o w64devkit em: {self.core_dir / 'thirdparty'}")
        return False

    def _check_internal_dependency(self, package_name):
        """Verifica se o pacote está na maleta do Doxoade (Batteries-Included)."""
        # Tenta carregar a spec (agora com o sys.path atualizado pelo bootstrap)
        try:
            spec = importlib.util.find_spec(package_name) or importlib.util.find_spec(package_name.title())
            if spec is not None:
                return True
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
            exc_trace(exc_tb)
            
        self.issues.append(f"Dependência interna faltando: {package_name}. (Rode: pip install {package_name})")
        return False

    def _check_directory(self, rel_path):
        p = self.root / rel_path
        p.mkdir(parents=True, exist_ok=True)
        return True

    def _check_disk_free(self):
        import psutil
        try:
            free_mb = psutil.disk_usage(str(self.root)).free / (1024 * 1024)
            return free_mb > 50
        except Exception as e:
            print(f"\033[0;33m _check_disk_free - Exception: {e}")
            return True

    def render_report(self):
        from colorama import Fore, Style
        print(f"\n{Fore.CYAN}{Style.BRIGHT}🔍 [VULCAN-DIAGNOSTIC] Checando maleta de ferramentas...{Style.RESET_ALL}")
        if not self.issues:
            print(f"   {Fore.GREEN}✔ [STATUS] Ferramentas prontas no Core.{Fore.RESET}")
        else:
            print(f"   {Fore.RED}✘ [ERRO] Maleta incompleta:{Fore.RESET}")
            for issue in self.issues:
                print(f"     ■ {issue}")
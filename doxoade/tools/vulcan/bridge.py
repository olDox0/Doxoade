# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/bridge.py (Fix v98.5)
import sys
import os
import importlib.util
import hashlib
from typing import List, Dict, Any
from pathlib import Path
from colorama import Fore

class VulcanBridge:
    def __init__(self, project_root):
        self.root = Path(project_root)
        self.bin_dir = self.root / ".doxoade" / "vulcan" / "bin"

    def get_optimized_module(self, script_path: str):
        """
        Busca e carrega o módulo nativo usando a Assinatura Única (v84.2).
        Fix: TypeError v84.1.
        """
        if not script_path: return None
        
        abs_path = Path(script_path).resolve()
        path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
        v_name = f"v_{abs_path.stem}_{path_hash}"
        
        ext = ".pyd" if os.name == 'nt' else ".so"
        bin_path = self.bin_dir / f"{v_name}{ext}"

        if not bin_path.exists():
            return None

        try:
            # Sincronia de Escopo: Injeta o Venv do Alvo antes de carregar o C
            old_path = sys.path.copy()
            target_dir = str(abs_path.parent)
            if target_dir not in sys.path:
                sys.path.insert(0, target_dir)

            spec = importlib.util.spec_from_file_location(v_name, str(bin_path))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[v_name] = mod
                spec.loader.exec_module(mod)
                return mod
        except Exception:
            return None
        finally:
            sys.path = old_path
        return None

    def is_binary_stale(self, script_path: str) -> bool:
        # Lógica de staleness mantida v83.5
        abs_path = Path(script_path).resolve()
        path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
        v_path = self.bin_dir / f"v_{abs_path.stem}_{path_hash}{'.pyd' if os.name == 'nt' else '.so'}"
        if not v_path.exists(): return True
        return os.path.getmtime(script_path) > os.path.getmtime(v_path)
        
    def get_optimized_module_by_name(self, mod_name: str):
        """Localiza o binário .pyd/.so mais recente para o módulo."""
        import importlib.util
        import sys
        
        pattern = f"v_{mod_name}"
        ext = ".pyd" if os.name == 'nt' else ".so"
        candidates = list(self.bin_dir.glob(f"{pattern}*{ext}"))
        
        if not candidates: return None

        try:
            # PASC-1.1: O mais novo é a verdade (Lida com duplicatas de hash)
            target_path = sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            internal_name = f"vulcan_metal.{mod_name}"

            spec = importlib.util.spec_from_file_location(internal_name, str(target_path))
            if spec and spec.loader:
                v_mod = importlib.util.module_from_spec(spec)
                sys.modules[internal_name] = v_mod
                spec.loader.exec_module(v_mod)
                return v_mod
        except Exception: return None
        return None

    def apply_turbo(self, mod_name: str, target_globals: dict):
        v_mod = self.get_optimized_module_by_name(mod_name)
        if v_mod:
            injected = []
            for attr in dir(v_mod):
                if attr.endswith('_vulcan_optimized'):
                    orig = attr.replace('_vulcan_optimized', '')
                    if orig in target_globals:
                        target_globals[orig] = getattr(v_mod, attr)
                        injected.append(orig)
            
            if injected:
                # FIX: original_module_name -> mod_name
                msg = f"\033[94m [VULCAN:ACTIVE] {mod_name} ({', '.join(injected)}) -> NATIVE\n\033[0m"
                sys.stdout.write(msg)
            return True
        else:
            return False
        
        # 2. Injeção de Símbolos (Ares Power)
        # Varre o módulo C em busca de funções com sufixo '_vulcan_optimized'
        try:
            success_count = 0
            for attr in dir(v_mod):
                if attr.endswith('_vulcan_optimized'):
                    # PASC-8.17: Proteção de Contrato
                    orig_func_name = attr.replace('_vulcan_optimized', '')
                    if orig_func_name in target_globals:
                        # Substituição Atômica
                        target_globals[orig_func_name] = getattr(v_mod, attr)
                        success_count += 1
            
            if success_count > 0:
                print(f"{Fore.YELLOW}🔥 [VULCAN] Turbo ativado em '{mod_name}' ({success_count} funções nativas).")
#                print(f"{Fore.YELLOW}🔥 [VULCAN] Turbo ativado em '{original_module_name}' ({success_count} funções nativas).")
                return True
        except Exception as e:
            # PASC-3: Safe-fail - Se a injeção der erro, o Python original permanece
            print(f"{Fore.RED}✘ [VULCAN-FAIL] Erro na injeção: {e}")
            import sys as dox_exc_sys
            _, exc_obj, exc_tb = dox_exc_sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_number = exc_tb.tb_lineno
            print(f"\033[0m \033[1m Filename: {fname}   ■ Line: {line_number} \033[31m ■ Exception type: {e} ■ Exception value: {exc_obj} \033[0m")
            return False
        
    def apply_turbo_recursive(self, package_path: str):
        """Varre um diretório e aplica turbo em todos os módulos .py (PASC-Flex)."""
        for root, _, files in os.walk(package_path):
            for f in files:
                if f.endswith('.py') and not f.startswith('__'):
                    mod_name = f[:-3]  # OBJ-REDUCE: slice→memoryview
                    # Tenta injetar metal silenciosamente
                    self.apply_turbo(mod_name, {})
        
    def _filter_safe_targets(self, hits_map) -> List[Dict[str, Any]]:
        candidates = []
        processed = set()
        bin_dir = self.root / ".doxoade" / "vulcan" / "bin"

        for file_path, hits in sorted(hits_map.items(), key=lambda x: x[1], reverse=True):
            if hits < self.MIN_HITS: continue
            
            # 1. Pula infra do próprio Vulcan
            if "tools/vulcan" in file_path.replace('\\', '/'): continue

            # 2. DETECÇÃO DE ESTADO (PASC-Flex)
            if self._needs_compilation(file_path, bin_dir):
                candidates.append({'file': file_path, 'hits': hits})
                processed.add(file_path)
            
        return candidates

    def _needs_compilation(self, py_path, bin_dir):
        """Verifica se o metal já foi forjado e se está atualizado."""
        if not os.path.exists(py_path): return False
        
        stem = os.path.splitext(os.path.basename(py_path))[0]
        ext = ".pyd" if os.name == 'nt' else ".so"
        
        # Busca binários existentes para este módulo
        existing_bins = list(bin_dir.glob(f"v_{stem}*{ext}"))
        if not existing_bins: return True # Não forjado
        
        # Se o .py mudou depois da última forja, precisa refazer
        last_forge = max(os.path.getmtime(b) for b in existing_bins)
        return os.path.getmtime(py_path) > last_forge
        
    def _load_native_binary(self, mod_name):
        """Carrega o .pyd/.so de forma isolada."""
        ext = ".pyd" if os.name == 'nt' else ".so"
        # O Vulcan salva como v_nome_modulo.pyd
        bin_path = self.bin_dir / f"v_{mod_name}{ext}"
        
        if not bin_path.exists():
            return None

        # Verificação de Staleness (PASC-2): Se o .py mudou, o .pyd é ignorado
        # py_path = Path(sys.modules[mod_name].__file__)
        # if os.path.getmtime(py_path) > os.path.getmtime(bin_path): return None

        try:
            spec = importlib.util.spec_from_file_location(f"vulcan.{mod_name}", str(bin_path))
            v_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(v_mod)
            return v_mod
        except Exception:
            return None

from ..filesystem import _find_project_root
vulcan_bridge = VulcanBridge(_find_project_root(os.getcwd()))
#vulcan_bridge = VulcanBridge(os.getcwd())

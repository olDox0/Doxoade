# doxoade/doxoade/tools/horus_scribe.py
import ast
import sys
import os
import importlib.abc
import importlib.util

HORUS_FORBIDDEN = {
    'doxoade.tools.telemetry_tools.logger',
    'doxoade.tools.telemetry_tools',
    'doxoade.tools.alexandria',
    'doxoade.tools.alexandria.engine',
    'doxoade.tools.filesystem',
    'doxoade.tools.analysis',
    'doxoade.database',
    'doxoade.core_database',
    'doxoade.tools.aegis.nexus_db',
    'doxoade.tools.horus_scribe',
    'doxoade.tools.horus',
    'doxoade.tools.doxcolors',
    'doxoade.tools.aegis.aegis_utils',
    'doxoade.tools.aegis.aegis_core',
    'doxoade.rescue',
    'doxoade.boot',
    'doxoade.tools.vulcan.shadow_runtime',
    'doxoade.tools.aegis.shadow_scribe',
    'doxoade.tools.vulcan.shadow_scribe',
    'doxoade.tools.vulcan.opt_cache',
    'doxoade.tools.command_metadata',
    'doxoade.tools.hermes_systems',
    'doxoade.tools.hermes_systems.native',
    'doxoade.tools.hermes_systems.hermes_loader',
    'doxoade.tools.hermes_systems.hermes_hook',
    'doxoade.tools.hermes_systems.hermes_hook_v2',
}

_INFRA_PREFIXES = (
    'doxoade.tools.telemetry_tools',
    'doxoade.tools.alexandria',
    'doxoade.tools.vulcan',
    'doxoade.tools.aegis',
    'doxoade.tools.hermes_systems',
    'doxoade.database',
    'doxoade.core_database',
    'doxoade.rescue',
    'doxoade.boot',
)

class HorusLoader(importlib.abc.Loader):
    def __init__(self, original_spec):
        self.spec = original_spec
        self.fullname = original_spec.name

    def exec_module(self, module):
        from doxoade.tools.aegis.aegis_core import nexus_exec
        origin = self.spec.origin
        
        # [FIX] SEGURANÇA: Se não for um arquivo .py, delega ao loader original
        if not origin or not origin.endswith('.py') or not os.path.exists(origin):
            if hasattr(self.spec.loader, 'exec_module'):
                self.spec.loader.exec_module(module)
            return

        # [FIX] Rede de segurança: Verifica bytes nulos (proteção contra leitura acidental de binários)
        try:
            with open(origin, 'rb') as f:
                head = f.read(1024)
                if b'\x00' in head:
                    if hasattr(self.spec.loader, 'exec_module'):
                        self.spec.loader.exec_module(module)
                    return
        except Exception:
            pass

        # Módulos vitais ou proibidos de instrumentação utilizam exec nativo diretamente.
        if module.__name__ in HORUS_FORBIDDEN or any(module.__name__.startswith(p) for p in _INFRA_PREFIXES):
            with open(origin, 'r', encoding='utf-8', errors='ignore') as f:
                nexus_exec(f.read(), module.__dict__)
            return

        try:
            with open(origin, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            
            module.__dict__['__file__'] = origin
            module.__dict__['__name__'] = module.__name__
            
            # [FIX] Injeção segura do chief_heartbeat (Evita Circular Import)
            try:
                from doxoade.tools.telemetry_tools.logger import chief_heartbeat
                module.__dict__['chief_heartbeat'] = chief_heartbeat
            except Exception:
                # Fallback dummy para não quebrar o código instrumentado se o logger não estiver pronto
                module.__dict__['chief_heartbeat'] = lambda *args, **kwargs: None

            try:
                tree = ast.parse(source)
                from doxoade.tools.vulcan.shadow_scribe import NexusShadowScribe
                vax = NexusShadowScribe(os.path.basename(origin))
                vax.visit(tree)
                ast.fix_missing_locations(tree)
                code = compile(tree, origin, 'exec')
                
                from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
                restricted_safe_exec(code, module.__dict__, filename=origin, allow_imports=True)
            except Exception:
                from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
                restricted_safe_exec(source, module.__dict__, filename=origin, allow_imports=True)
                
        except Exception as e:
            # [FIX] Fallback de Emergência: Se o Horus falhar, usa o loader original para não quebrar o boot
            try:
                if hasattr(self.spec.loader, 'exec_module'):
                    self.spec.loader.exec_module(module)
            except Exception:
                print(f"\x1b[31m [!] Falha Crítica no Horus Scribe ({module.__name__}): {e}\x1b[0m")


class HorusFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        # 1. Blacklist Exata e por Prefixo (Corrigido: sem espaços fantasmas)
        if fullname in HORUS_FORBIDDEN:
            return None
        if any(fullname.startswith(p) for p in _INFRA_PREFIXES):
            return None
            
        # 2. Filtro de Escopo (Apenas comandos e tools do doxoade)
        if not (fullname.startswith("doxoade.commands") or fullname.startswith("doxoade.tools")):
            return None
            
        # 3. Filtro de palavras-chave de infraestrutura
        if any(x in fullname for x in ["telemetry", "logger", "horus", "scribe", "aegis_core"]):
            return None

        # 4. Delegação e Interceptação
        for finder in sys.meta_path:
            if finder is self:
                continue
            
            # Não sobrescreve specs do Vulcan, Shadow ou Hermes
            finder_name = type(finder).__name__
            if finder_name in ("VulcanMetaFinder", "ShadowFinder", "HermesFinderV2"):
                continue

            try:
                spec = finder.find_spec(fullname, path, target)
                if spec and spec.origin:
                    # [FIX] SÓ INTERCEPTA ARQUIVOS PYTHON PUROS (.py)
                    # Isso impede que o Horus tente ler .pyd, .so, .dll como texto
                    if not spec.origin.endswith('.py'):
                        return spec  # Retorna o spec original sem o HorusLoader
                    
                    spec.loader = HorusLoader(spec)
                    return spec
            except Exception:
                pass
        return None

def activate_horus_shadow():
    if not any(isinstance(f, HorusFinder) for f in sys.meta_path):
        insert_pos = 0
        for i, f in enumerate(sys.meta_path):
            finder_name = type(f).__name__
            if finder_name in ("VulcanMetaFinder", "ShadowFinder"):
                insert_pos = i + 1
        sys.meta_path.insert(insert_pos, HorusFinder())
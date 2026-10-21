# doxoade/doxoade/tools/vulcan/compiler.py
import os
import sys
import time
import concurrent.futures
from pathlib import Path
# [DOX-UNUSED] from setuptools import Extension

from .diagnostic.soteria.scribe import SoteriaScribe
from .buildcraft.dedalo_engine import DedaloEngine
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.soteria_systems.soteria_engine import SoteriaForensic

COMPILATION_TELEMETRY = []

def _resolve_tool(name: str) -> str:
    """
    Resolve o caminho absoluto de um binário via Janus (gcc, g++, ar, etc).
    Fallback para shutil.which se Janus não estiver disponível.
    """
    from pathlib import Path
    from doxoade.tools.janus_systems import Janus
    import shutil

    try:
        Janus.ensure_active()
        info = Janus.get_info()
        if info:
            compiler_bin = Path(info.compiler_path).parent
            candidate = compiler_bin / name
            for ext in ("", ".exe"):
                full = Path(f"{candidate}{ext}")
                if full.exists():
                    return str(full)
            if name.lower() in ("g++", "g++.exe") and info.gpp_path:
                if Path(info.gpp_path).exists():
                    return info.gpp_path
    except Exception:
        pass

    found = shutil.which(name)
    if found:
        return found

    raise RuntimeError(
        f"[VULCAN] Não foi possível localizar '{name}'. "
        f"Janus não encontrou um compilador. "
        f"Execute: doxoade janus scan"
    )

class VulcanCompiler:
    _cached_env = None

    def __init__(self, env, pid_registry=None): # [FIX] Adicionado pid_registry
        
        import sysconfig
        self.env = env
        # Mantém compatibilidade com o sistema de monitoramento de processos
        self._pid_registry = pid_registry if pid_registry is not None else {}
        self.detailed_telemetry = {}
        # soteria e DedaloEngine
        self.soteria_dir = Path(__file__).resolve().parent / "diagnostic" / "soteria"
        self.soteria_include = self.soteria_dir / "include"
        self.soteria_src_dir = self.soteria_dir / "src"
        self.scribe = SoteriaScribe()
        self.forensic = SoteriaForensic()
        self.buildcraft = DedaloEngine(env.root)
        # Cache de caminhos do sistema (Otimização N2808)
        self.py_include = sysconfig.get_path('include')
        self.py_libs = os.path.join(sysconfig.get_config_var('installed_base'), "libs")
        # Detecta a versão do Python instalada
        py_ver = sysconfig.get_config_var('VERSION')
        if py_ver:
            py_ver = py_ver.replace('.', '')
        else:
            # Fallback manual se o config_var falhar
            py_ver = f"{sys.version_info.major}{sys.version_info.minor}"
            
        self.py_link_lib = f"-lpython{py_ver}"

    def _prepare_pitstop_env(self):
        """Prepara o toolkit GCC/Clang via Janus de forma agnóstica (Hefesto)."""
        if VulcanCompiler._cached_env is not None:
            return VulcanCompiler._cached_env

        from doxoade.tools.janus_systems import Janus
        Janus.ensure_active()
        info = Janus.get_info()

        env = os.environ.copy()
        if info:
            bin_dir = str(Path(info.compiler_path).parent)
            env['PATH'] = bin_dir + os.pathsep + env.get('PATH', '')
            env['CC'] = info.compiler_path
            if info.gpp_path:
                env['CXX'] = info.gpp_path
            env['DISTUTILS_USE_SDK'] = '1'
            env['PY_VULCAN_PITSTOP'] = '1'

        VulcanCompiler._cached_env = env
        return env

    @staticmethod
    def _format_verbose_build_error(module_name: str, cmd: list[str], returncode: int, stdout: str, stderr: str) -> str:
        """Gera diagnóstico verboso para falhas de compilação Cython."""

        def _tail(text: str, n: int=25) -> str:
            lines = [ln for ln in (text or '').splitlines() if ln.strip()]
            if not lines:
                return '(vazio)'
            return '\n'.join(lines[-n:])
        cmd_str = ' '.join(cmd)
        return f'Build failed for {module_name} (exit={returncode})\nCMD: {cmd_str}\n--- STDERR (tail) ---\n{_tail(stderr)}\n--- STDOUT (tail) ---\n{_tail(stdout)}'

    @staticmethod
    def _run_command_streaming(cmd: list[str], cwd: str, env: dict, *, max_tail_lines: int=80) -> tuple[int, str, str]:
        """Executa comando com coleta incremental de stdout/stderr (baixo uso de memória)."""
        from collections import deque
        import subprocess
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', bufsize=1)
        out_tail: deque[str] = deque(maxlen=max_tail_lines)
        err_tail: deque[str] = deque(maxlen=max_tail_lines)

        def _drain(pipe, target: deque[str]):
# [DOX-UNUSED]             from collections import deque
            try:
                for line in iter(pipe.readline, ''):
                    if line:
                        target.append(line.rstrip('\n'))
            finally:
                pipe.close()
        import threading
        t_out = threading.Thread(target=_drain, args=(proc.stdout, out_tail), daemon=True)
        t_err = threading.Thread(target=_drain, args=(proc.stderr, err_tail), daemon=True)
        t_out.start()
        t_err.start()
        code = proc.wait()
        t_out.join(timeout=2)
        t_err.join(timeout=2)
        return (code, '\n'.join(out_tail), '\n'.join(err_tail))

    def transpile_batch(self, modules_list, use_soteria=True):
        import time, os, shutil
        from pathlib import Path
        import doxoade 
        from setuptools import Extension 
        
        # 1. Setup de Ambiente
        project_root = Path(self.env.root).resolve()
        foundry_path = self.env.foundry.resolve()
        
        vulcan_root = Path(__file__).resolve().parent
        native_h = vulcan_root / "native" / "nexus_kernels.h"
        soteria_h = vulcan_root / "diagnostic" / "soteria" / "include" / "soteria.h"
        
        import shutil
        if native_h.exists(): shutil.copy2(native_h, foundry_path / "nexus_kernels.h")
        if soteria_h.exists(): shutil.copy2(soteria_h, foundry_path / "soteria.h")
        
        # PASC 8.13: Define a base de busca inicial (resiliente)
        original_src = project_root / "src"
        if not original_src.exists():
            original_src = project_root # Recua para a raiz se não houver 'src'

        # --- [ESTRATÉGIA SOTÉRIA 2.0: SHADOW PYX] ---
        if use_soteria:
#            soteria_files = list(self.soteria_src_dir.glob("*.c"))
#            sources.extend([str(f) for f in soteria_files])
            base_source_dir = foundry_path / "shadow_pyx"
            print(f"   🔮 [SOTÉRIA] Projetando sombra de segurança em: {base_source_dir.name}")
            self.scribe.generate_shadow(str(original_src), str(base_source_dir))
            
            # Copia header para o Cython enxergar na foundry
            soteria_h = self.soteria_include / "soteria.h"
            if soteria_h.exists():
                shutil.copy2(soteria_h, foundry_path / "soteria.h")
        else:
            base_source_dir = original_src

        # 2. Configuração das Extensões (PASC 8.7)
        extensions = []
        for m in modules_list:
            source_file = base_source_dir / f"{m}.pyx"
            # Se não estiver na sombra/src, tenta na foundry local
            if not source_file.exists():
                source_file = foundry_path / f"{m}.pyx"

            extensions.append(
                Extension(name=m, sources=[str(source_file)], include_dirs=["."])
            )
        
        t_start = time.perf_counter()
        print(f"   [LINK] Iniciando Metalurgia em {len(modules_list)} módulos...")
        
        from Cython.Build import cythonize
        try:
            cythonize(
                extensions, 
                nthreads=os.cpu_count() or 2, 
                quiet=True, 
                include_path=["."],
                compiler_directives={'language_level': "3", 'cdivision': True}
            )
            
            duration_ms = (time.perf_counter() - t_start) * 1000
            for m in modules_list:
                self.detailed_telemetry.setdefault(m, {})['transpile_ms'] = duration_ms / len(modules_list)
                
            print(f"   ✔ Sucesso: Lote finalizado em {duration_ms/1000:.2f}s")
            return True

        except Exception as e:
            from doxoade.tools.error_info import handle_error
            handle_error(e, context="transpile_batch_soteria", debug=True)
            return False

    def _ensure_pch(self):
        """
        Gera o cabeçalho pré-compilado (Python.h.gch) se não existir.
        [PATCH] Usa Janus para localizar o compilador — sem hardcode 'gcc'.
        """
        pch_file = self.env.foundry / "vulcan_headers.h"
        gch_file = self.env.foundry / "vulcan_headers.h.gch"

        if gch_file.exists():
            return pch_file

        print(f"   {Fore.YELLOW}❄ Preparando Criogenia de Cabeçalhos (PCH)...{Fore.RESET}")

        # [FIX] Localiza GCC via Janus
        try:
            compiler_bin = _resolve_tool("gcc")
        except RuntimeError as e:
            print(f"   {Fore.RED}✘ {e}{Fore.RESET}")
            return pch_file  # Retorna sem GCH; o build tentará sem PCH

        content = "#include <Python.h>\n#include <structmember.h>\n"
        pch_file.write_text(content, encoding="utf-8")

        cmd = [
            compiler_bin,
            "-x", "c-header",
            str(pch_file),
            f"-I{self.py_include}",
            "-o", str(gch_file),
        ]

        import subprocess
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            if result.returncode != 0:
                print(f"   {Fore.YELLOW}⚠ PCH falhou (continuando sem): {result.stderr[:200]}{Fore.RESET}")
        except Exception as e:
            print(f"   {Fore.YELLOW}⚠ PCH falhou (continuando sem): {e}{Fore.RESET}")

        return pch_file

    def _get_doxo_python(self):
        
        core_root = Path(__file__).resolve().parents[3]
        return core_root / 'venv' / 'Scripts' / 'python.exe' if os.name == 'nt' else sys.executable

    def compile(self, module_name):
        foundry_path = self.env.foundry.resolve()
        setup_path = foundry_path / f'setup_{module_name}.py'
        
        # 1. Localização e Relocação de Cabeçalhos (Ação Industrial)
        vulcan_root = Path(__file__).resolve().parent
        native_dir = (vulcan_root / "native").resolve()
        soteria_inc = (vulcan_root / "diagnostic" / "soteria" / "include").resolve()
#        native_h = vulcan_root / "native" / "nexus_kernels.h"
#        soteria_h = vulcan_root / "diagnostic" / "soteria" / "include" / "soteria.h"
        
        # Copia os headers para a foundry para que o include "..." local funcione
        import shutil
        if native_h.exists():
            shutil.copy2(native_h, foundry_path / "nexus_kernels.h")
        if soteria_h.exists():
            shutil.copy2(soteria_h, foundry_path / "soteria.h")
        
        build_env = self._prepare_pitstop_env()
        has_pch = self._ensure_pch()
        
        pch_flags = []
        if has_pch and os.name == 'nt':
            # Nota: foundry_path.as_posix() evita o bug de aspas no Windows
            pch_flags = [f'-I{foundry_path.as_posix()}', '-include', 'vulcan_pch.h', '-Winvalid-pch']
        
        _extra_args = ['-O2'] + pch_flags if os.name == 'nt' else ['-O3', '-ffast-math']
        
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        unique_work_dir = foundry_path / f'temp_{module_name}'
        unique_work_dir.mkdir(parents=True, exist_ok=True)

        # 2. Injeção de Headers no Blueprint (VITAL)
        # Colocamos os diretórios na lista include_dirs do Extension
        setup_content = f"""
import os, sys
from setuptools import setup, Extension
from Cython.Build import cythonize

_include_dirs = [
    r'{foundry_path.as_posix()}',
    r'{native_dir.as_posix()}',
    r'{soteria_inc.as_posix()}',
    r'{Path(self.py_include).as_posix()}'
]

ext = Extension(
    "{module_name}",
    ["{module_name}.pyx"],
    extra_compile_args={_extra_args},
    include_dirs=_include_dirs, # <--- O COMPILADOR ACHARÁ OS HEADERS AQUI
)

setup(
    ext_modules=cythonize(ext, language_level=3, quiet=True),
    script_args=['build_ext', '--inplace', '--build-temp', r'{unique_work_dir.as_posix()}']
)
"""
        setup_path.write_text(setup_content, encoding='utf-8')

        # 3. Execução Limpa do Comando
        core_root = Path(__file__).resolve().parents[3]
        doxo_python = core_root / 'venv' / 'Scripts' / 'python.exe' if os.name == 'nt' else sys.executable
        
        build_env = build_env.copy()
        build_env['TMP'] = str(unique_work_dir)
        build_env['TEMP'] = str(unique_work_dir)
        build_env['TMPDIR'] = str(unique_work_dir)

        # O comando agora não precisa de inc_flags, o setup.py já os tem
        cmd = [str(doxo_python), setup_path.name]
        if os.name == 'nt': 
            cmd.append('--compiler=mingw32')

        try:
            # Executa com streaming para o Lazarus capturar qualquer erro
            returncode, stdout_tail, stderr_tail = self._run_command_streaming(cmd, cwd=str(foundry_path), env=build_env)
            
            if returncode != 0:
                verbose_error = self._format_verbose_build_error(module_name=module_name, cmd=cmd, returncode=returncode, stdout=stdout_tail, stderr=stderr_tail)
                return (False, verbose_error)
            
            if self._promote_binary(module_name):
                return (True, None)
            else:
                return (False, 'Falha no Promote: Binário compilado não localizado.')
        except Exception as e:
            return (False, str(e))
        finally:
            try: setup_path.unlink(missing_ok=True)
            except Exception as e:
                import logging as _dox_log
                _dox_log.error(f"[INFRA] compile: {e}")

    def _promote_to_staging(self, module_name: str) -> Path | None:
        """Move o binário compilado para o diretório de staging."""
        ext = '.pyd' if os.name == 'nt' else '.so'
        src_file = next(self.env.foundry.glob(f'{module_name}*{ext}'), None)
        if not src_file:
            return None
        dest_dir = self.env.staging
        dest_file = dest_dir / src_file.name
        import shutil
        shutil.move(str(src_file), str(dest_file))
        return dest_file

    @staticmethod
    def save_telemetry_report(project_root: str):
        """Salva o relatório de telemetria da compilação."""
        import json
        if not COMPILATION_TELEMETRY:
            return
        report_path = Path(project_root) / '.doxoade' / 'vulcan' / 'logs' / f"compile_telemetry_{time.strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        summary = {'total': len(COMPILATION_TELEMETRY), 'success': sum((1 for r in COMPILATION_TELEMETRY if r['status'] == 'OK')), 'failed': sum((1 for r in COMPILATION_TELEMETRY if r['status'] not in ['OK', 'QUARANTINED'])), 'quarantined': sum((1 for r in COMPILATION_TELEMETRY if r['status'] == 'QUARANTINED')), 'total_time': sum((r['duration'] for r in COMPILATION_TELEMETRY))}
        full_report = {'summary': summary, 'details': COMPILATION_TELEMETRY}
        report_path.write_text(json.dumps(full_report, indent=2), encoding='utf-8')
        print(Fore.CYAN + f'\n[TELEMETRY] Relatório de compilação salvo em: {report_path}')

    def _promote_binary(self, module_name: str, to_staging: bool=False) -> bool:
        """Move o binário compilado para o diretório de staging ou bin."""
        ext = '.pyd' if os.name == 'nt' else '.so'
        src_file = next(self.env.foundry.glob(f'{module_name}*{ext}'), None)
        if not src_file:
            return False
        import shutil
        try:
            dest_dir = self.env.staging if to_staging else self.env.bin_dir
            dest_file = dest_dir / src_file.name
            shutil.move(str(src_file), str(dest_file))
            return True
        except Exception:
            return False

    def compile_batch(self, modules_list):
        from Cython.Build import cythonize
        import time
        import traceback # Necessário para o detalhamento que você pediu

        # Sensor de Início
        t_batch_start = time.perf_counter()
        metrics = {}

        foundry_path = self.env.foundry.resolve()
        sources = [str(foundry_path / f"{m}.pyx") for m in modules_list]
        
        # --- FASE 1: CYTHON CORE (TRANSPILLING) ---
        t0 = time.perf_counter()
        try:
            # O Cython gera os arquivos .c a partir dos .pyx
            cythonize(sources, nthreads=2, quiet=True, 
                      compiler_directives={'language_level': "3", 'boundscheck': False})
            metrics['cython_core_ms'] = (time.perf_counter() - t0) * 1000
        except Exception as e:
            # --- DETALHAMENTO DE FALHA NA FASE 1 ---
            print(f"\n{Fore.RED}✘ [ERRO CRÍTICO CYTHON]{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Causa:{Style.RESET_ALL} {e}")
            print(f"{Style.DIM}{traceback.format_exc()}{Style.RESET_ALL}")
            return False

        # --- FASE 2: GCC LINKING (BINARY GENERATION) ---
        t1 = time.perf_counter()
        success = True
        gcc_times = []
        
        print(f"\n{Fore.CYAN}{Style.BRIGHT}📦 RELATÓRIO DE FUNDIÇÃO DO LOTE:{Style.RESET_ALL}")
        print(f"{'MÓDULO':<30} │ {'RESULTADO':<10} │ {'TEMPO'}")
        print("─" * 55)
        
        for i, m in enumerate(modules_list):
            status = f"{Fore.GREEN}OK{Fore.RESET}" if i < len(gcc_times) else f"{Fore.RED}FALHA{Fore.RESET}"
            t_str = f"{gcc_times[i]:.0f}ms" if i < len(gcc_times) else "-"
            print(f"{m:<30} │ {status:<10} │ {t_str}")

        metrics['gcc_avg_ms'] = sum(gcc_times) / len(gcc_times) if gcc_times else 0
        metrics['gcc_total_ms'] = (time.perf_counter() - t1) * 1000
        metrics['total_ms'] = (time.perf_counter() - t_batch_start) * 1000
        
        # [TELEMETRY PUSH] Registra globalmente para o relatório final
        global COMPILATION_TELEMETRY
        COMPILATION_TELEMETRY.append(metrics)
        
        # REMOVIDO: O bloco 'if result.returncode' que causava o NameError.
        # A variável 'success' já rastreia o estado da fundição.
        
        if not success:
            print(f"\n{Fore.RED}⚠ Atenção: O lote terminou com falhas parciais.{Style.RESET_ALL}")
            print(f"{Fore.CYAN}O Vulcan tentará o fallback para Tier 2 (Python Otimizado) onde o Tier 1 falhou.{Style.RESET_ALL}")

        return success
        
    def _prepare_native_objects(self):
        """Compila os kernels para arquivos objeto (.o) uma única vez."""
        #native_dir = Path(self.env.root) / "doxoade" / "tools" / "vulcan" / "native"
        native_dir = Path(__file__).resolve().parent / "native"
        obj_dir = self.env.foundry / "static_objs"
        obj_dir.mkdir(exist_ok=True)
        
        core_c = native_dir / "nexus_kernels.c"
        core_s = native_dir / "nexus_asm.s"
        
        c_obj = obj_dir / "nexus_kernels.o"
        s_obj = obj_dir / "nexus_asm.o"

        # Compila C e ASM para objeto (sem linkar)
        if not c_obj.exists():
            import subprocess
            subprocess.run(f'gcc -O3 -c "{core_c}" -o "{c_obj}"', shell=True)
        if not s_obj.exists():
            import subprocess
            subprocess.run(f'gcc -c "{core_s}" -o "{s_obj}"', shell=True)
            
        return c_obj, s_obj

    def _prepare_static_lib(self):
        """
        Fundição Suprema: Cria a biblioteca libnexus.a (Industrial).
        [PATCH v2] native_dir e soteria vêm do CORE do doxoade, NÃO do projeto.
        """
        from pathlib import Path
        # Core installation do doxoade (onde vive este compiler.py)
        core_root = Path(__file__).resolve().parent  # .../doxoade/tools/vulcan
        native_dir = core_root / "native"
        foundry_path = self.env.foundry.resolve()
        lib_file = foundry_path / "libnexus.a"

        if lib_file.exists():
            return lib_file

        # Verifica se os arquivos nativos existem
        c_src = native_dir / "nexus_kernels.c"
        s_src = native_dir / "nexus_asm.s"
        if not c_src.exists():
            raise RuntimeError(f"[STATIC LIB] Nexus kernel source não encontrado: {c_src}")
        if not s_src.exists():
            # ASM opcional: pode estar ausente em algumas máquinas (ex: ARM)
            print(f"   {Fore.YELLOW}⚠ nexus_asm.s não encontrado — compilando apenas C{Fore.RESET}")
            s_src = None

        import subprocess
        try:
            gcc_bin = _resolve_tool("gcc")
            ar_bin = _resolve_tool("ar")
        except RuntimeError as e:
            print(f"   {Fore.RED}✘ [STATIC LIB] {e}{Fore.RESET}")
            raise

        print(f"   {Fore.YELLOW}📦 Forjando Biblioteca Estática Nexus...{Fore.RESET}")

        k_obj = foundry_path / "k.o"
        cmd_c = [gcc_bin, "-O3", f"-I{native_dir}", "-c", str(c_src), "-o", str(k_obj)]
        res_c = subprocess.run(cmd_c, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res_c.returncode != 0:
            raise RuntimeError(f"nexus_kernels.c compilation failed: {res_c.stderr[:500]}")

        objects = [str(k_obj)]
        if s_src:
            a_obj = foundry_path / "a.o"
            cmd_asm = [gcc_bin, "-c", str(s_src), "-o", str(a_obj)]
            res_asm = subprocess.run(cmd_asm, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if res_asm.returncode != 0:
                raise RuntimeError(f"nexus_asm.s compilation failed: {res_asm.stderr[:500]}")
            objects.append(str(a_obj))

        cmd_ar = [ar_bin, "rcs", str(lib_file)] + objects
        res_ar = subprocess.run(cmd_ar, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res_ar.returncode != 0:
            raise RuntimeError(f"'ar rcs' failed: {res_ar.stderr[:500]}")

        return lib_file

    def _run_gcc_direct(self, module_name: str, use_soteria: bool = True) -> bool:
        """
        Executa linkagem direta via GCC com suporte a Sotéria.
        [PATCH] Janus resolve o compilador — shell=False — lista de argumentos.
        """
        import subprocess, time

        t_start = time.perf_counter()
        core_root = Path(__file__).resolve().parent
        self.soteria_include = core_root / "diagnostic" / "soteria" / "include"
        self.soteria_src_dir = core_root / "diagnostic" / "soteria" / "src"
        # 1. Localização do arquivo C gerado pelo Cython
        c_file = self.env.foundry / f"{module_name}.c"
        if getattr(self, "use_soteria", False):
            shadow_c = self.env.foundry / "shadow_pyx" / f"{module_name}.c"
            if shadow_c.exists():
                c_file = shadow_c

        sources = [str(c_file)]

        if getattr(self, "use_soteria", False):
            soteria_files = list(self.soteria_src_dir.glob("*.c"))
            sources.extend([str(f) for f in soteria_files])

        obj_file = self.env.bin_dir / f"{module_name}.pyd"
        try:
            self._prepare_static_lib()
        except RuntimeError as e:
            print(f"{Fore.RED}✘ Static lib falhou em {module_name}: {e}{Fore.RESET}")
            return False

        lib_path = (self.env.foundry / "libnexus.a").resolve()
        is_infra = any(x in module_name for x in ["compiler", "pitstop", "forge"])
        opt_level = "-Os" if is_infra else "-O2"

        # [FIX] Janus resolve o compilador
        try:
            gcc_bin = _resolve_tool("gcc")
        except RuntimeError as e:
            print(f"{Fore.RED}✘ {e}{Fore.RESET}")
            return False

        # [FIX] Argumentos como lista — sem shell=True, sem quoting manual
        cmd = [
            gcc_bin,
            opt_level,
            "-shared",
            "-g",
            f"-I{str(self.soteria_include)}",
            f"-I{str(self.env.foundry)}",
            f"-I{str(self.env.foundry / 'shadow_pyx')}",
            f"-I{self.py_include}",
            f"-L{self.py_libs}",
        ]
        cmd.extend(sources)
        cmd.extend([str(lib_path), "-o", str(obj_file)])

        # Extras por plataforma
        cmd.append(self.py_link_lib)
        if os.name == "nt":
            cmd.extend(["-ldbghelp", "-lpsapi", "-lkernel32"])
        cmd.append("-Wall")

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,  # ← was 180; increased for large modules on slow hardware
            )
            elapsed = (time.perf_counter() - t_start) * 1000
            self.detailed_telemetry.setdefault(module_name, {})["link_ms"] = elapsed

            if res.returncode != 0:
                print(f"\n{Fore.RED}✘ Falha na Linkagem Sotéria ({module_name}):{Fore.RESET}")
                print(res.stderr[-2000:])
                return False
            return True
        except subprocess.TimeoutExpired:
            print(f"{Fore.RED}✘ Timeout na linkagem de {module_name}{Fore.RESET}")
            return False
        except Exception as e:
            print(f"🚨 Erro no GCC ({module_name}): {e}")
            return False

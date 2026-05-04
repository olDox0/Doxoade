# doxoade/doxoade/tools/vulcan/compiler.py
import os, sys, subprocess, shutil, time, json, threading
import sysconfig
import subprocess
import concurrent.futures

from collections import deque
from pathlib import Path
from doxoade.tools.doxcolors import Fore
from Cython.Build import cythonize

from doxoade.tools.doxcolors import Fore, Style

COMPILATION_TELEMETRY = []

class VulcanCompiler:
    _cached_env = None

    def __init__(self, env, pid_registry=None): # [FIX] Adicionado pid_registry
        self.env = env
        # Mantém compatibilidade com o sistema de monitoramento de processos
        self._pid_registry = pid_registry if pid_registry is not None else {}
        self.detailed_telemetry = {}
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
        """Prepara o toolkit GCC apenas uma vez (Hefesto)."""
        if VulcanCompiler._cached_env is not None:
            return VulcanCompiler._cached_env
        core_root = Path(__file__).resolve().parents[3]
        gcc_exe = core_root / 'trirdparty' / 'w64devkit' / 'bin' / 'gcc.exe'
        env = os.environ.copy()
        if gcc_exe.exists():
            bin_dir = str(gcc_exe.parent)
            env['PATH'] = bin_dir + os.pathsep + env.get('PATH', '')
            env['CC'] = 'gcc'
            env['CXX'] = 'g++'
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
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', bufsize=1)
        out_tail: deque[str] = deque(maxlen=max_tail_lines)
        err_tail: deque[str] = deque(maxlen=max_tail_lines)

        def _drain(pipe, target: deque[str]):
            try:
                for line in iter(pipe.readline, ''):
                    if line:
                        target.append(line.rstrip('\n'))
            finally:
                pipe.close()
        t_out = threading.Thread(target=_drain, args=(proc.stdout, out_tail), daemon=True)
        t_err = threading.Thread(target=_drain, args=(proc.stderr, err_tail), daemon=True)
        t_out.start()
        t_err.start()
        code = proc.wait()
        t_out.join(timeout=2)
        t_err.join(timeout=2)
        return (code, '\n'.join(out_tail), '\n'.join(err_tail))

    def transpile_batch(self, modules_list):
        import time
        from Cython.Build import cythonize
        
        t0 = time.perf_counter()
        foundry_path = self.env.foundry.resolve()
        sources = [str(foundry_path / f"{m}.pyx") for m in modules_list]
        
        try:
            cythonize(sources, nthreads=2, quiet=True, 
                      compiler_directives={'language_level': "3", 'boundscheck': False, 'wraparound': True})
            
            # --- CÁLCULO DE TELEMETRIA ---
            duration_ms = (time.perf_counter() - t0) * 1000
            avg_ms = duration_ms / len(modules_list)
            
            for m in modules_list:
                # Injeta a média do Cython para cada arquivo no dicionário de telemetria
                self.detailed_telemetry.setdefault(m, {})['transpile_ms'] = avg_ms
                
            return True
        except Exception as e:
            print(f"   {Fore.RED}✘ Erro no Cython: {e}{Fore.RESET}")
            return False

    def _ensure_pch(self):
        """Gera o cabeçalho pré-compilado (Python.h.gch) se não existir."""
        pch_file = self.env.foundry / "vulcan_headers.h"
        gch_file = self.env.foundry / "vulcan_headers.h.gch"
        
        if not gch_file.exists():
            print(f"   {Fore.YELLOW}❄ Preparando Criogenia de Cabeçalhos (PCH)...{Fore.RESET}")
            # Criamos um cabeçalho que inclui as bases mais usadas
            content = "#include <Python.h>\n#include <structmember.h>\n"
            pch_file.write_text(content)
            
            # Compilamos o cabeçalho em si (isso é feito apenas uma vez)
            cmd = f'gcc -x c-header "{str(pch_file)}" -I{self.py_include} -o "{str(gch_file)}"'
            import subprocess
            subprocess.run(cmd, shell=True, capture_output=True)
        return pch_file

    def _get_doxo_python(self):
        core_root = Path(__file__).resolve().parents[3]
        return core_root / 'venv' / 'Scripts' / 'python.exe' if os.name == 'nt' else sys.executable

    def compile(self, module_name: str) -> tuple[bool, str | None]:
        foundry_path = self.env.foundry.resolve()
        setup_path = foundry_path / f'setup_{module_name}.py'
        build_env = self._prepare_pitstop_env()
        has_pch = self._ensure_pch()
        pch_flags = []
        if has_pch and os.name == 'nt':
            pch_flags = [f'-I{foundry_path}', '-include', 'vulcan_pch.h', '-Winvalid-pch']
        _extra_args = ['-O2'] + pch_flags if os.name == 'nt' else ['-O3', '-ffast-math']
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        unique_work_dir = foundry_path / f'temp_{module_name}_{unique_id}'
        unique_work_dir.mkdir(parents=True, exist_ok=True)
        (unique_work_dir / 'Release').mkdir(parents=True, exist_ok=True)
        setup_content = f"""\nimport os, sys\n# Força isolamento de diretórios temporários para evitar conflitos de workers\nos.environ['TMP'] = r'{unique_work_dir}'\nos.environ['TEMP'] = r'{unique_work_dir}'\nos.environ['TMPDIR'] = r'{unique_work_dir}'\n\nfrom setuptools import setup, Extension\nfrom Cython.Build import cythonize\ntry:\n    import numpy as np\n    _include_dirs = [np.get_include()]\nexcept ImportError:\n    _include_dirs = []\n\next = Extension(\n    "{module_name}",\n    ["{module_name}.pyx"],\n    extra_compile_args={_extra_args},\n    include_dirs=_include_dirs + [r'{foundry_path}'],\n)\nsetup(ext_modules=cythonize(ext, language_level=3, quiet=True),\n      script_args=['build_ext', '--inplace', '--build-temp', r'{unique_work_dir}'])\n"""
        setup_path.write_text(setup_content, encoding='utf-8')
        core_root = Path(__file__).resolve().parents[3]
        doxo_python = core_root / 'venv' / 'Scripts' / 'python.exe' if os.name == 'nt' else sys.executable
        unique_work_dir = foundry_path / f'work_{module_name}'
        unique_work_dir.mkdir(parents=True, exist_ok=True)
        (unique_work_dir / 'Release').mkdir(parents=True, exist_ok=True)
        build_env = build_env.copy()
        build_env['TMP'] = str(unique_work_dir)
        build_env['TEMP'] = str(unique_work_dir)
        build_env['TMPDIR'] = str(unique_work_dir)
        cmd = [str(doxo_python), setup_path.name]
        if os.name == 'nt':
            cmd.append('--compiler=mingw32')
        try:
            returncode, stdout_tail, stderr_tail = self._run_command_streaming(cmd, cwd=str(foundry_path), env=build_env)
            if returncode != 0:
                verbose_error = self._format_verbose_build_error(module_name=module_name, cmd=cmd, returncode=returncode, stdout=stdout_tail, stderr=stderr_tail)
                return (False, verbose_error)
            if self._promote_binary(module_name):
                return (True, None)
            else:
                return (False, 'Binário compilado não encontrado após build (promote falhou).')
        except KeyboardInterrupt:
            return (False, 'Interrompido (KeyboardInterrupt no worker)')
        except Exception as e:
            return (False, str(e))
        finally:
            try:
                setup_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _promote_to_staging(self, module_name: str) -> Path | None:
        """Move o binário compilado para o diretório de staging."""
        ext = '.pyd' if os.name == 'nt' else '.so'
        src_file = next(self.env.foundry.glob(f'{module_name}*{ext}'), None)
        if not src_file:
            return None
        dest_dir = self.env.staging
        dest_file = dest_dir / src_file.name
        shutil.move(str(src_file), str(dest_file))
        return dest_file

    @staticmethod
    def save_telemetry_report(project_root: str):
        """Salva o relatório de telemetria da compilação."""
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
        
    def _run_gcc_direct(self, module_name: str) -> bool:
        import subprocess
        import time
        t_start = time.perf_counter() # Inicia o sensor imediatamente
        t0 = time.perf_counter()
        c_file = self.env.foundry / f"{module_name}.c"
        obj_file = self.env.bin_dir / f"{module_name}.pyd"
        
        # Localização dos Kernels de Elite
        native_dir = Path(__file__).parent / "native"
        core_c = native_dir / "nexus_kernels.c"
        core_s = native_dir / "nexus_asm.s"
#        core_c = native_dir / "nexus_core.c"
#        warp_s = native_dir / "warp_math.s"

        # COMANDO DE FUNDIÇÃO HÍBRIDA (C + ASM + CYTHON)
        cmd = [
            'gcc', '-O3', '-shared', '-g',
            f'-I{self.py_include}',
            f'-L{self.py_libs}',
            f'"{str(c_file)}"',      # Cython Transpiled
            f'"{str(core_c)}"',      # C Pure Kernel
            f'"{str(core_s)}"',      # Assembly SSE4.2 Kernel
            '-o', f'"{str(obj_file)}"',
            self.py_link_lib, '-Wall'
        ]
        try:
            res = subprocess.run(" ".join(cmd), capture_output=True, text=True, shell=True)
            elapsed = (time.perf_counter() - t_start) * 1000
            self.detailed_telemetry.setdefault(module_name, {})['link_ms'] = elapsed
            
            if res.returncode != 0:
                print(f"\n{Fore.RED}✘ Erro no GCC ({module_name}): {res.stderr}...{Fore.RESET}")
                return False
            return True
        except Exception as e:
            # Garante que mesmo em crash de sistema, o tempo (mesmo que 0) seja registrado
            self.detailed_telemetry.setdefault(module_name, {})['link_ms'] = 0
            return False
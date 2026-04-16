# doxoade/doxoade/tools/vulcan/compiler.py
import os, sys, subprocess, shutil, time, json, threading
from collections import deque
from pathlib import Path
from doxoade.tools.doxcolors import Fore
COMPILATION_TELEMETRY = []

class VulcanCompiler:
    _cached_env = None

    def __init__(self, env, pid_registry: dict=None):
        self.env = env
        self._pid_registry: dict = pid_registry if pid_registry is not None else {}
        self._registry_key: str = ''

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

    def _ensure_pch(self):
        """Gera o Precompiled Header (.gch) para o Python.h se necessário."""
        foundry = self.env.foundry
        pch_header = foundry / 'vulcan_pch.h'
        pch_compiled = foundry / 'vulcan_pch.h.gch'
        if pch_compiled.exists():
            return True
        content = '#include <Python.h>\n#include <structmember.h>\n'
        pch_header.write_text(content)
        build_env = self._prepare_pitstop_env()
        doxo_python = self._get_doxo_python()
        cmd = ['gcc', '-x', 'c-header', str(pch_header), '-o', str(pch_compiled)]
        import sysconfig
        py_include = sysconfig.get_path('include')
        cmd += [f'-I{py_include}']
        try:
            subprocess.run(cmd, env=build_env, check=True, capture_output=True)
            return True
        except Exception:
            return False

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
        report_path = Path(project_root) / '.doxoade' / 'vulcan' / 'logs' / f'compile_telemetry_{time.strftime('%Y%m%d_%H%M%S')}.json'
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
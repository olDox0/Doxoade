# doxoade/tools/vulcan/compiler.py  (patch v6)
import os, sys, subprocess, shutil, time, json

from pathlib import Path
from doxoade.tools.doxcolors import Fore
# [DOX-UNUSED] from .artifact_manager import probe_and_promote

# Global para telemetria da sessão de compilação
COMPILATION_TELEMETRY = []

class VulcanCompiler:
    _cached_env = None  # Cache de Classe (Pitstop)

    def __init__(self, env, pid_registry: dict = None):
        self.env = env
        self._pid_registry: dict = pid_registry if pid_registry is not None else {}
        self._registry_key: str  = ""

    def _prepare_pitstop_env(self):
        """Prepara o toolkit GCC apenas uma vez (Hefesto)."""
        if VulcanCompiler._cached_env is not None:
            return VulcanCompiler._cached_env

        core_root = Path(__file__).resolve().parents[3]
        gcc_exe   = core_root / "opt" / "w64devkit" / "bin" / "gcc.exe"

        env = os.environ.copy()
        if gcc_exe.exists():
            bin_dir = str(gcc_exe.parent)
            env["PATH"]              = bin_dir + os.pathsep + env.get("PATH", "")
            env["CC"]                = "gcc"
            env["CXX"]               = "g++"
            env["DISTUTILS_USE_SDK"] = "1"
            env["PY_VULCAN_PITSTOP"] = "1"

        VulcanCompiler._cached_env = env
        return env

    @staticmethod
    def _format_verbose_build_error(module_name: str, cmd: list[str], returncode: int, stdout: str, stderr: str) -> str:
        """Gera diagnóstico verboso para falhas de compilação Cython."""

        def _tail(text: str, n: int = 25) -> str:
            lines = [ln for ln in (text or "").splitlines() if ln.strip()]
            if not lines:
                return "(vazio)"
            return "\n".join(lines[-n:])

        cmd_str = " ".join(cmd)
        return (
            f"Build failed for {module_name} (exit={returncode})\n"
            f"CMD: {cmd_str}\n"
            f"--- STDERR (tail) ---\n{_tail(stderr)}\n"
            f"--- STDOUT (tail) ---\n{_tail(stdout)}"
        )

    def compile(self, module_name: str) -> tuple[bool, str | None]:
        """
        Compila o módulo e retorna uma tupla (sucesso, erro).
        Sincronizado com a API do Autopilot v83.1+.
        """
        foundry_path = self.env.foundry.resolve()
        setup_path   = foundry_path / f"setup_{module_name}.py"
        build_env    = self._prepare_pitstop_env()

        # FIX 1: numpy era importado incondicionalmente — quebrava 100% das
        # compilações de módulos que não usam arrays (venv_up, intelligence_engine…).
        # Agora é opcional via try/except dentro do próprio setup_tmp.py.
        #
        # FIX 2: -march=native e -ffast-math causam ICE no mingw32 em algumas
        # versões do w64devkit. Substituídos por -O2 no Windows.
        _extra_args = "['-O2']" if os.name == 'nt' else "['-O3', '-ffast-math']"

        setup_content = f"""
from setuptools import setup, Extension
from Cython.Build import cythonize

try:
    import numpy as np
    _include_dirs = [np.get_include()]
except ImportError:
    _include_dirs = []

ext = Extension(
    "{module_name}",
    ["{module_name}.pyx"],
    extra_compile_args={_extra_args},
    include_dirs=_include_dirs,
)
setup(ext_modules=cythonize(ext, language_level=3, quiet=True))
"""
        setup_path.write_text(setup_content, encoding='utf-8')

        core_root   = Path(__file__).resolve().parents[3]
        doxo_python = (core_root / "venv" / "Scripts" / "python.exe"
                       if os.name == 'nt' else sys.executable)

        cmd = [str(doxo_python), setup_path.name, "build_ext", "--inplace"]
        if os.name == 'nt':
            cmd.append("--compiler=mingw32")

        try:
            res = subprocess.run(
                cmd, cwd=str(foundry_path), env=build_env,
                capture_output=True, text=True, encoding='utf-8', errors='replace'
            )

            if res.returncode != 0:
                verbose_error = self._format_verbose_build_error(
                    module_name=module_name,
                    cmd=cmd,
                    returncode=res.returncode,
                    stdout=res.stdout or "",
                    stderr=res.stderr or "",
                )
                return False, verbose_error

            if self._promote_binary(module_name):
                return True, None
            else:
                return False, "Binário compilado não encontrado após build (promote falhou)."

        except KeyboardInterrupt:
            # FIX 3: sys.exit(130) em thread worker vira SystemExit(BaseException),
            # escapa do except Exception do Autopilot e chega ao vulcan_cmd, que
            # imprime "Comando interrompido. Saindo...".
            # Retornar tupla mantém tudo dentro do fluxo do ThreadPoolExecutor.
            return False, "Interrompido (KeyboardInterrupt no worker)"
        except Exception as e:
            return False, str(e)
        finally:
            try:
                setup_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _promote_to_staging(self, module_name: str) -> Path | None:
        """Move o binário compilado para o diretório de staging."""
        ext = ".pyd" if os.name == 'nt' else ".so"
        src_file = next(self.env.foundry.glob(f"{module_name}*{ext}"), None)
        if not src_file:
            return None

        dest_dir  = self.env.staging
        dest_file = dest_dir / src_file.name
        shutil.move(str(src_file), str(dest_file))
        return dest_file

    @staticmethod
    def save_telemetry_report(project_root: str):
        """Salva o relatório de telemetria da compilação."""
        if not COMPILATION_TELEMETRY:
            return

        report_path = (Path(project_root) / ".doxoade" / "vulcan" / "logs"
                       / f"compile_telemetry_{time.strftime('%Y%m%d_%H%M%S')}.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        summary = {
            'total':       len(COMPILATION_TELEMETRY),
            'success':     sum(1 for r in COMPILATION_TELEMETRY if r['status'] == 'OK'),
            'failed':      sum(1 for r in COMPILATION_TELEMETRY if r['status'] not in ['OK', 'QUARANTINED']),
            'quarantined': sum(1 for r in COMPILATION_TELEMETRY if r['status'] == 'QUARANTINED'),
            'total_time':  sum(r['duration'] for r in COMPILATION_TELEMETRY),
        }

        full_report = {'summary': summary, 'details': COMPILATION_TELEMETRY}
        report_path.write_text(json.dumps(full_report, indent=2), encoding="utf-8")
        print(Fore.CYAN + f"\n[TELEMETRY] Relatório de compilação salvo em: {report_path}")

    def _promote_binary(self, module_name: str, to_staging: bool = False) -> bool:
        """Move o binário compilado para o diretório de staging ou bin."""
        ext      = ".pyd" if os.name == 'nt' else ".so"
        src_file = next(self.env.foundry.glob(f"{module_name}*{ext}"), None)
        if not src_file:
            return False

        try:
            dest_dir  = self.env.staging if to_staging else self.env.bin_dir
            dest_file = dest_dir / src_file.name
            shutil.move(str(src_file), str(dest_file))
            return True
        except Exception:
            return False
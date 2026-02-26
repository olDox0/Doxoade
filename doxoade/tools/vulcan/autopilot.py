# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/autopilot.py  (patch v6)
import hashlib
import os
import sys
import signal
from pathlib import Path
from doxoade.tools.doxcolors import Fore
# [DOX-UNUSED] from multiprocessing import Manager

from .environment import VulcanEnvironment
from .advisor import VulcanAdvisor
# [DOX-UNUSED] from .forge import VulcanForge
from .compiler import VulcanCompiler
from concurrent.futures import ThreadPoolExecutor
from collections import Counter


def _forge_worker(task: dict) -> dict:
    """
    Worker isolado — roda em processo separado com silo próprio.

    CTRL+C FIX:
    O worker ignora SIGINT (SIG_IGN) — não imprime ruído.
    O pai captura KeyboardInterrupt, usa _kill_registry() para matar
    os PIDs gcc/python registrados, e encerra o executor limpo.
    """
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except (OSError, ValueError):
        pass

    file_path    = task['file_path']
    foundry_str  = task['foundry']
    bin_str      = task['bin_dir']
    pid_registry = task['pid_registry']   # Manager().dict() compartilhado
    abs_path     = Path(file_path).resolve()
    prevalidated = bool(task.get('prevalidated'))

    # Pula arquivos do próprio Vulcan e alvos de alto risco para Cython.
    from .forge import VulcanForge, assess_file_for_vulcan
    if not prevalidated:
        if VulcanForge.is_self_referential(str(abs_path)):
            return {'name': abs_path.name, 'ok': False,
                    'err': 'vulcan self-file: pulado', 'skip': True}

        eligible, reason = assess_file_for_vulcan(str(abs_path))
        if not eligible:
            return {'name': abs_path.name, 'ok': False, 'err': f'pulado: {reason}', 'skip': True}

    path_hash   = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
    module_name = f"v_{abs_path.stem}_{path_hash}"

    try:
        sys.stdout.write(f"   [VULCAN:FORGE] {abs_path.name}...\n")
        sys.stdout.flush()

        forge    = VulcanForge(str(abs_path))
        pyx_code = forge.generate_source(str(abs_path))

        if not pyx_code:
            return {'name': abs_path.name, 'ok': False, 'err': 'pyx_code vazio'}

        foundry = Path(foundry_str)
        bin_dir = Path(bin_str)

        (foundry / f"{module_name}.pyx").write_text(pyx_code, encoding='utf-8')

        from .environment import VulcanEnvironment
        from .compiler    import VulcanCompiler

        env          = object.__new__(VulcanEnvironment)
        env.root     = foundry.parent.parent
        env.work_dir = foundry.parent
        env.foundry  = foundry
        env.bin_dir  = bin_dir
        env.logs     = foundry.parent / "audit.log"

        # Passa o registry para o compiler registrar o PID do Popen(gcc)
        compiler = VulcanCompiler(env, pid_registry=pid_registry)
        ok, err  = compiler.compile(module_name)
        return {'name': abs_path.name, 'ok': ok, 'err': err or None}

    except Exception as e:
        return {'name': abs_path.name, 'ok': False, 'err': str(e)[:80]}


def _kill_registry(pid_registry: dict):
    """
    Mata toda a árvore de processos gcc/python registrados.
    Chamado pelo pai imediatamente no KeyboardInterrupt.
    """
    try:
        import psutil
        for key, pid in list(pid_registry.items()):
            try:
                proc = psutil.Process(pid)
                for child in proc.children(recursive=True):
                    child.kill()
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        # Fallback sem psutil
        for key, pid in list(pid_registry.items()):
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
    finally:
        pid_registry.clear()


class VulcanAutopilot:
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.env = VulcanEnvironment(self.root)
        self.advisor = VulcanAdvisor(self.root)
        self._pid_registry: dict = {}
        self.compiler = VulcanCompiler(self.env, pid_registry=self._pid_registry)

    @staticmethod
    def _available_mem_mb() -> int | None:
        """Memória disponível em MB (best-effort)."""
        try:
            import psutil
            return int(psutil.virtual_memory().available / (1024 * 1024))
        except Exception:
            return None

    @classmethod
    def _resolve_max_workers(cls, max_workers: int | None = None) -> int:
        """Resolve número de workers com prioridade: arg > env > default."""
        if isinstance(max_workers, int) and max_workers > 0:
            return max_workers

        env_jobs = os.environ.get("DOXOADE_VULCAN_JOBS", "").strip()
        if env_jobs.isdigit() and int(env_jobs) > 0:
            return int(env_jobs)

        cpu = os.cpu_count() or 2
        tuned = max(2, min(8, cpu + 1))

        avail_mb = cls._available_mem_mb()
        if avail_mb is not None:
            if avail_mb < 3072:
                return 2
            if avail_mb < 6144:
                return min(tuned, 3)

        return tuned

    def _filter_candidates(self, candidates: list[dict], force_recompile: bool) -> list[dict]:
        from .forge import assess_file_for_vulcan

        filtered: list[dict] = []
        skip_reasons: Counter[str] = Counter()

        for c in candidates:
            file_path = c['file']
            eligible, reason = assess_file_for_vulcan(file_path)
            if not eligible:
                skip_reasons[f"heurística: {reason}"] += 1
                continue

            if not force_recompile and self.advisor._is_already_compiled(file_path):
                skip_reasons["binário já atualizado"] += 1
                continue

            c["__vulcan_validated"] = True
            filtered.append(c)

        total_skips = sum(skip_reasons.values())
        if total_skips:
            print(f"   {Fore.BLUE}↷ Pulos inteligentes: {total_skips}{Fore.RESET}")
            for reason, count in skip_reasons.most_common():
                print(f"      - {count:>2}x {reason}")

        return filtered

    @staticmethod
    def _limit_auto_candidates(candidates: list[dict]) -> tuple[list[dict], int]:
        """Aplica limite em modo automático para reduzir picos de memória/tempo."""
        raw_limit = os.environ.get("DOXOADE_VULCAN_AUTO_TARGET_CAP", "12").strip()
        limit = int(raw_limit) if raw_limit.isdigit() and int(raw_limit) > 0 else 12
        if len(candidates) <= limit:
            return candidates, 0
        return candidates[:limit], len(candidates) - limit

    def scan_and_optimize(self, candidates=None, force_recompile=False, max_workers: int | None = None):
        auto_mode = not candidates
        if auto_mode:
            print(f"{Fore.CYAN}   > Consultando telemetria...{Fore.RESET}")
            candidates = self.advisor.get_optimization_candidates(force=force_recompile)
        
        if not candidates:
            print(f"   {Fore.WHITE}Nenhum candidato para otimização.{Fore.RESET}"); return

        total_before = len(candidates)
        candidates = self._filter_candidates(candidates, force_recompile=force_recompile)
        skipped = total_before - len(candidates)

        auto_trimmed = 0
        if auto_mode and candidates:
            candidates, auto_trimmed = self._limit_auto_candidates(candidates)
            if auto_trimmed:
                print(
                    f"   {Fore.BLUE}↷ Modo automático: limitando lote para {len(candidates)} alvos "
                    f"(restantes: {auto_trimmed}){Fore.RESET}"
                )

        if not candidates:
            print(f"   {Fore.WHITE}Nenhum candidato elegível para forja (skips={skipped}).{Fore.RESET}")
            return

        print(f"   {Fore.YELLOW}Alvos para compilação: {len(candidates)} (pulos inteligentes: {skipped}){Fore.RESET}")
        # FIX: cpu_count()//2 numa máquina de 2 cores dá 1 thread (sequencial).
        # Compilação Cython é CPU+IO bound mas cada worker chama um subprocess
        # separado (gcc), então N workers = N gcc simultâneos sem GIL contention.
        # Usamos todos os cores disponíveis com mínimo de 2.
        max_workers = self._resolve_max_workers(max_workers)
        print(f"   {Fore.MAGENTA}🔥 Ativando {max_workers} threads...{Fore.RESET}")

        success_count = 0
        executor = None
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for result in executor.map(self._process_target, candidates):
                    try:
                        file_path = result['file']
                        success = result['ok']
                        error_msg = result.get('err')
                        if success:
                            success_count += 1
                            print(f"   {Fore.GREEN}✔ {Path(file_path).name:<30}{Fore.RESET}")
                        else:
                            full_err = (error_msg or "falha desconhecida").strip()
                            print(f"   {Fore.RED}✘ {Path(file_path).name:<30}{Fore.RESET}")
                            print(f"      {Fore.RED}└─ {full_err.replace(chr(10), chr(10) + '      ')}{Fore.RESET}")
                    except Exception as e:
                        import sys as exc_sys
                        import os as exc_os
                        _, exc_obj, exc_tb = exc_sys.exc_info()
                        fname = exc_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "autopilot.py"
                        line_number = exc_tb.tb_lineno
                        exc_value = '\n  >>>   '.join(str(exc_obj).split("'"))
                        print(f"\033[0m \033[1m \nFilename: {fname}   \n■ Line: {line_number} \033[31m \n■ Exception type: {e} . . .  \n■ Exception value: {exc_value} \033[0m")
                        print(f"   {Fore.RED}✘ [ERRO CRÍTICO: {e}]{Fore.RESET}")

            if success_count > 0:
                print(f"\n{Fore.GREEN}✔ {success_count} de {len(candidates)} módulos forjados e validados.{Fore.RESET}")
            else:
                print(f"\n{Fore.RED}✘ Nenhum módulo pôde ser compilado.{Fore.RESET}")
            
            self.compiler.save_telemetry_report(self.root)
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}⚠ Interrompendo... matando processos em andamento.{Fore.RESET}")
            _kill_registry(self._pid_registry)
            if executor:
                executor.shutdown(wait=False, cancel_futures=True)
            print(f"{Fore.YELLOW}[VULCAN] Forja cancelada pelo usuário.{Fore.RESET}")
            # FIX: sys.exit(130) levanta SystemExit(BaseException), que o vulcan_cmd.py
            # captura como erro recuperável, imprime "Comando interrompido. Saindo..." e
            # CONTINUA a execução. Re-raise propaga o KeyboardInterrupt naturalmente
            # até o handler do CLI sem efeitos colaterais.
            raise

        finally:
            if executor:
                executor.shutdown(wait=False)

    def _process_target(self, candidate: dict) -> dict:
        """Forja um único arquivo via _forge_worker e retorna dict de resultado."""
        file_path = candidate['file']
        result = _forge_worker({
            'file_path':    file_path,
            'foundry':      str(self.env.foundry),
            'bin_dir':      str(self.env.bin_dir),
            'pid_registry': self._pid_registry,
            'prevalidated': bool(candidate.get('__vulcan_validated')),
        })
        return {'file': file_path, 'ok': result['ok'], 'err': result.get('err')}

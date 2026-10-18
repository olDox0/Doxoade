# -*- coding: utf-8 -*-
# doxoade/tools/metalcraft/metal_engine.py
"""
Nexus Metalcraft Engine v45.2 — Sotéria Integrated Build System (Janus-Aware & C++ Support).
"""
from __future__ import annotations
import os
import subprocess
import hashlib
import json
import re
import time
import shutil
from pathlib import Path
from glob import glob
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.telemetry_tools.logger import chief_heartbeat
from .metal_toolchain import NexusToolchain
from doxoade.tools.soteria_systems.soteria_engine import SoteriaForensic


class NexusMetalEngine:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.RST = Style.RESET_ALL
        self.toolchain = NexusToolchain()
        self._scribe = None
        self.cache_path = self.root / ".doxoade" / "metalcraft" / "build_cache.json"
        self.config = self._load_config()

    @property
    def scribe(self):
        if self._scribe is None:
            from doxoade.tools.vulcan.diagnostic.soteria.scribe import SoteriaScribe
            self._scribe = SoteriaScribe()
        return self._scribe

    def _load_config(self):
        conf_path = self.root / "metalcraft.toml"
        if not conf_path.exists():
            return None

        try:
            raw_bytes = conf_path.read_bytes()
        except Exception:
            return None

        try:
            content = raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = raw_bytes.decode('cp1252')
            except Exception:
                content = raw_bytes.decode('utf-8', errors='replace')

        try:
            import tomllib
            return tomllib.loads(content)
        except ImportError:
            try:
                import toml
                return toml.loads(content)
            except Exception as e:
                print(f"   {Fore.RED}✘ Erro no metalcraft.toml: {e}{self.RST}")
                return None
        except Exception as e:
            print(f"   {Fore.RED}✘ Erro de sintaxe TOML: {e}{self.RST}")
            return None

    def _get_bundle_hash(self, sources):
        hasher = hashlib.sha256()
        for src in sorted(sources):
            if src.exists():
                hasher.update(src.read_bytes())
        return hasher.hexdigest()

    def _is_stale(self, target_name, sources, output_path):
        """Verifica se o alvo precisa ser recompilado."""
        # Se o binário não existe, DEVE compilar. Nunca pode ser Cache Hit.
        if not output_path.exists():
            return True

        cache = {}
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
            except Exception:
                return True

        return cache.get(target_name) != self._get_bundle_hash(sources)


    def _update_cache(self, target_name, sources):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache = {}
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r') as f:
                    cache = json.load(f)
            except Exception:
                pass
        cache[target_name] = self._get_bundle_hash(sources)
        with open(self.cache_path, 'w') as f:
            json.dump(cache, f, indent=2)

    def _run_static_safety_audit(self, sources):
        CRITICAL_VULNS = {
            r'\bgets\s*\(': "BLOQUEIO: gets() causa buffer overflow.",
            r'\bstrcpy\s*\(': "AVISO: strcpy() detectado. Use strncpy().",
            r'\bscanf\s*\(\s*".*%s"': "VULN: scanf() sem limite de buffer.",
            r'\bmalloc\s*\(': "ADVISORY: Verifique retorno de malloc()."
        }
        print(f"   🛡️  [SOTÉRIA] Auditando {len(sources)} fontes...")
        passed = True
        for src in sources:
            content = src.read_text(encoding='utf-8', errors='ignore')
            for pattern, msg in CRITICAL_VULNS.items():
                if re.search(pattern, content):
                    print(f"      {Fore.RED}✘ {src.name}: {msg}{self.RST}")
                    if "gets" in pattern:
                        passed = False
        return passed

    def _validate_soteria_dna(self, bin_path: Path) -> bool:
        nm = shutil.which("nm") or shutil.which("nm.exe")
        if not nm:
            return True
        try:
            res = subprocess.run([nm, str(bin_path)], capture_output=True, text=True, timeout=10)
            symbols = res.stdout
            critical = ["soteria_init", "soteria_dispatch", "soteria_dump_leaks"]
            missing = [s for s in critical if s not in symbols]
            if missing:
                print(f"      {Fore.YELLOW}⚠ Sotéria parcial. Ausentes: {', '.join(missing)}{self.RST}")
                return False
            print(f"      {Fore.GREEN}✔ Sotéria integrada: {len(critical)} símbolos validados{self.RST}")
            return True
        except Exception:
            return True

    def _get_target(self, name):
        if self.config is None:
            return None
        targets = self.config.get('targets', [])
        if not targets:
            return {
                'name': self.config['project'].get('name', 'app'),
                'output': os.path.join(
                    self.config['paths'].get('output', 'bin'),
                    self.config['project'].get('name', 'app') + (".exe" if os.name == 'nt' else "")
                )
            }
        target = next((t for t in targets if t['name'] == name), None)
        return target or targets[0]

    def _resolve_compiler(self, final_sources: list[Path]) -> str:
        """Determina o executável do compilador (gcc vs g++) respeitando TOML e Janus."""
        has_cpp = any(s.suffix.lower() in ('.cpp', '.cxx', '.cc') for s in final_sources)
        compiler_conf = self.config.get('compiler', {}) if self.config else {}

        engine_bin = compiler_conf.get('compiler_path') or compiler_conf.get('engine')
        if engine_bin and os.path.exists(str(engine_bin)):
            return str(engine_bin)

        # Fallback para o Janus
        try:
            from doxoade.tools.janus_systems import Janus
            info = Janus.get_info()
            if info:
                if has_cpp and os.name == 'nt':
                    if '-static-libstdc++' not in cmd:
                        cmd.extend(['-static-libgcc', '-static-libstdc++'])
                if has_cpp and info.gpp_path and os.path.exists(info.gpp_path):
                    return info.gpp_path
                return info.compiler_path
        except Exception:
            pass

        if self.toolchain.detect():
            return self.toolchain.compiler_path

        return "g++" if has_cpp else "gcc"

    def build(self, target=None, release=False, use_soteria=True, force=False):
        if not self.config:
            print(f"\n   {Fore.RED}✘ metalcraft.toml não localizado.{self.RST}")
            return False

        all_targets = self.config.get('targets', [])
        if not all_targets:
            all_targets = [{
                'name': self.config['project'].get('name', 'app'),
                'sources': self.config['paths'].get('sources', ['src/*.c']),
                'output': os.path.join(
                    self.config['paths'].get('output', 'bin'),
                    self.config['project'].get('name', 'app') + (".exe" if os.name == 'nt' else "")
                )
            }]

        targets_to_forge = [t for t in all_targets if t.get('name') == target] if target else all_targets
        if target and not targets_to_forge:
            print(f"   {Fore.RED}✘ Alvo '{target}' não localizado.{self.RST}")
            return False

        global_success = True

        for t_cfg in targets_to_forge:
            t_name = t_cfg.get('name', 'unnamed')
            out_file = self.root / t_cfg['output']
            print(f"\n   [*] Fundição Alvo: {Fore.CYAN}{t_name}{self.RST}")

            raw_sources = t_cfg.get('sources', [])
            final_sources = []
            for pattern in raw_sources:
                full_pattern = str(self.root / pattern)
                matches = glob(full_pattern)
                final_sources.extend([Path(m) for m in matches])

            if not final_sources:
                print(f"      {Fore.RED}✘ Nenhuma fonte para: {raw_sources}{self.RST}")
                global_success = False
                continue

            target_use_soteria = t_cfg.get('soteria', use_soteria)
            if target_use_soteria:
                if not self._run_static_safety_audit(final_sources):
                    print(f"      {Fore.RED}✘ Rejeitado pela Auditoria Sotéria.{self.RST}")
                    global_success = False
                    continue

            if not force and not self._is_stale(t_name, final_sources, out_file):
                print(f"      {Fore.GREEN}✔ Alvo sincronizado (Cache Hit).{self.RST}")
                continue

            if target_use_soteria:
                shadow_dir = self.root / ".doxoade" / "metalcraft" / "shadow" / t_name
                shadow_dir.mkdir(parents=True, exist_ok=True)
                vacinados = []
                print("      💉 Vacinando módulos...")
                for src in final_sources:
                    dest = shadow_dir / src.name
                    content = src.read_text(encoding='utf-8', errors='ignore')
                    vacinado = self.scribe.instrument_code(content, src.name)
                    dest.write_text(vacinado, encoding='utf-8')
                    vacinados.append(dest)
            else:
                print(f"      {Fore.YELLOW}⚡ [BYPASS] Sotéria desativada.{self.RST}")
                vacinados = final_sources

            # Resolução do Compilador
            compiler_bin = self._resolve_compiler(final_sources)
            has_cpp = any(s.suffix.lower() in ('.cpp', '.cxx', '.cc') for s in final_sources)

            compiler_conf = self.config.get('compiler', {})
            opt = t_cfg.get('opt', compiler_conf.get('opt', 'O2'))
            std = t_cfg.get('std', compiler_conf.get('std', 'c++17' if has_cpp else 'c11'))
            flags = t_cfg.get('flags', [])

            project_type = self.config.get('project', {}).get('type', 'executable').lower()
            is_shared = project_type in ['shared_lib', 'shared', 'library', 'dll', 'so']

            custom_cflags = compiler_conf.get('cflags', [])
            if isinstance(custom_cflags, str):
                custom_cflags = [custom_cflags]

            source_dirs = list(set(str(s.parent) for s in final_sources))
            inc_flags = [f'-I{d}' for d in source_dirs]

            # Inclusões de cabeçalho do TOML
            paths_conf = self.config.get('paths', {})
            for h in paths_conf.get('headers', []):
                h_path = self.root / h
                if h_path.exists():
                    inc_flags.append(f'-I{h_path}')

            # Verificação de Python.h
            needs_python_h = any('#include <Python.h>' in src.read_text(errors='ignore')[:500] for src in final_sources)
            python_inc_flag = []
            python_lib_flags = []
            if needs_python_h:
                import sysconfig
                py_inc = sysconfig.get_path('include')
                if py_inc:
                    python_inc_flag = [f'-I{py_inc}']
                import sys
                py_version = f"{sys.version_info.major}{sys.version_info.minor}"
                libs_dir = Path(sys.base_prefix) / 'libs'
                found_lib = next((libs_dir / f for f in (f'libpython{py_version}.dll.a', f'python{py_version}.lib', f'libpython{py_version}.a') if (libs_dir / f).exists()), None)
                if found_lib:
                    python_lib_flags = [f'-L{libs_dir}', f'-lpython{py_version}']

            soteria_srcs = []
            soteria_inc_flag = []
            if target_use_soteria:
                soteria_srcs = [str(f) for f in self.scribe.soteria_src.glob("*.c")]
                soteria_inc_flag = [f'-I{self.scribe.soteria_inc}']

            # MONTAGEM DA LISTA CMD (ESTRITAMENTE SEM ASPAS LITERAIS)
            cmd = [str(compiler_bin)]

            if is_shared or '-shared' in custom_cflags:
                cmd.append('-shared')
                custom_cflags = [f for f in custom_cflags if f != '-shared']

            cmd.append(f'-{opt}' if not opt.startswith('-') else opt)
            cmd.append('-g')
            cmd.append(f'-std={std}')
            cmd.extend(custom_cflags)

            cmd.extend(python_inc_flag)
            cmd.extend(soteria_inc_flag)
            cmd.extend(inc_flags)
            inc_local = self.root / "include"
            if inc_local.exists():
                cmd.append(f'-I{inc_local}')

            if target_use_soteria:
                soteria_h = self.scribe.soteria_inc / "soteria.h"
                if soteria_h.exists():
                    cmd.extend(['-include', str(soteria_h)])

            cmd.extend([str(v) for v in vacinados])
            cmd.extend(soteria_srcs)
            cmd.extend(flags)

            # Destino do binário
            out_file.parent.mkdir(parents=True, exist_ok=True)
            ext = ('.dll' if is_shared else '.exe') if os.name == 'nt' else ('.so' if is_shared else '')
            final_out = out_file if out_file.suffix else out_file.with_suffix(ext)

            cmd.extend(['-o', str(final_out)])
            cmd.extend(python_lib_flags)
            if os.name == 'nt':
                cmd.extend(["-ldbghelp", "-lpsapi", "-lkernel32"])

            chief_heartbeat("METAL", "LINKER_CHECK", {
                "target": t_name, "opt": opt, "soteria": target_use_soteria,
                "shared": is_shared, "compiler": compiler_bin
            })

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"      {Fore.RED}✘ Falha na compilação ({compiler_bin}):{Style.RESET_ALL}")
                # Exibe as linhas relevantes do erro completo sem truncamento cego
                stderr_text = result.stderr.strip()
                lines = stderr_text.splitlines()
                # Mostra até 30 linhas de erro para não poluir, mas sem cortar o motivo real
                for line in lines[-25:] if len(lines) > 25 else lines:
                    print(f"        {line}")
                return False

            self._update_cache(t_name, final_sources)
            print(f"      {Fore.GREEN}✔ Fundição concluída com sucesso: {final_out.name}{self.RST}")

            # fail_marker = self.cache_path.parent / f".build_failed_{t_name}"
            # if fail_marker.exists():
            #     fail_marker.unlink()

            # self._update_cache(t_name, final_sources)
            # print(f"      {Fore.GREEN}✔ Fundição concluída com sucesso: {final_out.name}{self.RST}")

        return global_success

    def run_binary(self, target_name=None, extra_args=None):
        from doxoade.rescue import activate_protocol
        if self.config is None:
            print(f"   {Fore.RED}✘ metalcraft.toml ausente.{self.RST}")
            return False
            
        target = self._get_target(target_name)
        if not target:
            print(f"   {Fore.RED}✘ Alvo não resolvido.{self.RST}")
            return False
            
        out_exe = (self.root / target['output']).resolve()
        if os.name == 'nt' and not str(out_exe).lower().endswith(".exe"): 
            out_exe = Path(str(out_exe) + ".exe")
            
        if not out_exe.exists():
            print(f"   {Fore.RED}✘ Binário {out_exe.name} não localizado.{self.RST}")
            return False
            
        print(f"   🚀 {Style.BRIGHT}Invocando: {target['name']}{self.RST}")
        print("   " + "─" * 65)
        
        full_cmd = [str(out_exe)] + (extra_args or [])
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        compiler_path = self._resolve_compiler([out_exe])
        if compiler_path and os.path.exists(compiler_path):
            c_dir = str(Path(compiler_path).parent)
            env['PATH'] = c_dir + os.pathsep + env.get('PATH', '')
            
        process = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', env=env
        )
        
        captured_output = []
        try:
            for line in process.stdout:
                captured_output.append(line)
                # Filtra ruído do Sotéria durante a execução normal para não poluir o terminal
                if any(x in line for x in ["@SOTERIA_", "TAG_", "@NEXUS_"]): 
                    continue
                clean = line.encode('ascii', 'ignore').decode('ascii').strip()
                if clean: 
                    print(f"      {clean}")
                    
            process.wait()
            print("   " + "─" * 65)
            full_log = "".join(captured_output)
            
            # ==========================================================
            # MA'AT — Soberania do Exit Code (Lógica Pragmática ProDeNov)
            # ==========================================================
            
            # 1. Detecção de Race Condition (Diagnóstico controlado)
            if "RACE_CONDITION" in full_log:
                race_count = full_log.count("RACE_CONDITION")
                print(f"\n{Fore.YELLOW}⚠️  [SENTINEL] {race_count} conflitos detectados.{self.RST}")
                activate_protocol(full_log)
                return True

            # 2. Detecção de Crash Real (Sotéria + Exit Code != 0)
            # Só aciona o pânico se houver tag de erro E o processo realmente falhou
            # 2. Detecção de Crash Real (Sotéria + Exit Code != 0)
            if process.returncode != 0 and ("@SOTERIA_BEGIN@" in full_log or "TAG_MOTIVO:" in full_log):
                print(f"\\n{Fore.RED}🔬 [SOTÉRIA] Crash nativo — análise forense automática{self.RST}")
                try:
                    forensic = SoteriaForensic()
                    dossier = forensic.process_pipe(full_log)
                    if dossier:
                        print(f"\\n{Fore.CYAN}■ CAUSA: {dossier.get('explanation', 'N/A')}{self.RST}")
                        print(f"   {Fore.CYAN}■ ARQUIVO: {dossier.get('file', 'N/A')}:{dossier.get('line', 0)}{self.RST}")
                except Exception: 
                    pass
                activate_protocol(full_log, exit_code=process.returncode)
                return False

            # 3. Detecção de Leak em Encerramento Normal (Pragmatismo ProDeNov)
            if "TAG_MOTIVO: MEMORY_LEAK_REPORT" in full_log and process.returncode == 0:
                print(f"\\n{Fore.YELLOW}⚠️  [SOTÉRIA] Sucesso, com aviso de recursos órfãos no encerramento.{self.RST}")
                print(f"   {Fore.DIM}   💡 Sem TAG_LEAK_ENTRY no log: veredito sem evidência. Investigar instrumentação Sotéria.{self.RST}")

            # 4. Tratamento de Exit Code genérico (Respeita o interruptor Lazarus)
            if process.returncode != 0:
                from doxoade.boot import load_engine_config
                cfg = load_engine_config(self.root)
                lazarus_ativo = cfg.get("lazarus", True) and os.environ.get("DOXOADE_RESCUE") != "0"
                if lazarus_ativo:
                    print(f"\n{Fore.RED}🚨 [METAL-CRASH] Exit: {process.returncode}{self.RST}")
                    activate_protocol(full_log, exit_code=process.returncode)
                else: 
                    print(f"\n{Fore.YELLOW}⚠️  Execução encerrou com código {process.returncode} (Lazarus desativado).{self.RST}")
                return False
                
            print(f"   {Fore.GREEN}✔ Execução finalizada normalmente.{self.RST}")
            return True
            
        except Exception as e:
            print(f"   {Fore.RED}✘ Falha no monitor: {e}{self.RST}")
            return False

    def ensure_targets(self, verbose: bool = False) -> dict:
        stats = {'total': 0, 'built': 0, 'skipped': 0, 'failed': 0, 'details': []}
        if not self.config:
            if verbose:
                print(f"   {Fore.YELLOW}[METALCRAFT] metalcraft.toml não encontrado.{self.RST}")
            return stats

        targets = self.config.get('targets', [])
        if not targets:
            return stats

        stats['total'] = len(targets)
        for t_cfg in targets:
            t_name = t_cfg.get('name', 'unnamed')
            out_file = self.root / t_cfg['output']
            raw_sources = t_cfg.get('sources', [])
            final_sources = []
            for pattern in raw_sources:
                matches = glob(str(self.root / pattern))
                final_sources.extend([Path(m) for m in matches])

            if not final_sources:
                stats['failed'] += 1
                stats['details'].append({'name': t_name, 'status': 'failed', 'reason': f'Fontes não encontradas: {raw_sources}'})
                continue

            if not self._is_stale(t_name, final_sources, out_file):
                stats['skipped'] += 1
                stats['details'].append({'name': t_name, 'status': 'skipped', 'reason': 'Cache hit'})
                if verbose:
                    print(f"   {Fore.GREEN}✔{self.RST} {t_name}: cache hit")
                continue

            t_start = time.perf_counter()
            target_soteria = t_cfg.get('soteria', True)
            try:
                success = self.build(target=t_name, release=False, use_soteria=target_soteria, force=False)
                elapsed = time.perf_counter() - t_start
                if success:
                    stats['built'] += 1
                    stats['details'].append({'name': t_name, 'status': 'built', 'reason': f'{elapsed:.2f}s'})
                else:
                    stats['failed'] += 1
                    stats['details'].append({'name': t_name, 'status': 'failed', 'reason': 'Build falhou'})
            except Exception as e:
                stats['failed'] += 1
                stats['details'].append({'name': t_name, 'status': 'failed', 'reason': str(e)})

        return stats

    def build_single_file(self, file_path, release=False, use_soteria=True):
        src = Path(file_path).resolve()
        if not src.exists():
            print(f"   {Fore.RED}✘ Fonte não encontrada: {file_path}{self.RST}")
            return False

        shadow_dir = self.root / ".doxoade" / "metalcraft" / "shadow_src"
        shadow_dir.mkdir(parents=True, exist_ok=True)
        shadow_file = shadow_dir / src.name

        vacinado = self.scribe.instrument_code(src.read_text(errors='ignore'), src.name)
        shadow_file.write_text(vacinado, encoding='utf-8')

        compiler_bin = self._resolve_compiler([src])
        opt = "O3" if release else "O0"
        out_exe = self.root / (src.stem + (".exe" if os.name == "nt" else ""))

        cmd = [
            str(compiler_bin), f"-{opt}", "-g",
            f'-I{self.scribe.soteria_inc}',
            str(shadow_file)
        ]
        cmd.extend([str(f) for f in self.scribe.soteria_src.glob("*.c")])
        cmd.extend(['-o', str(out_exe)])
        if os.name == 'nt':
            cmd.extend(["-ldbghelp", "-lpsapi", "-lkernel32"])

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"   ✅ [LAB-OK] Gerado: {out_exe.name}")
            return True
        else:
            print(f"   ❌ [ERRO GCC]:\n{res.stderr}")
            return False

    def deploy_embedded(self, target_path, use_soteria=True):
        target_root = Path(target_path).resolve()
        nexus_dir = target_root / ".doxoade" / "metalcraft"
        sot_dir = nexus_dir / "soteria"

        try:
            for f in [nexus_dir, sot_dir / "include", sot_dir / "src"]:
                f.mkdir(parents=True, exist_ok=True)

            core_tools = Path(__file__).resolve().parents[1]
            sot_master = core_tools / "vulcan" / "diagnostic" / "soteria"

            shutil.copy2(sot_master / "include" / "soteria.h", sot_dir / "include")
            for c_file in (sot_master / "src").glob("*.c"):
                shutil.copy2(c_file, sot_dir / "src")

            shutil.copy2(core_tools.parent / "rescue.py", nexus_dir / "rescue.py")
            shutil.copy2(core_tools / "doxcolors.py", nexus_dir / "doxcolors.py")

            target_toml = target_root / "metalcraft.toml"
            if not target_toml.exists():
                toml_cfg = {
                    'project': {'name': target_root.name, 'version': '1.0.0'},
                    'compiler': {'engine': 'gcc', 'opt': 'O2', 'shield': use_soteria},
                    'paths': {
                        'sources': ['src/*.c', 'src/core/*.c'],
                        'headers': ['include/', 'src/core/'],
                        'output': 'bin/'
                    }
                }
                with open(target_toml, 'w', encoding='utf-8') as f:
                    import toml
                    toml.dump(toml_cfg, f)

            return True
        except Exception as e:
            print(f"   [!] Falha no Transplante: {e}")
            return False

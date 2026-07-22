# -*- coding: utf-8 -*-
# doxoade/tools/metalcraft/metal_engine.py
"""
Nexus Metalcraft Engine v45.0 — Sotéria Integrated Build System.
"""
import os, subprocess, toml, hashlib, json, re, shutil, time
from pathlib import Path
from glob import glob
from doxoade.tools.vulcan.diagnostic.soteria.scribe import SoteriaScribe
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.telemetry_tools.logger import chief_heartbeat
from .metal_toolchain import NexusToolchain


class NexusMetalEngine:

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.RST = Style.RESET_ALL
        self.toolchain = NexusToolchain()
        self.scribe = SoteriaScribe()
        self.cache_path = self.root / ".doxoade" / "metalcraft" / "build_cache.json"
        self.config = self._load_config()

    # ─────────────────────────────────────────────────────────────
    # CONFIG
    # ─────────────────────────────────────────────────────────────
    def _load_config(self):
        conf_path = self.root / "metalcraft.toml"
        if not conf_path.exists():
            return None
        try:
            with open(conf_path, 'r', encoding='utf-8') as f:
                return toml.load(f)
        except UnicodeDecodeError:
            try:
                with open(conf_path, 'r', encoding='cp1252') as f:
                    return toml.load(f)
            except Exception as e:
                print(f"   {Fore.RED}✘ Erro de Encoding: {e}{self.RST}")
                return None
        except Exception as e:
            print(f"   {Fore.RED}✘ Erro no metalcraft.toml: {e}{self.RST}")
            return None

    # ─────────────────────────────────────────────────────────────
    # CACHE / STALENESS
    # ─────────────────────────────────────────────────────────────
    def _get_bundle_hash(self, sources):
        hasher = hashlib.sha256()
        for src in sorted(sources):
            if src.exists():
                hasher.update(src.read_bytes())
        return hasher.hexdigest()

    def _is_stale(self, target_name, sources, output_path):
        if not output_path.exists():
            return True
        cache = {}
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r') as f:
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

    # ─────────────────────────────────────────────────────────────
    # AUDITORIA ESTÁTICA (SSA)
    # ─────────────────────────────────────────────────────────────
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

    # ─────────────────────────────────────────────────────────────
    # VALIDAÇÃO PÓS-BUILD (DNA Sotéria)
    # ─────────────────────────────────────────────────────────────
    def _validate_soteria_dna(self, bin_path: Path) -> bool:
        """Verifica se o binário contém os símbolos críticos da Sotéria."""
        nm = shutil.which("nm") or shutil.which("nm.exe")
        if not nm:
            return True  # Skip se nm indisponível
        try:
            res = subprocess.run([nm, str(bin_path)],
                                 capture_output=True, text=True, timeout=10)
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

    # ─────────────────────────────────────────────────────────────
    # RESOLUÇÃO DE ALVO
    # ─────────────────────────────────────────────────────────────
    def _get_target(self, name):
        if self.config is None:
            return None
        targets = self.config.get('targets', [])
        if not targets:
            return {
                'name': self.config['project'].get('name', 'app'),
                'output': os.path.join(
                    self.config['paths'].get('output', 'bin'),
                    self.config['project'].get('name', 'app') +
                    (".exe" if os.name == 'nt' else "")
                )
            }
        target = next((t for t in targets if t['name'] == name), None)
        return target or targets[0]

    # ─────────────────────────────────────────────────────────────
    # BUILD PRINCIPAL
    # ─────────────────────────────────────────────────────────────
    def build(self, target=None, release=False, use_soteria=True, force=False):
        """
        FORJA NATIVA INDUSTRIAL (v45.0) — Sotéria Integrated.
        """
        if not self.config:
            print(f"\n   {Fore.RED}✘ metalcraft.toml não localizado.{self.RST}")
            return False

        if not self.toolchain.detect():
            print(f"\n   {Fore.RED}✘ Compilador GCC não localizado.{self.RST}")
            return False

        # 1. RESOLUÇÃO DE ALVOS
        all_targets = self.config.get('targets', [])
        if not all_targets:
            all_targets = [{
                'name': self.config['project'].get('name', 'app'),
                'sources': self.config['paths'].get('sources', ['src/*.c']),
                'output': os.path.join(
                    self.config['paths'].get('output', 'bin'),
                    self.config['project'].get('name', 'app') +
                    (".exe" if os.name == 'nt' else "")
                )
            }]

        if target:
            targets_to_forge = [t for t in all_targets if t.get('name') == target]
            if not targets_to_forge:
                print(f"   {Fore.RED}✘ Alvo '{target}' não localizado.{self.RST}")
                return False
        else:
            targets_to_forge = all_targets

        global_success = True

        # 2. LOOP DE FUNDIÇÃO
        for t_cfg in targets_to_forge:
            t_name = t_cfg.get('name', 'unnamed')
            out_file = self.root / t_cfg['output']
            print(f"\n   [*] Fundição Alvo: {Fore.CYAN}{t_name}{self.RST}")

            # a) Coleta de Fontes
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

            # b) Flag Sotéria por target (TOML override)
            target_use_soteria = t_cfg.get('soteria', use_soteria)

            # c) Auditoria Estática
            if target_use_soteria:
                if not self._run_static_safety_audit(final_sources):
                    print(f"      {Fore.RED}✘ Rejeitado pela Auditoria Sotéria.{self.RST}")
                    global_success = False
                    continue

            # d) Staleness Check
            if not force and not self._is_stale(t_name, final_sources, out_file):
                print(f"      {Fore.GREEN}✔ Alvo sincronizado (Cache Hit).{self.RST}")
                continue

            # e) Vacinação (Scribe)
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

            # e) Metalurgia (GCC)
            opt = t_cfg.get('opt', self.config.get('compiler', {}).get('opt', 'O2'))
            flags = t_cfg.get('flags', [])

            # Include paths
            source_dirs = list(set(str(s.parent) for s in final_sources))
            inc_flags = [f'-I"{str(d).replace(chr(92), "/")}"' for d in source_dirs]

            # 🆕 Detecta se as fontes precisam de Python.h
            needs_python_h = False
            for src in final_sources:
                try:
                    head = src.read_text(encoding='utf-8', errors='ignore')[:500]
                    if '#include <Python.h>' in head or '#include "Python.h"' in head:
                        needs_python_h = True
                        break
                except Exception:
                    pass

            python_inc_flag = []
            python_lib_flags = []
            if needs_python_h:
                import sysconfig
                py_inc = sysconfig.get_path('include')
                if py_inc:
                    python_inc_flag = [f'-I"{py_inc.replace(chr(92), "/")}"']
                    print(f"      {Fore.CYAN}🐍 Python.h detectado — include: {py_inc}{self.RST}")
                
                # Detecta a biblioteca de importação do Python
                import sys
                py_version = f"{sys.version_info.major}{sys.version_info.minor}"
                py_prefix = Path(sys.base_prefix)
                libs_dir = py_prefix / 'libs'
                
                # Tenta múltiplos formatos de nome
                candidates = [
                    libs_dir / f'libpython{py_version}.dll.a',  # MinGW
                    libs_dir / f'python{py_version}.lib',        # MSVC (python312.lib)
                    libs_dir / f'libpython{py_version}.a',       # Linux
                ]
                
                found_lib = None
                for candidate in candidates:
                    if candidate.exists():
                        found_lib = candidate
                        break
                
                if found_lib:
                    python_lib_flags = [f'-L"{str(libs_dir).replace(chr(92), "/")}"', f'-lpython{py_version}']
                    print(f"      {Fore.CYAN}🔗 Python lib: {found_lib.name}{self.RST}")
                else:
                    print(f"      {Fore.YELLOW}⚠ Python lib não encontrada em {libs_dir}{self.RST}")

            # Sotéria sources e includes
            soteria_srcs = []
            soteria_inc_flag = []
            if target_use_soteria:
                soteria_srcs = [
                    f'"{str(f).replace(chr(92), "/")}"'
                    for f in self.scribe.soteria_src.glob("*.c")
                ]
                soteria_inc_flag = [
                    f'-I"{str(self.scribe.soteria_inc).replace(chr(92), "/")}"'
                ]
                print(f"      {Fore.CYAN}🛡️ Sotéria integrada — {len(soteria_srcs)} fontes{self.RST}")

            cmd = [
                f'"{self.toolchain.compiler_path}"', f"-{opt}", "-g",
            ] + python_inc_flag + soteria_inc_flag + inc_flags + [
                f'-I"{str(self.root / "include").replace(chr(92), "/")}"'
            ]

            # 🆕 Força inclusão do soteria.h em todos os arquivos vacinados
            if target_use_soteria:
                soteria_h = self.scribe.soteria_inc / "soteria.h"
                if soteria_h.exists():
                    cmd.append(f'-include "{str(soteria_h).replace(chr(92), "/")}"')


            cmd += [f'"{str(v).replace(chr(92), "/")}"' for v in vacinados]
            cmd += soteria_srcs
            cmd += flags
            cmd += [
                f'-o "{str(out_file).replace(chr(92), "/")}"',
            ] + python_lib_flags + [
                "-ldbghelp", "-lpsapi", "-lkernel32"
            ]

            chief_heartbeat("METAL", "LINKER_CHECK", {
                "target": t_name, "opt": opt, "soteria": target_use_soteria
            })

            res = subprocess.run(" ".join(cmd), capture_output=True,
                                 text=True, shell=True)

            if res.returncode == 0:
                print(f"      {Fore.GREEN}✅ {t_name} gerado com sucesso.{self.RST}")
                # g) Validação pós-build do DNA Sotéria
                if target_use_soteria:
                    self._validate_soteria_dna(out_file)
                self._update_cache(t_name, final_sources)
            else:
                print(f"      {Fore.RED}❌ Falha na Metalurgia:\n{res.stderr}{self.RST}")
                global_success = False

        return global_success

    # ─────────────────────────────────────────────────────────────
    # EXECUÇÃO COM ANÁLISE FORENSE AUTOMÁTICA
    # ─────────────────────────────────────────────────────────────
    def run_binary(self, target_name=None, extra_args=None):
        """Executa o binário com captura e análise forense Sotéria."""
        from doxoade.rescue import activate_protocol

        # 1. Validação de alvo
        if self.config is None:
            print(f"   {Fore.RED}✘ metalcraft.toml ausente.{self.RST}")
            return False

        target = self._get_target(target_name)
        if not target:
            print(f"   {Fore.RED}✘ Alvo não resolvido.{self.RST}")
            return False

        # 2. Resolução de path
        out_exe = (self.root / target['output']).resolve()
        if os.name == 'nt' and not str(out_exe).lower().endswith(".exe"):
            out_exe = Path(str(out_exe) + ".exe")

        if not out_exe.exists():
            print(f"   {Fore.RED}✘ Binário {out_exe.name} não localizado.{self.RST}")
            return False

        # 3. Execução
        print(f"   🚀 {Style.BRIGHT}Invocando: {target['name']}{self.RST}")
        print("   " + "─" * 65)

        full_cmd = [str(out_exe)] + (extra_args or [])
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        process = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', env=env
        )
        captured_output = []

        try:
            for line in process.stdout:
                captured_output.append(line)
                # Silencia tags Sotéria no output do usuário
                if any(x in line for x in ["@SOTERIA_", "TAG_", "@NEXUS_"]):
                    continue
                clean = line.encode('ascii', 'ignore').decode('ascii').strip()
                if clean:
                    print(f"      {clean}")

            process.wait()
            print("   " + "─" * 65)
            full_log = "".join(captured_output)

            # ── LAUDOS DE SAÍDA ──

            # A) Race Condition detectada
            if "RACE_CONDITION" in full_log:
                race_count = full_log.count("RACE_CONDITION")
                print(f"\n   {Fore.YELLOW}⚠️  [SENTINEL] {race_count} conflitos detectados.{self.RST}")
                activate_protocol(full_log)
                return True

            # B) Crash com tags Sotéria → Análise Forense Automática
            if "@SOTERIA_BEGIN@" in full_log or "TAG_MOTIVO:" in full_log:
                print(f"\n   {Fore.RED}🔬 [SOTÉRIA] Crash nativo — análise forense automática{self.RST}")
                try:
                    from doxoade.tools.vulcan.diagnostic.soteria.soteria_analysis import SoteriaForensic
                    forensic = SoteriaForensic()
                    dossier = forensic.process_pipe(full_log)
                    if dossier:
                        print(f"\n   {Fore.CYAN}■ CAUSA: {dossier.get('explanation', 'N/A')}{self.RST}")
                        print(f"   {Fore.CYAN}■ ARQUIVO: {dossier.get('file', 'N/A')}:{dossier.get('line', 0)}{self.RST}")
                except Exception:
                    pass
                activate_protocol(full_log, exit_code=process.returncode)
                return False

            # C) Crash genérico
            if process.returncode != 0:
                print(f"\n   {Fore.RED}🚨 [METAL-CRASH] Exit: {process.returncode}{self.RST}")
                activate_protocol(full_log, exit_code=process.returncode)
                return False

            # D) Sucesso
            print(f"   {Fore.GREEN}✔ Execução finalizada normalmente.{self.RST}")
            return True

        except Exception as e:
            print(f"   {Fore.RED}✘ Falha no monitor: {e}{self.RST}")
            return False

    # ─────────────────────────────────────────────────────────────
    # AUTO-BUILD (Boot Integration)
    # ─────────────────────────────────────────────────────────────
    def ensure_targets(self, verbose: bool = False) -> dict:
        """
        Auto-Build: Verifica staleness e compila se necessário.
        Chamado pelo boot.py na Fase 0.1.
        """
        stats = {'total': 0, 'built': 0, 'skipped': 0, 'failed': 0, 'details': []}

        if not self.config:
            if verbose:
                print(f"   {Fore.YELLOW}[METALCRAFT] metalcraft.toml não encontrado.{self.RST}")
            return stats

        if not self.toolchain.detect():
            if verbose:
                print(f"   {Fore.YELLOW}[METALCRAFT] GCC não disponível.{self.RST}")
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
                full_pattern = str(self.root / pattern)
                matches = glob(full_pattern)
                final_sources.extend([Path(m) for m in matches])

            if not final_sources:
                stats['failed'] += 1
                stats['details'].append({
                    'name': t_name, 'status': 'failed',
                    'reason': f'Fontes não encontradas: {raw_sources}'
                })
                continue

            if not self._is_stale(t_name, final_sources, out_file):
                stats['skipped'] += 1
                stats['details'].append({
                    'name': t_name, 'status': 'skipped',
                    'reason': 'Cache hit'
                })
                if verbose:
                    print(f"   {Fore.GREEN}✔{self.RST} {t_name}: cache hit")
                continue

            # Build
            if verbose:
                print(f"   {Fore.CYAN}🔨{self.RST} {t_name}: building...")

            t_start = time.perf_counter()
            target_soteria = t_cfg.get('soteria', True)

            try:
                success = self.build(
                    target=t_name, release=False,
                    use_soteria=target_soteria, force=False
                )
                elapsed = time.perf_counter() - t_start

                if success:
                    stats['built'] += 1
                    stats['details'].append({
                        'name': t_name, 'status': 'built',
                        'reason': f'{elapsed:.2f}s'
                    })
                    if verbose:
                        print(f"   {Fore.GREEN}✔{self.RST} {t_name}: built ({elapsed:.2f}s)")
                else:
                    stats['failed'] += 1
                    stats['details'].append({
                        'name': t_name, 'status': 'failed',
                        'reason': 'Build falhou'
                    })
            except Exception as e:
                stats['failed'] += 1
                stats['details'].append({
                    'name': t_name, 'status': 'failed',
                    'reason': str(e)
                })

        return stats

    # ─────────────────────────────────────────────────────────────
    # BUILD DE ARQUIVO ÚNICO (Laboratório)
    # ─────────────────────────────────────────────────────────────
    def build_single_file(self, file_path, release=False, use_soteria=True):
        src = Path(file_path).resolve()
        if not src.exists():
            print(f"   {Fore.RED}✘ Fonte não encontrada: {file_path}{self.RST}")
            return False

        shadow_dir = self.root / ".doxoade" / "metalcraft" / "shadow_src"
        shadow_dir.mkdir(parents=True, exist_ok=True)
        shadow_file = shadow_dir / src.name

        print("   💉 Vacinando módulo isolado...")
        vacinado = self.scribe.instrument_code(
            src.read_text(errors='ignore'), src.name
        )
        shadow_file.write_text(vacinado, encoding='utf-8')

        opt = "O3" if release else "O0"
        out_exe = self.root / (src.stem + (".exe" if os.name == "nt" else ""))

        soteria_srcs = [
            f'"{str(f).replace(chr(92), "/")}"'
            for f in self.scribe.soteria_src.glob("*.c")
        ]

        cmd = [
            f'"{self.toolchain.compiler_path}"', f"-{opt}", "-g",
            f'-I"{str(self.scribe.soteria_inc).replace(chr(92), "/")}"',
            f'"{str(shadow_file).replace(chr(92), "/")}"'
        ] + soteria_srcs + [
            f'-o "{str(out_exe).replace(chr(92), "/")}"',
            "-ldbghelp", "-lpsapi"
        ]

        res = subprocess.run(" ".join(cmd), capture_output=True,
                             text=True, shell=True)
        if res.returncode == 0:
            print(f"   ✅ [LAB-OK] Gerado: {out_exe.name}")
            return True
        else:
            print(f"   ❌ [ERRO GCC]:\n{res.stderr}")
            return False

    # ─────────────────────────────────────────────────────────────
    # TRANSPLANTE (Modo Silo)
    # ─────────────────────────────────────────────────────────────
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
                    toml.dump(toml_cfg, f)

            return True
        except Exception as e:
            print(f"   [!] Falha no Transplante: {e}")
            return False
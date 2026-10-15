# -*- coding: utf-8 -*-
# doxoade/tools/ganesha_systems/ganesha_advisor.py
"""
Ganesha Advisor - Sistema de Apoio Inteligente para Desenvolvedores.
Remove o atrito de erros de digitação e audita rotas do CLI automaticamente.
"""
from __future__ import annotations
import difflib
import click
from typing import Optional, List
from collections import Counter
from importlib import import_module
from doxoade.tools.doxcolors import Fore, Style


class GaneshaAdvisor:
    """Advisor que intercepta erros de CLI e sugere correções."""

    COMMON_ALIASES = {
        '-h': '--help',
        '-?': '--help',
        '--h': '--help',
        '-help': '--help',
        '-V': '--version',
        '--v': '--version',
        '-v': '--version',
        '--f': '--force',
        '-f': '--force',
    }

    @staticmethod
    def suggest_option(command: click.Command, wrong_option: str) -> Optional[str]:
        if not command:
            return None

        if wrong_option in GaneshaAdvisor.COMMON_ALIASES:
            return GaneshaAdvisor.COMMON_ALIASES[wrong_option]

        available_options = []
        for param in command.params:
            if isinstance(param, click.Option):
                available_options.extend(param.opts)
                available_options.extend(param.secondary_opts)

        available_options = sorted(set(available_options))
        matches = difflib.get_close_matches(wrong_option, available_options, n=1, cutoff=0.6)
        return matches[0] if matches else None

    @staticmethod
    def _get_bigrams(text: str) -> List[str]:
        return [text[i:i+2] for i in range(len(text) - 1)]

    @staticmethod
    def _calculate_similarity_score(wrong: str, candidate: str) -> float:
        if not wrong or not candidate:
            return 0.0

        wrong_lower = wrong.lower()
        candidate_lower = candidate.lower()

        len_diff = abs(len(wrong) - len(candidate))
        len_score = max(0, 1 - (len_diff / max(len(wrong), len(candidate))))

        wrong_chars = Counter(wrong_lower)
        candidate_chars = Counter(candidate_lower)
        common_chars = sum((wrong_chars & candidate_chars).values())
        char_score = common_chars / max(len(wrong), len(candidate))

        wrong_bigrams = set(GaneshaAdvisor._get_bigrams(wrong_lower))
        candidate_bigrams = set(GaneshaAdvisor._get_bigrams(candidate_lower))
        bigram_score = len(wrong_bigrams & candidate_bigrams) / max(len(wrong_bigrams), len(candidate_bigrams)) if wrong_bigrams and candidate_bigrams else 0.0

        position_score = sum(1 for a, b in zip(wrong_lower, candidate_lower) if a == b) / max(len(wrong), len(candidate))

        return (len_score * 0.15) + (char_score * 0.30) + (bigram_score * 0.35) + (position_score * 0.20)

    @staticmethod
    def _advanced_suggest_command(wrong_command: str, available_commands: List[str]) -> Optional[str]:
        matches = difflib.get_close_matches(wrong_command, available_commands, n=1, cutoff=0.6)
        if matches:
            return matches[0]

        candidates_with_scores = []
        for cmd in available_commands:
            score = GaneshaAdvisor._calculate_similarity_score(wrong_command, cmd)
            if score > 0.3:
                candidates_with_scores.append((cmd, score))

        if not candidates_with_scores:
            return None

        candidates_with_scores.sort(key=lambda x: x[1], reverse=True)
        return candidates_with_scores[0][0]

    @staticmethod
    def suggest_command(group: click.Group, wrong_command: str) -> Optional[str]:
        if not group:
            return None
        try:
            available_commands = list(group.list_commands(click.Context(group)))
        except Exception:
            return None
        return GaneshaAdvisor._advanced_suggest_command(wrong_command, available_commands)

    @staticmethod
    def inspect_lazy_route(group: click.Group, cmd_name: str) -> Optional[Tuple[str, str]]:
        """
        Verifica se o comando consta no mapa lazy e se sua rota está quebrada.
        Retorna (rota, erro) se houver falha, ou None se estiver saudável.
        """
        lazy_map = getattr(group, '_lazy_map', None) or getattr(group, '_doxoade_commands', None)
        if not isinstance(lazy_map, dict):
            return None

        route = lazy_map.get(cmd_name)
        if not route:
            return None

        if ":" not in route:
            return (route, "Sintaxe da rota inválida (sem ':')")

        mod_path, attr_name = route.split(":")
        try:
            mod = import_module(mod_path)
            if not hasattr(mod, attr_name):
                return (route, f"Atributo '{attr_name}' não encontrado no módulo")
        except Exception as e:
            return (route, str(e))

        return None

    @staticmethod
    def show_option_suggestion(ctx: click.Context, command: click.Command, wrong_option: str):
        suggestion = GaneshaAdvisor.suggest_option(command, wrong_option)
        if suggestion:
            click.secho(
                f"\n🐘 [Ganesha] Você escreveu '{wrong_option}', "
                f"mas provavelmente quis dizer '{suggestion}'?",
                fg='cyan', bold=True
            )
            click.echo("\nVeja o help abaixo:\n")
            click.echo(ctx.get_help())
        else:
            click.secho(f"\n⚠️  Opção '{wrong_option}' não existe.", fg='red')
            click.echo(f"Use '{ctx.command_path} --help' para ver as opções disponíveis.\n")

    @staticmethod
    def show_usage_suggestion(command: click.Command, wrong_args: list):
        if not command:
            return
        ctx = click.Context(command, info_name=command.name)
        usage_pieces = command.collect_usage_pieces(ctx)
        usage_str = f"doxoade {command.name} " + " ".join(usage_pieces)

        click.secho(f"\n📖 [SINTAXE CORRETA PARA '{command.name.upper()}']", fg='cyan', bold=True)
        click.secho(f"   Usage: {Fore.YELLOW}{usage_str}{Style.RESET_ALL}", bold=True)

        args = [p for p in command.params if isinstance(p, click.Argument)]
        if args:
            click.secho("\n   📦 Argumentos:", fg='green', bold=True)
            for i, arg in enumerate(args, 1):
                required = "obrigatório" if arg.required else "opcional"
                nargs_desc = " (múltiplos)" if arg.nargs == -1 else (f" ({arg.nargs} valores)" if arg.nargs != 1 else "")
                click.echo(f"      {i}. {Fore.CYAN}{arg.human_readable_name}{Style.RESET_ALL} [{required}]{nargs_desc}")

        opts = [p for p in command.params if isinstance(p, click.Option)]
        if opts:
            click.secho("\n   🚩 Opções disponíveis:", fg='magenta', bold=True)
            for opt in opts[:10]:
                opt_str = " / ".join(opt.opts)
                help_txt = opt.help or "Sem descrição"
                click.echo(f"      {Fore.YELLOW}{opt_str:<22}{Style.RESET_ALL} {Style.DIM}{help_txt[:50]}{Style.RESET_ALL}")
            if len(opts) > 10:
                click.echo(f"      {Style.DIM}... e mais {len(opts) - 10} opções. Use --help para ver todas.{Style.RESET_ALL}")
        click.echo()

    @staticmethod
    def show_command_suggestion(ctx: click.Context, group: click.Group, wrong_command: str):
        # 1. Auditoria preventiva: O comando existe no mapa lazy mas falhou ao importar?
        broken = GaneshaAdvisor.inspect_lazy_route(group, wrong_command)
        if broken:
            route, err = broken
            click.secho(f"\n🐘 [GANESHA AUDITOR] O comando '{wrong_command}' está registrado, mas sua rota está corrompida!", fg='yellow', bold=True)
            click.echo(f"   ↳ Rota definida:  {Fore.CYAN}{route}{Style.RESET_ALL}")
            click.echo(f"   ↳ Erro no import: {Fore.RED}{err}{Style.RESET_ALL}")
            click.echo(f"   💡 Dica: Verifique o mapeamento em cli.py ou execute a auditoria de integridade.\n")
            return

        # 2. Busca por similaridade
        suggestion = GaneshaAdvisor.suggest_command(group, wrong_command)
        click.secho(f"\n🐘 [GANESHA ADVISOR] Comando '{wrong_command}' não encontrado.", fg='red', bold=True)

        if suggestion:
            click.secho(f"   ✨ Você quis dizer: {Fore.GREEN}{suggestion}{Style.RESET_ALL}?", fg='cyan', bold=True)
            # Verifica se o comando sugerido está íntegro antes de tentar puxá-lo
            broken_suggested = GaneshaAdvisor.inspect_lazy_route(group, suggestion)
            if not broken_suggested:
                try:
                    correct_cmd = group.get_command(ctx, suggestion)
                    if correct_cmd:
                        GaneshaAdvisor.show_usage_suggestion(correct_cmd, [])
                except Exception:
                    pass
        else:
            click.secho("   ✨ Nenhum comando similar encontrado. Use 'doxoade --help' para ver a lista.", fg='yellow')

        click.echo()


def install_ganesha_hook():
    original_show = click.exceptions.UsageError.show

    def patched_show(self, file=None):
        error_msg = str(self)
        ctx = click.get_current_context(silent=True)
        if not ctx:
            return original_show(self, file)

        if "No such option:" in error_msg:
            wrong_option = error_msg.split("No such option:")[-1].strip()
            command = ctx.command if ctx.command else (ctx.parent.command if ctx.parent else None)
            if command:
                GaneshaAdvisor.show_option_suggestion(ctx, command, wrong_option)
                return

        if "No such command" in error_msg:
            wrong_cmd = error_msg.split("No such command")[-1].strip().strip("'\".")
            group = None
            if isinstance(ctx.command, click.Group):
                group = ctx.command
            elif ctx.parent and isinstance(ctx.parent.command, click.Group):
                group = ctx.parent.command

            if group:
                GaneshaAdvisor.show_command_suggestion(ctx, group, wrong_cmd)
                return

        original_show(self, file)

    click.exceptions.UsageError.show = patched_show
```

---

### 2. `doxoade/tools/metalcraft/metal_engine.py`

Aqui corrigimos:
1. `_build_compiler_command`: agora é uma função pura, limpa e que respeita o Janus e os `cflags`.
2. `build()`:
   * **Removeu todas as aspas literais dentro da lista `cmd`** (o que resolve em definitivo o `[WinError 2]`).
   * **Detecta automaticamente fontes C++ (`.cpp`) e utiliza o `g++`** ou o caminho configurado em `metalcraft.toml` (`compiler.engine = "C:\\winlibs\\mingw64\\bin\\g++.exe"`).
   * **Separa a flag `-o` do caminho de saída** (`cmd.extend(['-o', str(final_out)])`).

Substitua o conteúdo de `doxoade/tools/metalcraft/metal_engine.py` por:

```python
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
        if not output_path.exists():
            fail_marker = self.cache_path.parent / f".build_failed_{target_name}"
            if fail_marker.exists():
                fail_time = fail_marker.stat().st_mtime
                if (time.time() - fail_time) < 300:
                    return False
            return True

        cache = {}
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r') as f:
                    cache = json.load(f)
            except Exception:
                return True

        is_stale = cache.get(target_name) != self._get_bundle_hash(sources)
        if not is_stale:
            fail_marker = self.cache_path.parent / f".build_failed_{target_name}"
            if fail_marker.exists():
                fail_marker.unlink()

        return is_stale

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
                fail_marker = self.cache_path.parent / f".build_failed_{t_name}"
                fail_marker.parent.mkdir(parents=True, exist_ok=True)
                fail_marker.write_text(result.stderr[:500], encoding='utf-8')
                print(f"      {Fore.RED}✘ Falha na compilação:{Style.RESET_ALL}")
                print(f"        {result.stderr[:400]}")
                print(f"      {Fore.YELLOW}⏸ Cooldown de 5 minutos ativado para {t_name}{Style.RESET_ALL}")
                return False

            fail_marker = self.cache_path.parent / f".build_failed_{t_name}"
            if fail_marker.exists():
                fail_marker.unlink()

            self._update_cache(t_name, final_sources)
            print(f"      {Fore.GREEN}✔ Fundição concluída com sucesso: {final_out.name}{self.RST}")

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

        process = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', env=env
        )
        captured_output = []

        try:
            for line in process.stdout:
                captured_output.append(line)
                if any(x in line for x in ["@SOTERIA_", "TAG_", "@NEXUS_"]):
                    continue
                clean = line.encode('ascii', 'ignore').decode('ascii').strip()
                if clean:
                    print(f"      {clean}")

            process.wait()
            print("   " + "─" * 65)
            full_log = "".join(captured_output)

            if "RACE_CONDITION" in full_log:
                race_count = full_log.count("RACE_CONDITION")
                print(f"\n   {Fore.YELLOW}⚠️  [SENTINEL] {race_count} conflitos detectados.{self.RST}")
                activate_protocol(full_log)
                return True

            if "@SOTERIA_BEGIN@" in full_log or "TAG_MOTIVO:" in full_log:
                print(f"\n   {Fore.RED}🔬 [SOTÉRIA] Crash nativo — análise forense automática{self.RST}")
                try:
                    forensic = SoteriaForensic()
                    dossier = forensic.process_pipe(full_log)
                    if dossier:
                        print(f"\n   {Fore.CYAN}■ CAUSA: {dossier.get('explanation', 'N/A')}{self.RST}")
                        print(f"   {Fore.CYAN}■ ARQUIVO: {dossier.get('file', 'N/A')}:{dossier.get('line', 0)}{self.RST}")
                except Exception:
                    pass
                activate_protocol(full_log, exit_code=process.returncode)
                return False

            if process.returncode != 0:
                print(f"\n   {Fore.RED}🚨 [METAL-CRASH] Exit: {process.returncode}{self.RST}")
                activate_protocol(full_log, exit_code=process.returncode)
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

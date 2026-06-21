# -*- coding: utf-8 -*-
# doxoade/doxoade/tools/metalcraft/metal_engine.py
import os, subprocess, toml, hashlib, json, re, shutil
from pathlib import Path

from doxoade.tools.vulcan.diagnostic.soteria.scribe import SoteriaScribe
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.telemetry_tools.logger import chief_heartbeat

from .metal_toolchain import NexusToolchain

class NexusMetalEngine:
    def __init__(self, root):
        #self.root = Path(root)
        self.root = Path(root).resolve()
        # [VITAL] Defina as constantes de UI ANTES de carregar a config
        self.RST = Style.RESET_ALL 
        self.toolchain = NexusToolchain()
        self.scribe = SoteriaScribe()
        self.cache_path = self.root / ".doxoade" / "metalcraft" / "build_cache.json"
        
        # Agora sim, carregamos a config
        self.config = self._load_config()

    def _load_config(self):
        conf_path = self.root / "metalcraft.toml"
        if not conf_path.exists(): return None
        try:
            with open(conf_path, 'r', encoding='utf-8') as f: return toml.load(f)
        except UnicodeDecodeError:
            try:
                with open(conf_path, 'r', encoding='cp1252') as f: return toml.load(f)
            except Exception as e:
                print(f"   {Fore.RED}✘ Erro Crítico de Encoding: {e}{self.RST}")
                return None
        except Exception as e:
            print(f"   {Fore.RED}✘ Erro ao processar metalcraft.toml: {e}{self.RST}")
            return None

    def _get_bundle_hash(self, sources):
        """Gera um hash único para o conjunto de fontes (Estado do Sistema)."""
        hasher = hashlib.sha256()
        for src in sorted(sources):
            if src.exists():
                hasher.update(src.read_bytes())
        return hasher.hexdigest()

    def _is_stale(self, target_name, sources, output_path):
        """Detecta se o binário precisa de reforja (Diferencial)."""
        if not output_path.exists(): return True
        cache = {}
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r') as f: cache = json.load(f)
            except Exception as e:
                import logging as _dox_log
                _dox_log.error(f"[INFRA] _is_stale: {e}")
                return True
        return cache.get(target_name) != self._get_bundle_hash(sources)

    def _run_static_safety_audit(self, sources):
        """🛡️ SSA: Bloqueio de funções letais (Rigor TNSE)."""
        CRITICAL_VULNS = {
            r'\bgets\s*\(': "BLOQUEIO: gets() causa buffer overflow. Use fgets().",
            r'\bstrcpy\s*\(': "AVISO: strcpy() detectado. Use strncpy().",
            r'\bscanf\s*\(\s*".*%s"': "VULN: scanf() sem limite de buffer.",
            r'\bmalloc\s*\(': "ADVISORY: Verifique se o retorno de malloc() e NULL."
        }
        print(f"   🛡️  [SOTÉRIA] Auditando {len(sources)} fontes...")
        passed = True
        for src in sources:
            content = src.read_text(encoding='utf-8', errors='ignore')
            for pattern, msg in CRITICAL_VULNS.items():
                if re.search(pattern, content):
                    print(f"      {Fore.RED}✘ {src.name}: {msg}{self.RST}")
                    if "gets" in pattern: passed = False
        return passed

        # No método build, dentro do loop de targets, onde o 'cmd' é montado:
        # Adicione suporte para flags extras vindas do TOML
        linker_flags = self.config.get('linker', {}).get('flags', [])
        libs = self.config.get('linker', {}).get('libs', ["dbghelp", "psapi", "kernel32"])
        
        # Montagem do Comando Industrial para TNSE
        cmd_parts = [
            f'"{self.toolchain.compiler_path}"', f"-{opt}", "-g", "-fopenmp" # TNSE exige OpenMP
        ] + inc_flags + [f'"{str(s).replace("\\", "/")}"' for s in final_sources]
        
        cmd_parts += ["-o", f'"{str(out_file).replace("\\", "/")}"']
        cmd_parts += [f"-l{lib}" for lib in libs]
        cmd_parts += ["-lm"] # Matemática é vital para Tensores
        cmd_parts += linker_flags

    def _update_cache(self, target_name, sources):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache = {}
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r') as f: cache = json.load(f)
            except Exception as e:
                import logging as _dox_log
                _dox_log.error(f"[INFRA] _update_cache: {e}")
        cache[target_name] = self._get_bundle_hash(sources)
        with open(self.cache_path, 'w') as f: json.dump(cache, f, indent=2)
        
    def run_binary(self, target_name=None, extra_args=None):
        """Executa o binário filtrando o ruído sistêmico da Sotéria."""
        import subprocess
        from doxoade.rescue import activate_protocol
        
        proc = subprocess.run(
            [str(out_exe)] + (extra_args or []),
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        
        if proc.stdout: print(proc.stdout)
        if proc.stderr: print(proc.stderr)
        
        if proc.returncode != 0: # SE O BINÁRIO C MORREU, O LAZARUS FAZ A AUTÓPSIA
            activate_protocol(proc.stdout + proc.stderr, exit_code=proc.returncode)
            
        # 1. VALIDAÇÃO DE MAPA (VITAL: Primeiro resolvemos o alvo)
        if self.config is None:
            print(f"   {Fore.RED}✘ ERRO: Configuração metalcraft.toml ausente.{self.RST}")
            return False

        target = self._get_target(target_name)
        if not target:
            print(f"   {Fore.RED}✘ ERRO: Não foi possível resolver o alvo de execução.{self.RST}")
            return False

        # 2. RESOLUÇÃO DE PATH (Agora que sabemos que o alvo existe)
        out_exe = (self.root / target['output']).resolve()
        
        # Auto-correção para o padrão Windows
        if os.name == 'nt' and not str(out_exe).lower().endswith(".exe"):
            out_exe = Path(str(out_exe) + ".exe")

        if not out_exe.exists():
            print(f"   {Fore.RED}✘ Erro: Binário {out_exe.name} não localizado em bin/.{self.RST}")
            return False

        # 3. PREPARAÇÃO DE AMBIENTE
        print(f"   🚀 {Style.BRIGHT}Invocando: {target['name']}{self.RST}")
        print("   " + "─" * 65)
        
        full_cmd = [str(out_exe)] + (extra_args or [])
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        # 4. EXECUÇÃO COM CAPTURA DE FLUXO
        process = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', env=env
        )
        
        captured_output = []
        try:
            for line in process.stdout:
                captured_output.append(line)
                
                # Silenciador de Tags (Privacidade do Sistema)
                if any(x in line for x in ["@SOTERIA_", "TAG_", "@NEXUS_"]):
                    continue 
                
                # Output limpo para o usuário
                clean = line.encode('ascii', 'ignore').decode('ascii').strip()
                if clean:
                    print(f"      {clean}")
            
            process.wait()
            print("   " + "─" * 65)
            full_log = "".join(captured_output)

            # --- LAUDOS DE SAÍDA ---
            if "RACE_CONDITION" in full_log:
                race_count = full_log.count("RACE_CONDITION")
                print(f"\n   {Fore.YELLOW}⚠️  [SENTINEL-REPORT] Detectadas {race_count} instâncias de conflito.{self.RST}")
                from doxoade.rescue import activate_protocol
                activate_protocol(full_log) 
                return True

            if process.returncode != 0:
                from doxoade.rescue import activate_protocol
                print(f"\n   {Fore.RED}🚨 [METAL-CRASH] Falha crítica de sistema (Exit: {process.returncode}){self.RST}")
                activate_protocol(full_log, exit_code=process.returncode)
                return False

            print(f"   {Fore.GREEN}✔ Execução finalizada normalmente.{self.RST}")
            return True

        except Exception as e:
            print(f"   {Fore.RED}✘ Falha catastrófica no monitor: {e}{self.RST}")
            return False
            
    def _get_target(self, name):
        """Busca o alvo na configuração, com trava de segurança contra NoneType."""
        if self.config is None:
            # Em vez de crashar, retorna um alvo padrão de emergência ou None
            return None

        targets = self.config.get('targets', [])
        if not targets:
            return {
                'name': self.config['project'].get('name', 'app'),
                'output': os.path.join(self.config['paths'].get('output', 'bin'), 
                         self.config['project'].get('name', 'app') + (".exe" if os.name == 'nt' else ""))
            }
        
        target = next((t for t in targets if t['name'] == name), None)
        return target or targets[0]
        
    def deploy_embedded(self, target_path, use_soteria=True):
        """Transplanta o núcleo Sotéria e Lazarus para o projeto alvo."""
        target_root = Path(target_path).resolve()
        nexus_dir = target_root / ".doxoade" / "metalcraft"
        sot_dir = nexus_dir / "soteria"
        
        try:
            for f in [nexus_dir, sot_dir / "include", sot_dir / "src"]:
                f.mkdir(parents=True, exist_ok=True)

            # Localiza fontes no Core do Doxoade
            core_tools = Path(__file__).resolve().parents[1]
            sot_master = core_tools / "vulcan" / "diagnostic" / "soteria"
            
            # 1. Transplante C
            shutil.copy2(sot_master / "include" / "soteria.h", sot_dir / "include")
            for c_file in (sot_master / "src").glob("*.c"):
                shutil.copy2(c_file, sot_dir / "src")

            # 2. Transplante de UI e Resgate (Silo)
            shutil.copy2(core_tools.parent / "rescue.py", nexus_dir / "rescue.py")
            shutil.copy2(core_tools / "doxcolors.py", nexus_dir / "doxcolors.py")

            # 3. Criação do TOML no alvo
            target_toml = target_root / "metalcraft.toml"
            if not target_toml.exists():
                toml_cfg = {
                    'project': {'name': target_root.name, 'version': '1.0.0'},
                    'compiler': {'engine': 'gcc', 'opt': 'O2', 'shield': use_soteria},
                    'paths': {'sources': ['src/*.c', 'src/core/*.c'], 'headers': ['include/', 'src/core/'], 'output': 'bin/'}
                }
                with open(target_toml, 'w', encoding='utf-8') as f:
                    toml.dump(toml_cfg, f)
            
            return True
        except Exception as e:
            print(f"   [!] Falha no Transplante: {e}")
            return False

    def build(self, target=None, release=False, use_soteria=True, force=False):
#    def build(self, target_name=None, release=False, use_soteria=True, force=False):
        """
        FORJA NATIVA INDUSTRIAL (v44.2).
        Orquestrador de Metalurgia com suporte a Alvos Seletivos e Auditoria SSA.
        """
        if not self.config:
            print(f"\n   {Fore.RED}✘ FALHA LOGÍSTICA: metalcraft.toml não localizado.{Style.RESET_ALL}")
            return False

        if not self.toolchain.detect():
            print(f"\n   {Fore.RED}✘ FALHA DE TOOLCHAIN: Compilador GCC não localizado.{Style.RESET_ALL}")
            return False

        # 1. RESOLUÇÃO DE ALVOS (Contrato vs CLI)
        all_targets = self.config.get('targets', [])
        
        if target:
            targets_to_forge = [t for t in all_targets if t.get('name') == target]
        else:
            targets_to_forge = all_targets
        
        # Fallback: Se não houver a seção [[targets]] no TOML, gera um alvo padrão
        if not all_targets:
            all_targets = [{
                'name': self.config['project'].get('name', 'app'),
                'sources': self.config['paths'].get('sources', ['src/*.c']),
                'output': os.path.join(self.config['paths'].get('output', 'bin'), 
                                     self.config['project'].get('name', 'app') + (".exe" if os.name == 'nt' else ""))
            }]

        # 2. FILTRAGEM SELETIVA (--target)
        if target:
            targets_to_forge = [t for t in all_targets if t.get('name') == target]
            if not targets_to_forge:
                print(f"   {Fore.RED}✘ Alvo '{target}' não localizado no metalcraft.toml.{Style.RESET_ALL}")
                return False
        else:
            targets_to_forge = all_targets

        global_success = True

        # 3. LOOP DE FUNDIÇÃO INDUSTRIAL
        for t_cfg in targets_to_forge:
            t_name = t_cfg.get('name', 'unnamed')
            out_file = self.root / t_cfg['output']
            
            print(f"\n   [*] Fundição Alvo: {Fore.CYAN}{t_name}{Style.RESET_ALL}")

            # a) Coleta e Resolução de Fontes (Suporte a Glob: *.c)
            from glob import glob
            raw_sources = t_cfg.get('sources', [])
            final_sources = []
            for pattern in raw_sources:
                # Resolve o path absoluto para o glob
                full_pattern = str(self.root / pattern)
                matches = glob(full_pattern)
                final_sources.extend([Path(m) for m in matches])

            if not final_sources:
                print(f"      {Fore.RED}✘ Nenhuma fonte localizada para o padrão: {raw_sources}{Style.RESET_ALL}")
                global_success = False
                continue

            # b) Auditoria Estática de Segurança (SSA)
            if not self._run_static_safety_audit(final_sources):
                print(f"      {Fore.RED}✘ Alvo rejeitado pela Auditoria de Segurança Sotéria.{Style.RESET_ALL}")
                global_success = False
                continue

            # c) Check de Staleness (Incremental Build)
            if not force and not self._is_stale(t_name, final_sources, out_file):
                print(f"      {Fore.GREEN}✔ Alvo sincronizado (Cache Hit).{Style.RESET_ALL}")
                continue

            # d) Vacinação (Scribe) - Cria arquivos na sombra para não sujar o /src
            shadow_dir = self.root / ".doxoade" / "metalcraft" / "shadow" / t_name
            shadow_dir.mkdir(parents=True, exist_ok=True)
            
            vacinados = []
            print("      💉 Vacinando módulos...")
            for src in final_sources:
                dest = shadow_dir / src.name
                content = src.read_text(encoding='utf-8', errors='ignore')
                # Injeta rastro nativo
                vacinado = self.scribe.instrument_code(content, src.name)
                dest.write_text(vacinado, encoding='utf-8')
                vacinados.append(dest)

            # e) Metalurgia (GCC)
            opt = t_cfg.get('opt', self.config['compiler'].get('opt', 'O2'))
            flags = t_cfg.get('flags', [])
            
            # Coleta fontes da Sotéria para linkagem
            soteria_srcs = [f'"{str(f).replace("\\","/")}"' for f in self.scribe.soteria_src.glob("*.c")]
            
            cmd = [
                f'"{self.toolchain.compiler_path}"', f"-{opt}", "-g",
                f'-I"{str(self.scribe.soteria_inc).replace("\\","/")}"',
                f'-I"{str(self.root / "include").replace("\\","/")}"'
            ] 
            
            # Adiciona as fontes vacinadas
            cmd += [f'"{str(v).replace("\\","/")}"' for v in vacinados]
            # Adiciona o núcleo Sotéria
            cmd += soteria_srcs
            # Flags e Output
            cmd += flags
            cmd += [
                f'-o "{str(out_file).replace("\\","/")}"',
                "-ldbghelp", "-lpsapi", "-lkernel32"
            ]

            # Telemetria de Linkagem
            chief_heartbeat("METAL", "LINKER_CHECK", {
                "target": t_name, "opt": opt, "libs": ["dbghelp", "psapi"]
            })

            res = subprocess.run(" ".join(cmd), capture_output=True, text=True, shell=True)
            
            if res.returncode == 0:
                print(f"      {Fore.GREEN}✅ {t_name} gerado com sucesso.{Style.RESET_ALL}")
                self._update_cache(t_name, final_sources)
            else:
                print(f"      {Fore.RED}❌ Falha na Metalurgia:\n{res.stderr}{Style.RESET_ALL}")
                global_success = False

        return global_success

    def build_single_file(self, file_path, release=False, use_soteria=True):
        """Build de emergência para arquivos de laboratório."""
        src = Path(file_path).resolve()
        if not src.exists():
            print(f"   {Fore.RED}✘ Fonte não encontrada: {file_path}{self.RST}")
            return False

        # 1. Caminhos de Infraestrutura
        shadow_dir = self.root / ".doxoade" / "metalcraft" / "shadow_src"
        shadow_dir.mkdir(parents=True, exist_ok=True)
        shadow_file = shadow_dir / src.name
        
        # 2. Vacinação Sotéria (Hórus Scribe)
        print("   💉 Vacinando módulo isolado...")
        vacinado = self.scribe.instrument_code(src.read_text(errors='ignore'), src.name)
        shadow_file.write_text(vacinado, encoding='utf-8')

        # 3. Preparação da Linkagem
        opt = "O3" if release else "O0"
        out_exe = self.root / (src.stem + (".exe" if os.name == "nt" else ""))
        
        # Localiza arquivos objeto da Sotéria no core do Doxoade
        soteria_srcs = [f'"{str(f).replace("\\","/")}"' for f in self.scribe.soteria_src.glob("*.c")]
        
        # 4. Ordem de Metalurgia GCC
        cmd = [
            f'"{self.toolchain.compiler_path}"', f"-{opt}", "-g",
            f'-I"{str(self.scribe.soteria_inc).replace("\\","/")}"',
            f'"{str(shadow_file).replace("\\","/")}"'
        ] + soteria_srcs + [
            f'-o "{str(out_exe).replace("\\","/")}"',
            "-ldbghelp", "-lpsapi"
        ]

        res = subprocess.run(" ".join(cmd), capture_output=True, text=True, shell=True)
        if res.returncode == 0:
            print(f"   ✅ [LAB-OK] Gerado: {out_exe.name}")
            return True
        else:
            print(f"   ❌ [ERRO GCC]:\n{res.stderr}")
            return False
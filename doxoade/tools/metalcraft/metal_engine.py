# -*- coding: utf-8 -*-
# doxoade/doxoade/tools/metalcraft/metal_engine.py
import os, subprocess, toml, hashlib, json, re, shutil
from pathlib import Path
from doxoade.tools.vulcan.diagnostic.soteria.scribe import SoteriaScribe
from doxoade.tools.doxcolors import Fore, Style
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
            except: return True
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

    def build(self, release=False, use_soteria=True, force=False):
        """
        FORJA NATIVA INDUSTRIAL (v44.1).
        Agora com suporte total a múltiplos argumentos e segurança SSA.
        """
        if not self.config:
            # Se não houver TOML, criamos uma config padrão em memória
            print(f"\n   {Fore.RED}✘ FALHA LOGÍSTICA: metalcraft.toml não localizado em:{Style.RESET_ALL}")
            print(f"     > {self.root}")
            print(f"     {Fore.CYAN}DICA: Rode 'doxoade metal init' para gerar o blueprint.{Style.RESET_ALL}")
            return False

        if not self.toolchain.detect():
            print(f"\n   {Fore.RED}✘ FALHA DE TOOLCHAIN: Compilador GCC não localizado.{Style.RESET_ALL}")
            print(f"     > Verifique se o w64devkit está na pasta 'thirdparty' ou no PATH.")
            return False

        # --- LÓGICA DE MULTI-TARGETS ---
        targets = self.config.get('targets')
        if not targets:
            targets = [{
                'name': self.config['project'].get('name', 'app'),
                'sources': self.config['paths'].get('sources', ['src/*.c']),
                'output': os.path.join(self.config['paths'].get('output', 'bin'), 
                                     self.config['project'].get('name', 'app') + (".exe" if os.name == 'nt' else ""))
            }]

        tools_dir = Path(__file__).resolve().parents[1]
        global_success = True

        for target in targets:
            t_name = target.get('name', 'unnamed') # t_name = target['name']
            out_file = self.root / target['output']
            
            # 1. Coleta Fontes (Variável Local: src_files)
            src_files = []
            for pat in target['sources']:
                src_files.extend(list(self.root.glob(pat)))
            
            if not src_files:
                print(f"\n   {Fore.YELLOW}⚠️  ALVO [{t_name}]: Nenhum arquivo .c encontrado!{Style.RESET_ALL}")
                print(f"      Padrões buscados: {target.get('sources')}")
                print(f"      CWD: {os.getcwd()}")
                global_success = False
                continue

            print(f"\n   [*] Fundição Alvo: {Fore.CYAN}{t_name}{self.RST}")

            # 2. SSA: Sotéria Static Audit (Bloqueio de Segurança)
            if not self._run_static_safety_audit(src_files):
                print(f"      {Fore.RED}🛑 COMPILAÇÃO PARALISADA POR RISCO DE SEGURANÇA.{self.RST}")
                global_success = False
                continue

            # 3. Check de Cache (Diferencial)
            if not force and not self._is_stale(t_name, src_files, out_file):
                print(f"      {Fore.GREEN}✔ Alvo sincronizado (Cache Hit).{self.RST}")
                continue

            # 4. Preparação e Vacinação
            shadow_dir = self.root / ".doxoade" / "metalcraft" / "shadow" / t_name
            shadow_dir.mkdir(parents=True, exist_ok=True)
            
            final_sources = []
            shield_active = use_soteria and self.config['compiler'].get('shield', True)
            
            if shield_active:
                print(f"      💉 Injetando rastro Sotéria em {len(src_files)} módulos...")
                for src in src_files:
                    dst = shadow_dir / src.name
                    # Vacinação Hórus Scribe
                    vacinado = self.scribe.instrument_code(src.read_text(errors='ignore'), src.name)
                    dst.write_text(vacinado, encoding='utf-8')
                    final_sources.append(dst)
                
                # Injeta os núcleos .c da Sotéria
                sot_src = tools_dir / "vulcan" / "diagnostic" / "soteria" / "src"
                if sot_src.exists():
                    final_sources.extend(list(sot_src.glob("*.c")))
            else:
                final_sources = src_files

            # 5. Linkagem e Forja Final (GCC)
            opt = "O3" if release else self.config['compiler'].get('opt', 'O2')
            
            # Normalização de includes
            inc_flags = [f'-I"{str(self.root / d).replace("\\", "/")}"' for d in self.config['paths']['headers']]
            if shield_active:
                sot_inc = (tools_dir / "vulcan" / "diagnostic" / "soteria" / "include").resolve()
                local_inc = (self.root / ".doxoade" / "metalcraft" / "soteria" / "include").resolve()
                if local_inc.exists():
                    inc_flags.append(f'-I"{str(local_inc).replace("\\", "/")}"')
                else:
                    inc_flags.append(f'-I"{str(sot_inc).replace("\\", "/")}"')

            # Montagem do comando industrial
            cmd_parts = [
                f'"{self.toolchain.compiler_path}"', 
                f"-{opt}", "-g", "-fopenmp", 
                "-fno-omit-frame-pointer", "-fstack-protector-strong"
            ] + inc_flags
            
            cmd_parts += [f'"{str(s).replace("\\", "/")}"' for s in final_sources]
            cmd_parts += ["-o", f'"{str(out_file).replace("\\", "/")}"', "-ldbghelp", "-lpsapi", "-Wall"]

            print(f"      🔨 Fundindo {len(src_files)} módulos...")
            
            out_file.parent.mkdir(parents=True, exist_ok=True)
            res = subprocess.run(" ".join(cmd_parts), shell=True, capture_output=True, text=True)

            if res.returncode == 0:
                print(f"      {Fore.GREEN}✅ {t_name} gerado com sucesso.{self.RST}")
                self._update_cache(t_name, src_files)
            else:
                print(f"      {Fore.RED}❌ FALHA NA FUNDIÇÃO DE {t_name.upper()}{self.RST}")
                
                # [OURO] Formatador de Erros Hefesto
                err_lines = res.stderr.splitlines()
                for line in err_lines:
                    if "error:" in line.lower():
                        print(f"      {Fore.RED}● {line.strip()}{self.RST}")
                    elif "undefined reference" in line.lower():
                        func_name = re.findall(r"`(.*?)'", line)
                        print(f"      {Fore.YELLOW}⚓ LINK-MISS: Função '{func_name[0] if func_name else '?'}' sem implementação.{self.RST}")
                    elif "warning:" in line.lower():
                        print(f"      {Style.DIM}⚠ {line.strip()}{self.RST}")
                
                global_success = False
        
        return global_success

    def _update_cache(self, target_name, sources):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache = {}
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r') as f: cache = json.load(f)
            except: pass
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
        print(f"   " + "─" * 65)
        
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
            print(f"   " + "─" * 65)
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

    def build(self, release=False, use_soteria=True, force=False):
        """FORJA NATIVA INDUSTRIAL v45.0 - Optimized for TNSE."""
        if not self.config:
            print(f"\n   {Fore.RED}✘ ERRO DE COORDENADAS: metalcraft.toml não encontrado!{self.RST}")
            print(f"     Diretório Atual: {os.getcwd()}")
            print(f"     {Fore.CYAN}DICA: Rode 'doxoade metal init' ou entre na pasta do projeto C.{self.RST}")
            return False
        if not self.toolchain.detect(): return False

        targets = self.config.get('targets')
        if not targets:
            targets = [{
                'name': self.config['project'].get('name', 'app'),
                'sources': self.config['paths'].get('sources', ['src/*.c']),
                'output': os.path.join(self.config['paths'].get('output', 'bin'), 
                         self.config['project'].get('name', 'app') + (".exe" if os.name == 'nt' else ""))
            }]

        global_success = True
        tools_dir = Path(__file__).resolve().parents[1]

        for target in targets:
            t_name = target['name']
            out_file = self.root / target['output']
            src_files = []
            for pat in target['sources']:
                src_files.extend(list(self.root.glob(pat)))
            
            if not src_files: continue
            print(f"\n   [*] Fundição Alvo: {Fore.CYAN}{t_name}{self.RST}")

            if not self._run_static_safety_audit(src_files):
                print(f"      {Fore.RED}🛑 COMPILAÇÃO PARALISADA POR RISCO.{self.RST}")
                global_success = False; continue

            if not force and not self._is_stale(t_name, src_files, out_file):
                print(f"      {Fore.GREEN}✔ Alvo sincronizado (Cache Hit).{self.RST}")
                continue

            # --- SETUP DE DEFESA ---
            shield_active = use_soteria and self.config['compiler'].get('shield', True)
            final_sources = []
            sot_inc_path = None

            if shield_active:
                local_sot_src = self.root / ".doxoade" / "metalcraft" / "soteria" / "src"
                if local_sot_src.exists():
                    sot_src = local_sot_src
                    sot_inc_path = self.root / ".doxoade" / "metalcraft" / "soteria" / "include"
                else:
                    sot_src = tools_dir / "vulcan" / "diagnostic" / "soteria" / "src"
                    sot_inc_path = tools_dir / "vulcan" / "diagnostic" / "soteria" / "include"

                shadow_dir = self.root / ".doxoade" / "metalcraft" / "shadow" / t_name
                shadow_dir.mkdir(parents=True, exist_ok=True)
                print(f"      💉 Vacinando módulos...")
                for src in src_files:
                    dst = shadow_dir / src.name
                    vacinado = self.scribe.instrument_code(src.read_text(errors='ignore'), src.name)
                    dst.write_text(vacinado, encoding='utf-8')
                    final_sources.append(dst)
                final_sources.extend(list(sot_src.glob("*.c")))
            else:
                final_sources = src_files

            # --- MONTAGEM DO COMANDO GCC (TNSE SPEC) ---
            opt = "O3" if release else self.config['compiler'].get('opt', 'O2')
            inc_flags = [f'-I"{str(self.root / d).replace("\\", "/")}"' for d in self.config['paths']['headers']]
            if sot_inc_path:
                inc_flags.append(f'-I"{str(sot_inc_path).replace("\\", "/")}"')

            # Bibliotecas e Flags do TNSE
            libs = self.config.get('linker', {}).get('libs', ["dbghelp", "psapi", "kernel32", "gomp"])
            l_flags = self.config.get('linker', {}).get('flags', ["-static"])

            cmd = [
                f'"{self.toolchain.compiler_path}"', f"-{opt}", "-g", "-fopenmp"
            ] + inc_flags
            cmd += [f'"{str(s).replace("\\", "/")}"' for s in final_sources]
            cmd += ["-o", f'"{str(out_file).replace("\\", "/")}"']
            cmd += [f"-l{lib}" for lib in libs]
            cmd += ["-lm"] # Lib Math sempre inclusa
            cmd += l_flags

            out_file.parent.mkdir(parents=True, exist_ok=True)
            print(f"      🔨 Fundindo {len(src_files)} módulos...")
            res = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)

            if res.returncode == 0:
                print(f"      {Fore.GREEN}✅ {t_name} gerado com sucesso.{self.RST}")
                self._update_cache(t_name, src_files)
            else:
                print(f"      {Fore.RED}❌ Erro no GCC para {t_name}:{self.RST}\n{res.stderr}")
                global_success = False
        
        return global_success
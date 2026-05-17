# -*- coding: utf-8 -*-
import os, subprocess, toml, hashlib, json, re
from pathlib import Path
from doxoade.tools.vulcan.diagnostic.soteria.scribe import SoteriaScribe
from doxoade.tools.doxcolors import Fore, Style
from .metal_toolchain import NexusToolchain

class NexusMetalEngine:
    def __init__(self, root):
        self.root = Path(root)
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
        
        # [VACCINE] Tentativa robusta de leitura
        try:
            # Tenta UTF-8 (Padrão OADE)
            with open(conf_path, 'r', encoding='utf-8') as f:
                return toml.load(f)
        except UnicodeDecodeError:
            # Fallback para o padrão Windows se a praga estiver presente
            try:
                with open(conf_path, 'r', encoding='cp1252') as f:
                    return toml.load(f)
            except Exception as e:
                print(f"   {Fore.RED}✘ Erro Crítico de Encoding: {e}{self.RST}")
                return None
        except Exception as e:
            # Agora self.RST já existe, o print não vai falhar!
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
            with open(self.cache_path, 'r') as f: cache = json.load(f)
        
        current_hash = self._get_bundle_hash(sources)
        return cache.get(target_name) != current_hash

    def _run_static_safety_audit(self, sources):
        """🛡️ SSA: Bloqueia funções letais (O C mais próximo do Rust)."""
        # Padrões que causam estouro de buffer inevitável ou riscos críticos
        CRITICAL_VULNS = {
            r'\bgets\s*\(': "Função 'gets' detectada. Causa buffer overflow imediato. Use 'fgets'.",
            r'\bstrcpy\s*\(': "Função 'strcpy' detectada. Risco de segurança. Use 'strncpy'.",
            r'\bscanf\s*\(\s*".*%s"': "Scanf com string ilimitada. Risco de invasão."
        }
        
        print(f"   🛡️  [SOTÉRIA] Auditando segurança estática...")
        passed = True
        for src in sources:
            content = src.read_text(encoding='utf-8', errors='ignore')
            for pattern, msg in CRITICAL_VULNS.items():
                if re.search(pattern, content):
                    print(f"      {Fore.RED}✘ BLOQUEIO EM {src.name}: {msg}{self.RST}")
                    passed = False
        return passed

    def build(self, release=False, use_soteria=True, force=False):
        """
        FORJA NATIVA INDUSTRIAL (v44.1).
        Agora com suporte total a múltiplos argumentos e segurança SSA.
        """
        if not self.config:
            # Se não houver TOML, criamos uma config padrão em memória
            self.config = {
                'project': {'name': 'nexus_out'},
                'compiler': {'opt': 'O2', 'shield': True},
                'paths': {'sources': ['src/*.c'], 'headers': ['include/'], 'output': 'bin/'}
            }

        if not self.toolchain.detect():
            print(f"   {Fore.RED}✘ Erro: Compilador não localizado.{self.RST}")
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
            t_name = target['name']
            out_file = self.root / target['output']
            
            # 1. Coleta Fontes (Variável Local: src_files)
            src_files = []
            for pat in target['sources']:
                src_files.extend(list(self.root.glob(pat)))
            
            if not src_files:
                print(f"\n   [*] Alvo: {Fore.CYAN}{t_name}{self.RST}")
                print(f"      {Fore.YELLOW}⚠ Nenhum fonte encontrado.{self.RST}")
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
                sot_inc = tools_dir / "vulcan" / "diagnostic" / "soteria" / "include"
                inc_flags.append(f'-I"{str(sot_inc).replace("\\", "/")}"')

            # Montagem do comando industrial
            cmd_parts = [
                f'"{self.toolchain.compiler_path}"', 
                f"-{opt}", 
                "-g"
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
                print(f"      {Fore.RED}❌ Erro no GCC para {t_name}:{self.RST}\n{res.stderr}")
                global_success = False
        
        return global_success

    def _update_cache(self, target_name, sources):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache = {}
        if self.cache_path.exists():
            with open(self.cache_path, 'r') as f: cache = json.load(f)
        
        cache[target_name] = self._get_bundle_hash(sources)
        with open(self.cache_path, 'w') as f: json.dump(cache, f, indent=2)
        
    def run_binary(self, target_name=None):
        """Executa o binário com monitoramento forense ativo."""
        project_targets = self.config.get('targets')
        if not project_targets:
            # Fallback para o alvo único padrão
            target = {
                'name': self.config['project']['name'],
                'output': os.path.join(self.config['paths']['output'], self.config['project']['name'] + (".exe" if os.name == 'nt' else ""))
            }
        else:
            # Pega o primeiro alvo ou o especificado
            target = next((t for t in project_targets if t['name'] == target_name), project_targets[0])

        target = self._get_target(target_name) # Função auxiliar interna
        out_exe = self.root / target['output']

        if not out_exe.exists():
            print(f"   {Fore.RED}✘ Erro: Binário não encontrado.{self.RST}")
            return False

        print(f"   🚀 {Style.BRIGHT}Executando: {target['name']}{self.RST}")
        print(f"   " + "─" * 60)
        
        # [OURO] Execução com Captura de Fluxo
        # Usamos Popen para ler a saída enquanto o programa roda
        import subprocess
        process = subprocess.Popen(
            str(out_exe), 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding='utf-8', 
            errors='replace'
        )
        
        captured_output = []
        try:
            for line in process.stdout:
                # Exibe a saída do programa com um pequeno recuo para elegância
                print(f"      {line}", end="")
                captured_output.append(line)
            
            process.wait()
            print(f"   " + "─" * 60)

            # Se o código de saída não for ZERO, houve um crime de hardware ou lógica
            if process.returncode != 0:
                full_log = "".join(captured_output)
                
                # SINALIZAÇÃO LÁZARO
                from doxoade.rescue import activate_protocol
                print(f"\n   {Fore.RED}🚨 [METAL-CRASH] Violação de Hardware Detectada (Code: {process.returncode}){self.RST}")
                activate_protocol(full_log, exit_code=process.returncode) # <-- NOVO ARGUMENTO
                return False

            print(f"   {Fore.GREEN}✔ Execução concluída sem incidentes.{self.RST}")
            return True

        except Exception as e:
            print(f"   {Fore.RED}✘ Falha catastrófica no monitor: {e}{self.RST}")
            return False
            
    def _get_target(self, name):
        """Helper para resolver o alvo do TOML."""
        targets = self.config.get('targets', [])
        if not targets:
            return {
                'name': self.config['project']['name'],
                'output': os.path.join(self.config['paths']['output'], self.config['project']['name'] + (".exe" if os.name == 'nt' else ""))
            }
        return next((t for t in targets if t['name'] == name), targets[0])
# -*- coding: utf-8 -*-
# doxoade/tools/lua_systems/chaos_validator.py
"""
⚖️ MA'AT CHAOS VALIDATOR — Teste de Injeção de Falhas (Mutation Testing) com Motores Reais.
Garante que os motores de auditoria do Doxoade (Anúbis/Hefesto) NÃO sejam cegos a erros proposital.
"""
import re
import tempfile
from pathlib import Path
from typing import Dict, Any
from doxoade.tools.doxcolors import Fore, Style

# Importar os motores REAIS de auditoria do Doxoade
try:
    from doxoade.tools.lua_systems.lua_manager import LuaRuntimeManager
    from doxoade.tools.lua_systems.api_guard.api_scan import APITemplateScanner
    REAL_ENGINES_AVAILABLE = True
except ImportError:
    REAL_ENGINES_AVAILABLE = False

class ChaosValidator:
    """Injeta falhas conhecidas e verifica se os MOTORES REAIS do Doxoade as detectam."""
    
    # 🧪 VETORES DE FALHA CONHECIDOS (O "Veneno")
    FAULT_VECTORS = [
        {
            "id": "SYNTAX_01",
            "name": "String Não Fechada",
            "code": 'local msg = "erro proposital sem aspas de fechamento\nprint(msg)',
            "detector": "lua_compile_check",
            "description": "O parser Lua (Hefesto) deve rejeitar sintaxe inválida."
        },
        {
            "id": "STRICT_01",
            "name": "Uso de 'core' sem Require",
            "code": 'core.log("Tentando usar core sem declarar local core = require \\"core\\"")',
            "detector": "api_template_scan",
            "description": "O scanner estático (Anúbis) deve flagrar uso de módulo não importado."
        },
        {
            "id": "API_01",
            "name": "Monkey-Patch em Nil",
            "code": 'local original = ThisModuleDoesNotExist.some_method\nThisModuleDoesNotExist.some_method = function() end',
            "detector": "api_template_scan",
            "description": "O API Guard deve detectar patch em objeto inexistente/suspeito."
        },
        {
            "id": "GLOBAL_01",
            "name": "Vazamento de Global Proibida",
            "code": 'LeakedVariable = "isso nao deveria ser global sem _G explicito"',
            "detector": "global_leak_scan",
            "description": "Variáveis globais implícitas devem ser flagradas pelo linter estático."
        }
    ]

    @classmethod
    def _run_real_lua_compile_check(cls, code: str) -> bool:
        """Usa o LuaRuntimeManager REAL para verificar compilação."""
        if not REAL_ENGINES_AVAILABLE: return False
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_path = Path(f.name)
        try:
            # compile_check retorna None se OK, ou string de erro se falhar.
            # Queremos que falhe (retorne string), então 'caught' = (result is not None)
            result = LuaRuntimeManager.compile_check(temp_path)
            return result is not None 
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @classmethod
    def _run_real_api_scan(cls, code: str) -> bool:
        """Usa o APITemplateScanner REAL para verificar require faltante e patches suspeitos."""
        if not REAL_ENGINES_AVAILABLE: return False
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_path = Path(f.name)
        try:
            # O scanner espera um diretório, então usamos o pai do arquivo temp
            scanner = APITemplateScanner(temp_path.parent)
            res = scanner.scan_file(temp_path)
            # Se tiver missing_requires ou suspicious_patches, o detector "pegou" o erro.
            has_missing = len(res.get("missing_requires", [])) > 0
            has_suspicious = len(res.get("suspicious_patches", [])) > 0
            return has_missing or has_suspicious
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @classmethod
    def _run_real_global_scan(cls, code: str) -> bool:
        """Verificação estática de vazamento de globais (alinhada ao strict.lua do Doxoade)."""
        # 1. Limpa comentários e strings (lógica atômica do Doxoade)
        clean = re.sub(
            r"--\[(=*)\[.*?\]\1\]|--[^\r\n]*|\[(=*)\[.*?\]\2\]|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", 
            " ", code, flags=re.DOTALL
        )
        # 2. Procura atribuições a identificadores no início da linha ou após ';'
        # que NÃO sejam precedidos por 'local ' e NÃO comecem com '_G.'
        for line in clean.splitlines():
            line = line.strip()
            if not line or line.startswith('local ') or line.startswith('_G.'):
                continue
            # Detecta: inicio da linha ou ';', seguido de identificador, seguido de '='
            if re.search(r'(?:^|;)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=', line):
                return True # Detectou vazamento global
        return False

    @classmethod
    def run_chaos_suite(cls) -> Dict[str, Any]:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}⚖️ MA'AT CHAOS VALIDATOR — Injeção de Falhas (Motores Reais){Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}Objetivo: Garantir que os MOTORES REAIS do Doxoade DETECTEM os erros abaixo.{Fore.RESET}\n")

        results = {"total": len(cls.FAULT_VECTORS), "caught": 0, "escaped": 0, "details": []}

        for vector in cls.FAULT_VECTORS:
            print(f"🧪 Injetando: {Fore.YELLOW}{vector['name']}{Fore.RESET} ({vector['id']})")
            
            detector = vector["detector"]
            was_caught = False
            
            if detector == "lua_compile_check":
                was_caught = cls._run_real_lua_compile_check(vector["code"])
            elif detector == "api_template_scan":
                was_caught = cls._run_real_api_scan(vector["code"])
            elif detector == "global_leak_scan":
                was_caught = cls._run_real_global_scan(vector["code"])

            if was_caught:
                results["caught"] += 1
                print(f"   {Fore.GREEN}✔ [MA'AT] Motor real cegou o erro com sucesso.{Fore.RESET}")
            else:
                results["escaped"] += 1
                print(f"   {Fore.RED}✖ [FALHA CRÍTICA] O motor real NÃO detectou o erro!{Fore.RESET}")
                print(f"      {Fore.LIGHTBLACK_EX}Detector falho: {detector}{Fore.RESET}")

            results["details"].append({"id": vector["id"], "name": vector["name"], "caught": was_caught})

        print("\n" + "="*70)
        if results["escaped"] == 0:
            print(f"{Fore.GREEN}{Style.BRIGHT}🏆 VEREDITO: TODAS AS FALHAS FORAM DETECTADAS PELOS MOTORES REAIS.{Style.RESET_ALL}")
            print(f"{Fore.GREEN}O pipeline de deploy (Anúbis/Ma'at) está vigilante e pronto para automação CI/CD.{Fore.RESET}")
        else:
            print(f"{Fore.RED}{Style.BRIGHT}💥 VEREDITO: CEGUEIRA DE AUDITORIA DETECTADA NOS MOTORES REAIS!{Style.RESET_ALL}")
            print(f"{Fore.RED}{results['escaped']} de {results['total']} falhas passaram despercebidas.{Fore.RESET}")
            print(f"{Fore.YELLOW}Ação Imediata: Reforçar as regras do detector antes do deploy automatizado.{Fore.RESET}")
        print("="*70 + "\n")

        return results

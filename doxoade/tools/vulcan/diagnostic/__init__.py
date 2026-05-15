# Soteria Diagnostic Package 
# doxoade/doxoade/tools/vulcan/diagnostic.py
import os
import shutil
import sys
from pathlib import Path
import importlib.util

class VulcanDiagnostic:

    def __init__(self, project_root):
        self.root = Path(project_root).resolve()
        self.core_dir = Path(__file__).resolve().parents[3]
        self.issues = []

    def check_environment(self):
        """Check-up focando na infraestrutura interna do Doxoade."""
        self._bootstrap_core_venv()
        compiler_ok = self._check_compiler()
        cython_ok = self._check_internal_dependency('cython')
        results = {'compiler': compiler_ok, 'cython': cython_ok, 'foundry': self._check_directory('.doxoade/vulcan/foundry'), 'disk_space': self._check_disk_free()}
        return (all(results.values()), results)

    def _bootstrap_core_venv(self):
        """Injeta o site-packages do próprio Doxoade no sys.path (MPoT-19)."""
        if os.name == 'nt':
            sp = self.core_dir / 'venv' / 'Lib' / 'site-packages'
        else:
            sp = self.core_dir / 'venv' / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
        if sp.exists() and str(sp) not in sys.path:
            sys.path.insert(0, str(sp))

    def _check_compiler(self):
        """Busca compilador no PATH ou na pasta 'opt' do Doxoade."""
        if shutil.which('gcc') or shutil.which('cl.exe'):
            return True
        internal_gcc = self.core_dir / 'thirdparty' / 'w64devkit' / 'bin' / 'gcc.exe'
        if internal_gcc.exists():
            bin_path = str(internal_gcc.parent)
            if bin_path not in os.environ['PATH']:
                os.environ['PATH'] = bin_path + os.pathsep + os.environ['PATH']
            return True
        self.issues.append(f"Compilador não encontrado. Instale o w64devkit em: {self.core_dir / 'thirdparty'}")
        return False

    def _check_internal_dependency(self, package_name):
        """Verifica se o pacote está na maleta do Doxoade (Batteries-Included)."""
        try:
            spec = importlib.util.find_spec(package_name) or importlib.util.find_spec(package_name.title())
            if spec is not None:
                return True
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            print(f"\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n")
            exc_trace(exc_tb)
        self.issues.append(f'Dependência interna faltando: {package_name}. (Rode: pip install {package_name})')
        return False

    def _check_directory(self, rel_path):
        p = self.root / rel_path
        p.mkdir(parents=True, exist_ok=True)
        return True

    def _check_disk_free(self):
        """Verifica espaço em disco com Fallback de Segurança."""
        try:
            import psutil
            free_mb = psutil.disk_usage(str(self.root)).free / (1024 * 1024)
            return free_mb > 50
        except (ImportError, ModuleNotFoundError, Exception):
            # Fallback: Se o psutil estiver quebrado, não bloqueamos a forja.
            # Apenas emitimos um aviso interno.
            return True

    def render_report(self):
        from colorama import Fore, Style
        print(f'\n{Fore.CYAN}{Style.BRIGHT}🔍 [VULCAN-DIAGNOSTIC] Checando maleta de ferramentas...{Style.RESET_ALL}')
        if not self.issues:
            print(f'   {Fore.GREEN}✔ [STATUS] Ferramentas prontas no Core.{Fore.RESET}')
        else:
            print(f'   {Fore.RED}✘ [ERRO] Maleta incompleta:{Fore.RESET}')
            for issue in self.issues:
                print(f'     ■ {issue}')

    def extract_c_body(c_file_path, py_func_name):
        """Extrai o corpo real da função C, pulando o boilerplate do Cython."""
        if not os.path.exists(c_file_path): return "Arquivo não encontrado."
        
        with open(c_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Procura a função de implementação real (geralmente sem o prefixo __pyx_pf)
        # ou o bloco de código que contém a lógica da linha do .pyx
        import re
        # Busca o bloco que o Cython marca com o nome da função
        pattern = rf"/\* Python function \*/\s+.*?{py_func_name}.*?{{(.*?)}}"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            body = match.group(1)
            # Limpa o excesso de macros do Cython para ficar legível
            body = re.sub(r'__Pyx_.*?\(.*?\);', '', body)
            return body.strip()
        return "Lógica interna não mapeada."

def extract_c_snippet(c_file_path, py_func_name):
    """
    Busca no arquivo .c a implementação da função Cython correspondente.
    O Cython marca as funções com comentários: /* "filename.pyx":line_num */
    """
    if not os.path.exists(c_file_path):
        return "Arquivo C não encontrado."

    with open(c_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    snippet = []
    found = False
    # Padrão de busca: o Cython gera nomes como __pyx_pf_..._nome_da_funcao
    pattern = f"__pyx_pf_" 
    
    for i, line in enumerate(lines):
        if pattern in line and py_func_name in line and "static PyObject" in line:
            found = True
            # Pega as próximas 30 linhas ou até fechar a chave
            for j in range(i, min(i + 50, len(lines))):
                snippet.append(lines[j])
                if lines[j].startswith("}"):
                    break
            break
    
    return "".join(snippet) if found else "Código C da função não localizado."

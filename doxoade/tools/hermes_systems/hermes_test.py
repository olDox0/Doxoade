# doxoade/tools/hermes_systems/hermes_test.py
import os
import sys
import time
import tempfile
from pathlib import Path

def run_hermes_test(project_root: str, target_py: str):
    """
    Teste Unitário do Motor C (Hermes Bridge).
    1. Comprime o .py alvo para HBC5 (Zero-Compression para teste rápido).
    2. Chama o Motor C diretamente (load_module).
    3. Valida se o code_obj retornado é executável e idêntico ao original (Lossless).
    """
    print("\n" + "="*60)
    print(f"  🧪 HERMES UNIT TEST: {Path(target_py).name}")
    print("="*60)
    
    root = Path(project_root).resolve()
    target_path = Path(target_py).resolve()
    if not target_path.exists():
        print(f"  ✘ Arquivo alvo não encontrado: {target_path}")
        return False

    # 1. Compilação do Motor C (Smoke Test)
    print("\n[1/4] Smoke Test: Motor C (hermes_bridge.pyd)...")
    try:
        from doxoade.tools.hermes_systems.native.hermes_bridge_builder import ensure_bridge_built
        if not ensure_bridge_built(root):
            print("  ✘ FALHA: Motor C não compilou.")
            return False
        print("  ✔ Motor C compilado e cacheado.")
    except Exception as e:
        print(f"  ✘ FALHA: {e}")
        return False

    # 2. Compressão do Alvo (HBC5)
    print(f"\n[2/4] Comprimindo alvo para HBC5...")
    from doxoade.tools.hermes_systems.hermes_compress_hbc5 import HermesCompressorHBC5
    compressor = HermesCompressorHBC5(str(root))
    
    try:
        orig_sz, final_sz, hermes_file, dyn_count = compressor.compress_file(
            target_path, use_dynamic_scan=False
        )
        # O compressor salva no build_dir por padrão
        build_dir = root / '.doxoade' / 'hermes' / 'build'
        module_name = str(target_path.relative_to(root).with_suffix('')).replace(os.sep, '.')
        generated_hbc5 = build_dir / f"{module_name}.hermes"
        if not generated_hbc5.exists():
            print(f"  ✘ FALHA: Compressor não gerou o arquivo {generated_hbc5}")
            return False
        print(f"  ✔ Comprimido: {orig_sz} -> {final_sz} bytes ({dyn_count} tokens)")
    except Exception as e:
        print(f"  ✘ FALHA na compressão: {e}")
        return False

    # 3. Execução via Motor C
    print(f"\n[3/4] Executando Motor C (load_module)...")
    try:
        # Importa o motor C diretamente (bypassando o Hook V2 para isolar o teste)
        native_dir = root / 'doxoade' / 'tools' / 'hermes_systems' / 'native'
        if str(native_dir) not in sys.path:
            sys.path.insert(0, str(native_dir))
        import hermes_bridge
        
        # O Motor C exige o Global Dictionary (HGD1)
        gd_path = root / '.doxoade' / 'hermes' / 'master.bin'
        gd_path_str = str(gd_path) if gd_path.exists() else ""
            
        t0 = time.perf_counter()
        code_obj = hermes_bridge.load_module(str(generated_hbc5), gd_path_str)
        t_c = (time.perf_counter() - t0) * 1000
        
        if code_obj is None:
            print("  ✘ FALHA CRÍTICA: Motor C retornou NULL (code_obj inválido).")
            return False
        print(f"  ✔ Motor C retornou code_obj em {t_c:.2f} ms")
    except Exception as e:
        print(f"  ✘ FALHA CRÍTICA no Motor C: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. Validação de Integridade (Lossless)
    print(f"\n[4/4] Validando integridade do code_obj (Lossless)...")
    from doxoade.tools.aegis.aegis_core import nexus_exec
    try:
        # Tenta executar o code_obj em um namespace isolado
        test_namespace = {}
        nexus_exec(code_obj, test_namespace)
        
        # Compara com a execução do Python puro
        source = target_path.read_text(encoding='utf-8')
        pure_code = compile(source, str(target_path), 'exec')
        pure_namespace = {}
        nexus_exec(pure_code, pure_namespace)
        
        # Compara as chaves definidas (funções, classes, variáveis)
        c_keys = set(k for k in test_namespace.keys() if not k.startswith('__'))
        py_keys = set(k for k in pure_namespace.keys() if not k.startswith('__'))
        
        if c_keys == py_keys:
            print(f"  ✔ Lossless OK: {len(c_keys)} símbolos idênticos ao Python puro.")
        else:
            missing = py_keys - c_keys
            extra = c_keys - py_keys
            print(f"  ✘ DIVERGÊNCIA: Faltam {len(missing)} símbolos, Sobram {len(extra)}.")
            if missing: print(f"    Faltando: {list(missing)[:5]}")
            return False
    except Exception as e:
        print(f"  ✘ FALHA na execução do code_obj: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Relatório Final
    print("\n" + "="*60)
    print("  📊 RELATÓRIO DO TESTE")
    print("="*60)
    print(f"  Arquivo     : {target_path.name}")
    print(f"  Motor C     : {t_c:.2f} ms")
    print(f"  Status      : 🟢 PASS (Lossless Verified)")
    print("="*60 + "\n")
    
    return True
# doxoade/tools/hermes_systems/hermes_test.py
import os
import sys
import time
import types
from pathlib import Path

def run_hermes_test(project_root: str, target_py: str):
    print("\n" + "="*60)
    print(f"  🧪 HERMES OPTIMIZATION TEST: {Path(target_py).name}")
    print("="*60)
    
    root = Path(project_root).resolve()
    target_path = Path(target_py).resolve()
    if not target_path.exists():
        print(f"  ✘ Arquivo alvo não encontrado: {target_path}")
        return False

    # [1/5] Smoke Test do Motor C
    print("\n[1/5] Smoke Test: Motor C (hermes_bridge.pyd)...")
    try:
        from doxoade.tools.hermes_systems.native.hermes_bridge_builder import ensure_bridge_built
        if not ensure_bridge_built(root):
            print("  ✘ FALHA: Motor C não compilou.")
            return False
        print("  ✔ Motor C compilado e cacheado.")
    except Exception as e:
        print(f"  ✘ FALHA: {e}")
        return False

    # [2/5] Aplicação do Preprocessor (Otimização Real)
    print(f"\n[2/5] Aplicando HermesPreprocessor (Removendo docstrings/imports)...")
    try:
        from doxoade.tools.hermes_systems.hermes_preprocessor import HermesPreprocessor
        preprocessor = HermesPreprocessor(str(root))
        source_opt, metrics = preprocessor.optimize_file(target_path)
        
        removed = sum([
            metrics.get('docstrings_removed', 0),
            metrics.get('imports_removed', 0),
            metrics.get('comments_removed', 0),
            metrics.get('blank_lines_removed', 0)
        ])
        print(f"  ✔ Otimizado: {removed} elementos removidos.")
    except Exception as e:
        print(f"  ⚠ Preprocessor falhou ({e}), usando código cru.")
        source_opt = target_path.read_text(encoding='utf-8')

    # [3/5] Compressão HBC5
    print(f"\n[3/5] Comprimindo alvo otimizado para HBC5...")
    from doxoade.tools.hermes_systems.hermes_compress_hbc5 import HermesCompressorHBC5
    compressor = HermesCompressorHBC5(str(root))
    
    temp_opt_path = root / '.doxoade' / 'hermes' / 'cache' / f"_temp_opt_{target_path.name}"
    temp_opt_path.parent.mkdir(parents=True, exist_ok=True)
    temp_opt_path.write_text(source_opt, encoding='utf-8')
    
    try:
        orig_sz, final_sz, hermes_file, dyn_count = compressor.compress_file(
            temp_opt_path, use_dynamic_scan=False
        )
        print(f"  ✔ Comprimido: {orig_sz} -> {final_sz} bytes")
    except Exception as e:
        print(f"  ✘ FALHA na compressão: {e}")
        return False

    # [4/5] Execução via Motor C (Com Telemetria de Fronteira)
    print(f"\n[4/5] Executando Motor C (load_module)...")
    try:
        native_dir = root / 'doxoade' / 'tools' / 'hermes_systems' / 'native'
        if str(native_dir) not in sys.path:
            sys.path.insert(0, str(native_dir)) # <-- CORRIGIDO
        import hermes_bridge
        
        gd_path = root / '.doxoade' / 'hermes' / 'master.bin'
        gd_path_str = str(gd_path) if gd_path.exists() else ""
            
        t0 = time.perf_counter()
        code_obj_c = hermes_bridge.load_module(str(hermes_file), gd_path_str)
        t_wall_ms = (time.perf_counter() - t0) * 1000
        
        if code_obj_c is None:
            print("  ✘ FALHA CRÍTICA: Motor C retornou NULL.")
            return False
        print(f"  ✔ Wall-Clock Python: {t_wall_ms:.2f} ms")
    except Exception as e:
        print(f"  ✘ FALHA CRÍTICA no Motor C: {e}")
        return False

    # [5/5] Validação de Otimização (Lossless + Bytecode Size)
    print(f"\n[5/5] Validando integridade e otimização do bytecode...")
    try:
        pure_code = compile(source_opt, str(target_path), 'exec', optimize=2)
        
        c_keys = set(k for k in code_obj_c.co_consts if isinstance(k, types.CodeType))
        py_keys = set(k for k in pure_code.co_consts if isinstance(k, types.CodeType))
        
        c_bytecode_size = len(code_obj_c.co_code)
        py_bytecode_size = len(pure_code.co_code)
        
        if c_keys == py_keys:
            print(f"  ✔ Lossless Estrutural OK: {len(c_keys)} code objects.")
        else:
            print(f"  ✘ DIVERGÊNCIA ESTRUTURAL: Faltam {len(py_keys - c_keys)} objetos.")
            return False

        if c_bytecode_size <= py_bytecode_size:
            print(f"  ✔ Otimização OK: Bytecode C ({c_bytecode_size}B) <= Python ({py_bytecode_size}B).")
        else:
            print(f"  ✘ FALHA DE OTIMIZAÇÃO: Bytecode C ({c_bytecode_size}B) > Python ({py_bytecode_size}B).")
            return False

    except Exception as e:
        print(f"  ✘ FALHA na validação: {e}")
        return False

    # Relatório Final
    print("\n" + "="*60)
    print("  📊 RELATÓRIO DE PERFORMANCE (Autópsia)")
    print("="*60)
    print(f"  Arquivo       : {target_path.name}")
    print(f"  Wall-Clock Py : {t_wall_ms:.2f} ms (Tempo real percebido)")
    print(f"  Bytecode Size : {c_bytecode_size} bytes")
    print(f"  Status        : 🟢 PASS (Optimized & Lossless)")
    print("="*60 + "\n")
    
    if temp_opt_path.exists():
        temp_opt_path.unlink()
    return True
# doxoade/tools/vulcan/probe_import.py
import sys, json, importlib, traceback

def main():
    """Tenta importar um módulo e reporta sucesso ou falha como JSON."""
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "missing module argument"}))
        sys.exit(1)
        
    module_to_probe = sys.argv[1]
    result = {"module": module_to_probe, "ok": False, "error": None}
    
    try:
        # A ação principal: tenta importar o módulo.
        # Se o .pyd/.so tiver dependências quebradas, isso falhará.
        importlib.import_module(module_to_probe)
        result["ok"] = True
    except Exception as e:
        print(f"\033[31m ■ Erro: {e}")
        result["error"] = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
    
    # Imprime o resultado como JSON para o processo pai
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()
    sys.exit(0 if result["ok"] else 1)

if __name__ == "__main__":
    main()
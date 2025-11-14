# doxoade/probes/syntax_probe.py
import sys
import ast

def analyze(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        ast.parse(content, filename=file_path)
        return 0
    except SyntaxError as e:
        line = getattr(e, 'lineno', 1)
        msg = getattr(e, 'msg', str(e))
        sys.stderr.write(f"SyntaxError:{file_path}:{line}:{msg}")
        return 1
    except Exception as e:
        sys.stderr.write(f"ProbeInternalError:{file_path}:1:{type(e).__name__}: {str(e)}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(analyze(sys.argv[1]))
    else:
        sys.stderr.write("ProbeError: No file path provided.")
        sys.exit(1)
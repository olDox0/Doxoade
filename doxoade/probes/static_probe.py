# doxoade/probes/static_probe.py
import sys
import subprocess

def analyze(file_path):
    try:
        cmd = [sys.executable, '-m', 'pyflakes', file_path]
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore'
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode
    except Exception as e:
        sys.stderr.write(f"ProbeInternalError:{file_path}:1:{type(e).__name__}: {str(e)}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(analyze(sys.argv[1]))
    else:
        sys.stderr.write("ProbeError: No file path provided.")
        sys.exit(1)
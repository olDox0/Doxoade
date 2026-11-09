#!/usr/bin/env python3
"""fuzz_truncate.py — Fuzz testing do doxreveng por truncamento.

Gera N cópias truncadas do binário alvo (em pontos aleatórios e
em pontos estratégicos) e roda o parser em cada uma. Reporta:
  - OK (exit 0, JSON válido)
  - ERRO ESTRUTURADO (exit 1, mensagem em stderr)
  - CRASH (exit != 0 e != 1, ou sinal, ou timeout)

Uso:
    python fuzz_truncate.py <binario> <doxreveng.exe> [--n 50]
"""
import subprocess
import sys
import tempfile
import os
import random
import json

def run_parser(doxreveng, path, timeout=5):
    try:
        r = subprocess.run(
            [doxreveng, path],
            capture_output=True, timeout=timeout
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT", b"", b""
    except Exception as e:
        return "EXCEPTION", b"", str(e).encode()

def main():
    if len(sys.argv) < 3:
        print("uso: fuzz_truncate.py <binario> <doxreveng.exe> [--n 50]")
        return 1
    target = sys.argv[1]
    parser = sys.argv[2]
    n = 50
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])

    with open(target, "rb") as f:
        data = f.read()
    size = len(data)
    print(f"[FUZZ] alvo: {target} ({size} bytes), parser: {parser}, N={n}")

    # Pontos estratégicos: header, COFF, Optional, seções, imports
    strategic = [0, 1, 2, 0x3C, 0x40, 0x80, 0x84, 0x98, 0x100,
                 0x188, 0x430, size // 2, size - 1]
    points = [p for p in strategic if 0 < p < size]

    # Pontos aleatórios
    random.seed(42)
    for _ in range(n - len(points)):
        points.append(random.randint(1, size - 1))

    results = {"ok": 0, "err": 0, "crash": 0, "timeout": 0}
    crashes = []

    for i, cut in enumerate(points):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as tf:
            tf.write(data[:cut])
            tmp = tf.name
        try:
            rc, out, err = run_parser(parser, tmp)
            if rc == "TIMEOUT":
                results["timeout"] += 1
                crashes.append((cut, "TIMEOUT", err.decode(errors="replace")))
            elif rc == "EXCEPTION":
                results["crash"] += 1
                crashes.append((cut, "EXCEPTION", err.decode(errors="replace")))
            elif rc == 0:
                # Verificar se o stdout é JSON válido
                try:
                    json.loads(out)
                    results["ok"] += 1
                except json.JSONDecodeError:
                    results["crash"] += 1
                    crashes.append((cut, "JSON_INVALIDO", out[:200].decode(errors="replace")))
            elif rc == 1:
                results["err"] += 1
            else:
                results["crash"] += 1
                crashes.append((cut, f"RC={rc}", err.decode(errors="replace")))
        finally:
            os.unlink(tmp)

    print(f"\n[RESULTADO] ok={results['ok']} err={results['err']} "
          f"crash={results['crash']} timeout={results['timeout']}")
    if crashes:
        print(f"\n[CRASHES] {len(crashes)} encontrados:")
        for cut, kind, msg in crashes:
            print(f"  cut=0x{cut:04x} ({cut} bytes) kind={kind}")
            print(f"    {msg[:200]}")
    else:
        print("\n[OK] Nenhum crash. Parser robusto a truncamento.")
    return 0 if not crashes else 1

if __name__ == "__main__":
    sys.exit(main())

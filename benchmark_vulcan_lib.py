# benchmark_vulcan_lib.py
import time
import statistics
import sys

def bench(fn, args, kwargs, n=10000):
    for _ in range(100):
        fn(*args, **kwargs)
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn(*args, **kwargs)
        times.append(time.perf_counter() - t0)
    return times

def report(label, times_vulcan, times_py=None):
    us_v = [t * 1e6 for t in times_vulcan]
    med_v = statistics.median(us_v)
    p99_v = sorted(us_v)[int(len(us_v)*0.99)]
    if times_py:
        us_p = [t * 1e6 for t in times_py]
        med_p = statistics.median(us_p)
        speedup = med_p / med_v
        print(f"  {label:<42} vulcan={med_v:>7.1f}µs  py={med_p:>7.1f}µs  "
              f"speedup={speedup:>5.2f}x  p99={p99_v:>7.1f}µs")
    else:
        print(f"  {label:<42} median={med_v:>7.1f}µs  p99={p99_v:>7.1f}µs")

print("\n=== VULCAN LIB BENCHMARK — click no doxoade ===\n")

import click.formatting

text = "Este é um texto de teste para medir o desempenho do wrap_text no click com Vulcan ativo."

# Captura a função nativa diretamente para comparar
native_mod = sys.modules.get("v_formatting_da684d")
if native_mod:
    native_wrap = native_mod.wrap_text_vulcan_optimized
    native_iter = native_mod.iter_rows_vulcan_optimized
else:
    native_wrap = None

# Função Python pura (contorna o VulcanLoader)
# --- substitua o bloco antigo por isto ---
import importlib.util
orig_path = click.formatting.__spec__.origin  # caminho do .py original

# escolha um nome que não conflite com o módulo em cache (ou use 'click.formatting' se quiser sobrescrever)
spec_name = "click._formatting_plain"

_spec = importlib.util.spec_from_file_location(spec_name, orig_path)
_py_mod = importlib.util.module_from_spec(_spec)

# ESSENCIAL: dizer qual é o package pai para que 'from ._compat ...' funcione
_py_mod.__package__ = "click"

# registrar no sys.modules para que import interno funcione corretamente
import sys
sys.modules[spec_name] = _py_mod

# agora execute o módulo
_spec.loader.exec_module(_py_mod)

py_wrap = _py_mod.wrap_text

# --- 1. wrap_text direto ---
r_vulcan = bench(click.formatting.wrap_text, [text], {"width": 60})
r_py     = bench(py_wrap, [text], {"width": 60})
report("formatting.wrap_text (width=60)", r_vulcan, r_py)

if native_wrap:
    r_native = bench(native_wrap, [text], {"width": 60})
    report("  └─ nativo direto (sem overhead)", r_native, r_py)

# --- 2. HelpFormatter ---
def render_vulcan():
    f = click.formatting.HelpFormatter(width=80)
    with f.section("Opções"):
        f.write_dl([
            ("--verbose", "Ativa saída detalhada"),
            ("--output",  "Arquivo de saída"),
            ("--force",   "Força execução"),
        ])
    return f.getvalue()

def render_py():
    f = _py_mod.HelpFormatter(width=80)
    with f.section("Opções"):
        f.write_dl([
            ("--verbose", "Ativa saída detalhada"),
            ("--output",  "Arquivo de saída"),
            ("--force",   "Força execução"),
        ])
    return f.getvalue()

r2v = bench(render_vulcan, [], {})
r2p = bench(render_py, [], {})
report("HelpFormatter.write_dl (3 items)", r2v, r2p)

# --- 3. get_help do doxoade (impacto real) ---
import click
from doxoade.cli import cli

def render_help():
    ctx = click.Context(cli, info_name="doxoade")
    return cli.get_help(ctx)

r3 = bench(render_help, [], {}, n=500)
report("doxoade cli.get_help() (500x)", r3)

# --- Resumo ---
print(f"\n  wrap_text ativo: {click.formatting.wrap_text.__qualname__}")
print(f"  módulo:          {click.formatting.wrap_text.__module__}")
if native_wrap:
    print(f"  nativo direto:   {type(native_wrap).__name__}")
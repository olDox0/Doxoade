# bench_click_vulcan.py
import sys
from pathlib import Path

# Injeta o loader Vulcan ANTES de importar click
VULCAN_LIB = Path(".doxoade/vulcan/lib_bin").resolve()
sys.path.insert(0, str(VULCAN_LIB))

import time
import click

ROUNDS = 200_000


@click.command()
@click.option("--count", default=1)
@click.option("--name", default="World")
def hello(count, name):
    return f"{name} x{count}"


start = time.perf_counter()
for _ in range(ROUNDS):
    hello.main(
        args=["--count", "3", "--name", "Tester"],
        standalone_mode=False,
    )
end = time.perf_counter()

print(f"CLICK + VULCAN: {end - start:.4f}s")
import sys
from pathlib import Path
import time

# AJUSTE PARA O PATH REAL GERADO PELO VULCAN
OPT_CLICK = Path(
    r"C:\Users\olDox222\AppData\Local\Temp\vulcan_opt_click_w78n_kzo"
)

sys.path.insert(0, str(OPT_CLICK))

import click  # agora é o click OTIMIZADO

def bench():
    start = time.perf_counter()

    for _ in range(50000):
        @click.command()
        @click.option("--x", default=1)
        def cmd(x):
            return x + 1

    return time.perf_counter() - start


if __name__ == "__main__":
    t = bench()
    print(f"[CLICK OPT SOURCE]: {t:.4f}s")
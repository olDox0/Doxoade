# bench_click_pure.py
import time
import click

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
    print(f"[CLICK PURE]: {t:.4f}s")
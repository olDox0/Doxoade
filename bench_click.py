# bench_click.py
import time
import sys
import importlib

ROUNDS = 10_000


def run_benchmark(label: str):
    import click

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

    print(f"{label}: {end - start:.4f}s")


if __name__ == "__main__":
    run_benchmark("CLICK")
import sys
import time
from pathlib import Path

from click.testing import CliRunner


def run_test(label: str, iterations: int = 5000):
    import click

    @click.command()
    @click.option("--count", default=10, type=int)
    def cmd(count):
        s = 0
        for i in range(count):
            s += i
        click.echo(s)

    runner = CliRunner()

    # warm-up
    for _ in range(100):
        runner.invoke(cmd, ["--count", "20"])

    start = time.perf_counter()

    for _ in range(iterations):
        result = runner.invoke(cmd, ["--count", "20"])
        if result.exit_code != 0:
            raise RuntimeError(result.output)

    elapsed = time.perf_counter() - start
    print(f"{label}: {elapsed:.4f}s")
    return elapsed


if __name__ == "__main__":
    mode = sys.argv[1]

    if mode == "pure":
        # garante click do site-packages
        sys.modules.pop("click", None)

    elif mode == "opt":
        # 🔴 ajuste para o path real da cópia otimizada
        OPT_PATH = Path(
            r"C:\Users\olDox222\AppData\Local\Temp\vulcan_opt_click_x2zf56oi"
        )
        sys.path.insert(0, str(OPT_PATH))
        sys.modules.pop("click", None)

    else:
        raise SystemExit("use: pure | opt")

    run_test(f"[{mode.upper()} CLICK]")
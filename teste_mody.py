# tianzun_cli.py
import click, subprocess
from pathlib import Path

@click.group()
def cli():
   """Tianzun Engine CLI."""

@cli.command()
def build():
   """Compila o C++ (Fase 3)."""
   subprocess.run(["doxoade", "metal", "build", "--target", "tianzun_prototype_1"], check=True)

@cli.command()
def test():
    """Build + run the Trilha D test suite (exit code = CI pass/fail)."""
    subprocess.run(["doxoade", "metal", "build", "--target", "tianzun_tests"], check=True)
    subprocess.run(["doxoade", "metal", "run", "tianzun_tests"], check=True)


@cli.command()
def run():
   """Executa a simulação."""
   subprocess.run(["doxoade", "metal", "run", "--target", "tianzun_prototype_1"], check=True)

@cli.command()
def analyze():
   """Analisa o CSV gerado."""
   subprocess.run(["python", "analyze.py"], check=True)

@cli.command()
def lua():
   """Executa o runner Lua."""
   subprocess.run(["doxoade", "lua", "run", "lua_sys/scripts/main.lua"], check=True)

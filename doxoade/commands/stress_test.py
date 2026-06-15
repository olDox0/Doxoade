# doxoade/commands/stress_test.py
import click
import time

@click.command('stress-hades')
@click.option('--count', default=1000)
def stress_hades(count):
    """Teste de Inundação Hades (NSR)."""
    click.echo(f"🚀 Iniciando Estresse Hades: {count} funções...")
    t0 = time.perf_counter()
    for i in range(count):
        _batimento(i)
    dur = time.perf_counter() - t0
    click.echo(f"✔ Finalizado em {dur:.2f}s. ({count/dur:.0f} logs/s)")

def _batimento(n):
    return n * 2

@click.command('stress-abyss')
def stress_abyss():
    """Teste de Estabilidade Sotéria (Recursão)."""
    click.echo("🌀 Entrando no abismo...")
    def _cair(n):
        return _cair(n + 1)
    _cair(1)
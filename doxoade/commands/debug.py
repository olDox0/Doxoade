# -*- coding: utf-8 -*-
"""
Debug Suite v2.1 - Chief Gold Orchestrator.
Compliance: MPoT-1, PASC-1.
"""
import click
from .debug_systems.debug_engine import execute_debug


@click.command('debug')
@click.argument('script', type=click.Path(exists=True))
@click.option('--watch',        help='Monitora uma variável em tempo real.')
@click.option('--bottleneck', '-b', is_flag=True, help='Exibe linhas com tempo por linha.')
@click.option('--threshold',  '-t', type=float, default=0.0,
              help='Filtra linhas abaixo de N ms no modo -b (aceita decimais: -t 0.5).')
@click.option('--no-compress', '-nc', is_flag=True,
              help='Desativa compressão de loops repetidos (Iron Gate).')
@click.option('--profile',    '-p', is_flag=True,
              help='Perfil profundo: line-timer + cProfile + tracemalloc.')
@click.option('--args',       help='Args do script.')
def debug(script, watch, bottleneck, threshold, no_compress, profile, args):
    """🩺 Autópsia Forense, Monitoramento ou Perfil Profundo (MPoT-5)."""
    execute_debug(script, watch, bottleneck, threshold, no_compress, args, profile=profile)
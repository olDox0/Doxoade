# doxoade/doxoade/commands/vulcan_cmd/vulcan_cmd_diag.py
"""Diagnóstico empírico do pipeline Vulcan — ProDeNov §3.1.4 (W5H)."""
import ast
import json
import sys
from pathlib import Path

import click

from doxoade.tools.doxcolors import Fore, Style


@click.command('diag')
@click.argument('target', required=True, type=click.Path(exists=True))
@click.option('--env-root', help='Project root do projeto alvo (inferido se omitido).')
@click.option('--verbose', '-v', is_flag=True)
def vulcan_diag(target, env_root, verbose):
    """Diagnóstico empírico do pipeline Vulcan para um arquivo."""
    target_path = Path(target).resolve()
    if env_root:
        env_root = str(Path(env_root).resolve())
    else:
        # Inferir: walk up até pyproject.toml ou .git
        cur = target_path.parent
        while cur != cur.parent:
            if (cur / 'pyproject.toml').exists() or (cur / '.git').exists():
                env_root = str(cur)
                break
            cur = cur.parent

    click.secho(f'\n  ⬡ VULCAN DIAG — {target_path.name}', fg='cyan', bold=True)
    click.echo(f'  Target   : {target_path}')
    click.echo(f'  Env Root : {env_root}')
    click.echo()

    # === [1] Source analysis ===
    click.secho('  [1] Fonte original', fg='yellow', bold=True)
    src = target_path.read_text(encoding='utf-8')
    tree = ast.parse(src)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.append(('import', 0, a.name, a.asname))
        elif isinstance(node, ast.ImportFrom):
            imports.append(('from', node.level or 0, node.module or '', 
                          [a.name for a in node.names]))
    click.echo(f'      Total imports: {len(imports)}')
    for kind, level, mod, names in imports:
        dots = '.' * level
        name_list = names if isinstance(names, list) else [names]
        click.echo(f'        {kind} {dots}{mod} -> {name_list}')

    # === [2] VulcanForge availability ===
    click.secho('\n  [2] VulcanForge', fg='yellow', bold=True)
    from doxoade.tools.vulcan.forge import VulcanForge
    click.echo(f'      NodeTransformer: {issubclass(VulcanForge, ast.NodeTransformer)}')
    import inspect
    sig = inspect.signature(VulcanForge.__init__)
    click.echo(f'      __init__: {list(sig.parameters.keys())}')
    gen_src = inspect.getsource(VulcanForge.generate_source)
    click.echo(f'      calls self.visit(tree): {"self.visit(tree)" in gen_src}')

    # === [3] Forge the pyx ===
    click.secho('\n  [3] Forge output', fg='yellow', bold=True)
    try:
        forge = VulcanForge(str(target_path), env_root=env_root)
        pyx = forge.generate_source(str(target_path))
    except Exception as e:
        click.secho(f'      FORGE FAILED: {e}', fg='red')
        return

    pyx_path = target_path.with_suffix('.diag.pyx')
    pyx_path.write_text(pyx, encoding='utf-8')
    click.echo(f'      Wrote: {pyx_path}')
    click.echo(f'      Lines: {len(pyx.splitlines())}')

    # Check for known problem patterns
    problems = []
    for i, line in enumerate(pyx.splitlines(), 1):
        if 'nexus_get_filename(self)' in line and '=' in line:
            problems.append(f'      L{i}: INVALID ASSIGNMENT → {line.strip()}')
        if line.strip().startswith('from .') or ' from .' in line:
            problems.append(f'      L{i}: UNCONVERTED RELATIVE IMPORT → {line.strip()}')
        if 'with nogil:' in line:
            # Check if next non-empty line exists and is indented
            next_lines = pyx.splitlines()[i:i+3]
            has_body = any(l.strip() and not l.strip().startswith('#') for l in next_lines)
            if not has_body:
                problems.append(f'      L{i}: EMPTY NOGIL BLOCK')

    if problems:
        click.secho('      PROBLEMS DETECTED:', fg='red', bold=True)
        for p in problems:
            click.echo(p)
    else:
        click.secho('      ✓ No obvious problems detected', fg='green')

    # === [4] native_dir resolution ===
    click.secho('\n  [4] Kernel paths', fg='yellow', bold=True)
    from doxoade.tools.vulcan import compiler as comp_mod
    compiler_file = Path(comp_mod.__file__)
    native_from_file = compiler_file.parent / 'native'
    click.echo(f'      compiler.py: {compiler_file}')
    click.echo(f'      native_dir (Path(__file__).parent / "native"):')
    click.echo(f'        → {native_from_file} (exists: {native_from_file.exists()})')
    click.echo(f'        → nexus_kernels.c: {(native_from_file / "nexus_kernels.c").exists()}')

    # === [5] Import context resolution ===
    click.secho('\n  [5] Import conversion preview', fg='yellow', bold=True)
    click.echo(f'      (env_root = {env_root})')
    for kind, level, mod, names in imports:
        if level > 0:
            click.echo(f'      Would convert: from {"." * level}{mod}')

    click.echo()


def register(group):
    group.add_command(vulcan_diag)

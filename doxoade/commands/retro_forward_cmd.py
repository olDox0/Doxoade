# -*- coding: utf-8 -*-
# doxoade/commands/retro_forward_cmd.py
"""
Orquestrador de PoCs de pesquisa (retro-forward).

Uso:
    doxoade retro-forward list
    doxoade retro-forward run <poc> [--debug]
    doxoade retro-forward trace <poc>     # = run --debug
    doxoade retro-forward all
    doxoade retro-forward doctor
    doxoade retro-forward accept <poc>    # regenera expected_<num>.txt
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import click

from doxoade.tools.doxcolors import Fore, Style


POC_BASE = Path(__file__).resolve().parent.parent / "research"
PLACEHOLDER_RE = re.compile(r"<[A-Z_]+>")
MAX_DIFF_LINES = 5


# ============================================================
# Descoberta
# ============================================================
def _discover_pocs() -> list[dict]:
    """Descobre PoCs em research/*/poc/. Expected: expected_<num>.txt."""
    if not POC_BASE.is_dir():
        return []
    pocs: list[dict] = []
    for line_dir in sorted(POC_BASE.iterdir()):
        if not line_dir.is_dir() or line_dir.name.startswith("_"):
            continue
        poc_dir = line_dir / "poc"
        if not poc_dir.is_dir():
            continue
        for poc_path in sorted(poc_dir.iterdir()):
            if not poc_path.is_dir() or poc_path.name.startswith("_"):
                continue
            num = poc_path.name.split("_", 1)[0]
            if num and num[0].isdigit():
                pattern = "engine_p*.py"
                expected_engine_name = f"engine_p{num}.py"
            else:
                pattern = "engine_*.py"
                expected_engine_name = f"engine_{num}.py"
            engines = sorted(poc_path.glob(pattern))
            if not engines:
                continue
            engine = engines[0]
            expected_path = poc_path / f"expected_{num}.txt"
            pocs.append({
                "name": poc_path.name,
                "num": num,
                "line": line_dir.name,
                "dir": poc_path,
                "engine": engine,
                "expected_engine_name": expected_engine_name,
                "engine_ok": engine.name == expected_engine_name,
                "expected_path": expected_path,
                "has_expected": expected_path.exists(),
            })
    return pocs


def _find_poc(name: str, pocs: list[dict]) -> dict | None:
    name = name.strip().lower().rstrip("/")
    for p in pocs:
        folder = p["name"].lower()
        num = p["num"].lower()
        if name in (folder, num, folder.split("_", 1)[0]):
            return p
    return None


# ============================================================
# Execucao e comparacao
# ============================================================
def _run_engine(poc: dict, debug: bool = False) -> tuple[bool, str, str, str]:
    """Executa engine em subprocess. Retorna (ok, err_msg, stdout, stderr).

    Em timeout, retorna stdout/stderr PARCIAIS capturados (nao vazios).
    Todos os paths retornam 4-tupla; nunca None.
    """
    cmd = [sys.executable, poc["engine"].name]
    if debug:
        cmd.append("--debug")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(poc["dir"]),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as e:
        partial_out = e.stdout or ""
        partial_err = e.stderr or ""
        if isinstance(partial_out, bytes):
            partial_out = partial_out.decode("utf-8", "replace")
        if isinstance(partial_err, bytes):
            partial_err = partial_err.decode("utf-8", "replace")

        out_lines = partial_out.splitlines()
        err_lines = partial_err.splitlines()
        out_tail = "\n".join(out_lines[-10:]) if out_lines else "  (vazio)"
        err_tail = "\n".join(err_lines[-10:]) if err_lines else "  (vazio)"

        msg = (
            f"timeout (60s)\n"
            f"  stdout_total: {len(out_lines)} linha(s)\n"
            f"  stderr_total: {len(err_lines)} linha(s)\n"
            f"\n"
            f"  --- stdout (ultimas 10 linhas) ---\n"
            f"{out_tail}\n"
            f"\n"
            f"  --- stderr (ultimas 10 linhas) ---\n"
            f"{err_tail}\n"
            f"\n"
            f"  --- como diagnosticar ---\n"
            f"  * Rodar direto: cd {poc['dir']}\n"
            f"                  py {poc['engine'].name}{' --debug' if debug else ''}\n"
            f"  * Se hang persistir: pip install py-spy\n"
            f"    py -3.12 engine_XX.py &  (em outra janela, py-spy dump --pid <PID>)"
        )
        return False, msg, partial_out, partial_err
    except Exception as e:
        return False, f"subprocess error: {type(e).__name__}: {e}", "", ""

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if result.returncode != 0:
        lines = stderr.strip().splitlines()
        non_debug = [ln for ln in lines if not ln.startswith("[DEBUG]")]
        head = (non_debug[-1] if non_debug else
                (lines[-1] if lines else "(sem stderr)"))
        return False, f"engine exit {result.returncode}: {head[:200]}", stdout, stderr

    return True, "", stdout, stderr
    
def _read_outputs(poc: dict) -> tuple[str | None, str | None]:
    output_path = poc["dir"] / "output.txt"
    if not output_path.exists():
        return None, "output.txt nao foi gerado"
    if not poc["has_expected"]:
        return None, f"{poc['expected_path'].name} ausente"
    try:
        out = output_path.read_text(encoding="utf-8", errors="replace")
        exp = poc["expected_path"].read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return None, f"read error: {e}"
    return out.replace("\r\n", "\n"), exp.replace("\r\n", "\n")


def _format_diff(out: str, exp: str, poc: dict) -> tuple[str, int, bool]:
    out_lines = out.splitlines()
    exp_lines = exp.splitlines()
    mismatches: list[tuple[int, str | None, str | None]] = []
    total = 0
    for i in range(max(len(out_lines), len(exp_lines))):
        o = out_lines[i] if i < len(out_lines) else None
        e = exp_lines[i] if i < len(exp_lines) else None
        if o != e:
            total += 1
            if len(mismatches) < MAX_DIFF_LINES:
                mismatches.append((i + 1, e, o))

    parts = [
        f"  arquivo esperado: {poc['expected_path']}",
        f"  arquivo atual:    {poc['dir'] / 'output.txt'}",
        "",
    ]
    for idx, e, o in mismatches:
        parts.append(f"  linha {idx}:")
        if e is None:
            parts.append(f"    exp: <EOF>")
            parts.append(f"    out: {o!r}")
        elif o is None:
            parts.append(f"    exp: {e!r}")
            parts.append(f"    out: <EOF>")
        else:
            parts.append(f"    exp: {e!r}")
            parts.append(f"    out: {o!r}")
    if total > MAX_DIFF_LINES:
        parts.append(f"  ... e mais {total - MAX_DIFF_LINES} divergencia(s)")

    has_ph = bool(PLACEHOLDER_RE.search(exp))
    return "\n".join(parts), total, has_ph

def _run_one(poc: dict, debug: bool = False) -> tuple[bool, str, str, str]:
    """Retorna (ok, msg, stdout, stderr)."""
    ok, err, stdout, stderr = _run_engine(poc, debug=debug)
    if not ok:
        return False, f"  {err}", stdout, stderr   # <-- era: f"  engine falhou: {err}"
    out, exp_or_err = _read_outputs(poc)
    if out is None:
        return False, f"  {exp_or_err}", stdout, stderr
    if out == exp_or_err:
        return True, "", stdout, stderr
    msg, total, has_ph = _format_diff(out, exp_or_err, poc)
    if has_ph:
        msg += (
            "\n\n"
            f"  DICA: {poc['expected_path'].name} contem placeholders <...>.\n"
            f"        Rode: doxoade retro-forward accept {poc['num']}"
        )
    return False, msg, stdout, stderr
    
# ============================================================
# Doctor
# ============================================================
def _doctor_report() -> tuple[list[dict], int]:
    results = []
    total_problems = 0
    for poc in _discover_pocs():
        problems = []
        if not poc["engine_ok"]:
            problems.append(
                f"engine '{poc['engine'].name}' "
                f"(esperado '{poc['expected_engine_name']}')"
            )
        if not poc["has_expected"]:
            problems.append(f"{poc['expected_path'].name} ausente")
        results.append({"poc": poc, "problems": problems})
        if problems:
            total_problems += 1
    return results, total_problems


# ============================================================
# CLI
# ============================================================
@click.group("retro-forward")
def retro_forward_group():
    """Orquestrador de PoCs de pesquisa (forward_chaining, code_classification)."""
    pass


@retro_forward_group.command("list")
def cmd_list():
    """Lista PoCs disponiveis em todas as linhas de pesquisa."""
    pocs = _discover_pocs()
    if not pocs:
        click.secho(f"Nenhum PoC em {POC_BASE}", fg="yellow")
        return
    by_line: dict[str, list[dict]] = {}
    for p in pocs:
        by_line.setdefault(p["line"], []).append(p)
    click.echo(f"PoCs em {Fore.CYAN}{POC_BASE}{Style.RESET_ALL}:")
    for line, items in sorted(by_line.items()):
        click.echo()
        click.secho(f"  [{line}]", fg="cyan", bold=True)
        for p in items:
            status = ""
            if not p["engine_ok"] or not p["has_expected"]:
                reasons = []
                if not p["engine_ok"]:
                    reasons.append("engine errado")
                if not p["has_expected"]:
                    reasons.append(f"sem {p['expected_path'].name}")
                status = click.style(f" [{', '.join(reasons)}]", fg="red")
            click.echo(f"    {p['name']:<30}{status}")


@retro_forward_group.command("run")
@click.argument("poc_name")
@click.option("--debug", "-d", is_flag=True,
              help="Mostra stdout completo do engine (mesmo em PASS)")
def cmd_run(poc_name: str, debug: bool):
    """Executa um PoC especifico ('30b', 'p30b', 'q00', ou nome completo)."""
    pocs = _discover_pocs()
    poc = _find_poc(poc_name, pocs)
    if poc is None:
        click.secho(f"PoC '{poc_name}' nao encontrado.", fg="red")
        if pocs:
            click.echo("Disponiveis: " + ", ".join(p["name"] for p in pocs))
        sys.exit(1)

    click.secho(f"=== {poc['name']} ===", fg="cyan", bold=True)
    ok, msg, stdout, stderr = _run_one(poc, debug=debug)
    if ok:
        click.secho(f"{poc['name']}: PASS", fg="green", bold=True)
        if debug and stdout:
            click.echo()
            click.secho("--- engine stdout ---", fg="yellow", bold=True)
            click.echo(stdout)
        if debug and stderr:
            click.echo()
            click.secho("--- engine stderr ---", fg="yellow", bold=True)
            click.echo(stderr)
    else:
        click.secho(f"{poc['name']}: FAIL", fg="red", bold=True)
        click.echo()
        click.echo(msg)
        if debug and stdout:
            click.echo()
            click.secho("--- engine stdout ---", fg="yellow", bold=True)
            click.echo(stdout)
        sys.exit(1)


@retro_forward_group.command("trace")
@click.argument("poc_name")
def cmd_trace(poc_name: str):
    """Alias para 'run <poc> --debug' (mostra derivacao completa)."""
    ctx = click.get_current_context()
    ctx.invoke(cmd_run, poc_name=poc_name, debug=True)


@retro_forward_group.command("all")
def cmd_all():
    """Pre-flight + todos os PoCs."""
    click.secho("=== Pre-flight: doctor ===", fg="cyan", bold=True)
    results, problems = _doctor_report()
    for r in results:
        if r["problems"]:
            click.secho(
                f"  {r['poc']['name']}: {', '.join(r['problems'])}", fg="red",
            )
    if problems > 0:
        click.secho(
            f"PRE-FLIGHT FALHOU: {problems} PoC(s) com problema",
            fg="red", bold=True,
        )
        sys.exit(1)

    click.secho(f"{len(results)}/{len(results)} PoCs OK", fg="green")
    click.echo()
    click.secho("=== Executando PoCs ===", fg="cyan", bold=True)

    pass_count, fail_count = 0, 0
    failed: list[str] = []
    for r in results:
        poc = r["poc"]
        click.echo()
        click.secho(f"==== {poc['name']} ====", fg="cyan")
        ok, msg, _, _ = _run_one(poc)
        if ok:
            click.secho(f"{poc['name']}: PASS", fg="green")
            pass_count += 1
        else:
            click.secho(f"{poc['name']}: FAIL", fg="red")
            click.echo(msg)
            fail_count += 1
            failed.append(poc["name"])

    click.echo()
    click.echo("=" * 40)
    if fail_count:
        click.secho(f"PASS: {pass_count} | FAIL: {fail_count}",
                    fg="red", bold=True)
        click.echo(f"Failed: {' '.join(failed)}")
        sys.exit(1)
    click.secho(f"PASS: {pass_count} | FAIL: 0", fg="green", bold=True)


@retro_forward_group.command("doctor")
def cmd_doctor():
    """Diagnostico estrutural (sem executar engines)."""
    results, problems = _doctor_report()
    if not results:
        click.secho(f"Nenhum PoC em {POC_BASE}", fg="yellow")
        return
    for r in results:
        poc = r["poc"]
        click.echo(f"--- {poc['name']} ---")
        if r["problems"]:
            for prob in r["problems"]:
                click.secho(f"  {prob}", fg="red")
        else:
            click.secho("  OK", fg="green")
        click.echo()
    if problems == 0:
        click.secho(f"Resumo: {len(results)}/{len(results)} PoCs OK",
                    fg="green", bold=True)
    else:
        click.secho(
            f"Resumo: {len(results) - problems}/{len(results)} OK | "
            f"{problems} problema(s)", fg="red", bold=True,
        )
        sys.exit(1)


@retro_forward_group.command("accept")
@click.argument("poc_name")
@click.option("--no-diff", is_flag=True, help="Nao mostrar diff antes de aceitar")
def cmd_accept(poc_name: str, no_diff: bool):
    """Aceita output.txt atual como novo expected_<num>.txt (regenera)."""
    pocs = _discover_pocs()
    poc = _find_poc(poc_name, pocs)
    if poc is None:
        click.secho(f"PoC '{poc_name}' nao encontrado.", fg="red")
        sys.exit(1)

    ok, err, _, _ = _run_engine(poc)
    if not ok:
        click.secho(f"Engine falhou, abortando accept: {err}", fg="red")
        sys.exit(1)

    out, exp_or_err = _read_outputs(poc)
    if out is None:
        # Se expected ainda nao existe, le so output.txt
        output_path = poc["dir"] / "output.txt"
        if output_path.exists():
            out = output_path.read_text(encoding="utf-8", errors="replace")
            out = out.replace("\r\n", "\n")
        else:
            click.secho(f"Falha lendo output: {exp_or_err}", fg="red")
            sys.exit(1)

    if not no_diff:
        old = exp_or_err if isinstance(exp_or_err, str) else ""
        if old and old != out:
            diff_msg, total, _ = _format_diff(out, old, poc)
            click.secho(f"=== Diff a ser aceito ({total} divergencia(s)) ===",
                        fg="yellow", bold=True)
            click.echo(diff_msg)
            click.echo()

    output_path = poc["dir"] / "output.txt"
    output_path.replace(poc["expected_path"])

    n_lines = out.count("\n")
    click.secho(f"{poc['expected_path'].name} atualizado ({n_lines} linhas)",
                fg="green")
    click.echo(f"Arquivo: {poc['expected_path']}")
    click.echo("Verifique o diff antes de commitar: git diff")

def _parse_engine_error(stderr: str, poc: dict) -> str:
    """Extrai SyntaxError/Traceback path do stderr do engine."""
    for line in stderr.splitlines():
        m = re.search(r'File "([^"]+)", line (\d+)', line)
        if m:
            return f"  arquivo: {m.group(1)}\n  linha:   {m.group(2)}"
        m = re.search(r'(\S+\.py)["\s,]+line (\d+)', line)
        if m:
            return f"  arquivo: {m.group(1)}\n  linha:   {m.group(2)}"
    return f"  arquivo: {poc['dir'] / poc['engine'].name}"

if __name__ == "__main__":
    retro_forward_group()

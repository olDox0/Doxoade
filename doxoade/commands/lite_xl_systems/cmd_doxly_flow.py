# doxoade/commands/lite_xl_systems/cmd_doxly_flow.py
"""🌊 DOXLY FLOW — Rastreador de ativação e invariantes (CLI V3.0)."""
import json
import time
import click
from datetime import datetime
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style


# ═══════════════════════════════════════════════════════════════════
# PARSERS DEFENSIVOS
# ═══════════════════════════════════════════════════════════════════
def _as_dict(value, default=None):
    default = default if default is not None else {}
    if value is None:
        return default
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s or s == "null":
            return default
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else default
        except (json.JSONDecodeError, TypeError, ValueError):
            return default
    return default


def _as_list(value, default=None):
    default = default if default is not None else []
    if value is None:
        return default
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s or s == "null":
            return default
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, list) else default
        except (json.JSONDecodeError, TypeError, ValueError):
            return default
    return default


def _load_events(flow_file: Path) -> list:
    events = []
    if not flow_file.exists():
        return events
    for line in flow_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            pass
    return events


def _parse_hhmm(s: str):
    """Retorna timestamp de hoje em HH:MM ou None."""
    try:
        h, m = s.strip().split(":")[:2]
        now = datetime.now()
        return datetime(now.year, now.month, now.day,
                        int(h), int(m)).timestamp()
    except (ValueError, TypeError):
        return None


def _is_aot_unresolved(src: str) -> bool:
    """Detecta se `src` é bytecode AOT não-mapeável (tmpXXX.lua)."""
    if not src:
        return False
    s = str(src).lower()
    return s.startswith("tmp") and s.endswith(".lua")


# ═══════════════════════════════════════════════════════════════════
# FILTRAGEM
# ═══════════════════════════════════════════════════════════════════
def _apply_filters(events, *, template, mark_only, key, cmd_name,
                   errors_only, repairs_only, since):
    out = events
    if errors_only:
        out = [e for e in out if e.get("phase") in ("ERR", "ERROR")]
    if repairs_only:
        out = [e for e in out if e.get("phase") == "REPAIR"]
    if mark_only:
        out = [e for e in out if e.get("phase") == "MARK"]
    if template:
        t = template.lower()
        out = [e for e in out if t in str(e.get("src", "")).lower()]
    if key:
        k = key.lower().strip().replace(" ", "")
        filtered = []
        for e in out:
            info = _as_dict(e.get("info"))
            e_key = str(info.get("key", "")).lower().replace(" ", "")
            e_cmd = str(e.get("cmd", "")).lower()
            if k in e_key or k in e_cmd:
                filtered.append(e)
        out = filtered
    if cmd_name:
        c = cmd_name.lower().strip()
        out = [e for e in out if c in str(e.get("cmd", "")).lower()]
    if since:
        ts_min = _parse_hhmm(since)
        if ts_min:
            out = [e for e in out if (e.get("ts") or 0) >= ts_min]
    return out


# ═══════════════════════════════════════════════════════════════════
# RENDERIZAÇÃO
# ═══════════════════════════════════════════════════════════════════
def _render_event(e: dict):
    try:
        ts = e.get("ts", 0)
        time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    except (ValueError, TypeError):
        time_str = "??:??:??"

    phase = e.get("phase", "?")
    cmd_name = e.get("cmd") or "(sem comando)"
    src = e.get("src") or "unknown"
    line = e.get("line") or 0
    info = _as_dict(e.get("info"))
    viol = _as_list(e.get("viol"))

    color = {"ERR": Fore.RED, "ERROR": Fore.RED, "REPAIR": Fore.CYAN,
             "MARK": Fore.MAGENTA, "TREE": Fore.BLUE, "KEY": Fore.YELLOW,
             "EXEC": Fore.GREEN}.get(phase, Fore.WHITE)

    print(f"\n{color}[{time_str}] {phase}{Fore.RESET}  "
          f"{Style.BRIGHT}{cmd_name}{Style.RESET_ALL}")

    if src != "unknown" and src:
        print(f"  {Fore.WHITE}Origem:{Fore.RESET} "
              f"{Fore.CYAN}{src}:{line}{Fore.RESET}")

    if info.get("key"):
        print(f"  {Fore.WHITE}Key   :{Fore.RESET} {info['key']}")

    if info.get("details"):
        print(f"  {Fore.WHITE}Detalhe:{Fore.RESET} {info['details']}")

    if info.get("ms") is not None:
        try:
            ms = float(info["ms"])
            c = Fore.GREEN if ms < 16 else (Fore.YELLOW if ms < 50 else Fore.RED)
            print(f"  {Fore.WHITE}Tempo :{Fore.RESET} {c}{ms:.2f}ms{Fore.RESET}")
        except (ValueError, TypeError):
            pass

    pre = e.get("pre") or ""
    post = e.get("post") or ""
    if pre and pre != post:
        print(f"  {Fore.WHITE}Pre   :{Fore.RESET} {pre}")
        print(f"  {Fore.WHITE}Post  :{Fore.RESET} {post}")

    if viol:
        print(f"  {Fore.RED}⚠ Invariantes ({len(viol)}):{Fore.RESET}")
        for v in viol:
            if not isinstance(v, dict):
                continue
            fix = f" {Fore.GREEN}[auto-fix]{Fore.RESET}" if v.get("fix") else ""
            print(f"    {Fore.RED}├─ {v.get('node', '?')}: "
                  f"{v.get('inv', '?')}{Fore.RESET}{fix}")

    if phase == "ERR" and info.get("err"):
        print(f"  {Fore.RED}Erro: {info['err']}{Fore.RESET}")
    if info.get("msg"):
        print(f"  {Fore.RED}Msg : {info['msg']}{Fore.RESET}")


def _render_audit(events, flow_file: Path):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🌊 AUDITORIA DE INVARIANTES + REPAROS{Style.RESET_ALL}\n")

    total = len(events)
    by_phase = {}
    viol_by_node = {}
    for e in events:
        p = e.get("phase", "?")
        by_phase[p] = by_phase.get(p, 0) + 1
        for v in _as_list(e.get("viol")):
            if not isinstance(v, dict):
                continue
            viol_by_node.setdefault(v.get("node", "?"), []).append({
                "cmd": e.get("cmd"),
                "inv": v.get("inv", "?"),
                "ts": e.get("ts"),
                "src": f"{e.get('src', '?')}:{e.get('line', 0)}",
            })

    print(f"  {Fore.WHITE}Eventos totais :{Fore.RESET} {total}")
    for p, n in sorted(by_phase.items()):
        c = {"EXEC": Fore.GREEN, "ERR": Fore.RED, "ERROR": Fore.RED,
             "REPAIR": Fore.CYAN, "MARK": Fore.MAGENTA,
             "KEY": Fore.YELLOW, "TREE": Fore.BLUE}.get(p, Fore.WHITE)
        print(f"  {Fore.WHITE}{p:<10}{Fore.RESET} {c}{n}{Fore.RESET}")
    print(f"  {Fore.WHITE}Nós c/ violação:{Fore.RESET} "
          f"{Fore.RED if viol_by_node else Fore.GREEN}"
          f"{len(viol_by_node)}{Fore.RESET}\n")

    if not viol_by_node and by_phase.get("REPAIR", 0) == 0:
        print(f"  {Fore.GREEN}✔ Árvore íntegra.{Fore.RESET}\n")
        return

    for node, viols in viol_by_node.items():
        print(f"  {Fore.RED}▶ {node}{Fore.RESET} ({len(viols)}×)")
        for v in viols[-3:]:
            try:
                t = datetime.fromtimestamp(v.get("ts") or 0).strftime("%H:%M:%S")
            except (ValueError, TypeError):
                t = "??"
            print(f"    {Fore.LIGHTBLACK_EX}[{t}]{Fore.RESET} "
                  f"{v['cmd']} ({v['src']}) → {v['inv']}")
    print()


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════
@click.command("flow")
@click.option("--template", "-t", default=None,
              help="Filtra por template (ex: 05_split_mover)")
@click.option("--mark", "mark_only", is_flag=True,
              help="Só eventos MARK (instrumentação manual)")
@click.option("--tail", is_flag=True,
              help="Modo tail (streaming ao vivo)")
@click.option("--since", default=None,
              help="Filtra por timestamp mínimo (formato HH:MM)")
@click.option("--key", "-k", default=None, help="Filtra por tecla (ex: ctrl+l)")
@click.option("--cmd", "cmd_name", "-c", default=None,
              help="Filtra por comando (fuzzy match)")
@click.option("--last", "-n", default=10, type=int, help="Últimas N")
@click.option("--audit", is_flag=True, help="Auditoria completa")
@click.option("--errors-only", "-e", is_flag=True, help="Só erros")
@click.option("--repairs-only", "-r", is_flag=True, help="Só reparos")
@click.option("--mode", "-m",
              type=click.Choice(["production", "test", "sandbox"]),
              default="production")
@click.option("--fresh", is_flag=True,
              help="Limpa o trace antes de executar (útil pós-deploy)")
def cmd_flow(template, mark_only, tail, since, key, cmd_name, fresh,
             last, audit, errors_only, repairs_only, mode):
    """🌊 Rastreia ativação de features, invariantes e origem de erros."""
    from doxoade.commands.lite_xl_systems.typhon_deploy import TyphonDeployEngine

    target = TyphonDeployEngine._get_deploy_dir(mode)
    flow_file = target / ".doxoade" / "diagnostics" / "flow_trace.ndjson"

    init_file = target / "init.lua"
    if init_file.exists():
        try:
            if init_file.read_bytes()[:4].startswith(b"\x1bLua"):
                click.echo(f"{Fore.MAGENTA}ℹ Init em AOT bytecode — tracebacks não resolvem. "
                           f"Use `deploy production --no-khonsu` para debug.{Fore.RESET}\n")
        except OSError:
            pass

    if not flow_file.exists():
        click.echo(f"{Fore.YELLOW}⚠ Sem trace em {flow_file}{Fore.RESET}\n"
                   f"  {Fore.LIGHTBLACK_EX}Execute algo na IDE primeiro.{Fore.RESET}")
        return

    if fresh:
        flow_file.unlink(missing_ok=True)
        click.echo(f"{Fore.GREEN}✔ Trace limpo. Aguardando novos eventos...{Fore.RESET}")
        return

    # ── TAIL MODE ────────────────────────────────────────────────
    if tail:
        seen = len(_load_events(flow_file))
        click.echo(f"{Fore.CYAN}⏳ Tail mode (Ctrl+C para sair){Fore.RESET}")
        try:
            while True:
                time.sleep(0.5)
                all_events = _load_events(flow_file)
                for e in all_events[seen:]:
                    e = e  # local variable binding
                    filtered = _apply_filters(
                        [e], template=template, mark_only=mark_only,
                        key=key, cmd_name=cmd_name,
                        errors_only=errors_only, repairs_only=repairs_only,
                        since=since)
                    if filtered:
                        _render_event(e)
                seen = len(all_events)
        except KeyboardInterrupt:
            click.echo()
        return

    # ── MODO NORMAL ──────────────────────────────────────────────
    events = _load_events(flow_file)
    if not events:
        click.echo(f"{Fore.YELLOW}⚠ Arquivo vazio.{Fore.RESET}")
        return

    filtered = _apply_filters(
        events, template=template, mark_only=mark_only,
        key=key, cmd_name=cmd_name,
        errors_only=errors_only, repairs_only=repairs_only, since=since)

    if audit:
        _render_audit(filtered, flow_file)
        return

    if not filtered:
        click.echo(f"{Fore.LIGHTBLACK_EX}Nenhum evento corresponde ao filtro.{Fore.RESET}")
        return

    for e in filtered[-last:]:
        try:
            _render_event(e)
        except Exception as ex:
            click.echo(f"{Fore.RED}⚠ Erro renderizando: {ex}{Fore.RESET}")
    click.echo()

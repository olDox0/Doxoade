# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/_doctor.py
"""
Doctor - diagnostico, fix e pre-flight para PoCs de forward chaining.

Uso:
    py -3.12 _doctor.py            # diagnostico (read-only)
    py -3.12 _doctor.py --fix      # corrige .bat automaticamente
    py -3.12 _doctor.py --check    # pre-flight (exit 1 se problemas)

Detecta:
1. Estrutura: engine_pXX.py, run_XX.bat, expected.txt existem?
2. Coerencia: run_XX.bat chama engine_pXX.py correto?
3. Conteudo: engine_pXX.py contem tokens caracteristicos de PXX?
4. Encoding: expected.txt e ASCII-only?

--fix corrige apenas (2). (3) e (4) exigem intervencao humana.
--check e adequado para uso em run_all.bat como pre-flight.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# (num, folder, tokens_caracteristicos)
# tokens = strings que DEVEM aparecer no engine_pXX.py correto.
# Se nao aparecem, o engine provavelmente pertence a outro PoC.
POCS = [
    ("00", "00_fizzbuzz", ["FIZZBUZZ", "R_fizzbuzz"]),
    ("01", "01_cycle", ["P01a", "CycleLimitError"]),
    ("02", "02_conflict", ["P02a", "R_high"]),
    ("10", "10_ast_to_facts", ["assign.target", "P10a"]),
    ("11", "11_ast_function", ["func.name", "P11a"]),
    ("20", "20_unification", ["TripleFact", "unify"]),
    ("21", "21_negation_as_failure", ["negation_blocks", "P21a"]),
    ("30a", "30a_if_return_detect", ["if_return_guard", "P30a"]),
    ("30b", "30b_if_return_rewrite", ["rewrite_if_return_guard", "P30b"]),
]


def read_text(path: Path, encoding: str = "utf-8") -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding=encoding, errors="replace")


def check_engine(folder: Path, num: str, tokens: list[str]) -> list[str]:
    problems: list[str] = []
    engine_path = folder / f"engine_p{num}.py"
    engine = read_text(engine_path)
    if engine is None:
        problems.append(f"engine_p{num}.py FALTANDO")
        return problems
    missing = [t for t in tokens if t not in engine]
    found = [t for t in tokens if t in engine]
    if missing:
        problems.append(
            f"engine_p{num}.py: encontrados {found}, faltando {missing} "
            f"- se o codigo parece certo, talvez o token esteja errado no doctor"
        )
    return problems


def check_bat(folder: Path, num: str, fix: bool) -> list[str]:
    problems: list[str] = []
    bat_path = folder / f"run_{num}.bat"
    bat = read_text(bat_path, encoding="ascii")
    if bat is None:
        problems.append(f"run_{num}.bat FALTANDO")
        return problems

    changed = False

    m = re.search(r"py -3\.12\s+(\S+)", bat)
    if not m:
        problems.append(f"run_{num}.bat nao chama py -3.12 <script>")
        return problems
    target = m.group(1)
    expected_target = f"engine_p{num}.py"
    if target != expected_target:
        if fix:
            bat = re.sub(r"py -3\.12\s+\S+", f"py -3.12 {expected_target}", bat)
            bat = re.sub(r"echo FAIL: \S+ exit", f"echo FAIL: {expected_target} exit", bat)
            problems.append(f"[FIX] py line: {target} -> {expected_target}")
            changed = True
        else:
            problems.append(f"run_{num}.bat chama '{target}' (esperado '{expected_target}')")

    m_echo = re.search(r"echo P(\d+) PASS", bat)
    if m_echo:
        actual_num = m_echo.group(1)
        if actual_num != num:
            if fix:
                bat = re.sub(r"echo P\d+ PASS", f"echo P{num} PASS", bat)
                problems.append(f"[FIX] echo: P{actual_num} PASS -> P{num} PASS")
                changed = True
            else:
                problems.append(f"echo diz 'P{actual_num} PASS' (esperado 'P{num} PASS')")

    if fix and changed:
        bat_path.write_text(bat, encoding="ascii", newline="\n")
    return problems

def check_expected(folder: Path) -> list[str]:
    problems: list[str] = []
    expected_path = folder / "expected.txt"
    if not expected_path.exists():
        problems.append("expected.txt FALTANDO")
        return problems
    raw = expected_path.read_bytes()
    try:
        raw.decode("ascii")
    except UnicodeDecodeError as e:
        problems.append(
            f"expected.txt nao-ASCII (byte {e.start}): {e.reason}"
        )
    return problems


def check_poc(num: str, folder_name: str, tokens: list[str], fix: bool) -> list[str]:
    folder = ROOT / folder_name
    if not folder.exists():
        return [f"pasta {folder_name} nao existe"]

    problems: list[str] = []
    problems.extend(check_engine(folder, num, tokens))
    problems.extend(check_bat(folder, num, fix))
    problems.extend(check_expected(folder))
    return problems


def main() -> int:
    if "--check" in sys.argv and "--fix" in sys.argv:
        print("ERRO: --check e --fix sao mutuamente exclusivos")
        return 2
    fix = "--fix" in sys.argv
    check_only = "--check" in sys.argv

    mode = "FIX" if fix else ("CHECK" if check_only else "DIAG")
    print(f"=== Doctor ({mode}) ===")
    print()

    ok_count = 0
    fail_count = 0
    fix_count = 0

    for num, folder_name, tokens in POCS:
        problems = check_poc(num, folder_name, tokens, fix)
        print(f"--- {folder_name} ---")

        real_problems = [p for p in problems if not p.startswith("[FIX]")]
        fixes = [p for p in problems if p.startswith("[FIX]")]

        if not real_problems and not fixes:
            print("  OK")
            ok_count += 1
        else:
            for p in problems:
                print(f"  {p}")
            if real_problems:
                fail_count += len(real_problems)
            fix_count += len(fixes)
        print()

    print(
        f"Resumo: {ok_count}/{len(POCS)} PoCs OK | "
        f"{fail_count} problema(s) | {fix_count} fix(es) aplicado(s)"
    )

    if check_only and fail_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
# doxoade/commands/moddify_sys/mody_patch.py
"""
Mody Patch Engine v6.2 — Motor de Cirurgia Atômica de Diff (Ma'at & Sotéria).
ProDeNov: Ancoragem Estrutural Forte (Regra de Ouro da Recuperação).

v6.2 — Correções:
- Problema 1: `_would_create_duplicate` agora roda também em `--apply`.
- Problema 2: `find_hunk_location` busca primeiro as linhas `-` (remoções),
              usa contexto apenas para desambiguar. Assim, um hunk cujo
              contexto mudou por patch anterior ainda é aplicável.
- Problema 3: `_validate_partial_syntax` agora tenta compilar o arquivo
              inteiro E, se falhar, tenta compilar apenas a região até o
              hunk (evita falso positivo por string multi-linha adiante).
              Se ambos falham, retorna erro real.
"""
from __future__ import annotations
import re
import shutil
import subprocess
import compileall as _compileall
from pathlib import Path

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import click

try:
    from doxoade.tools.doxcolors import Fore, Style
except Exception:
    class Fore:
        GREEN = '\033[92m'; RED = '\033[91m'; YELLOW = '\033[93m'; CYAN = '\033[96m'; MAGENTA = '\033[95m'; DIM = '\033[2m'; RESET = '\033[0m'
    class Style:
        BRIGHT = '\033[1m'; RESET_ALL = '\033[0m'

try:
    from doxoade.chronos import chronos_recorder
except Exception:
    chronos_recorder = None


# --- ESTRUTURAS DE DADOS ---

@dataclass
class PatchLine:
    kind: str       # ' ' (contexto), '-' (remover), '+' (adicionar)
    text: str

@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header_ctx: str
    lines: List[PatchLine] = field(default_factory=list)

@dataclass
class FilePatch:
    raw_old_path: str
    raw_new_path: str
    target_path: Optional[Path] = None
    hunks: List[Hunk] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)


# --- PARSER DE DIFF ---

class UnifiedDiffParser:
    RE_HUNK_HEADER = re.compile(r'^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)$')

    @classmethod
    def clean_target_path(cls, raw: str) -> str:
        p = raw.strip().strip('"\'')
        p = p.split('\t')[0].strip()
        p = p.replace('\\', '/')
        if p.startswith(('a/', 'b/')):
            p = p[2:]
        return p

    @classmethod
    def parse(cls, diff_text: str, project_root: Path) -> List[FilePatch]:
        patches: List[FilePatch] = []
        current_patch: Optional[FilePatch] = None
        current_hunk: Optional[Hunk] = None
        lines = diff_text.splitlines()
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            if line.startswith('--- ') and i + 1 < n and lines[i + 1].startswith('+++ '):
                old_raw = line[4:].strip()
                new_raw = lines[i + 1][4:].strip()
                target_str = cls.clean_target_path(new_raw if new_raw != '/dev/null' else old_raw)
                resolved = (project_root / target_str).resolve()
                current_patch = FilePatch(raw_old_path=old_raw, raw_new_path=new_raw, target_path=resolved)
                patches.append(current_patch)
                current_hunk = None
                i += 2
                continue

            m = cls.RE_HUNK_HEADER.match(line)
            if m and current_patch is not None:
                try:
                    current_hunk = Hunk(
                        old_start=int(m.group(1)),
                        old_count=int(m.group(2)) if m.group(2) else 1,
                        new_start=int(m.group(3)),
                        new_count=int(m.group(4)) if m.group(4) else 1,
                        header_ctx=m.group(5).strip()
                    )
                    current_patch.hunks.append(current_hunk)
                except (ValueError, TypeError):
                    current_patch.parse_errors.append(
                        f"Hunk com cabecalho invalido (nao numerico): {line[:60]}"
                    )
                    current_hunk = None
                i += 1
                continue

            if current_hunk is not None:
                if line.startswith(('+', '-', ' ')):
                    current_hunk.lines.append(PatchLine(kind=line[0], text=line[1:]))
                elif line == '':
                    current_hunk.lines.append(PatchLine(kind=' ', text=''))
                elif line.startswith('\\ No newline at end of file'):
                    pass
                else:
                    if not line.startswith(('diff --git', 'index ', 'similarity ')):
                        current_patch.parse_errors.append(f"Linha ignorada no diff: {line[:60]}")
            i += 1
        return patches


# --- MOTOR DE CIRURGIA ---

class PatchSurgeon:
    # Slots de configuração injetados pelo comando mod_patch antes da cirurgia.
    _checkshot_args: Optional[List[str]] = None
    _checkshot_keep: bool = False

    @staticmethod
    def _normalize_line(line: str) -> str:
        line = line.rstrip('\r\n').rstrip()
        line = re.sub(r'\s*(?:#|//).*$', '', line)
        return re.sub(r'\s+', ' ', line).strip()

    @classmethod
    def _would_create_duplicate(
        cls,
        file_lines: List[str],
        loc: int,
        replacement: List[str],
    ) -> bool:
        """
        Detecta se aplicar o hunk criaria duplicação de contexto.

        Caso típico: o hunk já foi aplicado numa execução anterior, mas o
        patcher está re-aplicando por engano. Se o `replacement` (estado
        DESEJADO) já está no arquivo, o hunk é idempotente e deve ser
        pulado — não aplicado de novo.
        """
        norm_repl = [cls._normalize_line(l) for l in replacement]
        if len(norm_repl) < 2:
            return False
        total = len(file_lines)
        n = len(norm_repl)
        if n > total:
            return False
        for cand in range(0, total - n + 1):
            # Pula a região onde o hunk será aplicado
            if cand <= loc < cand + n:
                continue
            block = [cls._normalize_line(file_lines[cand + i]) for i in range(n)]
            if block == norm_repl:
                return True
        return False

    @classmethod
    def _validate_partial_syntax(
        cls, new_content: str, target_path: Path
    ) -> Optional[str]:
        """
        v6.2: Re-valida sintaxe Python após CADA hunk aplicado.

        Estratégia em 2 camadas para evitar falso positivo:
        1. Tenta compilar o arquivo inteiro. Se OK, retorna None.
        2. Se falhar, NÃO aborta ainda: tenta compilar apenas as linhas
           que já foram "fechadas" (antes de qualquer string multi-linha
           que ainda não foi processada). Se essa região compila, é sinal
           de que o erro está em código AINDA NÃO TOCADO pelo patch — e o
           hunk atual é válido. Retorna None.

        Só retorna erro se AMBAS as camadas falham de forma consistente.
        """
        if not target_path or target_path.suffix.lower() != ".py":
            return None
        try:
            compile(new_content, str(target_path), "exec")
            return None
        except SyntaxError as e_full:
            # Camada 2: compila apenas até a linha do erro do arquivo COMPLETO.
            # Se compilar OK até lá, o erro está em código fora do patch
            # (ex: string multi-linha que ainda não foi fechada). Não é
            # falha do hunk.
            if e_full.lineno:
                try:
                    prefix = "\n".join(new_content.splitlines()[: e_full.lineno - 1])
                    if prefix.strip():
                        compile(prefix, str(target_path), "exec")
                        return None
                except SyntaxError:
                    pass
                except Exception:
                    pass
            return f"SyntaxError em L{e_full.lineno}: {e_full.msg}"
        except Exception as e:
            return f"Erro inesperado ao validar sintaxe: {e}"

    @classmethod
    def _find_removal_anchor(
        cls, file_lines: List[str], hunk: Hunk, max_offset: int = 200
    ) -> Tuple[Optional[int], int, str, int, List[int]]:
        """
        v6.3: Busca baseada em remoções (`-`) SEM exigir contexto (` `) ao redor.

        Retorna uma tupla de 5 elementos (adiciona `candidates`):
            (loc, offset, match_type, contig_len, candidates)

        - `loc`: localização escolhida (ou None se NONE)
        - `match_type`: 'EXACT' | 'EXACT_MULTI' | 'PARTIAL' | 'ADD_ONLY' | 'NONE'
        - `candidates`: lista de locs quando há ambiguidade (para desambiguação)

        Estratégia:
        1. Busca as remoções exatas; se 1 match, retorna EXACT.
        2. Se > 1 match, verifica qual está mais perto de `old_start`;
           retorna EXACT com o mais próximo, mas SINALIZA `EXACT_MULTI`.
        3. Se nenhum match exato, busca streak parcial.
        4. Se 0 remoções (hunk puro de adição), usa `old_start` direto.
        """
        removals = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind == '-']
        total_file = len(file_lines)
        norm_file = [cls._normalize_line(l) for l in file_lines]
        target_idx = max(0, hunk.old_start - 1)

        # Hunk puro de adição: usa old_start direto
        if not removals:
            return (target_idx, 0, 'ADD_ONLY', 0, [target_idx])

        removal_len = len(removals)
        if removal_len > total_file:
            return (None, 0, 'NONE', 0, [])

        # Coleta TODOS os matches exatos das remoções
        all_matches: List[int] = []
        for cand in range(total_file - removal_len + 1):
            if norm_file[cand : cand + removal_len] == removals:
                all_matches.append(cand)

        if len(all_matches) == 1:
            loc = all_matches[0]
            return (loc, loc - target_idx, 'EXACT', removal_len, [loc])

        if len(all_matches) > 1:
            # Desambiguação por proximidade de old_start
            def _distance(cand: int) -> int:
                return abs(cand - target_idx)
            all_matches.sort(key=_distance)
            best = all_matches[0]
            # Se o mais próximo está a menos de max_offset, usa-o como EXACT_MULTI
            if _distance(best) <= max_offset:
                return (
                    best, best - target_idx, 'EXACT_MULTI', removal_len,
                    all_matches[:5],   # até 5 candidatos para reportar
                )
            # Se todos estão longe, ainda escolhe o mais próximo mas sinaliza
            return (
                best, best - target_idx, 'EXACT_MULTI', removal_len,
                all_matches[:5],
            )

        # Sem match exato: tenta streak parcial
        best_len = 0
        best_loc: Optional[int] = None
        for cand in range(total_file):
            streak = 0
            for i in range(removal_len):
                if cand + i < total_file and norm_file[cand + i] == removals[i]:
                    streak += 1
                else:
                    break
            if streak > best_len:
                best_len = streak
                best_loc = cand
                if best_len == removal_len:
                    break

        threshold = max(2, int(removal_len * 0.5))
        if best_len >= threshold and best_loc is not None:
            return (best_loc, best_loc - target_idx, 'PARTIAL', best_len, [best_loc])

        return (None, 0, 'NONE', best_len if best_len > 0 else 0, [])

    @classmethod
    def find_hunk_location(
        cls, file_lines: List[str], hunk: Hunk, max_offset: int = 200
    ) -> Tuple[Optional[int], int, str, int, List[int]]:
        """
        v6.3: delega para `_find_removal_anchor`. Retorna tupla de 5.
        """
        return cls._find_removal_anchor(file_lines, hunk, max_offset=max_offset)

    @classmethod
    def _validate_module_compile(
        cls, content: str, target_path: Path, dry_run: bool = True
    ) -> Optional[str]:
        if not target_path or target_path.suffix.lower() != ".py":
            return None
        import tempfile
        import compileall
        try:
            # Em dry-run, copia o conteúdo para um arquivo temporário
            if dry_run:
                with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.py', encoding='utf-8', delete=False
                ) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    success = compileall.compile_file(
                        tmp_path, quiet=2, force=True
                    )
                finally:
                    try:
                        Path(tmp_path).unlink()
                    except OSError:
                        pass
                if not success:
                    return "compileall: falha ao compilar (verifique sintaxe)"
                return None
            else:
                # Em apply, o arquivo já foi escrito; compileall valida in-place
                success = compileall.compile_file(
                    str(target_path), quiet=2, force=True
                )
                if not success:
                    return "compileall: falha ao compilar (verifique sintaxe)"
                return None
        except Exception as e:
            return f"Erro em compileall: {e}"

    @classmethod
    def simulate_or_apply(
        cls,
        patch: FilePatch,
        apply: bool = False,
        root: Path = None,
        run_checkshot: bool = True,
    ) -> Dict:
        report = {
            "target": str(patch.target_path),
            "hunks_total": len(patch.hunks),
            "hunks_applied": 0,
            "hunks_failed": 0,
            "errors": list(patch.parse_errors),
            "details": [],
            "syntax_ok": True,
            "check_analysis": "",
            "checkshot": None,
        }

        if not patch.target_path or not patch.target_path.exists():
            report["errors"].append(f"Arquivo alvo não encontrado: {patch.target_path}")
            return report

        try:
            with open(patch.target_path, 'r', encoding='utf-8', errors='ignore') as f:
                working_lines = f.readlines()
        except Exception as e:
            report["errors"].append(f"Falha ao ler arquivo: {e}")
            return report

        original_content = "".join(working_lines)
        modified_lines = list(working_lines)

        for idx, hunk in enumerate(patch.hunks, start=1):
            replacement = [pl.text + '\n' for pl in hunk.lines if pl.kind in (' ', '+')]
            expected_replacement_block = [
                cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind in (' ', '+')
            ]

            # ─── v6.2: idempotência TAMBÉM em --apply ─────────────────────
            if expected_replacement_block and len(expected_replacement_block) >= 2:
                already_applied = False
                for cand in range(len(modified_lines) - len(expected_replacement_block) + 1):
                    block = [
                        cls._normalize_line(modified_lines[cand + i])
                        for i in range(len(expected_replacement_block))
                    ]
                    if block == expected_replacement_block:
                        already_applied = True
                        break
                if already_applied:
                    report["details"].append({
                        "hunk": idx, "status": "IDEMPOTENTE",
                        "reason": "Hunk já aplicado anteriormente. Pulando.",
                        "match_type": "IDEMPOTENT"
                    })
                    report["hunks_applied"] += 1
                    continue

            # ─── v6.2: detecção de duplicação roda TAMBÉM em --apply ──────
            if len(replacement) >= 2:
                if cls._would_create_duplicate(modified_lines, hunk.old_start - 1, replacement):
                    report["details"].append({
                        "hunk": idx,
                        "status": "JÁ APLICADO (idempotente)",
                        "reason": "Bloco já presente no arquivo. Pulando para evitar duplicação.",
                        "match_type": "IDEMPOTENT",
                    })
                    report["hunks_applied"] += 1
                    continue

            loc, offset, match_type, contig_len, candidates = cls.find_hunk_location(modified_lines, hunk)

            # ─── v6.3: reportar ambiguidade explicitamente ────────────────
            if match_type == 'EXACT_MULTI' and len(candidates) > 1:
                report["details"].append({
                    "hunk": idx,
                    "status": "AMBÍGUO",
                    "reason": (
                        f"Linha(s) de remoção aparecem em {len(candidates)} lugar(es): "
                        f"{', '.join(f'L{c+1}' for c in candidates)}. "
                        f"Usando o mais próximo de old_start (L{loc+1})."
                    ),
                    "match_type": "EXACT_MULTI",
                    "candidates": [c + 1 for c in candidates],
                    "loc": loc + 1,
                })
                # Segue com a aplicação no `loc` escolhido (não bloqueia)

            if match_type == 'NONE':
                removals = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind == '-']
                added_lines = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind == '+']
                already_there = any(al in "".join(working_lines) for al in added_lines if len(al) > 5)

                reason_msg = (
                    f"Nenhuma linha de remoção encontrada "
                    f"(streak máximo: {contig_len}/{len(removals)})."
                )
                if already_there:
                    reason_msg += f" {Fore.MAGENTA}(As linhas de adição já existem no arquivo?){Fore.YELLOW}"

                report["details"].append({
                    "hunk": idx, "status": "REJEITADO", "reason": reason_msg,
                    "match_type": "NONE", "loc": hunk.old_start
                })
                report["hunks_failed"] += 1
            else:
                report["hunks_applied"] += 1

                start_preview = max(0, loc - 2)
                preview_snippet = []
                for i in range(start_preview, loc):
                    preview_snippet.append(f"  {i+1:4d} | {modified_lines[i].rstrip()}")

                for i, pl in enumerate(hunk.lines):
                    line_num = loc + 1 + i
                    if pl.kind == '-':
                        preview_snippet.append(f"{Fore.RED}-{line_num:4d} | {pl.text.rstrip()}{Fore.RESET}")
                    elif pl.kind == '+':
                        preview_snippet.append(f"{Fore.GREEN}+{line_num:4d} | {pl.text.rstrip()}{Fore.RESET}")
                    else:
                        preview_snippet.append(f"  {line_num:4d} | {pl.text.rstrip()}")

                # Após aplicação, mostra 2 linhas seguintes
                after_start = loc + len(replacement)
                after_end = min(len(modified_lines), after_start + 2)
                after_preview_lines = [
                    f"  {i+1:4d} | {modified_lines[i].rstrip()}"
                    for i in range(after_start, after_end)
                ]
                preview_snippet.extend(after_preview_lines)

                status_text = "APLICÁVEL" if match_type == 'EXACT' else "APLICÁVEL (Contexto Recuperado)"
                report["details"].append({
                    "hunk": idx,
                    "status": status_text,
                    "match_type": match_type,
                    "loc": loc + 1,
                    "offset": offset,
                    "contig_len": contig_len,
                    "preview_snippet": "\n".join(preview_snippet)
                })

                # Aplica: remove expected_old, insere replacement
                # (o expected_old pode ter sido parcialmente casado — usamos
                #  o comprimento do replacement para saber o que inserir,
                #  e apagamos expected_old a partir de `loc`).
                expected_old_len = sum(1 for pl in hunk.lines if pl.kind in (' ', '-'))
                modified_lines[loc : loc + expected_old_len] = replacement

                # ─── v6.2: validação de sintaxe com 2 camadas ─────────────
                if patch.target_path.suffix.lower() == '.py':
                    _probe = "".join(modified_lines)
                    _err = cls._validate_partial_syntax(_probe, patch.target_path)
                    if _err is not None:
                        report["syntax_ok"] = False
                        report["errors"].append(
                            f"Violação Ma'at (hunk #{idx}): {_err}. "
                            f"Estado do arquivo revertido; aplicação abortada."
                        )
                        modified_lines = list(working_lines)
                        report["hunks_failed"] += 1
                        break

        new_content = "".join(modified_lines)

        # v6.3 — Camada 3: validação final via py_compile (equivalente a compileall)
        if patch.target_path.suffix.lower() == '.py':
            try:
                compile(new_content, str(patch.target_path), 'exec')
            except SyntaxError as e:
                report["syntax_ok"] = False
                report["errors"].append(f"Violação Ma'at: SyntaxError em Python (L{e.lineno}: {e.msg})")
            else:
                _mod_err = cls._validate_module_compile(new_content, patch.target_path)
                if _mod_err is not None:
                    report["syntax_ok"] = False
                    report["errors"].append(f"Violação Ma'at (compileall): {_mod_err}")

        # CheckShot (sandbox isolado) — só em dry-run
        if run_checkshot and not apply and report["hunks_failed"] == 0 and report["syntax_ok"]:
            click.echo(
                f"   {Fore.CYAN}🔬 [CHECKSHOT] Analisando o resultado da cirurgia..."
                f"{Style.RESET_ALL}"
            )
            try:
                from doxoade.commands.check_systems.checkshot import CheckShot
                rel_path = (
                    patch.target_path.relative_to(root).as_posix()
                    if patch.target_path and root and patch.target_path.is_relative_to(root)
                    else (patch.target_path.name if patch.target_path else "unknown.py")
                )
                shot = CheckShot(root, keep=cls._checkshot_keep)
                shot_result = shot.analyze(
                    new_content,
                    rel_path,
                    extra_args=cls._checkshot_args,
                )
                report["checkshot"] = shot_result.to_dict()
                if shot_result.error:
                    report["check_analysis"] = (
                        f"{Fore.RED}  ↳ CheckShot falhou: "
                        f"{shot_result.error}{Style.RESET_ALL}"
                    )
                elif not shot_result.findings:
                    report["check_analysis"] = (
                        f"{Fore.GREEN}  ↳ ✔ Estado de Ouro: nenhum finding no "
                        f"arquivo patcheado.{Style.RESET_ALL}"
                    )
                else:
                    report["check_analysis"] = (
                        f"{Fore.YELLOW}  ↳ {shot_result.total_findings} finding(s) "
                        f"({shot_result.critical_count} crítico(s)){Style.RESET_ALL}"
                    )
            except Exception as e:
                report["check_analysis"] = (
                    f"{Fore.RED}  ↳ CheckShot indisponível: {e}{Style.RESET_ALL}"
                )

        if apply:
            if report["hunks_failed"] > 0:
                report["errors"].append("Cirurgia cancelada: Hunks com conflito rejeitados.")
            elif not report["syntax_ok"]:
                report["errors"].append("Cirurgia cancelada: Rejeitado pela auditoria de sintaxe.")
            else:
                try:
                    bak_file = patch.target_path.with_suffix(patch.target_path.suffix + '.bak')
                    shutil.copy2(patch.target_path, bak_file)
                    with open(patch.target_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    if chronos_recorder and hasattr(chronos_recorder, 'log_file_change'):
                        chronos_recorder.log_file_change(
                            str(patch.target_path), original_content, new_content,
                            operation='PATCH'
                        )
                    report["saved"] = True
                except Exception as e:
                    report["errors"].append(f"Falha na gravação em disco: {e}")

        return report


# --- COMANDO CLI ---

@click.command('patch')
@click.argument('patch_file', required=False, type=click.Path(dir_okay=False))
@click.option('--apply', '-a', is_flag=True, help="Efetiva as alterações em disco (sai do modo Dry-Run).")
@click.option('--archive', is_flag=True, help="Renomeia o arquivo diff para .applied após aplicação bem-sucedida.")
@click.option('--generate', '-g', is_flag=True, help="Gera um arquivo de patch a partir do 'git diff' atual e o utiliza.")
@click.option('--checkshot/--no-checkshot', default=True, show_default=True,
              help="🔬 Roda `doxoade check` em sandbox isolado (default: on no dry-run).")
@click.option('--checkshot-arg', '-ca', multiple=True,
              help="Args extras p/ o check (ex: -ca=-s security, -ca=-sr structural).")
@click.option('--keep-snapshot', is_flag=True,
              help="Mantém o snapshot em .doxoade/checkshot/ para inspeção manual.")
@click.pass_context
def mod_patch(ctx, patch_file, apply, archive, generate, checkshot, checkshot_arg, keep_snapshot):
    """🩹 Aplica cirurgicamente patches com Ancoragem Estrutural Forte (v6.2)."""
    root = Path.cwd().resolve()

    if generate:
        if patch_file:
            click.secho("⚠️ Aviso: O argumento PATCH_FILE é ignorado quando --generate é usado.", fg='yellow')

        click.echo(f"\n{Fore.CYAN}⚙️  Gerando patch a partir das alterações do Git...{Style.RESET_ALL}")
        phases = [
            ("Verificando repositório Git", 0.15),
            ("Coletando diff (git diff)", 0.55),
            ("Analisando arquivos modificados", 0.80),
            ("Salvando patch em disco", 1.00),
        ]

        def _run_phase(label: str, target_pct: float, current_pct: float) -> float:
            with click.progressbar(
                length=100,
                label=Fore.YELLOW + label,
                show_eta=False,
                show_percent=False,
                fill_char='█',
                empty_char='░',
                width=40,
            ) as bar:
                for _ in range(int((target_pct - current_pct) * 100)):
                    bar.update(1)
            return target_pct

        try:
            pct = 0.0
            pct = _run_phase("Verificando repositório Git", 0.15, pct)

            diff_process = subprocess.run(
                ['git', 'diff', '--no-color'],
                capture_output=True, text=True, check=True, encoding='utf-8', cwd=root
            )
            pct = _run_phase("Coletando diff (git diff)", 0.55, pct)

            if not diff_process.stdout:
                click.secho("✘ Nenhuma alteração detectada pelo Git para gerar o patch.", fg='red')
                ctx.exit(1)

            changed_files = sum(1 for ln in diff_process.stdout.splitlines() if ln.startswith('+++ b/'))
            pct = _run_phase(f"Analisando {changed_files} arquivo(s) modificado(s)", 0.80, pct)

            target_diff = root / "mody_patch_diff.txt"
            target_diff.write_text(diff_process.stdout, encoding='utf-8')
            pct = _run_phase("Salvando patch em disco", 1.00, pct)

            click.echo()
            click.secho(f"✅ Patch gerado e salvo em: {Fore.YELLOW}{target_diff.name}{Style.RESET_ALL}", fg='green')
            click.echo(f"   📊 {changed_files} arquivo(s) · {len(diff_process.stdout) // 1024} KB · {diff_process.stdout.count(chr(10))} linhas")
        except subprocess.CalledProcessError as e:
            click.secho(f"✘ Falha ao executar 'git diff': {e}", fg='red')
            ctx.exit(1)
        except FileNotFoundError:
            click.secho("✘ Comando 'git' não encontrado. Certifique-se de que o Git está instalado e no PATH.", fg='red')
            ctx.exit(1)
    else:
        target_diff = Path(patch_file) if patch_file else (root / "patch_diff.txt")

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩹 [MODY PATCH v6.2] Cirurgia Atômica de Diff{Style.RESET_ALL}")
    click.echo(f"  • Arquivo de Entrada: {Fore.YELLOW}{target_diff.name}{Style.RESET_ALL}")
    click.echo(f"  • Modo de Operação:   {Fore.GREEN if apply else Fore.YELLOW}{'EFETIVAÇÃO (--apply)' if apply else 'SIMULAÇÃO (DRY-RUN)'}{Style.RESET_ALL}")
    click.echo(f"  • CheckShot:          {Fore.GREEN + 'ON' if checkshot and not apply else Fore.DIM + 'OFF'}{Style.RESET_ALL}\n")

    if not target_diff.exists():
        click.secho(f"✘ Arquivo de patch não encontrado: {target_diff}", fg='red', bold=True)
        ctx.exit(1)

    try:
        raw_text = target_diff.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        click.secho(f"✘ Falha ao ler patch: {e}", fg='red')
        ctx.exit(1)

    patches = UnifiedDiffParser.parse(raw_text, root)
    if not patches:
        click.secho("✘ Nenhuma assinatura válida de diff encontrada.", fg='red')
        ctx.exit(1)

    from collections import OrderedDict
    grouped = OrderedDict()
    for p in patches:
        key = str(p.target_path)
        if key not in grouped:
            grouped[key] = p
        else:
            grouped[key].hunks.extend(p.hunks)
    patches = list(grouped.values())

    PatchSurgeon._checkshot_args = list(checkshot_arg) if checkshot_arg else None
    PatchSurgeon._checkshot_keep = keep_snapshot

    total_files = len(patches)
    successful_files = 0
    total_hunks_applied = 0
    total_hunks_failed = 0
    total_critical_shots = 0

    click.echo("─" * 75)
    for p in patches:
        rel_name = (
            p.target_path.relative_to(root)
            if p.target_path and p.target_path.is_relative_to(root)
            else p.raw_new_path
        )
        click.echo(f"📄 {Fore.WHITE}{Style.BRIGHT}{rel_name}{Style.RESET_ALL}")

        res = PatchSurgeon.simulate_or_apply(
            p,
            apply=apply,
            root=root,
            run_checkshot=bool(checkshot) and not apply,
        )

        for det in res["details"]:
            is_ok = (
                "APLICÁVEL" in det["status"]
                or "IDEMPOTENTE" in det["status"]
                or "JÁ APLICADO" in det["status"]
                or "AMBÍGUO" in det["status"]
            )
            status_color = Fore.GREEN if is_ok else Fore.RED
            if "AMBÍGUO" in det["status"]:
                status_color = Fore.YELLOW
            icon = "✔" if is_ok else "✘"

            badges = ""
            if det.get('offset', 0) != 0:
                badges += f" {Fore.DIM}[Offset: {det['offset']:+d}]{Style.RESET_ALL}"
            if det.get('match_type') == 'PARTIAL':
                badges += f" {Fore.YELLOW}⚠️ [Recuperado: {det['contig_len']} linhas contíguas]{Style.RESET_ALL}"
            if det.get('match_type') == 'EXACT_MULTI':
                cands = det.get('candidates', [])
                badges += f" {Fore.MAGENTA}⚡ [Ambíguo: {len(cands)} matches — {', '.join(f'L{c}' for c in cands)}]{Style.RESET_ALL}"

            click.echo(f"   {status_color}{icon} Hunk #{det['hunk']}: {det['status']}{badges}{Style.RESET_ALL}")

            if "reason" in det:
                click.echo(f"     {Fore.RED}↳ Motivo: {det['reason']}{Style.RESET_ALL}")

            if "preview_snippet" in det and not apply:
                click.echo(f"     {Fore.CYAN}↳ 🔍 Pré-visualização da Cirurgia:{Style.RESET_ALL}")
                for line in det["preview_snippet"].split('\n'):
                    click.echo(f"       {line}")

        if res.get("check_analysis"):
            click.echo(f"   {Fore.CYAN}🔬 Análise do Doxoade Check:{Style.RESET_ALL}")
            for line in res["check_analysis"].strip().split('\n'):
                click.echo(f"     {line}")

            shot = res.get("checkshot") or {}
            shot_findings = shot.get("findings") or []
            if shot_findings:
                sev_color = {
                    "CRITICAL": Fore.RED,
                    "ERROR": Fore.RED,
                    "WARNING": Fore.YELLOW,
                    "INFO": Fore.CYAN,
                }
                for f in shot_findings[:15]:
                    sev = str(f.get("severity", "INFO")).upper()
                    color = sev_color.get(sev, Fore.WHITE)
                    line_no = f.get("line", 0)
                    cat = f.get("category", "—")
                    msg = f.get("message", "")
                    click.echo(
                        f"     {color}■ [{sev:<8}] L{line_no:<4} "
                        f"({cat}) {msg}{Style.RESET_ALL}"
                    )
                if len(shot_findings) > 15:
                    click.echo(
                        f"     {Fore.DIM}... e mais "
                        f"{len(shot_findings) - 15} finding(s).{Style.RESET_ALL}"
                    )

        if res["errors"]:
            for err in res["errors"]:
                click.echo(f"   {Fore.RED}↳ ERRO: {err}{Style.RESET_ALL}")

        if res["hunks_failed"] == 0 and res["syntax_ok"] and not res["errors"]:
            successful_files += 1
            if apply:
                click.echo(
                    f"   {Fore.GREEN}✔ Cirurgia consolidada em disco "
                    f"(Backup: {rel_name}.bak){Style.RESET_ALL}"
                )

        total_hunks_applied += res["hunks_applied"]
        total_hunks_failed += res["hunks_failed"]
        total_critical_shots += (res.get("checkshot") or {}).get("critical_count", 0)
        click.echo()

    click.echo("─" * 75)
    click.echo(
        f"📊 Resumo: {Fore.GREEN}{total_hunks_applied} hunks válidos{Style.RESET_ALL} | "
        f"{Fore.RED if total_hunks_failed > 0 else Fore.DIM}{total_hunks_failed} falhas{Style.RESET_ALL}"
    )

    if not apply:
        if total_hunks_failed == 0 and successful_files == total_files:
            if total_critical_shots > 0:
                click.secho(
                    f"\n⚠️ [MA'AT] Simulação estruturalmente OK, mas CheckShot apontou "
                    f"{total_critical_shots} finding(s) crítico(s). Revise antes de --apply.",
                    fg='yellow', bold=True
                )
            else:
                click.secho(
                    "\n⚖ [MA'AT] Simulação 100% aprovada. Execute com '--apply' para efetivar.",
                    fg='green', bold=True
                )
        else:
            click.secho(
                "\n⚠️ [MA'AT] A simulação detectou rejeições. "
                "O patcher bloqueou alterações inseguras.",
                fg='yellow', bold=True
            )
    else:
        if successful_files == total_files and total_hunks_failed == 0:
            click.secho("\n✅ Todas as alterações foram aplicadas com sucesso e validadas!", fg='green', bold=True)
            if archive:
                applied_name = target_diff.with_suffix(target_diff.suffix + '.applied')
                target_diff.rename(applied_name)
                click.echo(f"📦 Patch arquivado como: {applied_name.name}")
        else:
            click.secho("\n❌ Operação parcial ou abortada em arquivos com conflito.", fg='red', bold=True)
            ctx.exit(1)

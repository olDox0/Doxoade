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
    is_new_file: bool = False          # v6.4
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
            if not line.startswith(('diff --git', 'index ', 'similarity ', 'new file mode', 'deleted file mode')):
                if line.startswith('--- ') and i + 1 < n and lines[i + 1].startswith('+++ '):
                    old_raw = line[4:].strip()
                    new_raw = lines[i + 1][4:].strip()
                    
                    # v6.4: detectar criação (--- /dev/null)
                    is_new_file = (old_raw == '/dev/null')
                    
                    target_str = cls.clean_target_path(new_raw if new_raw != '/dev/null' else old_raw)
                    resolved = (project_root / target_str).resolve()
                    
                    current_patch = FilePatch(
                        raw_old_path=old_raw,
                        raw_new_path=new_raw,
                        target_path=resolved,
                        is_new_file=is_new_file,   # v6.4
                    )
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
                        if not line.startswith(('diff --git', 'index ', 'similarity ', 'new file mode', 'deleted file mode')):
    #                    if not line.startswith(('diff --git', 'index ', 'similarity ')):
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
    def _triangulate_addition(
        cls, file_lines: List[str], hunk: Hunk, target_idx: int, max_offset: int = 200
    ) -> Tuple[Optional[int], int, str, int, List[int]]:
        """
        v6.7 — Triangulação para hunks de adição pura.
        
        Estratégia em camadas (do mais forte ao mais fraco):
        1. Match exato do contexto completo (' ' + '+') no disco.
        2. Match exato apenas do contexto ' ' (pré e pós-âncora).
        3. Triangulação por âncoras separadas (pré-âncora + pós-âncora).
        4. Âncora semântica (linha única mais longa do contexto).
        5. Fallback: old_start (com aviso).
        """
        norm_file = [cls._normalize_line(l) for l in file_lines]
        total_file = len(file_lines)
        
        # Índices das linhas de contexto e adição
        context_indices = [i for i, pl in enumerate(hunk.lines) if pl.kind == ' ']
        plus_indices = [i for i, pl in enumerate(hunk.lines) if pl.kind == '+']
        
        if not context_indices:
            # Sem contexto: adicionar no old_start
            return (target_idx, 0, 'ADD_ONLY', 0, [target_idx])
        
        # ── Camada 1: match exato do contexto completo ───────────────
        context_lines = [cls._normalize_line(hunk.lines[i].text) for i in context_indices]
        all_matches = []
        for cand in range(total_file - len(context_lines) + 1):
            if norm_file[cand:cand + len(context_lines)] == context_lines:
                all_matches.append(cand)
        
        if len(all_matches) == 1:
            loc = all_matches[0]
            # loc é onde o PRIMEIRO contexto aparece. Inserir após o último
            # contexto antes da primeira adição.
            first_plus = plus_indices[0]
            insert_offset = sum(1 for i in context_indices if i < first_plus)
            insert_loc = loc + insert_offset
            return (insert_loc, insert_loc - target_idx, 'ADD_ONLY_CTX', 0, [insert_loc])
        
        if len(all_matches) > 1:
            all_matches.sort(key=lambda c: abs(c - target_idx))
            best = all_matches[0]
            first_plus = plus_indices[0]
            insert_offset = sum(1 for i in context_indices if i < first_plus)
            insert_loc = best + insert_offset
            return (insert_loc, insert_loc - target_idx, 'ADD_ONLY_CTX_MULTI', 0, all_matches[:5])
        
        # ── Camada 2: match da pré-âncora (contexto antes das adições) ──
        first_plus = plus_indices[0]
        pre_context_indices = [i for i in context_indices if i < first_plus]
        post_context_indices = [i for i in context_indices if i > first_plus]
        
        if pre_context_indices:
            pre_lines = [cls._normalize_line(hunk.lines[i].text) for i in pre_context_indices]
            pre_matches = []
            for cand in range(total_file - len(pre_lines) + 1):
                if norm_file[cand:cand + len(pre_lines)] == pre_lines:
                    pre_matches.append(cand + len(pre_lines))
            
            if len(pre_matches) >= 1:
                pre_matches.sort(key=lambda c: abs(c - target_idx))
                best = pre_matches[0]
                return (best, best - target_idx, 'ADD_ONLY_PRE', 0, pre_matches[:5])
        
        # ── Camada 3: match da pós-âncora (contexto depois das adições) ─
        if post_context_indices:
            post_lines = [cls._normalize_line(hunk.lines[i].text) for i in post_context_indices]
            post_matches = []
            for cand in range(total_file - len(post_lines) + 1):
                if norm_file[cand:cand + len(post_lines)] == post_lines:
                    post_matches.append(cand)
            
            if len(post_matches) >= 1:
                post_matches.sort(key=lambda c: abs(c - target_idx))
                best = post_matches[0]
                return (best, best - target_idx, 'ADD_ONLY_POST', 0, post_matches[:5])
        
        # ── Camada 4: âncora semântica (linha mais longa do contexto) ───
        # Usar a linha mais longa (mais específica) como âncora
        if context_indices:
            longest_idx = max(context_indices, key=lambda i: len(hunk.lines[i].text.strip()))
            anchor_text = cls._normalize_line(hunk.lines[longest_idx].text)
            
            anchor_matches = []
            for i, line in enumerate(norm_file):
                if line == anchor_text:
                    anchor_matches.append(i)
            
            if len(anchor_matches) >= 1:
                anchor_matches.sort(key=lambda c: abs(c - target_idx))
                best = anchor_matches[0]
                # Calcular offset: onde a adição deve ir em relação à âncora
                offset_from_anchor = sum(1 for i in context_indices if i < longest_idx)
                insert_loc = best + offset_from_anchor
                insert_loc = min(insert_loc, total_file)
                return (insert_loc, insert_loc - target_idx, 'ADD_ONLY_ANCHOR', 0, anchor_matches[:5])
        
        # ── Camada 5: fallback para old_start ──────────────────────────
        return (target_idx, 0, 'ADD_ONLY_FALLBACK', 0, [target_idx])

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
            return cls._triangulate_addition(file_lines, hunk, target_idx, max_offset)

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
        """ v6.3: delega para `_find_removal_anchor`. Retorna tupla de 5. """
        return cls._find_removal_anchor(file_lines, hunk, max_offset=max_offset)

    @classmethod
    def _validate_module_compile(cls, content: str, target_path: Path) -> Optional[str]:
        """v6.4: valida via py_compile (equivalente a compileall, sem escrever .pyc)."""
        if not target_path or target_path.suffix.lower() != ".py":
            return None
        import py_compile, tempfile
        try:
            with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as tf:
                tf.write(content)
                tf_path = tf.name
            py_compile.compile(tf_path, doraise=True, cfile=None)
            Path(tf_path).unlink(missing_ok=True)
            return None
        except py_compile.PyCompileError as e:
            return f"PyCompileError: {e.msg}"
        except Exception as e:
            return f"compile falhou: {e}"

    @classmethod
    def _preflight_analysis(
        cls, file_lines: List[str], patch: FilePatch
    ) -> Dict:
        """
        v6.5: Classifica cada hunk ANTES de aplicar.
        
        Retorna:
        {
            "hunks": [
                {"idx": 1, "status": "WILL_APPLY" | "ALREADY_APPLIED" |
                "WILL_DUPLICATE" | "WILL_CONFLICT" | "UNKNOWN",
                "loc": int|None, "reason": str, "partial_dup_score": float}
            ],
            "will_corrupt": bool,
            "safe_to_apply": bool,
        }
        """
        result = {
            "hunks": [],
            "will_corrupt": False,
            "safe_to_apply": True,
        }
        
        applied_ranges: List[Tuple[int, int, int]] = []
        
        for idx, hunk in enumerate(patch.hunks, start=1):
            classification = {"idx": idx, "status": "UNKNOWN", "loc": None,
                            "reason": "", "partial_dup_score": 0.0}
            
            # 1. Hunk já aplicado?
            replacement_block = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind in (' ', '+')]
            already_applied = False
            if len(replacement_block) >= 2:
                for cand in range(len(file_lines) - len(replacement_block) + 1):
                    block = [cls._normalize_line(file_lines[cand + i]) for i in range(len(replacement_block))]
                    if block == replacement_block:
                        already_applied = True
                        classification["loc"] = cand
                        break
            if already_applied:
                classification["status"] = "ALREADY_APPLIED"
                classification["reason"] = "Bloco já presente no arquivo."
                result["hunks"].append(classification)
                continue
            
            # 2. Encontra âncora (com fuzzy/anchor-only)
            loc, offset, match_type, contig_len, candidates = cls.find_hunk_location(file_lines, hunk)
            
            if match_type == 'NONE':
                classification["status"] = "WILL_CONFLICT"
                classification["reason"] = f"Contexto insuficiente ({contig_len} linhas)."
                result["will_corrupt"] = True
                result["safe_to_apply"] = False
                result["hunks"].append(classification)
                continue
            
            classification["loc"] = loc
            
            # 3. Sobreposição com hunks anteriores?
            new_start = loc
            new_end = loc + sum(1 for pl in hunk.lines if pl.kind in (' ', '-'))
            overlap = None
            for prev_start, prev_end, prev_idx in applied_ranges:
                if new_start < prev_end and new_end > prev_start:
                    overlap = (prev_start, prev_end, prev_idx)
                    break
            
            if overlap is not None:
                classification["status"] = "WILL_CONFLICT"
                classification["reason"] = (
                    f"Sobreposição com hunk #{overlap[2]} "
                    f"(L{overlap[0]+1}-L{overlap[1]})."
                )
                result["will_corrupt"] = True
                result["safe_to_apply"] = False
                result["hunks"].append(classification)
                continue
            
            # 4. Duplicação parcial? (linhas `+` que já existem fora do range)
            plus_lines = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind == '+']
            if plus_lines:
                expected_old_len = sum(1 for pl in hunk.lines if pl.kind in (' ', '-'))
                hunk_range = set(range(loc, loc + expected_old_len))
                already_in_file = 0
                for plus in plus_lines:
                    if len(plus) < 5:
                        continue
                    for i, line in enumerate(file_lines):
                        if i in hunk_range:
                            continue
                        if cls._normalize_line(line) == plus:
                            already_in_file += 1
                            break
                dup_score = already_in_file / max(1, len(plus_lines))
                classification["partial_dup_score"] = dup_score
                if dup_score >= 0.5:
                    classification["status"] = "WILL_DUPLICATE"
                    classification["reason"] = (
                        f"{already_in_file}/{len(plus_lines)} linhas de adição "
                        f"já existem no arquivo (fix parcialmente aplicado)."
                    )
                    result["will_corrupt"] = True
                    result["safe_to_apply"] = False
                    result["hunks"].append(classification)
                    continue
            
            # 5. Vai aplicar OK
            classification["status"] = "WILL_APPLY"
            classification["reason"] = f"Contexto {match_type} em L{loc+1}."
            applied_ranges.append((new_start, new_end, idx))
            result["hunks"].append(classification)
        
        return result

    @classmethod
    def simulate_or_apply(
        cls,
        patch: FilePatch,
        apply: bool = False,
        root: Path = None,
        run_checkshot: bool = True,
        force: bool = False,   # ← NOVO
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

        if patch.is_new_file:
            # v6.4: criação de arquivo
            new_lines = []
            for hunk in patch.hunks:
                for pl in hunk.lines:
                    if pl.kind in (' ', '+'):
                        new_lines.append(pl.text + '\n')
            new_content = ''.join(new_lines)
            # criar diretório pai se não existir
            if patch.target_path.parent and not patch.target_path.parent.exists():
                patch.target_path.parent.mkdir(parents=True, exist_ok=True)
            if apply:
                with open(patch.target_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                report["saved"] = True
            report["details"].append({
                "hunk": 0, "status": "ARQUIVO CRIADO",
                "reason": f"{len(new_lines)} linhas escritas",
            })
            report["hunks_applied"] = 1   # ← ADICIONAR
            return report

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
        applied_ranges = []

        for idx, hunk in enumerate(patch.hunks, start=1):
            # v6.6 — FIX: replacement deve conter APENAS linhas após a última
            # remoção (contexto de fechamento) + adições. Linhas de contexto
            # ANTES da primeira remoção já estão no arquivo e NÃO devem ser
            # reinseridas (causariam duplicação).
            last_minus_idx = -1
            for _i, _pl in enumerate(hunk.lines):
                if _pl.kind == '-':
                    last_minus_idx = _i
            # v6.6 — FIX: replacement deve conter APENAS linhas após a última remoção.
            # Se não há remoções (hunk puro de adição), replacement = só linhas '+'.
            if last_minus_idx == -1:
                replacement = [pl.text + '\n' for pl in hunk.lines if pl.kind == '+']
            else:
                replacement = [
                    pl.text + '\n'
                    for _i, pl in enumerate(hunk.lines)
                    if _i > last_minus_idx and pl.kind in (' ', '+')
                ]
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
                expected_old = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind in (' ', '-')]
                added_lines = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind == '+']
                already_there = any(al in "".join(working_lines) for al in added_lines if len(al) > 5)

                # v6.5 — Destacar linhas de adição que já existem no arquivo
                # (evidência de que o patch já foi aplicado ou o arquivo mudou)
                suspicious_lines = []
                if already_there:
                    for al in added_lines:
                        if len(al) < 5:
                            continue
                        for i, line in enumerate(working_lines):
                            if cls._normalize_line(line) == al:
                                suspicious_lines.append((i + 1, line.rstrip()))
                                break

                # v6.7 — DETECÇÃO DE DIVERGÊNCIA: linhas de remoção que
                # "quase casam" no arquivo (ex: comentadas, com espaço extra,
                # ou com texto adicionado). Destacar em amarelo.
                divergence_lines = []
                for rem in removals:
                    if len(rem) < 5:
                        continue
                    for i, line in enumerate(working_lines):
                        norm_line = cls._normalize_line(line)
                        # Match exato: já coberto por find_hunk_location
                        if norm_line == rem:
                            continue
                        # Match parcial: um contém o outro
                        if (rem in norm_line) or (norm_line in rem):
                            divergence_lines.append({
                                "line": i + 1,
                                "patch_expected": rem,
                                "file_actual": line.rstrip(),
                            })
                            break

                # v6.4 — diagnóstico estruturado
                file_lines_for_ctx = working_lines
                target_idx = max(0, hunk.old_start - 1)
                ctx_start = max(0, target_idx - 5)
                ctx_end = min(len(file_lines_for_ctx), target_idx + 15)
                actual_context = [
                    f"{i+1:4d} | {file_lines_for_ctx[i].rstrip()}"
                    for i in range(ctx_start, ctx_end)
                ]
                expected_display = [
                    f"{pl.kind} {hunk.old_start + i:4d} | {pl.text.rstrip()}"
                    for i, pl in enumerate(hunk.lines) if pl.kind in (' ', '-')
                ]

                # v6.4.1: computar rel_name no escopo de simulate_or_apply
                # (é usado no diagnóstico estruturado)
                _rel_name = (
                    str(patch.target_path.relative_to(root))
                    if (patch.target_path and root and patch.target_path.is_relative_to(root))
                    else (str(patch.target_path) if patch.target_path else "unknown")
                )
                reason_msg = (
                    f"Contexto insuficiente: {contig_len} de {len(expected_old)} linhas contíguas.\n"
                    f"      Arquivo: {_rel_name}\n"                   # ← CORRIGIDO
                    f"      Hunk #{idx} (old_start={hunk.old_start})\n"
                    f"      Esperado (linhas ' ' e '-'):\n"
                    + "\n".join(f"        {l}" for l in expected_display[:8])
                    + f"\n      Encontrado (linhas {ctx_start+1}-{ctx_end} do arquivo):\n"
                    + "\n".join(f"        {l}" for l in actual_context[:15])
                )
                if already_there:
                    reason_msg += (
                        f"\n      ⚠ Linhas de adição já existem no arquivo (fix provavelmente aplicado)."
                    )

                if suspicious_lines:
                    reason_msg += f"\n      🔍 Linhas suspeitas (já presentes no arquivo):\n"
                    for ln, txt in suspicious_lines[:5]:
                        reason_msg += f"        L{ln}: {txt}\n"

                if divergence_lines:
                    reason_msg += f"\n      🔶 Linhas com divergência (patch esperava vs. arquivo tem):\n"
                    for d in divergence_lines[:5]:
                        reason_msg += f"        L{d['line']}: arquivo='{d['file_actual']}' | patch='{d['patch_expected']}'\n"
                
                # v6.4 — sugestões acionáveis
                suggestions = [
                    f"doxoade mody show {_rel_name} --part {ctx_start+1}-{ctx_end}",  # ← CORRIGIDO
                ]
                if already_there:
                    suggestions.append(f"# Fix provavelmente já aplicado. Verifique antes de re-aplicar.")
                else:
                    first_removal = next((pl for pl in hunk.lines if pl.kind == '-'), None)
                    if first_removal:
                        suggestions.append(
                            f"doxoade mody replace {_rel_name} "            # ← CORRIGIDO
                            f"\"{first_removal.text.strip()}\" \"<novo>\""
                        )
                reason_msg += "\n      Sugestões:\n" + "\n".join(
                    f"        • {s}" for s in suggestions
                )
                
                report["details"].append({
                    "hunk": idx, "status": "REJEITADO",
                    "reason": reason_msg,
                    "match_type": "NONE", "loc": hunk.old_start,
                })
                report["hunks_failed"] += 1
            else:
                report["hunks_applied"] += 1

                # v6.4 — Preview defensivo contra IndexError
                _mlen = len(modified_lines)
                start_preview = max(0, loc - 2)
                preview_snippet = []
                for i in range(start_preview, min(loc, _mlen)):
                    preview_snippet.append(f"  {i+1:4d} | {modified_lines[i].rstrip()}")

                for i, pl in enumerate(hunk.lines):
                    line_num = loc + 1 + i
                    if pl.kind == '-':
                        preview_snippet.append(f"{Fore.RED}-{line_num:4d} | {pl.text.rstrip()}{Fore.RESET}")
                    elif pl.kind == '+':
                        preview_snippet.append(f"{Fore.GREEN}+{line_num:4d} | {pl.text.rstrip()}{Fore.RESET}")
                    else:
                        preview_snippet.append(f"  {line_num:4d} | {pl.text.rstrip()}")

                # v6.4: after_start usa `replacement` (pós-cirurgia) e é clampado
                after_start = min(loc + len(replacement), _mlen)
                after_end = min(_mlen, after_start + 2)
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

                # Aplica: remove expected_old, insere replacement.
                # v6.5 — FIX (C2b): se o match foi PARTIAL, o `find_hunk_location`
                # já nos disse quantas linhas contíguas realmente casaram
                # (`contig_len`). Usar `expected_old_len` do corpo removeria
                # linhas a mais e desalinharia o arquivo. Usamos `contig_len`
                # como o comprimento efetivo a remover.
                expected_old_len = sum(1 for pl in hunk.lines if pl.kind in (' ', '-'))
                if match_type == 'PARTIAL':
                    effective_old_len = contig_len
                else:
                    effective_old_len = expected_old_len

                # v6.5 — Aviso quando PARTIAL remove menos que o corpo pedia
                if match_type == 'PARTIAL' and contig_len < expected_old_len:
                    report["details"].append({
                        "hunk": idx,
                        "status": "AVISO (PARTIAL)",
                        "warning": (
                            f"Corpo pedia {expected_old_len} linhas, "
                            f"mas só {contig_len} casaram. "
                            f"Removendo {contig_len} linhas (do contig_len)."
                        ),
                        "match_type": "PARTIAL_WARN",
                    })

                # v6.4.2 — GUARD: detectar sobreposição de hunks
                new_start = loc
                new_end = loc + effective_old_len

                # FIX 2: hunk puro de adição não pode conflitar (só insere)
                if effective_old_len > 0:
                    overlap = None
                    for prev_start, prev_end, prev_idx in applied_ranges:
                        if new_start < prev_end and new_end > prev_start:
                            overlap = (prev_start, prev_end, prev_idx)
                            break

                    if overlap is not None:
                        prev_start, prev_end, prev_idx = overlap
                        report["details"].append({
                            "hunk": idx,
                            "status": "CONFLITO (overlap)",
                            "reason": (
                                f"Sobreposição com hunk #{prev_idx} "
                                f"(range anterior: L{prev_start+1}-L{prev_end}, "
                                f"range novo: L{new_start+1}-L{new_end})."
                            ),
                            "match_type": "OVERLAP",
                        })
                        report["hunks_failed"] += 1
                        report["hunks_applied"] -= 1  # desfaz incremento anterior
                        # FIX 3: NÃO faz break — continua step-by-step.
                        # Próximos hunks podem aplicar independentemente.
                        continue

                applied_ranges.append((new_start, new_end, idx))

                # Aplica: remove `effective_old_len` linhas a partir de `loc`
                modified_lines[loc:loc + effective_old_len] = replacement

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

        # v6.7 — Comparação de sintaxe antes/depois (detecta regressões)
        report["syntax_pre"] = None    # None = OK, str = erro
        report["syntax_post"] = None
        report["syntax_regression"] = False
        report["syntax_fix"] = False

        if patch.target_path.suffix.lower() == '.py':
            # Sintaxe do arquivo ORIGINAL
            try:
                compile(original_content, str(patch.target_path), 'exec')
            except SyntaxError as e:
                report["syntax_pre"] = f"L{e.lineno}: {e.msg}"

            # Sintaxe do arquivo MODIFICADO
            try:
                compile(new_content, str(patch.target_path), 'exec')
            except SyntaxError as e:
                report["syntax_post"] = f"L{e.lineno}: {e.msg}"

            # Classificação
            if report["syntax_pre"] and not report["syntax_post"]:
                report["syntax_fix"] = True  # corrigiu
            elif not report["syntax_pre"] and report["syntax_post"]:
                report["syntax_regression"] = True  # piorou
            elif report["syntax_pre"] and report["syntax_post"]:
                # Já estava quebrado, continua quebrado
                pass

        # v6.3 — Camada 3: validação final via py_compile (equivalente a compileall)
        if patch.target_path.suffix.lower() == '.py':
            try:
                compile(new_content, str(patch.target_path), 'exec')
            except SyntaxError as e:
                report["syntax_ok"] = False
                report["errors"].append(f"Violação Ma'at: SyntaxError em Python (L{e.lineno}: {e.msg})")
            # else:
            #     _mod_err = cls._validate_module_compile(new_content, patch.target_path)
            #     if _mod_err is not None:
            #         report["syntax_ok"] = False
            #         report["errors"].append(f"Violação Ma'at (compileall): {_mod_err}")

        # CheckShot (sandbox isolado) — só em dry-run
        if run_checkshot and not apply and report["hunks_failed"] == 0 and report["syntax_ok"]:
            if patch.target_path.suffix.lower() != '.py':
                pass  # Skip checkshot para TOML, C++, etc.
            else:
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
@click.option('--report-pre-broken/--no-report-pre-broken', default=True, show_default=True,
              help="Compara sintaxe antes/depois do patch (detecta regressões).")
@click.option('--force', is_flag=True,
              help="Aplica mesmo se o patch introduzir novo erro de sintaxe.")
@click.pass_context
def mod_patch(ctx, patch_file, apply, archive, generate, checkshot, checkshot_arg,
              keep_snapshot, report_pre_broken, force):
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

    #click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩹 [MODY PATCH v6.2] Cirurgia Atômica de Diff{Style.RESET_ALL}")
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩹 [MODY PATCH v6.4.2] Cirurgia Atômica de Diff{Style.RESET_ALL}")
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
            force=force,   # ← NOVO
        )

        for det in res["details"]:
            if det["status"] == "ARQUIVO CRIADO":
                click.echo(
                    f"   {Fore.GREEN}✔ {det['status']}: "
                    f"{det['reason']}{Style.RESET_ALL}"
                )
                continue # ← pula o loop genérico
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
                reason_text = det['reason']
                # Destaca linhas suspeitas em amarelo dentro do reason
                import re as _re
                lines = reason_text.split('\n')
                for ln in lines:
                    if '🔍 Linhas suspeitas' in ln or '🔶 Linhas com divergência' in ln:
                        click.echo(f"     {Fore.YELLOW}{ln}{Style.RESET_ALL}")
                    elif ln.strip().startswith('L') and (':' in ln or '|' in ln):
                        click.echo(f"     {Fore.YELLOW}  {ln.strip()}{Style.RESET_ALL}")
                    else:
                        click.echo(f"     {Fore.RED}{ln}{Style.RESET_ALL}")

            if "warning" in det:
                click.echo(f"     {Fore.YELLOW}↳ Aviso: {det['warning']}{Style.RESET_ALL}")

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

        # v6.7 — Sintaxe antes/depois
        if res.get("syntax_regression"):
            click.echo(
                f"   {Fore.RED}🔴 REGRESSÃO: patch introduz novo erro de sintaxe "
                f"({res['syntax_post']}).{Style.RESET_ALL}"
            )
        elif res.get("syntax_fix"):
            click.echo(
                f"   {Fore.GREEN}✅ FIX: patch corrige erro pré-existente "
                f"(antes: {res['syntax_pre']}).{Style.RESET_ALL}"
            )
        elif res.get("syntax_pre") and not res.get("syntax_post"):
            pass  # já tratado
        elif res.get("syntax_pre") and res.get("syntax_post"):
            click.echo(
                f"   {Fore.YELLOW}⚠️  Arquivo já estava quebrado ({res['syntax_pre']}) "
                f"e continua quebrado ({res['syntax_post']}).{Style.RESET_ALL}"
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

@click.command('replace')
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False))
@click.argument('pairs', nargs=-1, required=True)
@click.option('--line', '-l', default=None,
              help="Aplica apenas nas linhas especificadas (ex: '10' ou '10-20').")
def mod_replace(file_path, pairs, line):
    """Substitui texto em lote.

    Uso: replace arquivo.txt "velho1" "novo1" "velho2" "novo2"

    ⚠️ O `replace` faz substituição LITERAL de string. `@@` não é
       interpretado como newline. Para multi-linha, use `mody add`.

    Opções:
      --line N      Aplica apenas na linha N
      --line N-M    Aplica apenas nas linhas N a M
    """
    # ─── GUARD 1: rejeitar '@@' (delimitador do `add`, não do `replace`) ──
    for i, arg in enumerate(pairs):
        if '@@' in arg:
            click.secho(
                f"✘ Erro: o argumento #{i+1} contém '@@'.\n"
                f"   O comando `replace` faz substituição LITERAL de string.\n"
                f"   '@@' é o delimitador do `mody add` (multi-linha), não do `replace`.\n"
                f"\n"
                f"   Se você quer inserir múltiplas linhas:\n"
                f"     doxoade mody add {file_path} \"linha1@@linha2@@linha3\" --line N\n"
                f"\n"
                f"   Se você quer substituir uma única linha por múltiplas:\n"
                f"     doxoade mody remove {file_path} --line N\n"
                f"     doxoade mody add {file_path} \"linha1@@linha2@@linha3\" --line N\n"
                f"\n"
                f"   Argumento problemático: {arg!r}",
                fg='red', err=True,
            )
            raise click.exceptions.Exit(1)

    # ─── GUARD 2: número par de argumentos ───────────────────────────────
    if len(pairs) % 2 != 0:
        click.secho(
            f"✘ Erro: número ímpar de argumentos ({len(pairs)}).\n"
            f"   Esperado: pares OLD NEW [OLD NEW ...]\n"
            f"   Exemplo: doxoade mody replace arq.txt \"velho\" \"novo\"",
            fg='red', err=True,
        )
        raise click.exceptions.Exit(1)

    # ─── LER ARQUIVO ─────────────────────────────────────────────────────
    from pathlib import Path
    fp = Path(file_path)
    try:
        content = fp.read_text(encoding='utf-8')
    except Exception as e:
        click.secho(f"✘ Erro ao ler {file_path}: {e}", fg='red', err=True)
        raise click.exceptions.Exit(1)

    # ─── PARSE DO --line (se presente) ───────────────────────────────────
    line_start = None
    line_end = None
    if line is not None:
        try:
            if '-' in line:
                ls, le = line.split('-', 1)
                line_start, line_end = int(ls), int(le)
            else:
                line_start = line_end = int(line)
            if line_start < 1 or line_end < line_start:
                raise ValueError
        except (ValueError, TypeError):
            click.secho(
                f"✘ Erro: --line inválido ({line!r}). Use 'N' ou 'N-M'.",
                fg='red', err=True,
            )
            raise click.exceptions.Exit(1)

    # ─── APLICAR SUBSTITUIÇÕES ───────────────────────────────────────────
    total = 0
    pairs_list = list(pairs)
    original_content = content
    lines_list = None

    if line_start is not None:
        # Modo --line: só dentro do range
        lines_list = content.splitlines(keepends=True)
        if line_end > len(lines_list):
            click.secho(
                f"✘ Erro: range L{line_start}-L{line_end} excede o arquivo "
                f"({len(lines_list)} linhas).",
                fg='red', err=True,
            )
            raise click.exceptions.Exit(1)

        for i in range(0, len(pairs_list), 2):
            old = pairs_list[i]
            new = pairs_list[i+1]
            found = 0
            for ln_idx in range(line_start - 1, line_end):
                if old in lines_list[ln_idx]:
                    lines_list[ln_idx] = lines_list[ln_idx].replace(old, new)
                    found += 1

            if found == 0:
                click.secho(
                    f"⚠ Aviso: pattern não encontrado em L{line_start}-L{line_end}:\n"
                    f"   {old!r}",
                    fg='yellow',
                )
            else:
                total += found

        content = ''.join(lines_list)
    else:
        # Modo global: substituir em todo o arquivo
        for i in range(0, len(pairs_list), 2):
            old = pairs_list[i]
            new = pairs_list[i+1]
            count = content.count(old)

            if count == 0:
                # Reportar pattern não encontrado com contexto
                click.secho(
                    f"⚠ Aviso: pattern não encontrado:\n"
                    f"   {old!r}",
                    fg='yellow',
                )
                old_stripped = old.strip()
                similar = []
                for ln_idx, ln in enumerate(content.splitlines(), 1):
                    ln_stripped = ln.strip()
                    if (old_stripped[:30] and old_stripped[:30] in ln_stripped) or \
                       (ln_stripped[:30] and ln_stripped[:30] in old_stripped):
                        similar.append((ln_idx, ln_stripped[:80]))
                        if len(similar) >= 3:
                            break
                if similar:
                    click.secho(f"   Linhas parecidas no arquivo:", fg='yellow')
                    for ln_no, ln_text in similar:
                        click.secho(f"     L{ln_no:4d} | {ln_text}", fg='yellow')
                click.secho(
                    f"   Sugestão: doxoade mody show {file_path} --search \"{old_stripped[:30]}\"",
                    fg='cyan',
                )
            else:
                content = content.replace(old, new)
                total += count

    # ─── GRAVAR (com backup) ─────────────────────────────────────────────
    if total > 0:
        try:
            bak = fp.with_suffix(fp.suffix + '.bak')
            bak.write_text(original_content, encoding='utf-8')
            fp.write_text(content, encoding='utf-8')
            click.echo(
                f"[MODDIFY] Realizadas {total} substituições em {file_path} "
                f"(backup: {bak.name})."
            )
        except Exception as e:
            click.secho(f"✘ Erro ao gravar {file_path}: {e}", fg='red', err=True)
            raise click.exceptions.Exit(1)
    else:
        click.secho(
            f"[MODDIFY] Nenhuma substituição realizada em {file_path}.",
            fg='yellow',
        )


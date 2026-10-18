# -*- coding: utf-8 -*-
# doxoade/commands/moddify_sys/mody_patch.py
"""
Mody Patch Engine v4.1 — Motor de Cirurgia Atômica de Diff (Ma'at & Sotéria).
ProDeNov: Ancoragem Estrutural Forte (Regra de Ouro da Recuperação).
Bloqueia aplicações baseadas em coincidências fracas (ex: 1 linha de "}") 
exigindo blocos contíguos de contexto para recuperação parcial.
"""
from __future__ import annotations
import os
import sys
import re
import ast
import shutil
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

@dataclass
class PatchLine:
    kind: str       # ' ' (contexto), '-' (remover), '+' (adicionar)
    text: str       # conteúdo sem o prefixo

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
                current_hunk = Hunk(
                    old_start=int(m.group(1)),
                    old_count=int(m.group(2)) if m.group(2) else 1,
                    new_start=int(m.group(3)),
                    new_count=int(m.group(4)) if m.group(4) else 1,
                    header_ctx=m.group(5).strip()
                )
                current_patch.hunks.append(current_hunk)
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

class PatchSurgeon:
    @staticmethod
    def _normalize_line(line: str) -> str:
        """
        Normaliza a linha para comparação robusta (ProDeNov Resiliência).
        1. Remove quebras de linha e espaços no final.
        2. Remove comentários de linha (Python '#' e C/C++ '//') para evitar 
           falhas de ancoragem por alucinações de LLM em comentários.
        3. Colapsa TODOS os espaços em branco múltiplos em um único espaço.
        
        NOTA DE SEGURANÇA: Isso afeta APENAS a busca pelo contexto. 
        As linhas de adição ('+') manterão seus comentários originais ao serem gravadas.
        """
        # 1. Limpeza básica de quebras de linha
        line = line.rstrip('\r\n').rstrip()
        
        # 2. Remoção de comentários de linha (para fins de matching)
        # Remove '#' (Python) ou '//' (C/C++) e tudo que vem depois, incluindo espaços antes deles
        line = re.sub(r'\s*(?:#|//).*$', '', line)
        
        # 3. Colapso de espaços em branco múltiplos
        return re.sub(r'\s+', ' ', line).strip()

    @classmethod
    def find_hunk_location(cls, file_lines: List[str], hunk: Hunk, max_offset: int = 200) -> Tuple[Optional[int], int, str, int]:
        """
        Retorna (indice_inicio, offset, tipo_de_match, contiguo_max).
        tipo_de_match: 'EXACT', 'PARTIAL', ou 'NONE'
        """
        expected_old = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind in (' ', '-')]
        if not expected_old:
            return (hunk.old_start - 1 if hunk.old_start > 0 else 0, 0, 'EXACT', 0)
        
        expected_len = len(expected_old)
        total_file = len(file_lines)
        norm_file = [cls._normalize_line(l) for l in file_lines]
        target_idx = max(0, hunk.old_start - 1)
        
        # 1. Busca Exata (Tolerância a Offset)
        search_start = max(0, target_idx - max_offset)
        search_end = min(total_file - expected_len + 1, target_idx + max_offset + 1)
        
        for cand in range(search_start, search_end):
            if norm_file[cand : cand + expected_len] == expected_old:
                return (cand, cand - target_idx, 'EXACT', expected_len)
        
        # 2. Busca por Ancoragem Parcial (Maior Bloco Contíguo)
        best_match_len = 0
        best_match_loc = None
        
        for cand in range(total_file):
            current_streak = 0
            max_streak_here = 0
            for i in range(expected_len):
                if cand + i < total_file and norm_file[cand + i] == expected_old[i]:
                    current_streak += 1
                    if current_streak > max_streak_here:
                        max_streak_here = current_streak
                else:
                    current_streak = 0
            
            if max_streak_here > best_match_len:
                best_match_len = max_streak_here
                best_match_loc = cand
                
        # REGRA DE OURO DA RECUPERAÇÃO (ProDeNov Segurança):
        # Só aceitamos "PARTIAL" se o bloco contíguo for >= 60% do contexto esperado
        # E no mínimo 2 linhas (para evitar âncoras em linhas únicas como "}" ou linhas em branco)
        threshold = max(2, int(expected_len * 0.6))
        
        if best_match_len >= threshold:
            return (best_match_loc, best_match_loc - target_idx, 'PARTIAL', best_match_len)
            
        return (None, 0, 'NONE', best_match_len)

    @classmethod
    def simulate_or_apply(cls, patch: FilePatch, apply: bool = False) -> Dict:
        report = {
            "target": str(patch.target_path),
            "hunks_total": len(patch.hunks),
            "hunks_applied": 0,
            "hunks_failed": 0,
            "errors": list(patch.parse_errors),
            "details": [],
            "syntax_ok": True
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
            expected_old = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind in (' ', '-')]
            replacement = [pl.text + '\n' for pl in hunk.lines if pl.kind in (' ', '+')]
            
            loc, offset, match_type, contig_len = cls.find_hunk_location(modified_lines, hunk)
            
            if match_type == 'NONE':
                report["hunks_failed"] += 1
                added_lines = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind == '+']
                already_there = any(al in "".join(working_lines) for al in added_lines if len(al) > 5)
                
                threshold = max(2, int(len(expected_old) * 0.6))
                reason_msg = f"Contexto Insuficiente: Apenas {contig_len} linhas contíguas encontradas (mínimo {threshold})."
                if already_there:
                    reason_msg += f" {Fore.MAGENTA}(As linhas de adição já existem no arquivo?){Fore.YELLOW}"
                    
                report["details"].append({
                    "hunk": idx, "status": "REJEITADO", "reason": reason_msg, 
                    "match_type": "NONE", "loc": hunk.old_start
                })
            else:
                report["hunks_applied"] += 1
                
                start_preview = max(0, loc - 2)
                end_preview = min(len(modified_lines), loc + len(expected_old) + 2)
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
                
                for i in range(loc + len(expected_old), end_preview):
                    preview_snippet.append(f"  {i+1:4d} | {modified_lines[i].rstrip()}")

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
                
                modified_lines[loc : loc + len(expected_old)] = replacement

        new_content = "".join(modified_lines)
        
        if patch.target_path.suffix.lower() == '.py':
            try:
                compile(new_content, str(patch.target_path), 'exec')
            except SyntaxError as e:
                report["syntax_ok"] = False
                report["errors"].append(f"Violação Ma'at: SyntaxError em Python (L{e.lineno}: {e.msg})")
                
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
                        chronos_recorder.log_file_change(str(patch.target_path), original_content, new_content, operation='PATCH')
                    report["saved"] = True
                except Exception as e:
                    report["errors"].append(f"Falha na gravação em disco: {e}")
                    
        return report

@click.command('patch')
@click.argument('patch_file', required=False, type=click.Path(dir_okay=False))
@click.option('--apply', '-a', is_flag=True, help="Efetiva as alterações em disco (sai do modo Dry-Run).")
@click.option('--archive', is_flag=True, help="Renomeia o arquivo diff para .applied após aplicação bem-sucedida.")
@click.pass_context
def mod_patch(ctx, patch_file, apply, archive):
    """🩹 Aplica cirurgicamente patches com Ancoragem Estrutural Forte (v4.1)."""
    root = Path.cwd().resolve()
    target_diff = Path(patch_file) if patch_file else (root / "patch_diff.txt")
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩹 [MODY PATCH v4.1] Cirurgia Atômica de Diff{Style.RESET_ALL}")
    click.echo(f"  • Arquivo de Entrada: {Fore.YELLOW}{target_diff.name}{Style.RESET_ALL}")
    click.echo(f"  • Modo de Operação:   {Fore.GREEN if apply else Fore.YELLOW}{'EFETIVAÇÃO (--apply)' if apply else 'SIMULAÇÃO (DRY-RUN)'}{Style.RESET_ALL}\n")
    
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
        
    total_files = len(patches)
    successful_files = 0
    total_hunks_applied = 0
    total_hunks_failed = 0
    
    click.echo("─" * 75)
    for p in patches:
        rel_name = p.target_path.relative_to(root) if p.target_path and p.target_path.is_relative_to(root) else p.raw_new_path
        click.echo(f"📄 {Fore.WHITE}{Style.BRIGHT}{rel_name}{Style.RESET_ALL}")
        
        res = PatchSurgeon.simulate_or_apply(p, apply=apply)
        
        for det in res["details"]:
            status_color = Fore.GREEN if "APLICÁVEL" in det["status"] else Fore.RED
            icon = "✔" if "APLICÁVEL" in det["status"] else "✘"
            
            badges = ""
            if det.get('offset', 0) != 0:
                badges += f" {Fore.DIM}[Offset: {det['offset']:+d}]{Style.RESET_ALL}"
            if det.get('match_type') == 'PARTIAL':
                badges += f" {Fore.YELLOW}⚠️ [Recuperado: {det['contig_len']} linhas contíguas]{Style.RESET_ALL}"
                
            click.echo(f"   {status_color}{icon} Hunk #{det['hunk']}: {det['status']}{badges}{Style.RESET_ALL}")
            
            if "reason" in det:
                click.echo(f"     {Fore.RED}↳ Motivo: {det['reason']}{Style.RESET_ALL}")
                
            if "preview_snippet" in det and not apply:
                click.echo(f"     {Fore.CYAN}↳ 🔍 Pré-visualização da Cirurgia:{Style.RESET_ALL}")
                for line in det["preview_snippet"].split('\n'):
                    click.echo(f"       {line}")
                    
        if res["errors"]:
            for err in res["errors"]:
                click.echo(f"   {Fore.RED}↳ ERRO: {err}{Style.RESET_ALL}")
                
        if res["hunks_failed"] == 0 and res["syntax_ok"] and not res["errors"]:
            successful_files += 1
            if apply:
                click.echo(f"   {Fore.GREEN}✔ Cirurgia consolidada em disco (Backup: {rel_name}.bak){Style.RESET_ALL}")
                
        total_hunks_applied += res["hunks_applied"]
        total_hunks_failed += res["hunks_failed"]
        click.echo()
        
    click.echo("─" * 75)
    click.echo(f"📊 Resumo: {Fore.GREEN}{total_hunks_applied} hunks válidos{Style.RESET_ALL} | {Fore.RED if total_hunks_failed > 0 else Fore.DIM}{total_hunks_failed} falhas{Style.RESET_ALL}")
    
    if not apply:
        if total_hunks_failed == 0 and successful_files == total_files:
            click.secho("\n⚖ [MA'AT] Simulação 100% aprovada. Execute com '--apply' para efetivar.", fg='green', bold=True)
        else:
            click.secho("\n⚠️ [MA'AT] A simulação detectou rejeições. O patcher bloqueou alterações inseguras.", fg='yellow', bold=True)
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

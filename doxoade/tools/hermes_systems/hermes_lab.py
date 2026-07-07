# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_lab.py
"""
Hermes Lab — Incubador de Pesquisa de Bytecode
===============================================
Modos:
  - ngram-local : Microscópio intra-arquivo (repetições DENTRO de 1 arquivo)
  - ngram-global: Telescópio cross-file (repetições ENTRE N arquivos)
"""
import dis
import ast
import hashlib
from pathlib import Path
from collections import Counter, defaultdict
from doxoade.tools.doxcolors import Fore, Style

# Opcodes de ruído do CPython 3.11+ (não carregam significado semântico)
_NOISE_OPCODES = frozenset({
    'RESUME', 'NOP', 'PRECALL', 'CACHE', 'PUSH_NULL', 'COPY',
    'EXTENDED_ARG', 'INSTRUMENTED_LINE', 'INSTRUMENTED_INSTRUCTION',
})

class BytecodeNgramScanner:
    """Motor de N-grams com suporte a análise Local (intra) e Global (cross)."""

    def __init__(self, target: str, n_sizes=(4, 6, 8, 10)):
        self.target_path = Path(target).resolve()
        self.n_sizes = n_sizes
        self.file_results = {}  # {filepath: {hash: {count, ops, byte_size}}}

    # ─────────────────────────────────────────────────────────────────
    # 1. COLETA DE ARQUIVOS (aceita arquivo único OU diretório)
    # ─────────────────────────────────────────────────────────────────
    def _collect_files(self) -> list[Path]:
        ignore_dirs = {"venv", ".venv", ".doxoade", "__pycache__",
                       "build", "dist", "node_modules", ".git"}

        if self.target_path.is_file():
            if self.target_path.suffix != '.py':
                print(f"{Fore.RED}✘ Alvo não é um arquivo .py: {self.target_path}{Style.RESET_ALL}")
                return []
            if not self.target_path.exists():
                print(f"{Fore.RED}✘ Arquivo não encontrado: {self.target_path}{Style.RESET_ALL}")
                return []
            return [self.target_path]

        if self.target_path.is_dir():
            return [
                f for f in self.target_path.rglob("*.py")
                if not any(part in f.parts for part in ignore_dirs)
            ]

        print(f"{Fore.RED}✘ Caminho inválido: {self.target_path}{Style.RESET_ALL}")
        return []

    # ─────────────────────────────────────────────────────────────────
    # 2. EXTRAÇÃO DE OPCODES LIMPOS (sem ruído)
    # ─────────────────────────────────────────────────────────────────
    def _extract_clean_ops(self, code_obj) -> list[str]:
        clean = []
        try:
            for instr in dis.get_instructions(code_obj):
                op = instr.opname
                if op in _NOISE_OPCODES:
                    continue
                if 'JUMP' in op or 'FOR_ITER' in op:
                    clean.append('JUMP')
                else:
                    clean.append(op)
        except Exception:
            pass
        return clean

    # ─────────────────────────────────────────────────────────────────
    # 3. SLIDING WINDOW (extrai N-grams de uma lista de opcodes)
    # ─────────────────────────────────────────────────────────────────
    def _slide(self, clean_ops: list[str], n: int) -> Counter:
        """Retorna Counter de {hash: count} para janelas de tamanho n."""
        counts = Counter()
        mapping = {}  # hash -> ops tuple
        for i in range(len(clean_ops) - n + 1):
            window = tuple(clean_ops[i:i + n])
            h = hashlib.md5("|".join(window).encode()).hexdigest()[:8]
            counts[h] += 1
            if h not in mapping:
                mapping[h] = window
        return counts, mapping

    # ─────────────────────────────────────────────────────────────────
    # 4. WALK RECURSIVO (percorre funções aninhadas)
    # ─────────────────────────────────────────────────────────────────
    def _walk(self, code_obj, accumulator: dict):
        """Acumula N-grams desta função + recursão em co_consts."""
        clean_ops = self._extract_clean_ops(code_obj)

        for n in self.n_sizes:
            if len(clean_ops) < n:
                continue
            counts, mapping = self._slide(clean_ops, n)
            for h, cnt in counts.items():
                if h not in accumulator:
                    accumulator[h] = {'count': 0, 'ops': mapping[h], 'byte_size': n * 2}
                accumulator[h]['count'] += cnt

        for const in code_obj.co_consts:
            if hasattr(const, 'co_code'):
                self._walk(const, accumulator)

    # ─────────────────────────────────────────────────────────────────
    # 5. SCAN PRINCIPAL
    # ─────────────────────────────────────────────────────────────────
    def scan(self):
        files = self._collect_files()
        print(f"\n{Fore.MAGENTA}🔬 [HERMES LAB] Alvo: {self.target_path}")
        print(f"   Arquivos encontrados: {len(files)}{Style.RESET_ALL}")

        for py_file in files:
            try:
                source = py_file.read_text(encoding='utf-8', errors='ignore')
                tree = ast.parse(source, filename=str(py_file))
                code_obj = compile(tree, str(py_file), 'exec', optimize=2)
                acc = {}
                self._walk(code_obj, acc)
                self.file_results[py_file] = acc
            except SyntaxError as e:
                print(f"  {Fore.YELLOW}⚠ SyntaxError: {py_file.name}: {e}{Style.RESET_ALL}")
            except Exception as e:
                print(f"  {Fore.RED}✘ {py_file.name}: {e}{Style.RESET_ALL}")

    # ─────────────────────────────────────────────────────────────────
    # 6. RELATÓRIO LOCAL (Intra-Arquivo)
    # ─────────────────────────────────────────────────────────────────
    def print_local_report(self, top_n=40, min_freq=3):
        """Mostra repetições DENTRO de cada arquivo."""
        print(f"\n{Fore.GREEN}{'═' * 78}")
        print(f"  📊 RELATÓRIO LOCAL (Repetições Intra-Arquivo)")
        print(f"{'═' * 78}{Style.RESET_ALL}")

        for filepath, ngrams in self.file_results.items():
            # Filtra: só padrões que se repetem >= min_freq vezes NO MESMO ARQUIVO
            viable = [
                (h, data) for h, data in ngrams.items()
                if data['count'] >= min_freq
            ]
            # Score local: bytes_saved = (byte_size - 2) * (count - 1)
            viable.sort(
                key=lambda x: (x[1]['byte_size'] - 2) * (x[1]['count'] - 1),
                reverse=True
            )

            print(f"\n{Fore.CYAN}  📄 {filepath.name} "
                  f"({filepath.parent.relative_to(self.target_path.parent) if filepath.parent != self.target_path else ''})"
                  f"{Style.RESET_ALL}")
            print(f"  {'HASH':<10} | {'FREQ':<5} | {'BYTES':<5} | {'SAVE':<6} | OPCODES")
            print(f"  {'-'*10} | {'-'*5} | {'-'*5} | {'-'*6} | {'-'*50}")

            total_saved = 0
            shown = 0
            for h, data in viable[:top_n]:
                ops_str = "|".join(data['ops'][:8])
                if len(data['ops']) > 8:
                    ops_str += "..."
                saved = (data['byte_size'] - 2) * (data['count'] - 1)
                total_saved += saved
                color = Fore.GREEN if saved > 100 else Fore.WHITE
                print(f"  {h:<10} | {data['count']:<5} | {data['byte_size']:<5} | "
                      f"{color}{saved:<6}{Style.RESET_ALL} | {ops_str}")
                shown += 1

            if not viable:
                print(f"  {Fore.YELLOW}(nenhum padrão com freq >= {min_freq}){Style.RESET_ALL}")
            else:
                remaining = len(viable) - shown
                print(f"  {Fore.MAGENTA}  💰 Economia potencial neste arquivo: "
                      f"~{total_saved} bytes "
                      f"({total_saved / 1024:.1f} KB){Style.RESET_ALL}"
                      + (f"  (+{remaining} padrões omitidos)" if remaining > 0 else ""))

    # ─────────────────────────────────────────────────────────────────
    # 7. RELATÓRIO GLOBAL (Cross-File)
    # ─────────────────────────────────────────────────────────────────
    def print_global_report(self, top_n=40, min_dispersion=2):
        """Mostra repetições ENTRE arquivos diferentes."""
        print(f"\n{Fore.GREEN}{'═' * 78}")
        print(f"  📊 RELATÓRIO GLOBAL (Repetições Cross-File)")
        print(f"{'═' * 78}{Style.RESET_ALL}")

        global_ngrams = defaultdict(lambda: {'total_count': 0, 'files': set(), 'ops': (), 'byte_size': 0})

        for filepath, ngrams in self.file_results.items():
            for h, data in ngrams.items():
                global_ngrams[h]['total_count'] += data['count']
                global_ngrams[h]['files'].add(filepath.name)
                global_ngrams[h]['ops'] = data['ops']
                global_ngrams[h]['byte_size'] = data['byte_size']

        viable = []
        for h, data in global_ngrams.items():
            file_count = len(data['files'])
            if file_count >= min_dispersion:
                score = data['byte_size'] * (file_count ** 2)
                viable.append((h, data, file_count, score))

        viable.sort(key=lambda x: x[3], reverse=True)

        print(f"\n  {'HASH':<10} | {'TOTAL':<5} | {'FILES':<5} | {'BYTES':<5} | {'SCORE':<8} | OPCODES")
        print(f"  {'-'*10} | {'-'*5} | {'-'*5} | {'-'*5} | {'-'*8} | {'-'*50}")

        total_savings = 0
        for h, data, fc, score in viable[:top_n]:
            ops_str = "|".join(data['ops'][:8])
            if len(data['ops']) > 8:
                ops_str += "..."
            color = Fore.GREEN if score > 500 else Fore.CYAN if score > 100 else Fore.WHITE
            saved = (data['byte_size'] - 2) * (data['total_count'] - fc)
            total_savings += saved
            print(f"  {h:<10} | {data['total_count']:<5} | {fc:<5} | "
                  f"{data['byte_size']:<5} | {color}{score:<8}{Style.RESET_ALL} | {ops_str}")

        print(f"\n{Fore.MAGENTA}  💰 Economia global estimada (Top {min(top_n, len(viable))}): "
              f"~{total_savings / 1024:.1f} KB{Style.RESET_ALL}")
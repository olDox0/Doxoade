# Convenções de PoC — forward chaining

## Estrutura fixa por PoC

Cada PoC vive em `poc/XX_name/`:

| Arquivo | Papel | Versionado? |
|---|---|---|
| `engine_pXX.py` | código do PoC (entrada única) | sim |
| `run_XX.bat` | orquestrador: executa + compara | sim |
| `expected.txt` | saída canônica (LF, UTF-8) | sim |
| `README.md` | contrato, err table, planos A/B/C | sim |
| `output.txt` | gerado por engine_pXX.py | **não** (runtime) |
| `logging.txt` | gerado por engine_pXX.py | **não** (runtime) |

## Regras

- **Nunca** `run.py` / `run.bat` genéricos. Sempre `engine_pXX` / `run_XX`.
- Orquestração **apenas** por `.bat` (Windows) ou Python. **Sem `.ps1`, `.sh`.**
- `expected.txt` **sempre LF** — `engine_pXX.py` escreve `output.txt` em LF, e `fc` compara.
- `output.txt` e `logging.txt` no `.gitignore` (runtime, não contrato).
- Sem `__init__.py` por PoC — engines não são importados como módulos.

## Por que o nome embute o número

`run.bat` genérico funciona em isolamento mas quebra quando se alterna entre pastas em `cmd`. `run_21.bat` diz qual PoC rodou mesmo fora de contexto. Custo: renomear em cada PoC. Ganho: `P21 PASS` no terminal é univocamente rastreável.

## Rastreio

- `poc/run_all.bat` executa todos os PoCs e reporta PASS/FAIL.
- `docs/research/poc_notes.md` registra lições por PoC.
- `docs/Research/forward_chaining/research_directions.md` registra direções deferidas com gatilhos objetivos.

---

## ASCII-only em output

`print()` e `expected.txt` **não usam caracteres não-ASCII**. Sem `→`, `ã`, `ê`, `ç`.

Motivo: `cmd`'s codepage (cp850/cp1252) não exibe UTF-8; `fc` compara bytes
brutos e falha mesmo quando o conteúdo é semanticamente idêntico. `->` em
vez de `→`. `quiescencia` em vez de `quiescência`. `joao` em vez de `joão`.

Regra técnica: se precisa passar pelo terminal Windows, use ASCII.
Exceção: se o script escreve direto em arquivo via `write_text(..., encoding="utf-8")`
e NUNCA imprime na tela, aí UTF-8 é seguro — mas `expected.txt` ainda precisa
ser ASCII para `fc` funcionar. Simplificação: ASCII sempre.

---

## Doctor

`poc/_doctor.py` — utilitario permanente, nao e PoC.

| Comando | Comportamento | Exit code |
|---|---|---|
| `py -3.12 _doctor.py` | diagnostico (read-only) | 0 sempre |
| `py -3.12 _doctor.py --fix` | corrige `run_XX.bat` automaticamente | 0 sempre |
| `py -3.12 _doctor.py --check` | pre-flight | 1 se problemas |

**O que verifica:**
1. Estrutura: `engine_pXX.py`, `run_XX.bat`, `expected.txt` existem.
2. Coerencia: `run_XX.bat` chama `engine_pXX.py` correto.
3. Conteudo: `engine_pXX.py` contem tokens caracteristicos do PoC (heuristico).
4. Encoding: `expected.txt` e ASCII-only.

**O que NAO verifica** (deixa para `run_all.bat`):
- Se `engine_pXX.py` executa sem erro.
- Se `output.txt` bate com `expected.txt`.

Esses dois ficam com `run_XX.bat` — o doctor valida **estrutura**, nao semantica.

## Regras operacionais

- **Antes de `copy`/`move`/`ren` entre pastas**: rodar `_doctor.py` primeiro.
- **Antes de rodar PoC que falhou**: rodar `_doctor.py` primeiro.
- **Apos reorganizar pastas**: rodar `_doctor.py --fix`.
- **`run_all.bat` chama `_doctor.py --check` como pre-flight.** Nao desabilitar.

---

## Sobre `accept`

`accept` regenera expected.txt a partir de output.txt. Use quando:
- Output mudou legitimamente (refactor, otimizacao, novo comportamento).
- Primeiro run de um PoC novo (expected ainda nao existia ou tinha placeholders).

NAO use quando:
- Voce nao entendeu a divergencia.
- O engine foi alterado e voce nao sabe por que output mudou.

Antes de `accept`, sempre veja o diff. Antes de commitar, `git diff expected.txt`.

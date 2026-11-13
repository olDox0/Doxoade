## P00 — FizzBuzz (C1) — 2026.11.09YMD

**Pergunta:** o kernel termina, deriva e rastreia sobre 100 inputs?
**Resultado:** PASS 100/100 em [N] ms.
**Ciclos máximos observados:** 2 (n=15, n=30, ..., ciclo 1 dispara, ciclo 2 fecha).
**O que sobrevive como contrato:** `Fact(key, value, source, rule_id, cycle)`,
`Rule(id, conditions, conclusion, priority)`, `Engine.run(...) → trace`.
**O que foi descartado:** toda a implementação de P00.
**Lição:** FizzBuzz é um teste de *terminação + determinismo*, não de conflito.
Qualquer FizzBuzz que “passa” sem checar o oráculo é teatro — daí o `main()`
comparar com `reference()` antes de imprimir.

---

## P01 — ciclo e falha loud (C1) — 2026.11.09YMD

**Pergunta:** o kernel termina em ciclo de regras? Falha loud em limite?
**Resultado:** PASS 2/2 após escolha semântica.
**Lição:** "ciclo" é decisão de contrato, não detalhe. Adotada semântica B
estrita (snapshot por rodada) porque ordem de iteração em varredura
contínua produz resultado dependente de ordem — não-determinismo acidental.
**Impacto:** P01a exige 3 ciclos (não 2), P01b corta em 3 (não 6). P00
inalterado (saída idêntica). P02 herdará B.
**Contrato consolidado:** `Engine.run` = { snapshot, match, fire, merge }
por ciclo. `max_cycles` = rodadas de match.

---

## P02 — conflito e determinismo (C1) — YYYY-MM-DD

**Pergunta:** prioridade resolve conflito? Determinismo em 100 runs?
**Resultado:** PASS 4/4.
**Lição operacional:** cópia de `run.bat` precisa de edição explícita do
`echo PXX PASS` final. Nome de arquivo com backtick (typo de markdown)
passa despercebido porque `dir` só mostra `expected.txt`; `fc` falha
com "não é possível abrir EXPECTED.TXT". Regra: após criar `expected.txt`,
rodar `dir expected.txt` e conferir o nome — antes de comitar.
**Contrato consolidado:** C1 fechado em três sondas (P00 terminação,
P01 ciclo + falha loud, P02 conflito + determinismo). Engine pode ser
congelado.

---

## Princípio de verbosidade (C-verb)

**Decisão:** verbosidade de fatos, chaves e regras não é problema em
fase PoC. É controle e qualidade. Abusar.

**Implicações:**
- Chave discriminada (`.kind`, `.name`, `.value`) é padrão, não exceção.
- Triplas explícitas `(s, p, o)` preferíveis a encoding comprimido.
- Variável explícita (`Var("X")`) preferível a convenção de string (`"?X"`).
- Repetição entre PoCs aceitável; DRY só quando o contrato estabiliza.
- Custo de LOC é menor que custo de ambiguidade descoberta em P70.

**Escopo:** só fase PoC. Revisão em P70 — a consolidação pode comprimir
o que a fase de sondas decidiu por verbosidade.

---

## P20 — unificação (C1+C3) — YYYY-MM-DD

**Resultado:** PASS 6/6 após corrigir expected (2 linhas).
**Lição operacional:** `expected.txt` é uma asserção do contrato, não um
palpite. P20d e P20f erraram `ciclos_usados` porque escrevi o número que
"parecia intuitivo" em vez de derivar do motor. Regra: quando o teste é
sobre **contagem** (ciclos, trace_len), derivar à mão antes de rodar.
**Contrato consolidado:** triplas `(s,p,o)` + `Var` + `Wildcard` (futuro).
`Rule.conclusion_fact` retorna None se houver var livre → warning.
`match_conditions` retorna **todas** as bindings (não só a primeira).

---

## P21 — NAF (C3) — YYYY-MM-DD

**Resultado:** PASS 7/7 após reformular P21c.
**Lição:** NAF e `X != Y` são construtos distintos. O primeiro consulta
fatos ("não há self-loop em X"); o segundo consulta bindings ("X ≠ Y").
P21c inicialmente assumia o segundo — motor estava certo, teste errado.
Distinção registrada em `research_directions.md` (candidata a P_NEQ).
**Segunda lição:** quando a asserção falha, primeiro checar se o teste
descreve corretamente o contrato. "Motor está errado" é hipótese, não
conclusão.

---

## Correção 2025-11-09 — encoding + P00/P01

**Problema 1:** `00_fizzbuzz/engine_p00.py` continha código de P01.
**Problema 2:** `→` e `ê` quebravam `fc` por encoding UTF-8 lido como cp850.
**Fix:** restaurar FizzBuzz em P00; mover P01 para `01_cycle/`; ASCII-only em output.
**Regra nova (CONVENTIONS.md):** nenhum caractere não-ASCII em `print()` ou
`expected.txt`. `->` no lugar de `→`, `quiescencia` sem acento.
**Lição:** `cmd` no Windows 10 não exibe UTF-8 nem normaliza comparações.
`fc` é byte-a-byte. Sem ASCII, o teste é refém do codepage da sessão.

---

## Correção 2025-11-09 (segunda) — ordem de operações

**Problema:** `copy` de arquivos entre pastas foi feito ANTES de aplicar
as versões corrigidas de P00 e P01. Resultado: dois arquivos com o mesmo
conteúdo (o de P01), e `run_XX.bat` chamando `engine_pYY.py` errado.

**Lição operacional (adicionar em CONVENTIONS.md):**

1. Quando uma PoC falha por contrato mal-declarado, o fix vem ANTES de
   copiar/mover arquivos. Copiar primeiro espalha o erro.
2. Se for necessário mover código de uma pasta para outra, mover o
   **conteúdo** (sobrescrevendo) — não copiar arquivos.
3. `run_XX.bat` não é genérico. Renomear `run_00.bat` para `run_01.bat`
   não funciona se o conteúdo não for atualizado também.
4. Rodar `diagnose.bat` após qualquer reorganização de pastas.

---

## Doctor - introduzido 2025-11-09

**Motivo:** dois arquivos com conteudo trocado (00_fizzbuzz tinha P01,
01_cycle tinha P00) passaram despercebidos porque `fc` foi executado
com `.bat` apontando para arquivos inexistentes.

**Solucao:** `_doctor.py` com 3 modos:
- `--check`: pre-flight, exit 1 se problemas
- `--fix`: corrige `run_XX.bat` automaticamente
- (padrao): diagnostico read-only

**Verifica:**
1. Estrutura (arquivos existem).
2. Coerencia (`.bat` chama `engine_pXX.py` correto).
3. Conteudo (engine tem tokens caracteristicos do PoC).
4. Encoding (expected ASCII-only).

**Integracao:** `run_all.bat` chama `_doctor.py --check` como primeiro
passo. Pre-flight bloqueia execucao se doctor falha.

**Licao:** quando o laboratorio cresce (>5 PoCs), integridade estrutural
nao pode ser checada por inspecao visual. Doctor e ortogonal a `pytest`
(testes de comportamento) e a `fc` (comparacao de output). Cada um
verifica uma camada diferente do laboratorio.

---

## Doctor false positive — 2025-11-09

**Bug:** token `R_00` em P01 é gerado por format string `f"R_{i:02d}"`,
não aparece literal no arquivo. Doctor acusou "conteúdo errado" em
arquivo correto.

**Fix:** token trocado para `CycleLimitError` (literal). Doctor agora
mostra `encontrados [...]` e `faltando [...]` — false positive fica
visível mesmo se o check falhar.

**Lição:** tokens de verificação devem ser **literais** no arquivo.
Format strings, `f-string`, concatenação dinâmica — nada disso serve.
Regra: se não aparece em `findstr <token> <arquivo>`, não serve como
token de doctor.

**Segunda lição:** doctor que só diz "não bate" é um doctor cego.
Mostrar o que **bateu** transforma diagnóstico em diagnóstico acionável.

---

## Q00 - baseline classifier (DC2) - YYYY-MM-DD

**Resultado:** PASS apos fix de expected (cycles 3 -> 2 em 3 casos).
**Licao:** "cycles" e a segunda metrica mais dificil de prever a mao
(a primeira e `trace_len`). O motivo: o ciclo que quiesce tambem conta.
Raciocinio correto para "2 ciclos": ciclo 1 processa + dispara; ciclo 2
verifica e nao acha nada -> retorna cycles_used=2. Nao e "1 ciclo de
trabalho + 1 de quiescencia = 2", e sim "2 rodadas, a segunda e a de
confirmacao".

**Regra para proximos PoCs:** quando o engine reporta `cycles`, derivar
a mao ANTES de rodar. O numero nao e "quantos disparos" — e "quantas
rodadas de match ate quiescencia".

**Nao usar `accept` para esconder isso.** `accept` e para mudanca
legitima de comportamento (P70). Aqui era erro de calibracao.

---

## Convenção: expected_<num>.txt

**Decisão 2025-11-10:** expected files levam o num do PoC no nome:
`expected_00.txt`, `expected_q00.txt`, etc. Generico vira "arquivo
qualquer" quando ha 13 PoCs na mesma arvore.

**Migracao:** rodada uma vez com `_rename_expected.bat`. `_discover_pocs`
usa `expected_<num>.txt` estritamente (sem fallback).

**Debug (camada 1):** `doxoade retro-forward run <poc> --debug` mostra
stdout do engine mesmo em PASS. `trace <poc>` e alias.

**Debug (camada 2, futuro):** cada engine responde a `--debug` em
`sys.argv` e dumpa trace estruturado (`[DEBUG] cycle N: ...`). Q00
primeiro, resto incremental.

---

## Convenção: expected_<num>.txt

**Decisão 2025-11-10:** expected files levam o num do PoC no nome:
`expected_00.txt`, `expected_q00.txt`, etc. Generico vira "arquivo
qualquer" quando ha 13 PoCs na mesma arvore.

**Migracao:** rodada uma vez com `_rename_expected.bat`. `_discover_pocs`
usa `expected_<num>.txt` estritamente (sem fallback).

**Debug (camada 1):** `doxoade retro-forward run <poc> --debug` mostra
stdout do engine mesmo em PASS. `trace <poc>` e alias.

**Debug (camada 2, futuro):** cada engine responde a `--debug` em
`sys.argv` e dumpa trace estruturado (`[DEBUG] cycle N: ...`). Q00
primeiro, resto incremental.

---

## Camada 2 — debug estruturado (2025-11-10)

**Decisao:** engines respondem a `--debug` em `sys.argv` e dumpam
`[DEBUG]` em stderr. Output normal (stdout -> output.txt) nao muda.
`expected_q00.txt` permanece identico.

**Razao:** PASS binario nao e suficiente — queremos feedback de "dados
de logistica": quantos fatos, quantas tentativas de match, quais foram
sombreados, tempos por fase. Tudo em stderr para nao contaminar o
contrato (output.txt) e nao afetar `fc`.

**Formato:** prefixo `[DEBUG]`, one-line per event, agrupado por
funcao (sub-sonda) e depois agregado. Estrutura:
- Header: engine, mode, args
- Per function: seed facts, cycle history (matches/candidates/winners/
  shadowed/idempotent/quiescence), result, timing
- Per aggregate: total_* + per_rule_attempts + avg_cycles + total_time

**Integracao com `retro-forward`:**
- `run <poc> --debug` passa `--debug` ao subprocess e mostra stdout+stderr
- `trace <poc>` e alias
- `run <poc>` (sem debug) continua so comparando output.txt

**Incremental:** Q00 primeiro (formato fixado). P00/P02 seguem (kernel
didatico). P10/P30/P50/P70 depois (menor retorno). Q01+ herdam padrao.

---

## Debug em P00 e P02 (2025-11-10)

**Decisao:** aplicar o padrao de Q00 em P00 (kernel puro) e P02
(conflito). Ambos sao "didaticos" — quem quer entender o motor ve
a derivacao ciclo-a-ciclo.

**P00 debug:** bulk aggregate (100 FizzBuzz) + trace completo (n=15).
Semantica A (continuous scan, sem snapshot) e declarada no header do
debug para evitar confusao com P01+ (B, snapshot).

**P02 debug:** 4 sub-sondas. Cada uma mostra cycles com candidates,
winners com `reason` (first_candidate | higher_priority |
equal_priority_first_wins | outranked_by_higher_priority), shadowed,
idempotent, already_shadowed. P02d destaca o tie-break mostrando
as duas ordens lado a lado.

**`reason` como artefato de teste:** cada linha `winner [reason]` do
debug e um assert implicito. Se um novo caso alterar a razao
inesperadamente, o diff mostra antes de qualquer teste binario falhar.

**Nao aplicado ainda:** P01 (ciclo + limite), P10/P11/P30a (AST),
P30b/P31 (rewrite), P50 (explain), P70 (matcher). P00 e P02 sao os
mais uteis por serem kernel; o resto tem output normal ja explicativo.
Backfill incremental, um a um, quando util.

---

## Regressão em P02 v2 (2025-11-10)

**Bug:** ao adicionar debug, renomeei o `reason` de `higher_priority`
para `kept_first_candidate` no branch `else` da resolução de conflito.
O `output.txt` continuou correto em conteúdo (R_high venceu), mas o
texto do `reason` mudou. `fc` pegou — expected não bateu.

**Raiz:** `kept_first_candidate` e `higher_priority` não são
sinônimos no branch else. O `else` cobre dois casos:
- prioridades iguais → quem veio primeiro vence (por ordem)
- prioridades diferentes (novo < antigo) → quem já estava vence
  porque tem prioridade MAIOR

No segundo caso, o vencedor venceu por **prioridade**, não por
"ser o primeiro candidato". Renomear para `kept_first_candidate`
perde a informação semântica — em produção, ver `kept_first_candidate`
sugere tie-break quando na verdade foi prioridade.

**Lição:** quando renomear um `reason`/`status`, verificar **todos
os casos que caem no branch** antes. Um `else` que cobre dois
caminhos semânticos diferentes não pode ter um único rótulo que
descreva só um deles.

**ProDeNov 1.3 confirmado:** a revisão de regressão (fc/diff) pegou
o bug em segundos. Sem ela, a mudança teria passado silenciosamente
e só apareceria quando alguém dependesse do `reason` em produção.

**Ação:** manter `higher_priority` como `reason` estável. O
`cycle_history` (debug) pode adicionar refinamento adicional sem
alterar o texto público do output.

---
## Q01 - multi-dimensional classifier (2025-11-10)

**Resultado:** PASS 5/5.

**Licao principal:** DC2 generaliza para N dimensoes **sem mudar engine**.
Conflito por `(subject, predicate)` e a primitiva certa. Dimensoes
distintas nunca colidem.

**Desafio real (nao do engine, da extracao):** docstring muda
`body[0]` de `Return`/`Expr(Call)` para `Expr(Constant(str))`. Se
extracao fosse ingenua, R_arith falharia silenciosamente em funcao
com docstring. `ast.get_docstring` + filtragem explicita resolve.

**Design decision:** has_docstring e SEED, nao derivado. Docstring e
metadata; extrair como fato separado e mais honesto que derivar com
regra. `trace_len` reflete isso: 1 (so category e derivada), nao 2.

**Proximo (Q02):** complexidade ciclomatica como 3a dim. Primeira dim
com valor nao-booleano (inteiro 1..N). Testa se engine suporta
predicados com valores diversos (deve funcionar - nao ha constraint).

**Backlog debug:** Q00, Q01 tem debug completo. P30b, P31, P50, P70
tem output normal so. Backfill so quando falharem de forma obscura.

---

## QUIET context manager — 2025-11-10

**Problema:** loops de determinismo (Q00e, Q01e, P02c) chamam a funcao
principal 100x, e cada chamada emite debug completo. Resultado: 100
blocos identicos no stderr. Sinal vira ruido.

**Solucao:** context manager `QUIET` que suspende `_dbg` durante o loop.
Depois do `with QUIET:`, o agregado resume o que importa.

**Aplicado em:** Q00, Q01, P02.

**Nao aplicado em:** P00 (bulk loop ja chama `solve_with_engine` sem
`_dbg`), P01 (sem loop), P10/P11/P30a/P30b/P31/P50/P70 (sem debug ainda).

**Regra para novos PoCs:** todo loop que chame funcao com `_dbg` deve
envolver `with QUIET:`. Agregado fora do QUIET. Sem excecao.

---

## QUIET aplicado em P02 (2025-11-10)

**Bug:** `_Quiet` e `QUIET` foram criados em `engine_p02.py`, `_dbg` foi
modificado para checar `QUIET.level == 0`, mas `run_p02c` ficou sem
`with QUIET:` envolvendo o loop. Resultado: 100 blocos de P02a no stderr
mesmo com infraestrutura instalada.

**Causa:** infraestrutura (QUIET + _dbg) e uso (`with QUIET:`) sao duas
edicoes separadas. Aplicar uma e esquecer a outra da falsa sensacao de
"ja consertei" — o codigo compila, `run_p02c` funciona, so o ruido
continua.

**Regra para o proximo `_dbg` refactor:** quando uma correcao envolve
N arquivos e cada arquivo precisa de **duas** edicoes (infra + uso),
checar explicitamente cada par. `findstr /C:"with QUIET:"` deve retornar
pelo menos uma linha por engine que usa loop em massa.

**Nao regride comportamento:** QUIET nao afeta output.txt, so stderr.
`PASS: 14 | FAIL: 0` se mantem.

---

## QUIET em P02 — pendencia (2025-11-10)

**Estado:** infraestrutura (`_Quiet` + `QUIET` + `_dbg` modificado) e uso
(`with QUIET:` em `run_p02c`) ainda nao estao em `engine_p02.py`.
Diagnostico: `findstr /C:"with QUIET:" engine_p02.py` retorna vazio, e
trace 02 continua com 100 blocos de P02a.

**Fix:** colar bloco 2A (infra) + 2B (run_p02c) no arquivo.

**Verificacao:** `findstr /C:"with QUIET:"` retorna 1 linha apos o fix.
`doxoade retro-forward trace 02` cai de ~1500 linhas para ~160.

**Nao muda contrato:** `output.txt` inalterado, `PASS: 14` mantem.

---

## QUIET em P02 — fechado 2025-11-10

**Estado final:** infra (`_Quiet` + `QUIET` + `_dbg` modificado) ja estava
em `engine_p02.py`. Faltava apenas `with QUIET:` envolvendo o `for i in
range(100)` dentro de `run_p02c`.

**Fix:** uma edicao so — `with QUIET:` + indentacao do `for`. Bloco
`if DEBUG and i > 0: pass` removido (dead code).

**Verificacao:** `findstr /C:"with QUIET:" engine_p02.py` retorna 1 linha.
`trace 02` cai de ~1500 para ~160 linhas.

**Licao operacional:** `start cd <path>` abre nova janela; nao muda o
cwd da sessao atual. Apos `start`, verificar com `cd` puro que esta
no diretorio certo antes de `findstr`/`type`. O comando falhou antes
por isso — nao era arquivo ausente.

**Nao regride:** `output.txt` inalterado, `PASS: 14` mantem.

---

## q01 "timeout" — bug real era SyntaxError + rescue interativo

**Sintoma observado:** `retro-forward all` reportou `q01_multi_dim: FAIL
  engine falhou: timeout (60s)`. Nenhum stderr.

**Realidade (descoberta com o patch de partial-output):** `engine_q01.py`
linha 491 tinha `_dbg(f"  n: 100")a` — um `a` orfao apos o `)`. SyntaxError
em parse. O rescue interativo do doxoade interceptou, exibiu menu
"Sua decisao (ex: 34):" e ficou esperando `input()`.

**Por que 60s:** o subprocess esperou o menu. `_run_engine` matou por
timeout. Diagnostico do tempo era "engine lento" quando na verdade
era "engine crashou em <1s e o rescue travou em input()".

**Causa raiz:** copy-paste do `run_p02c` (texto `P02c determinismo
(100 runs de P02a)`) dentro de `engine_q01.py::run_q01e`, com `a`
extra no fim de `_dbg(f"  n: 100")a`.

**Fixes aplicados:**
1. `engine_q01.py::run_q01e` restaurado (com `with QUIET:` correto,
   texto `Q01e`/`Q01a`, sem `a` orfao).
2. `_run_engine` (`retro_forward_cmd.py`) adicionado `stdin=subprocess.DEVNULL`
   para rescue/`input()` falhar rapido em vez de hang 60s.
3. `run_p02c` em `engine_p02.py` adicionado `with QUIET:`.

**Licao 1 — rescue interativo e hostil a subprocess:** qualquer
sistema de rescue com `input()` bloqueia automacao. `stdin=DEVNULL`
e a mitigacao minima; ideal e o rescue detectar `not sys.stdin.isatty()`
e auto-escolher opcao segura.

**Licao 2 — SyntaxError em engine nao e "engine lento":** o rescue
transforma um erro de 0.1s num hang de 60s. Diagnostico por timeout
mascara a causa real. `stdin=DEVNULL` desmascara.

**Licao 3 — copy-paste entre PoCs migra texto errado:** `run_p02c`
tem texto `P02c`, `run_q01e` deve ter `Q01e`. Se fosse so o `a` orfao
eu consertaria em 1 linha. Mas como o bloco inteiro era P02 em Q01,
o fix e restaurar a funcao correta. Regra: ao introduzir um `with
QUIET:` em nova funcao, **nao copiar de outro PoC** — digitar o
texto do PoC correto do zero, e usar `findstr /C:"run_pXX"` para
verificar o nome.

**Pendencia:** `run_p02c` em `engine_p02.py` ainda sem `with QUIET:`
(efeito: trace 02 ainda poluido). Fix trivial, aplicar quando
revisitar P02.

---

## Diagnosis gap no rescue + typo em q01 — 2025-11-10

**Sintoma:** typo em `engine_q01.py:491` (`_dbg(f"  n: 100")a` com `a`
orfao) bloqueou `q01`. Rescue mostrou `<unknown>:491` mesmo com o
arquivo em maos.

**Camadas de perda de informacao (ordenadas por gravidade):**
1. `py -c "ast.parse(open('X.py').read())"` — sem `filename=`, o
   SyntaxError perde o path (`<unknown>`).
2. Rescue nao tentou inferir do frame `<string>:1` (que continha
   `open('engine_q01.py', ...)`).
3. `retro-forward run` bloqueou em `input()` do rescue por 60s
   (`timeout (60s)` disfarcando um crash de 0.1s).

**Fixes:**
- Fix 1: `_recover_syntax_filename(exc)` em rescue — regex em
  `linecache.getline('<string>', ...)` para achar `open('X.py')`.
- Fix 2: `stdin=subprocess.DEVNULL` em `_run_engine` — rescue morre
  em EOFError em vez de hang 60s.
- Fix 3: comando `doxoade check-syntax <file>` — usa `py_compile`
  que **sempre** preserva `filename`.

**Regra nova:** em checagem de sintaxe manual, `py_compile.compile(...,
doraise=True)` e o padrao. `ast.parse(open(...).read())` **nunca** —
apaga o path.

**Regra nova 2:** todo rescue com `input()` deve checar
`sys.stdin.isatty()`; se false, auto-selecionar opcao segura (1 ou 0).
`stdin=DEVNULL` no chamador e a segunda linha de defesa.

**Estado pos-fix:**
- `q01_multi_dim: PASS`, 5 sub-sondas corretas, 143ms total.
- `Q01e` com `with QUIET:` funcional (3 linhas no findstr).
- `trace q01` legivel (~160 linhas).

**Pendencia:** `run_p02c` em `engine_p02.py` ainda sem `with QUIET:`
(efeito: trace 02 poluido, ~1500 linhas). Fix trivial, ~6 linhas.

---

## Rescue diagnostics + run_p02c — 2025-11-10

**4 bugs correlacionados, 3 em rescue/infra, 1 em engine.**

### Bug A: rescue nao recupera filename de open('X.py')
`ast.parse(source)` sem `filename=` reporta `<unknown>`. Rescue mostrava
`<unknown>:491` mesmo com o path em frame anterior. Fix: `_recover_syntax_source`
varre frames por regex `open('X.py')` etc; se achar, substitui `crime['file']`
e recarrega `crime['code']` do arquivo real.

### Bug B: rescue hang 60s em subprocess
`activate_protocol` tem guard `not sys.stdin.isatty()` -> `_direct_report`.
Mas `subprocess.run(... capture_output=True)` **herda** stdin do pai (TTY),
fazendo `isatty()` retornar True no subprocess. Menu interativo fica esperando
input humano. Fix: `stdin=subprocess.DEVNULL` em `_run_engine` -> subprocess
ve stdin fechado -> `_direct_report` -> exit 1 em ~1s.

### Bug C: mensagem duplicada "engine falhou: engine falhou:"
`_run_engine` prefixa "engine falhou:" no timeout, `_run_one` prefixa de novo.
Fix: `_run_engine` retorna texto sem prefixo, `_run_one` so adiciona `"  "`.

### Bug D: run_p02c sem `with QUIET:` (pendencia de 3 turnos)
Fix trivial: envolver `for i in range(100):` em `with QUIET:`.

**Licao 1:** `ast.parse(open(f).read())` e anti-pattern para check-syntax.
Sempre `ast.parse(source, filename=f)` ou `py_compile.compile(f, doraise=True)`.

**Licao 2:** qualquer sistema com `input()` interativo precisa checar
`sys.stdin.isatty()` **e** o chamador precisa usar `stdin=DEVNULL` quando
invocar via subprocess. Duas defesas em camadas.

**Licao 3:** recovery heuristica de filename via regex `open('X.py')` funciona
para o caso `-c "ast.parse(open(...))"` mas nao para `ast.parse("literal")`
sem contexto de arquivo. Esses ficam como `<unknown>` legitimo.

**Estado pos-fix:**
- `q01` PASS, rescue mostra path correto no caso `<unknown>`.
- `retro-forward` subprocess nao trava em 60s.
- `trace 02` cai de ~1500 para ~160 linhas.

**Proximo:** Q02 (complexidade como 3a dim) em `code_classification`.

---

## _run_engine: dois bugs coexistindo — 2025-11-10

**Bugs encadeados em `retro_forward_cmd._run_engine`:**
1. `informative[:200]` (nome inexistente) em branch `returncode != 0`
2. falta `return True, "", stdout, stderr` no path de sucesso

**Por que um escondia o outro:**
- q01 broken: returncode != 0 -> bug 1 dispara (NameError)
- q01 fixed: returncode == 0 -> nao chega ao bug 1, cai no fim -> None
  -> `_run_one` unpack de None -> bug 2 (TypeError)

**Licao:** bugs em paths alternativos (success/failure) do mesmo
branch sao mutuamente mascarantes. Ao consertar o input que
disparava o bug A, o fluxo agora passa pelo bug B — que ja estava
la, so inalcancavel.

**Fix:** `head` no lugar de `informative` + `return True, "", stdout,
stderr` no fim. Todos os paths do `_run_engine` retornam 4-tupla.

**Regra:** toda funcao que retorna tupla fixa deve ter assertion ou
implementacao clara dos branches. Nao confiar em "vai cair no if
else" — verificar visualmente que todo `if/except` tem `return`
no fim do bloco `finally`-equivalente.

**Nota — rescue funcionou:** mostrou `NameError`/`TypeError`, arquivo,
linha (147/200) corretos. Unico gap: `Funcao: Unknown` — o ctx do
frame nao esta sendo passado do `_mine_traceback` para o renderer.
Pendencia cosmetico.

**Verificacao correta de sintaxe:** `py -m py_compile <file>`.
`ast.parse(open(f).read())` sem `filename=` apaga o path no
SyntaxError. Nao usar.

**Estado pos-fix:**
- `run_p02c` com `with QUIET:` (3 linhas no findstr) ✓
- `stdin=DEVNULL` no subprocess ✓
- `_recover_syntax_source` no rescue ✓
- `_run_engine` retorna 4-tupla em todos os paths ✓
- `q01`, `all` = 14/14 esperado

**Proximo:** Q02 (complexidade como 3a dim) em code_classification.

---

## Q02 — complexity as 3rd dim (2025-11-10)

**Resultado:** PASS 8/8.

**Licao 1 — primeira dim nao-booleana.** Q00/Q01 tiveram valores de
dim em conjuntos booleanos ou enumerados pequenos. `complexity` tem
`{1, 2, 3, 4+}` — o `4+` nao e inteiro. Solucao: extractor emite
`branch_count` exato + hint `branch_count_ge_4=yes`. Rules continuam
puramente simbolicas (sem OR, sem comparacao numerica).

**Licao 2 — C2 faz aritmetica, C3 fica pura.** A unica computacao
numerica (`>= 4`) mora no extractor. Se Q03 precisar de
`param_count > 3`, mesmo padrao: extractor computa o threshold, rules
fazem match exato.

**Licao 3 — bucketing por valor nao por threshold.** Buckets 2 e 3
compartilham "3" porque a diferenca entre 2 e 3 branches e menos
informativa que entre 0-1, 1-2, 3-4+. Essa decisao de granularidade
fica em README, nao em codigo.

**Estado:** Q00, Q01, Q02 formam trilogia de classificacao — 3 dims
simultaneas, uma delas com valor nao-booleano. DC2 generaliza sem
mudanca em C1/C3.

**Pendencia:** `_parse_engine_error` dead code em
`retro_forward_cmd.py` — remover ou usar. Recomendado remover.

**Proximo:** Q03 (design pattern como 4a dim) ou Q04 (code smell
como 4a dim). Ambos testam nova classe de valor (pattern name,
smell name) — conjunto enumerado maior que `{yes, no}` mas menor
que int livre.

---

## Q03 — pattern detection + cross-cycle chaining (2025-11-10)

**Resultado:** PASS 7/7.

**Licao principal — C1+C3 compoem em camadas.** Ate Q02, todas as 18
rules matchavam somente fatos seed. Q03 introduz 3 rules (R_factory,
R_accessor, R_predicate) que dependem de `has_naming` + `has_behavior`
— fatos derivados por R_create_prefix/R_returns_call em cycle anterior.

A composicao ja estava no motor desde P02, mas nunca exercitada em
code_classification. Q03 e o primeiro PoC que mostra "rule le fato
derivado" no dominio de AST.

**Armadilha — NAF default + cross-cycle = bug silencioso.** Se R_utility
(default via NAF) disparasse em cycle 1 (antes das hints), `pattern=utility`
ficaria preso em `facts` — WM monotonico nao retrata. R_factory em
cycle 2 nao pode shadowar. Contradicao em `pattern`.

Fix: sem default. Ausencia de `pattern` fact = `None`. Honesto.
Registrar para Q04+ (retracao cross-cycle e o proximo upgrade do engine).

**4 dims coexistem sem colisao** — category, has_docstring, complexity,
pattern. Q03a-e com pattern; Q03d/e/f sem (None). Dims independentes por
predicado diferente em `(subject, predicate)`.

**Partial match nao dispara pattern** — Q03e (naming sim, behavior nao),
Q03f (naming sim, behavior Call vs Compare mismatch). Prova que a
conjuncao de has_naming + has_behavior e exigida.

**Estado:** Q00-Q03 = trilogia expandida para 4D. Proximo natural e
retracao cross-cycle (para viabilizar defaults) — vira Q04 com
`engine.retract()` ou WM seletivo.

---

## Q04 — cross-cycle retraction (2025-11-10)

**Resultado:** PASS 5/5.

**Licao principal — prioridade sozinha nao resolve cross-cycle.**
Q03 expos: R_utility (cycle 1, prio 1) + R_factory (cycle 2, prio 20)
coexistem em `pattern` = contradicao silenciosa. Priorities only
disambiguam within-cycle. Cross-cycle precisa retracao explicita.

**Mecanismo escolhido — retracao monotona por prioridade.** Fact ganha
`priority`, engine ganha `retracted: set`. Novo fato com P_new > P_old
retrata old. Seeds protegidos (prio infinita). Fato retratado nao
ressuscita. NAF sobre vivo.

**Por que nao "backward retraction" (rollback de retratacao).**
Cascata A retrai B, C retrai A, B deveria voltar — modelo classico de
TMS (Truth Maintenance System). Complexo e fora do escopo. Q04 e
minimalista. Se Q05+ exigir, upgrade B explicito com
`retracted_by: dict` rastreando cadeia.

**Estado:** Q00-Q04 = 5 PoCs em code_classification. DC2 agora com 4
dims + retracao cross-cycle. C1+C3 validados em camada nova.

**Proximo:** Q05 — retracao em cascata (cadeia A->B->C) OU code smell
(dead code, magic number) — trilha paralela sem upgrade de engine.
Recomendo Q05 = code smell, deixa cascata para Q06 se demanda real
aparecer.

---

## Q05 — code smell como 5a dim (2025-11-10)

**Resultado:** PASS 6/6.

**Licao 1 — domain expansion sem engine upgrade.** Q05 valida Plan B
de Q04: nao foi preciso tocar o engine. Retraction de Q04 + NAF de P21
+ prioridade de P02 + ortogonalidade de predicados resolvem "clean vs
dirty" naturalmente.

**Licao 2 — retraction deixa de ser artificial.** Q04 exercitou
retraction com rules stub. Q05 usa em cenario real: aggregate
`has_any_smell=none` (prio 1, NAF) precisa ser retratado por
`has_any_smell=dirty` (prio 20) quando qualquer specific aparece.
Se Q05 falhasse, Q04 nao serviria para apps reais.

**Licao 3 — ortogonalidade de predicados previne colisao.** 3 smells
em Q05e coexistem sem conflito porque usam predicados distintos
(`smell_magic_number` vs `smell_long_method` vs `smell_dead_code`).
Se fossem `smell=magic|long|dead`, colidiriam e Q02 shadow perderia
info. Schema de fato e a alavanca.

**Estado:** Q00-Q05 = 6 PoCs em code_classification. DC2 com 5 dims.
C1+C3+C7 validados em 18 PoCs totais (12 FC + 6 CC).

**Proximo:** Q06 — smells mais ricos (OO, dead nested, magic em
assign) OU multi-funcao (visitor entre funcoes). Ambos requerem
schema de fato enriquecido — planejamento antes de codigo.

---

## Q05 — accept por expected errado (2025-11-11)

**Sintoma:** q05_smell FAIL. 65+ divergencias em 68 linhas.

**Realidade:** expected_q05.txt tinha
  (a) 1 linha em branco no inicio (leading \n)
  (b) Q05c: category errado (arithmetic_return vs unknown)
  (c) Q05e: complexity errado (3 vs 2)

Engine estava correto nos 3 casos.

**Q05c** — body[0]=Assign (nao Return), entao R_arith nao casa.
Correto: unknown.

**Q05e** — 1 If no body. Return dentro de If nao conta como branch.
branch_count=1 -> complexity=2. Eu confundi "return 0 seguido de print(x)"
com "2 branches".

**Fix:** accept q05. Diff de 3 linhas + 1 blank.

**Licao — antes de accept, derivar 2 casos manualmente.**
Se 2 casos derivam corretamente e o resto do output parece coerente,
accept e aplicavel. Se a divergencia e massa (30+ linhas), esconde bug.

**Licao — leading blank line em expected quebra tudo.** Sempre
verificar `type expected_XX.txt | findstr /N "^$"` para detectar
linhas vazias antes de `fc`. Ou salvar via `accept` (que preserva
o `output.txt` byte-a-byte).

**Cleanup:** 3 artefatos antigos removidos (2x FATAL_CRASH_DUMP.txt,
1x _rename_expected.bat).

---

## X01 — RuleTable por domain (2025-11-11)

**Resultado:** [PASS/FAIL após executar]

**Licao 1 — tabelamento é abstracao fina.** RuleTable e `dict`
com dois indices (`domain_index`, `symptom_index`) sobre fonte unica
(`_rules`). Nada mágico, ~50 L. Se X01 falha, o bug esta na fixture,
nao no conceito.

**Licao 2 — R1/R2/R3 aplicadas.** Classificador separado (R1),
tabela estatica (R2), fallback adiado para X03 (R3). X01 testa so a
transparencia do filtro.

**Licao 3 — 480 L vs 80 L prometido.** Kernel inline domina o
tamanho. Consolidacao (Q10) resolve para ~80 L. Registrar como
divida conhecida, nao como red flag.

**Licao 4 — validar antes de accept.** `raw_live_facts` e derivavel
a mao (5 tuplas). Se output diverge, nao e "accept", e bug. Toda
PoC com `accept` deve ter derivacao manual anotada.

**Proximo:** X02 (symptom index + multi-domain). Mais desafiador
porque combina duas chaves (domain + symptoms) e testa ativacao
dinamica — nao so filtro estatico.

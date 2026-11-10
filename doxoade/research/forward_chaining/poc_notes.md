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

# BLITZPLAN — X00 + Q06–Q10

## Objeto de Produção como contato controlado com problemas reais

---

## 0. Contexto — a máquina maior

O `code_classification` não é um fim. É componente de uma **máquina de decisão** que atua em três domínios sobrepostos:

| Domínio | Entrada | Saída | Exemplo de uso |
|---|---|---|---|
| **Programação** | AST, código | Classificação, smell, pattern | "esta função é factory?", "este loop tem bug?" |
| **Diagnóstico** | Traces, logs, W5 | Hipótese de causa, plano de fix | "por que este crash aconteceu?" |
| **Linguagem** | Texto natural | Classificação simbólica, sem embedding | "este parágrafo é descritivo?" |

Q00–Q05 validaram o motor **em isolamento**, com inputs sintéticos. Nenhum deles teve **contexto real**:
- Código escrito por engenheiros reais (não 5 linhas de teste)
- Problemas reais (não truques para a rule casar)
- Consequências (não só output em arquivo)

**Sem objeto de produção, Q06+ vira mais sintético**, e o motor pode se especializar em resolver problemas que ninguém tem.

---

## 1. Por que Objeto de Produção, e por que agora

Três razões concretas:

**1.1. Custo do erro sintético é baixo demais.** Q00–Q05 passaram de primeira. Mas isso não prova que o motor lida com `doxoade/tools/aegis/aegis_utils.py` (350 linhas, imports encadeados, classes). Pode ser que `category=unknown` para 90% do código real — o que é **falha de cobertura**, não de motor.

**1.2. W5 de problemas reais é diferente.** Problema real tem: quem invocou, quando, em qual build, com qual config, qual commit. Sintético tem só o input.

**1.3. ProDeNov "Anti Long Shot" (3.1.6) exige sonda.** Sem medir performance/smell/pattern em código real, não sabemos se o motor é útil ou se é exercício acadêmico.

**O que muda com X00:** cada false positive é **informação** (rule mal calibrada), cada true positive é **valor produzido** (auditoria da base real). Ambos domesticáveis.

---

## 2. Critérios de Objeto de Produção

Todo objeto de produção de teste deve satisfazer **6 critérios**:

| # | Critério | Pergunta de teste |
|---|---|---|
| **C1** | **Real** | Existe fora do escopo PoC? É usado por alguém (mesmo que só o dev)? |
| **C2** | **Controlado** | Podemos restringir escopo (1 diretório, N arquivos)? |
| **C3** | **Domesticável** | False positives são corrigíveis sem reescrever? |
| **C4** | **Reversível** | Podemos voltar ao estado anterior sem corromper nada? |
| **C5** | **Observável** | W5 completo: onde, o que, quando, quem, por que? |
| **C6** | **Pequeno** | Cabe na cabeça do dev (~500–2000 LOC) para diagnóstico manual? |

Um objeto que falha em qualquer critério não serve como testbed — vira fonte de ruído ou de rabbit hole.

---

## 3. Candidatos e seleção

| Candidato | C1 Real | C2 Control | C3 Domest | C4 Revers | C5 Obs | C6 Peq | Veredito |
|---|---|---|---|---|---|---|---|
| **A. Doxoade Source Auditor** | ✅ código do doxoade | ✅ subdir | ✅ rule-refine | ✅ read-only | ✅ AST + W5 | ✅ | **selecionado** |
| B. Doxoade Doctor v2 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | reserva Q08 |
| C. Doxarchives lexical | ✅ | ⚠️ precisa corpus | ⚠️ vocabulário aberto | ✅ | ✅ | ❌ grande | deferido Q09+ |
| D. Mini Python parser | ⚠️ inventado | ✅ | ⚠️ we own bugs | ✅ | ✅ | ✅ | descartado (não é real) |

**Selecionado: A — Doxoade Source Auditor (X00).**

Por quê:
- **Código real** do próprio doxoade, com bugs reais (você mesmo já corrigiu `_run_engine` duas vezes hoje)
- **Escopo ajustável**: começar em `doxoade/tools/doxcolors/` (~500 LOC), expandir conforme confiança
- **Domesticável**: false positives viram patch de rule; true positives viram *smells registrados*
- **Reversível**: X00 só **lê** código; não modifica nada
- **Observável**: cada função reportada tem `category`, `complexity`, `smell_*`, `pattern`
- **Pequeno**: 1 arquivo por vez, diagnóstico manual viável

**Bônus não-trivial:** quando X00 ganhar confiança, o **retro-forward-doctor** pode usar X00 para auto-auditar o próprio doxoade. **O sistema começa a se usar.**

---

## 4. X00 — Doxoade Source Auditor (definição)

### 4.1. Contrato

```
audit(path: str|Path) -> AuditReport
```

Onde:
- `path` = arquivo `.py` OU diretório (recursivo)
- `AuditReport` = estrutura serializável (dict/JSON)

X00 **não** substitui Q00–Q05. Usa o mesmo kernel inline (por enquanto — consolidação fica para Q10), mas o output é diferente:
- Q00–Q05: `expected_XX.txt`, um arquivo por PoC
- X00: relatório por arquivo/função, comparado contra baseline `expected_audit.txt`

### 4.2. Estrutura

```
doxoade/research/code_classification/
  x00_source_auditor/
    audit.py                    # ~350 L (kernel + rules + report)
    expected_audit_colors.txt   # baseline de doxoade/tools/doxcolors/
    README.md                   # escopo, critérios, contrato
    notes.md                    # catálogo de FPs/FNs domados
```

Não é `poc/X00/`. X00 é **produção-shaped** desde o início. Fica fora do `poc/` porque:
- Não vai ser descartada após PASS
- Vai evoluir (Q07+ refinam rules)
- Baseline é regressão de longo prazo

### 4.3. Interface

```cmd
:: auditoria básica (só output)
py -3.12 doxoade\research\code_classification\x00_source_auditor\audit.py doxoade\tools\doxcolors\

:: comparar com baseline
py -3.12 ... audit.py doxoade\tools\doxcolors\ --expected expected_audit_colors.txt

:: regenerar baseline (após aceitar mudança)
py -3.12 ... audit.py doxoade\tools\doxcolors\ --accept expected_audit_colors.txt
```

**CLI registration fica para Q08.** MVP: standalone script (mais simples, mais reversível).

### 4.4. Saída esperada

```
=== doxoade/tools/doxcolors/colors.py ===
  [1] ansi_strip            category=unknown        complexity=2    smell_magic_number=yes   pattern=None
  [2] fore_color            category=unknown        complexity=1    smell_magic_number=yes   pattern=None
  [3] fore_color_256        category=unknown        complexity=3    smell_magic_number=yes   pattern=None
  [4] back_color            category=unknown        complexity=1    smell_magic_number=yes   pattern=None
  [5] fore_rgb              category=unknown        complexity=1    smell_magic_number=yes   pattern=None
  [6] back_rgb              category=unknown        complexity=1    smell_magic_number=yes   pattern=None
  [7] init                  category=unknown        complexity=2    smell_long_method=yes    pattern=None
  ...

=== SUMMARY ===
  files scanned:      3
  functions scanned:  19
  category dist:      {unknown: 17, arithmetic_return: 2}
  smell dist:         {magic: 12, long: 1, dead: 0}
  retractions total:  0
```

**Sinal honesto:** `unknown: 17` para `doxcolors` significa que `category` **não cobre** código de constante/atribuição. É informação valiosa — Q07+ vai refinar categorias com base neste output.

### 4.5. Baseline — `expected_audit_colors.txt`

Snapshot determinístico do output atual para regressão. Toda mudança em X00 (Q07 rules, Q10 consolidação) que altere output é revisada via diff.

Se `expected` diverge muito em Q07, **não usar `accept` cegamente**. Cada linha divergente é:
- bug de rule → patch
- nova capacidade → aceitar com nota
- mudança de contrato → `expected` versionado + tag no README

---

## 5. Blitzplan — Q06 a Q10

### Cap. 1 — Q06: multi-função (pré-requisito de X00)

**Contrato:** DC2 com sujeitos distintos. Fatos de `f1` casam com regras que produzem fatos de `f2`.

**Task list:**
- [ ] `_extract_calls(func)` → `Call.func.id` de cada `ast.Call` no body
- [ ] Fatos `(f, calls, helper)` por função chamada
- [ ] Pattern `delegating_factory`: `(f1, pattern, factory)` AND `(f1, returns_call, helper)` AND `(helper, pattern, factory)` → `(f1, pattern, delegating_factory)`
- [ ] Sub-sondas: `factory` chama outro `factory` (visitor), `factory` chama `helper` comum (não pattern)

**Plano A:** extração direta via `ast.walk(body)`, filtrar `ast.Call`, pegar `func.id` se `ast.Name`.

**Plano B (se walk gera ruído):** visitor pattern explícito, só `ast.Call` no body-level + 1 nível de nested.

**Plano C (se multi-função exige engine reescrito):** adiar Q06 e começar X00 com kernel Q05 (sem multi-função). Q06 vira Q07.

**Saída esperada:**
```
=== Q06a ===
  input: 'def create_user(n): return User.make(n)'
  pattern:       factory

=== Q06b ===
  input: 'def build(n): return create_user(n)'
  pattern:       delegating_factory   (calls create_user que é factory)
```

**RIT:** discussão → implementação → 5 sub-sondas → revisão.

**Promoção:** Q06 verde → X00 pode usar pattern composto.

---

### Cap. 2 — X00 MVP: Doxoade Source Auditor

**Contrato:** `audit(path) -> report` determinístico, reversível (read-only).

**Task list:**
- [ ] `audit.py` com kernel inline (Q05 inlined + Q06 calls extraction)
- [ ] `--expected <file>` e `--accept <file>`
- [ ] `--json` (além do default texto)
- [ ] Escopo inicial: `doxoade/tools/doxcolors/` (3 arquivos)
- [ ] Gerar `expected_audit_colors.txt`
- [ ] Anotar FPs conhecidos em `notes.md`
- [ ] README com escopo explícito

**Plano A:** kernel inline completo (Q05 + Q06). ~350 L.

**Plano B:** se inline é grande demais, extrair kernel para `x00_source_auditor/_kernel.py` (import de si mesmo). Não é "shared lib" ainda — é privado de X00.

**Plano C:** se for ler código do doxoade e travar em algum arquivo (import circular, syntax rara), fazer `--skip <pattern>` para excluir arquivos problemáticos. Anotar em `notes.md`.

**Saída esperada:**
```
$ py -3.12 audit.py doxoade/tools/doxcolors/ --expected expected_audit_colors.txt
PASS: 3 files, 19 functions
```

**RIT:**
1. Rodar `audit.py` sem baseline (gerar output cru)
2. Inspecionar manualmente 5–10 funções (2 minutos)
3. Salvar como baseline se tudo coerente
4. Rodar de novo com `--expected` (deve PASS imediatamente, determinismo)

**Promoção:** X00 MVP estável em `doxcolors` → expandir escopo em Q07.

---

### Cap. 3 — Q07: X00 iteration 1 (real feedback)

**Contrato:** X00 roda em 3–5 diretórios do doxoade; false positives são catalogados; rules são refinadas.

**Task list:**
- [ ] Rodar em `doxoade/tools/error_info/`, `doxoade/tools/aegis/`, `doxoade/commands/` (parcial)
- [ ] Catalogar FPs em `notes.md` (formato: arquivo:função → razão)
- [ ] Catalogar FNs (o que X00 **deveria** flagar e não flagou)
- [ ] Refinar rules com base no catálogo → **bump de versão** de X00 (X00.1, X00.2)
- [ ] Cada refino tem `expected_audit_<dir>.txt` próprio

**Plano A:** 1 diretório por vez, 3 iterações, refinar 1–2 rules por iteração.

**Plano B:** se o volume de FPs é alto (>30% das funções), **congelar** refinamento e voltar para Q06 (falta extração mais rica).

**Plano C:** se o padrão é sistemático (ex: "todas as funções com `__` no nome geram magic_number"), adicionar `_name_prefix` para `dunder` e refinar em batch.

**Saída esperada:**
- Primeira rodada: ~30% FPs identificados
- Segunda rodada: ~10%
- Terceira rodada: ~3% (aceitável como "long tail" — documentada em notes.md)

**RIT:** rodar → catalogar → refinar → re-rodar → diff baseline → revisão.

**Promoção:** FP rate < 5% nos 3 diretórios → X00 candidato a doctor embed.

---

### Cap. 4 — Q08: X00 integrado ao rescue

**Contrato:** rescue detecta crashes em arquivos com smells conhecidas e **sugere** (não auto-aplica) hipótese.

**Task list:**
- [ ] `rescue._collect_fixes_for_crime` chama `x00.audit(crime_file)` (só o arquivo do crime)
- [ ] Se smell detectado na **linha do crime** (ou adjacente), mostrar `[AUDIT]` block:
  ```
  ■ AUDITORIA (X00):
    linha 147: smell_magic_number=yes (valor 200)
    → possível: constante não-trivial hardcoded
  ```
- [ ] Sem auto-fix — só sugestão. Fix continua manual.
- [ ] Option 9 no menu rescue: "Ver auditoria X00 do arquivo"

**Plano A:** integração via subprocess (`py audit.py <file> --json`) com timeout curto (5s). Sem import direto (isola crash loops).

**Plano B:** import direto `from code_classification.x00_source_auditor import audit` — mais rápido, mas adiciona dependência de rescue em X00.

**Plano C:** se subprocess é instável, rescue lê `notes.md` cache (offline).

**Saída esperada (rescue no `_run_engine` crash):**
```
■ CENA DO CRIME : retro_forward_cmd.py:147
  >>  147 | return False, f"engine exit ...: {informative[:200]}", ...

■ AUDITORIA (X00):
  smoke: nenhum smell na linha 147
  hint: variavel 'informative' nao definida — typo em nome?
```

**RIT:** provocar crash com smell conhecido → verificar AUDIT block → comparar com output sem X00.

**Promoção:** rescue com X00 reduz tempo de diagnóstico (medido em 3 crashes reais).

---

### Cap. 5 — Q09: X00 multi-domínio (seed de linguagem)

**Contrato:** X00 ganha modo `--lang` que classifica **tokens** em vez de AST. Primeiro passo rumo ao domínio de linguagem.

**Task list:**
- [ ] `audit.py --lang` usa mini-lexicon (100 palavras: substantivo, verbo, adjetivo, conectivo)
- [ ] Fatos viram `(token, kind, noun|verb|...)` em vez de `(func, category, ...)`
- [ ] Patterns simples: "frase declarativa" = verb + noun
- [ ] Escopo: 10 parágrafos de teste (README do próprio doxoade, por exemplo)

**Plano A:** lexicon hardcoded mínimo (100 entradas) em `audit.py`.

**Plano B:** lexicon lido de `data/lexicon_mini.json` (separável).

**Plano C:** se multi-domínio força refactor do kernel, **adia** Q09. X00 fica mono-domínio (só programação) até Q10.

**Saída esperada:**
```
=== README.md (parágrafo 1) ===
  tokens: 42
  kinds: noun=15, verb=12, adj=8, conn=7
  pattern: declarative_paragraph
```

**RIT:** rodar em 3 READMEs, inspecionar manualmente.

**Promoção:** X00 `--lang` em 3 documentos reais com classificação >70% acerto manual.

---

### Cap. 6 — Q10: Consolidação e preparação de promoção

**Contrato:** X00 é promovível a `src/`. Kernel é extraído para módulo compartilhado.

**Task list:**
- [ ] Extrair kernel compartilhado: `src/code_classification/lib/` (Engine, Fact, Rule, matcher)
- [ ] Q00–Q05 mantidos como PoCs históricos (não refatorados — congelados)
- [ ] Q06+ e X00 importam de `lib/`
- [ ] Doc `docs/Research/code_classification/promotion.md` com critérios
- [ ] Coverage: quantos `%` das funções de `doxcolors`, `error_info`, `aegis` são cobertas?
- [ ] Decide próximo vetor: Q11 (mais smells), ou W01 (doxarchives lang seed)

**Plano A:** lib mínimo — `Engine`, `Fact`, `Rule`, `substitute`, `unify`, `match_with_negations`, `_Quiet`, `_dbg`. ~200 L. Rules ficam nos PoCs (não compartilhadas).

**Plano B:** lib completo — inclui `extract_facts` AST + Q00–Q05 rules. X00 importa tudo. PoCs usam lib.

**Plano C:** se promoção vira rabbit hole, **congela** Q10 como está. Lib vira Q11.

**Saída esperada:** `all` = 18/18 verde + X00 PASS em 3 diretórios + lib importável.

**RIT:** extração → teste de importação → `all` → `x00 audit` → revisão.

**Promoção:** X00 + lib em `src/`; PoCs históricos mantidos como regression.

---

## 6. Err table consolidada

| ID | Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|---|
| E1 | X00 trava em arquivo com syntax exótica | média | médio | `--skip <pattern>`; catch `SyntaxError` por arquivo |
| E2 | FPs sistemáticos (ex: `__init__` sempre `long_method`) | alta | médio | refino em batch (Q07); dunder exception |
| E3 | Baseline vira "accept cego" | média | alto | rules em notes.md; diff obrigatório antes de accept |
| E4 | X00 integration no rescue quebra rescue | média | crítico | subprocess com timeout 5s; fallback silencioso |
| E5 | Multi-domínio Q09 conflita com Q06 (kernel divergente) | baixa | alto | plano C: adia Q09 |
| E6 | Consolidação Q10 quebra PoCs históricos | baixa | alto | congelar Q00–Q05; lib só usada por Q06+ e X00 |
| E7 | X00 vira maintanance burden (rules + baseline por diretório) | média | médio | escopo cresce 1 diretório por iteração, não em batch |

---

## 7. Reversibilidade e domesticabilidade

**Reversibilidade** (ProDeNov "Segurança"):
- X00 é **read-only**. Nenhuma escrita em código analisado.
- Baseline versionado em git. `accept` requer commit explícito.
- Rescue integration pode ser desligada por env (`DOXOADE_X00=0`).

**Domesticabilidade:**
- Cada FP catalogado em `notes.md` — referência para não regredir.
- Rule refine tem versão (`X00.1`, `X00.2`) e changelog.
- FP rate é métrica: reportar por rodada, não apenas por arquivo.

**Domar ≠ zerar:** alguns FPs sempre existirão (código real é diverso). Meta não é 0% mas **<5%** e **documentado**.

---

## 8. Critérios de promoção (X00 vira ferramenta de produção)

X00 vira ferramenta oficial de doxoade quando:

| # | Critério | Como medir |
|---|---|---|
| P1 | FP rate < 5% em 3 diretórios | Catalogação em notes.md |
| P2 | Determinismo em 100 runs | Sub-sonda X00f como Q05f |
| P3 | Integration rescue reduz diagnóstico em crashes reais | Medir em 3 crashes reais |
| P4 | Não bloqueia CI (X00 roda < 5s em 3 diretórios) | Time via `timeit` |
| P5 | Baseline versionado e diff-able | `expected_audit_*.txt` por diretório |

Passando P1–P5, X00 sai de `research/` e vira `doxoade/commands/audit_src_cmd.py` (nome reservado — `doxoade audit` já existe).

---

## 9. RIT global (ordem de execução)

```
Q06 ─────► X00 MVP ─────► Q07 iter1 ─────► Q08 rescue ─────► Q09 lang ─────► Q10 promote
 │           │               │               │                │              │
 │           │               │               │                │              │
0.5d        1d              1d              1d               1d             1d

Pré-req:   Fornece         Refina          Valida          Seed           Consolida
          X00 com          rules           integração      multi-dom      kernel
          multi-func
```

**Total estimado:** 5–6 dias úteis (sem contar refinamentos imprevistos).

**Cada capítulo tem seu próprio RIT.** Não pular: `discussão → implementação → teste → discussão/fix`.

---

## 10. Glossário interno do Blitzplan

- **X00** — Doxoade Source Auditor (objeto de produção testbed).
- **Objeto de Produção** — sistema real, controlado e domesticável, usado como testbed para o motor.
- **FP / FN** — false positive / false negative.
- **FP rate** — `FPs / funções analisadas`; meta <5%.
- **Baseline** — `expected_audit_<dir>.txt`, snapshot determinístico.
- **Domesticar** — reduzir FPs via refino de rule, mantendo catálogo em `notes.md`.
- **Escopo MVP** — `doxoade/tools/doxcolors/` (3 arquivos, ~500 LOC).
- **Chapters** — capítulos do Blitzplan, um por "sonda" (Q06, X00, Q07…).
- **RIT** — Roteiro de Implementação e Testagem (ProDeNov conceito).

---

## 11. Próximo passo imediato

Escrever este documento como:

```
doxoade/research/code_classification/BLITZPLAN_X00_Q10.md
```

Salvar, revisar 24h depois (fresh eyes), **só então** começar Q06.

**Não escrever código de Q06 antes de salvar o Blitzplan.** A tentação de "só testar uma coisinha" viola o princípio 5.6.6 (discussão antes de implementação).

---

## 12. Nota — por que não Q06 direto

Q06 direto é **tecnicamente possível** mas **estratégico errado**:

- Q06 vai produzir mais uma sonda sintética.
- Sem objeto de produção, o "PASS" de Q06 não prova nada sobre código real.
- X00 é a **primeira** sonda cujo "PASS" **produz valor** (auditoria da base).

Ordem **Q06 → X00** faz Q06 servir a X00. Ordem **X00 sem Q06** faz X00 ficar mono-função, perdendo pattern composto que é justamente o que Doxoade precisa (funções chamam funções).

**Q06 é pré-requisito de X00. Não é sonda independente.**

---

Salve como `doxoade/research/code_classification/BLITZPLAN_X00_Q10.md`. Revisão depois — dois ajustes que você provavelmente quer discutir antes de Q06:

1. **Escopo do MVP X00** — `doxcolors` é bom, ou prefere `error_info` (arquivo único, ~200 L, ainda menor)?
2. **Baseline por diretório** — `expected_audit_<dirname>.txt` (vários) ou `expected_audit.txt` único (centralizado)?

Só depois que concordar nesses dois, escrevemos `audit.py` (Cap. 2) e rodamos Q06 no Cap. 1.

---

# Discussão — Arquitetura de Tabelamento de Regras

## 1. Antes de tudo — três significados de "tabelamento"

O termo tem três interpretações distintas na literatura. Vale separar para não confundir o que você quer com o que você não quer:

| Acepção | Significado | Onde existe |
|---|---|---|
| **Tabling (SLG resolution)** | Memoização de subgoals em Prolog tabled (XSB, SWI-Prolog). Evita loops e rederivação. | Prolog, Datalog |
| **Decision Tables** | Matriz condição → ação. Cada linha é uma regra, colunas são condições. | Sistemas especialistas clássicos |
| **Rule Catalog / Index** | Tabela organizada de regras consultável por contexto (sua analogia de xadrez). | RETE, CBR, Rule Engines |

**Sua analogia com xadrez aponta para a terceira.** A primeira (tabling) é uma *técnica* — pode ser implementação de suporte. A segunda é um *formato*. A terceira é uma *arquitetura organizacional*, que é o que você parece querer.

Vou tratar das três, com foco na terceira.

---

## 2. Analogia de xadrez — onde ela é honesta e onde engana

A analogia é sedutora e parcialmente verdadeira. Vamos ao mapa real:

| Elemento de xadrez | Estrutura real | Seu equivalente seria |
|---|---|---|
| Opening book | Tabela fixa, contexto = primeiros N movimentos | Regras para "cenários conhecidos" |
| Tablebase (endgame) | Tabela exata, **só** para ≤ 7 peças | Regras para subdomínio **bounded** |
| Tactical patterns | Reconhecimento (fork, pin, skewer) | Padrões (Q03, Q05) |
| Heuristic evaluation | Função contínua, sem tabela | Complexity (Q02), confidence |
| **Mid-game search** | **α-β / MCTS, profundidade 20–40** | **Forward chaining irrestrito** |

**Onde a analogia mente:**

Xadrez **não** funciona "só com regras que tem". Stockfish sem busca perde para humano fraco. Opening book + tablebase cobrem **< 10% das posições de uma partida típica**. Os outros 90% são **busca + heurística**.

**Sua intuição correta:** não precisamos prever "milhões de cenários" *exaustivamente*. Motores modernos **podem** usar α-β com pruning agressivo — que é *essencialmente* tabling + heurística.

**Sua intuição arriscada:** "regras que ele tem" cobre todo cenário. Não cobre — cobre **regiões** que a tabela indexa. Fora da região, sem busca ou sem fallback, você tem **falha silenciosa** (exatamente o problema de Q04 antes de retração).

**Portanto:** a arquitetura é viável **com fallback explícito**, não como substituição.

---

## 3. Sketcho arquitetural — o que "Rule Table" significaria concretamente

Proposta mínima, baseada em três camadas de indexação:

```
RuleTable
  ├── core_rules        → sempre ativas (defaults, invariantes)
  ├── domain_index      → dict[domain, RuleSet]
  │     "programming"   → Q02, Q03, Q05 rules
  │     "diagnosis"     → rescue W5 rules
  │     "language"      → Q09 lexical rules
  ├── symptom_index     → dict[symptom, RuleSet]
  │     "crash"         → stack_trace, error_context
  │     "slow"          → performance hints
  │     "wrong_output"  → semantic checks
  └── rules             → dict[rule_id, Rule]  (single source of truth)
```

**Ativação** — dada uma cena `(facts, domain, symptoms)`:
```
candidates = core_rules
           ∪ domain_index.get(domain, ∅)
           ∪ ⋃_{s ∈ symptoms} symptom_index.get(s, ∅)
```

Forward chaining roda **restrito a `candidates`**. Não roda sobre todas as 20 regras de Q00–Q05; roda sobre 5–8.

**Aprendizado** — cada rule mantém:
```
stats: {fires, unique_conclusions, cycles_used, cost_estimate, fp_rate}
```

Refino periódico:
- **prune** — `fires == 0` após N cenas → desabilitar
- **split** — `fires alto, precisão baixa` → quebrar em sub-regras
- **merge** — `A e B sempre juntas` → regra composta
- **quarantine** — `adicionada recentemente` → confiança baixa por N cenas

**Chaos log** — quando a engine quiesce **sem produzir saída útil** (nenhum `category`, `pattern`, `smell` útil):
```
miss_log.append({
  scene_id, facts_hash, candidates_used, 
  why_nothing_fired, human_took_long
})
```
Este log é **o sinal mais valioso do sistema**. Cada entrada é uma lacuna concreta, não uma opinião.

---

## 4. Viabilidade — análise honesta

### 4.1 Onde é viável

| Cenário | Viável? | Razão |
|---|---|---|
| X00 sobre `doxcolors` (3 arquivos, ~500 LOC) | **Sim** | Bounded, domain = "python", symptoms = "smell"/"pattern" |
| Rescue com X00 em crash | **Sim** | Symptoms = "crash", domínio conhecido |
| Xadrez ≤ 7 peças (tablebase) | **Sim** | Bounded, exato |
| Linguagem natural aberta | **Não** | Contexto não classificável em O(k) |

### 4.2 Onde NÃO é viável (armadilhas)

**Armadilha 1 — o classificador de contexto é recursivo.**
"Em qual cena estou?" é *ele mesmo* um problema de classificação. Se você resolve com keywords (`_has_magic_number`), quebra em código real (nomes ofuscados, metaprogramação). Se resolve com regras, você precisa de *outra* tabela para classificar o classificador. **Profundidade infinita** se não parar.

**Mitigação:** contexto classificado por **regras core** (tier 0, sempre ativa, sem dependência de domain). Core é **estático**, revisado em code review.

**Armadilha 2 — regra única em duas tabelas diverge.**
Se a mesma regra aparece em `domain=programming` e `symptom=crash`, alguém edita uma e esquece a outra. Depois de 3 iterações, divergem silenciosamente.

**Mitigação:** `rules: dict[rule_id, Rule]` é **fonte única**. `domain_index` e `symptom_index` guardam só `rule_id`. Se a mesma regra tem dois contextos, usa composite key: `domain="programming"`, `symptom=["crash"]`.

**Armadilha 3 — falha silenciosa.**
Se a regra correta não está na tabela ativa, engine quiesce **errado** (exatamente Q04a antes de retração). Pior: o output parece plausível (`unknown`).

**Mitigação:** `chaos_log`. Toda quiescência sem `category` útil gera entrada. Sem isso, você não sabe que a tabela está incompleta.

**Armadilha 4 — feedback loop de regra ruim.**
Regra adicionada por dedução ruim → próxima cena usa → conclusão pior → nova dedução pior. Loop degradante.

**Mitigação:** quarentena. Nova regra entra em `candidate` com confiança inicial baixa. Precisa de N cenas com FP_rate baixo para virar `stable`. `rule_registry` de PASC-6 já cobre isso — só não estava ativo em PoCs.

**Armadilha 5 — custo do classificador > custo da inferência.**
Se classificar a cena é `O(scenarios × facts)`, você ganhou zero. O classificador tem que ser **O(k)** com `k` constante pequena (keywords, AST depth, hash prefix).

**Mitigação:** classifier de contexto **indexado por hash** — `context_hash = f(domain, symptoms)`; lookup em dict é O(1). Extração do hash é O(facts).

### 4.3 Veredito de viabilidade

**Viável para domínios bounded (programação, diagnóstico, jogos fechados).**

**Não viável como arquitetura única** para linguagem aberta.

**Correto é híbrido:**
1. **Tabela** para cenário conhecido (rápido, interpretável)
2. **Busca restrita** (forward chaining sobre `candidates`) para fora da tabela
3. **Fallback core** (forward chaining sobre todas) quando candidatos falham
4. **Chaos log** como sinal de necessidade de expansão

Isso **é** o modelo Stockfish: opening (tabela) → mid-game search (forward) → endgame tablebase (tabela) → fallback heurístico.

---

## 5. Multi-propósito — como generaliza

O ponto crítico: **a tabela é sobre o domínio, não sobre a engine**.

```python
# X00 (programação)
audit_src("file.py", domain="programming", symptoms=["smell","pattern"])

# Rescue + X00 (diagnóstico sobre código)
diagnose_crash(trace, domain="diagnosis", symptoms=["crash","code_context"])

# Q09 (linguagem)
classify_text(text, domain="language", symptoms=["ambiguity"])
```

**A engine é a mesma.** O que muda: `core_rules` + `domain_index[domain]`. Isso é exatamente o que você quer — "multi-propósito" com custo de *dados*, não de *código*.

**Risco multi-propósito:** domínios interferem. Regra `_has_magic_number` (programação) não deveria disparar em análise de texto. **Boundary explícito:** rule carrega `domain` field. Core pode ter `domain=core` (todos). Nunca inferência em domínio errado.

---

## 6. Sondas propostas — testar viabilidade em 5 passos

Antes de codar a arquitetura completa, provar viabilidade com sondas pequenas. Seguindo o padrão Q00–Q05, uma pergunta binária por sonda.

### **X01 — Rule Table básico**
**Pergunta:** tabling por `domain` preserva resultado de Q05?
**Teste:** `doxcolors` no X00; engine com `domain_index={"programming": Q05_rules}` restrito. Comparar `output.txt` com Q05 baseline.
**Critério:** PASS byte-a-byte. Se diverge, indexação perdeu regra.
**Tamanho:** ~80 L.

### **X02 — Ativação por symptom**
**Pergunta:** symptom_index reduz cenas de 20 para 5 sem perder resultado?
**Teste:** 5 cenas sintéticas (crash, slow, wrong_output, valid, empty). Cada cena tem `symptom` tag. Só as rules de symptoms ativos rodam. Compare com full-set.
**Critério:** resultado igual + `rules_attempted` cai ≥ 50%.
**Tamanho:** ~100 L.

### **X03 — Chaos log**
**Pergunta:** quiescência silenciosa é detectável?
**Teste:** rodar X00 em `doxoade/tools/doxcolors/` (3 arquivos, ~19 funções). Toda função com `category=unknown` **e** `pattern=None` **e** `smell_*=None` → miss.
**Critério:** ≥ 3 misses identificadas; cada uma com `facts_hash`, `candidates`, `why_nothing_fired`.
**Tamanho:** ~60 L.
**Valor:** primeiros dados de lacuna concreta.

### **X04 — Refino de regra em cena real**
**Pergunta:** uma iteração de refino reduz FP rate?
**Teste:** com X03 misses em mãos, escolher 1 caso. Refinar rule ou adicionar nova. Rodar X00 de novo. Contar quantos misses fecharam, quantos FPs apareceram.
**Critério:** ≥ 1 miss fechada, ≤ 1 novo FP. Se o saldo é negativo, plano B é congelar refino e revisar arquitetura.
**Tamanho:** ~40 L.

### **X05 — Table vs Full-Set**
**Pergunta:** indexação vale o custo?
**Teste:** rodar `doxcolors` com tabela e sem tabela. Medir `rules_attempted`, `cycles`, `wall_time`.
**Critério:** tabela usa ≥ 30% menos `rules_attempted`, não perde resultado.
**Tamanho:** ~30 L (reusa X01/X02).

**X01–X05 juntos: ~310 L.** Cabe em 1 dia. Se todos passam, **arquitetura viável**; expandir para X06+ (context classifier, quarantine, etc.).

---

## 7. Integração com o que existe

| Componente | Como encaixa |
|---|---|
| **Q00–Q05** | Viram `core_rules` + `domain_index["programming"]` |
| **Retraction (Q04)** | Fica na engine, orquestra. Tabela é só indexação |
| **X00 (doxcolors)** | Primeiro consumidor da tabela |
| **rescue.py** | Segundo consumidor (domain="diagnosis") |
| **Q09 (linguagem)** | Terceiro consumidor (domain="language") — **só se** X01–X05 passarem |
| **PASC-6 `rule_registry`** | Implementa quarentena/estado (candidate/stable/deprecated) |
| **TYPHON** | Chaos log vira tabela de erros (já previsto em ProDeNov 5.4) |

---

## 8. Os três riscos arquiteturais que merecem decisão antes de codar

### **R1 — Classificador de contexto: separado ou embutido?**

**Separado:** `ContextClassifier` é um módulo próprio. Recebe `facts`, retorna `(domain, symptoms, confidence)`. Determinístico, testável isoladamente.

**Embutido:** core rules derivam `(scene, domain, symptom)` como fatos. Engine usa via fact lookup.

**Recomendação:** **separado**, mas o classificador é uma `Rule` especializada (não código hardcoded). Assim segue o vocabulário do motor. Se a classificação falha, você vê no `chaos_log` como regra miss.

### **R2 — Tabela estática (build-time) ou dinâmica (learn-time)?**

**Estática:** tabelas em YAML/JSON. Versionadas. Determinismo absoluto. Refino é manual (dev). Nenhum risco de feedback loop.

**Dinâmica:** tabela cresce com `chaos_log` e refino. Determinismo depende de versão. Risco real de degradação.

**Recomendação:** **estática no MVP (X01–X05)**. Dinâmica só depois que quarentena estiver provada (X06+).

### **R3 — Fallback explícito ou erro?**

**Fallback:** se candidates falham, roda full-set. Sempre produz algum output. Risco: performance ruim em chaos, falha silenciosa ainda possível se full-set também não cobre.

**Erro:** se candidates falham, **raise** `NoRuleApplicable`. Diagnóstico honesto, mas quebra automação.

**Recomendação:** **fallback + log**. Full-set roda; se full-set também quiesce sem produzir nada útil, aí sim `miss` no chaos_log. Duas camadas de honestidade.

---

## 9. Próximos passos concretos

Sugiro esta ordem, **discutida antes de implementada**:

1. **Discutir R1/R2/R3** (esta resposta)
2. **Salvar como `docs/Research/code_classification/BLITZPLAN_X00_RULETABLE.md`** — extensão do BLITZPLAN anterior
3. **Decidir escopo MVP** (`doxcolors` confirmado? `error_info` como alternativa?)
4. **X01 primeiro** — 80 L, prova que tabling por domain preserva resultado
5. Se X01 verde, **X03** (chaos log) antes de X02 — o log ensina mais que a otimização
6. X04, X02, X05 nesta ordem
7. **Só então** considerar X06+ (quarentena, refine automático)

**A pergunta que precede tudo:** você quer tabling **como experimento viável** (5 sondas, ~1 dia) ou **como arquitetura de produção** (refatorar Q00–Q05 + X00 agora)? Minha recomendação clara é a **primeira** — testar viabilidade antes de refatorar. A segunda vira rabbit hole se a tabela não ganhar nada.

---

## 10. Uma crítica que precisa ser dita

Sua frase *"ele não prevê milhões de cenários, ele trabalha com as regras que ele tem"* é verdade para **opening/endgame**, mas **falsa** para mid-game. Xadrez sem busca perde. Sistemas simbólicos sem busca falham em código real (você viu isso em Q04, Q05 hoje).

**A tabela não substitui busca.** Ela **restringe** a busca. Isso é bom — mas o framework mental precisa ser:
- **Tabela é filtro**, não substituto
- **Forward chaining continua sendo o motor**
- **Chaos log é o sensor** de lacunas

Se você concorda com isso, X01–X05 fazem sentido. Se você quer "tabela que substitui engine", a arquitetura não é viável — e a discussão fica honesta ao dizer isso agora.

---

Diga **"vai X01"** se quiser ver o primeiro probe implementado, ou abra as decisões R1/R2/R3 primeiro. Minha sugestão: **decidir R3 primeiro** (fallback ou erro) — é a decisão que define se X01–X05 testam uma arquitetura útil ou uma quebrada.

R1 separado, R2 por hora estatica, R3 fallback + log, problema sempre vai ter a questão é como vamos aprender com ele. esta linha de pesquia sobre tabelamento é algo particular para o futuro devido a complexidade e viabilidade, por hora vamos proseguir com X01

---



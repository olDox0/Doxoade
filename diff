--- [AUDIT] RFC_llm.xml vs disco ---

■ doxoade/research/blitz_plano_x00.md
  xml=510 linhas | disco=750 linhas
--- XML:doxoade/research/blitz_plano_x00.md
+++ DISCO:doxoade/research/blitz_plano_x00.md
@@ -1,29 +1,46 @@
-
 # BLITZPLAN — X00 + Q06–Q10
+
 ## Objeto de Produção como contato controlado com problemas reais
----
+
+---
+
 ## 0. Contexto — a máquina maior
+
 O `code_classification` não é um fim. É componente de uma **máquina de decisão** que atua em três domínios sobrepostos:
+
 | Domínio | Entrada | Saída | Exemplo de uso |
 |---|---|---|---|
 | **Programação** | AST, código | Classificação, smell, pattern | "esta função é factory?", "este loop tem bug?" |
 | **Diagnóstico** | Traces, logs, W5 | Hipótese de causa, plano de fix | "por que este crash aconteceu?" |
 | **Linguagem** | Texto natural | Classificação simbólica, sem embedding | "este parágrafo é descritivo?" |
+
 Q00–Q05 validaram o motor **em isolamento**, com inputs sintéticos. Nenhum deles teve **contexto real**:
 - Código escrito por engenheiros reais (não 5 linhas de teste)
 - Problemas reais (não truques para a rule casar)
 - Consequências (não só output em arquivo)
+
 **Sem objeto de produção, Q06+ vira mais sintético**, e o motor pode se especializar em resolver problemas que ninguém tem.
----
+
+---
+
 ## 1. Por que Objeto de Produção, e por que agora
+
 Três razões concretas:
+
 **1.1. Custo do erro sintético é baixo demais.** Q00–Q05 passaram de primeira. Mas isso não prova que o motor lida com `doxoade/tools/aegis/aegis_utils.py` (350 linhas, imports encadeados, classes). Pode ser que `category=unknown` para 90% do código real — o que é **falha de cobertura**, não de motor.
+
 **1.2. W5 de problemas reais é diferente.** Problema real tem: quem invocou, quando, em qual build, com qual config, qual commit. Sintético tem só o input.
+
 **1.3. ProDeNov "Anti Long Shot" (3.1.6) exige sonda.** Sem medir performance/smell/pattern em código real, não sabemos se o motor é útil ou se é exercício acadêmico.
+
 **O que muda com X00:** cada false positive é **informação** (rule mal calibrada), cada true positive é **valor produzido** (auditoria da base real). Ambos domesticáveis.
----
+
+---
+
 ## 2. Critérios de Objeto de Produção
+
 Todo objeto de produção de teste deve satisfazer **6 critérios**:
+
 | # | Critério | Pergunta de teste |
 |---|---|---|
 | **C1** | **Real** | Existe fora do escopo PoC? É usado por alguém (mesmo que só o dev)? |
@@ -32,16 +49,22 @@
 | **C4** | **Reversível** | Podemos voltar ao estado anterior sem corromper nada? |
 | **C5** | **Observável** | W5 completo: onde, o que, quando, quem, por que? |
 | **C6** | **Pequeno** | Cabe na cabeça do dev (~500–2000 LOC) para diagnóstico manual? |
+
 Um objeto que falha em qualquer critério não serve como testbed — vira fonte de ruído ou de rabbit hole.
----
+
+---
+
 ## 3. Candidatos e seleção
+
 | Candidato | C1 Real | C2 Control | C3 Domest | C4 Revers | C5 Obs | C6 Peq | Veredito |
 |---|---|---|---|---|---|---|---|
 | **A. Doxoade Source Auditor** | ✅ código do doxoade | ✅ subdir | ✅ rule-refine | ✅ read-only | ✅ AST + W5 | ✅ | **selecionado** |
 | B. Doxoade Doctor v2 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | reserva Q08 |
 | C. Doxarchives lexical | ✅ | ⚠️ precisa corpus | ⚠️ vocabulário aberto | ✅ | ✅ | ❌ grande | deferido Q09+ |
 | D. Mini Python parser | ⚠️ inventado | ✅ | ⚠️ we own bugs | ✅ | ✅ | ✅ | descartado (não é real) |
+
 **Selecionado: A — Doxoade Source Auditor (X00).**
+
 Por quê:
 - **Código real** do próprio doxoade, com bugs reais (você mesmo já corrigiu `_run_engine` duas vezes hoje)
 - **Escopo ajustável**: começar em `doxoade/tools/doxcolors/` (~500 LOC), expandir conforme confiança
@@ -49,20 +72,29 @@
 - **Reversível**: X00 só **lê** código; não modifica nada
 - **Observável**: cada função reportada tem `category`, `complexity`, `smell_*`, `pattern`
 - **Pequeno**: 1 arquivo por vez, diagnóstico manual viável
+
 **Bônus não-trivial:** quando X00 ganhar confiança, o **retro-forward-doctor** pode usar X00 para auto-auditar o próprio doxoade. **O sistema começa a se usar.**
----
+
+---
+
 ## 4. X00 — Doxoade Source Auditor (definição)
+
 ### 4.1. Contrato
+
 ```
 audit(path: str|Path) -> AuditReport
 ```
+
 Onde:
 - `path` = arquivo `.py` OU diretório (recursivo)
 - `AuditReport` = estrutura serializável (dict/JSON)
+
 X00 **não** substitui Q00–Q05. Usa o mesmo kernel inline (por enquanto — consolidação fica para Q10), mas o output é diferente:
 - Q00–Q05: `expected_XX.txt`, um arquivo por PoC
 - X00: relatório por arquivo/função, comparado contra baseline `expected_audit.txt`
+
 ### 4.2. Estrutura
+
 ```
 doxoade/research/code_classification/
   x00_source_auditor/
@@ -71,21 +103,29 @@
     README.md                   # escopo, critérios, contrato
     notes.md                    # catálogo de FPs/FNs domados
 ```
+
 Não é `poc/X00/`. X00 é **produção-shaped** desde o início. Fica fora do `poc/` porque:
 - Não vai ser descartada após PASS
 - Vai evoluir (Q07+ refinam rules)
 - Baseline é regressão de longo prazo
+
 ### 4.3. Interface
+
 ```cmd
 :: auditoria básica (só output)
 py -3.12 doxoade\research\code_classification\x00_source_auditor\audit.py doxoade\tools\doxcolors\
+
 :: comparar com baseline
 py -3.12 ... audit.py doxoade\tools\doxcolors\ --expected expected_audit_colors.txt
+
 :: regenerar baseline (após aceitar mudança)
 py -3.12 ... audit.py doxoade\tools\doxcolors\ --accept expected_audit_colors.txt
 ```
+
 **CLI registration fica para Q08.** MVP: standalone script (mais simples, mais reversível).
+
 ### 4.4. Saída esperada
+
 ```
 === doxoade/tools/doxcolors/colors.py ===
   [1] ansi_strip            category=unknown        complexity=2    smell_magic_number=yes   pattern=None
@@ -96,6 +136,7 @@
   [6] back_rgb              category=unknown        complexity=1    smell_magic_number=yes   pattern=None
   [7] init                  category=unknown        complexity=2    smell_long_method=yes    pattern=None
   ...
+
 === SUMMARY ===
   files scanned:      3
   functions scanned:  19
@@ -103,39 +144,59 @@
   smell dist:         {magic: 12, long: 1, dead: 0}
   retractions total:  0
 ```
+
 **Sinal honesto:** `unknown: 17` para `doxcolors` significa que `category` **não cobre** código de constante/atribuição. É informação valiosa — Q07+ vai refinar categorias com base neste output.
+
 ### 4.5. Baseline — `expected_audit_colors.txt`
+
 Snapshot determinístico do output atual para regressão. Toda mudança em X00 (Q07 rules, Q10 consolidação) que altere output é revisada via diff.
+
 Se `expected` diverge muito em Q07, **não usar `accept` cegamente**. Cada linha divergente é:
 - bug de rule → patch
 - nova capacidade → aceitar com nota
 - mudança de contrato → `expected` versionado + tag no README
----
+
+---
+
 ## 5. Blitzplan — Q06 a Q10
+
 ### Cap. 1 — Q06: multi-função (pré-requisito de X00)
+
 **Contrato:** DC2 com sujeitos distintos. Fatos de `f1` casam com regras que produzem fatos de `f2`.
+
 **Task list:**
 - [ ] `_extract_calls(func)` → `Call.func.id` de cada `ast.Call` no body
 - [ ] Fatos `(f, calls, helper)` por função chamada
 - [ ] Pattern `delegating_factory`: `(f1, pattern, factory)` AND `(f1, returns_call, helper)` AND `(helper, pattern, factory)` → `(f1, pattern, delegating_factory)`
 - [ ] Sub-sondas: `factory` chama outro `factory` (visitor), `factory` chama `helper` comum (não pattern)
+
 **Plano A:** extração direta via `ast.walk(body)`, filtrar `ast.Call`, pegar `func.id` se `ast.Name`.
+
 **Plano B (se walk gera ruído):** visitor pattern explícito, só `ast.Call` no body-level + 1 nível de nested.
+
 **Plano C (se multi-função exige engine reescrito):** adiar Q06 e começar X00 com kernel Q05 (sem multi-função). Q06 vira Q07.
+
 **Saída esperada:**
 ```
 === Q06a ===
   input: 'def create_user(n): return User.make(n)'
   pattern:       factory
+
 === Q06b ===
   input: 'def build(n): return create_user(n)'
   pattern:       delegating_factory   (calls create_user que é factory)
 ```
+
 **RIT:** discussão → implementação → 5 sub-sondas → revisão.
+
 **Promoção:** Q06 verde → X00 pode usar pattern composto.
----
+
+---
+
 ### Cap. 2 — X00 MVP: Doxoade Source Auditor
+
 **Contrato:** `audit(path) -> report` determinístico, reversível (read-only).
+
 **Task list:**
 - [ ] `audit.py` com kernel inline (Q05 inlined + Q06 calls extraction)
 - [ ] `--expected <file>` e `--accept <file>`
@@ -144,41 +205,61 @@
 - [ ] Gerar `expected_audit_colors.txt`
 - [ ] Anotar FPs conhecidos em `notes.md`
 - [ ] README com escopo explícito
+
 **Plano A:** kernel inline completo (Q05 + Q06). ~350 L.
+
 **Plano B:** se inline é grande demais, extrair kernel para `x00_source_auditor/_kernel.py` (import de si mesmo). Não é "shared lib" ainda — é privado de X00.
+
 **Plano C:** se for ler código do doxoade e travar em algum arquivo (import circular, syntax rara), fazer `--skip <pattern>` para excluir arquivos problemáticos. Anotar em `notes.md`.
+
 **Saída esperada:**
 ```
 $ py -3.12 audit.py doxoade/tools/doxcolors/ --expected expected_audit_colors.txt
 PASS: 3 files, 19 functions
 ```
+
 **RIT:**
 1. Rodar `audit.py` sem baseline (gerar output cru)
 2. Inspecionar manualmente 5–10 funções (2 minutos)
 3. Salvar como baseline se tudo coerente
 4. Rodar de novo com `--expected` (deve PASS imediatamente, determinismo)
+
 **Promoção:** X00 MVP estável em `doxcolors` → expandir escopo em Q07.
----
+
+---
+
 ### Cap. 3 — Q07: X00 iteration 1 (real feedback)
+
 **Contrato:** X00 roda em 3–5 diretórios do doxoade; false positives são catalogados; rules são refinadas.
+
 **Task list:**
 - [ ] Rodar em `doxoade/tools/error_info/`, `doxoade/tools/aegis/`, `doxoade/commands/` (parcial)
 - [ ] Catalogar FPs em `notes.md` (formato: arquivo:função → razão)
 - [ ] Catalogar FNs (o que X00 **deveria** flagar e não flagou)
 - [ ] Refinar rules com base no catálogo → **bump de versão** de X00 (X00.1, X00.2)
 - [ ] Cada refino tem `expected_audit_<dir>.txt` próprio
+
 **Plano A:** 1 diretório por vez, 3 iterações, refinar 1–2 rules por iteração.
+
 **Plano B:** se o volume de FPs é alto (>30% das funções), **congelar** refinamento e voltar para Q06 (falta extração mais rica).
+
 **Plano C:** se o padrão é sistemático (ex: "todas as funções com `__` no nome geram magic_number"), adicionar `_name_prefix` para `dunder` e refinar em batch.
+
 **Saída esperada:**
 - Primeira rodada: ~30% FPs identificados
 - Segunda rodada: ~10%
 - Terceira rodada: ~3% (aceitável como "long tail" — documentada em notes.md)
+
 **RIT:** rodar → catalogar → refinar → re-rodar → diff baseline → revisão.
+
 **Promoção:** FP rate < 5% nos 3 diretórios → X00 candidato a doctor embed.
----
+
+---
+
 ### Cap. 4 — Q08: X00 integrado ao rescue
+
 **Contrato:** rescue detecta crashes em arquivos com smells conhecidas e **sugere** (não auto-aplica) hipótese.
+
 **Task list:**
 - [ ] `rescue._collect_fixes_for_crime` chama `x00.audit(crime_file)` (só o arquivo do crime)
 - [ ] Se smell detectado na **linha do crime** (ou adjacente), mostrar `[AUDIT]` block:
@@ -189,30 +270,45 @@
   ```
 - [ ] Sem auto-fix — só sugestão. Fix continua manual.
 - [ ] Option 9 no menu rescue: "Ver auditoria X00 do arquivo"
+
 **Plano A:** integração via subprocess (`py audit.py <file> --json`) com timeout curto (5s). Sem import direto (isola crash loops).
+
 **Plano B:** import direto `from code_classification.x00_source_auditor import audit` — mais rápido, mas adiciona dependência de rescue em X00.
+
 **Plano C:** se subprocess é instável, rescue lê `notes.md` cache (offline).
+
 **Saída esperada (rescue no `_run_engine` crash):**
 ```
 ■ CENA DO CRIME : retro_forward_cmd.py:147
   >>  147 | return False, f"engine exit ...: {informative[:200]}", ...
+
 ■ AUDITORIA (X00):
   smoke: nenhum smell na linha 147
   hint: variavel 'informative' nao definida — typo em nome?
 ```
+
 **RIT:** provocar crash com smell conhecido → verificar AUDIT block → comparar com output sem X00.
+
 **Promoção:** rescue com X00 reduz tempo de diagnóstico (medido em 3 crashes reais).
----
+
+---
+
 ### Cap. 5 — Q09: X00 multi-domínio (seed de linguagem)
+
 **Contrato:** X00 ganha modo `--lang` que classifica **tokens** em vez de AST. Primeiro passo rumo ao domínio de linguagem.
+
 **Task list:**
 - [ ] `audit.py --lang` usa mini-lexicon (100 palavras: substantivo, verbo, adjetivo, conectivo)
 - [ ] Fatos viram `(token, kind, noun|verb|...)` em vez de `(func, category, ...)`
 - [ ] Patterns simples: "frase declarativa" = verb + noun
 - [ ] Escopo: 10 parágrafos de teste (README do próprio doxoade, por exemplo)
+
 **Plano A:** lexicon hardcoded mínimo (100 entradas) em `audit.py`.
+
 **Plano B:** lexicon lido de `data/lexicon_mini.json` (separável).
+
 **Plano C:** se multi-domínio força refactor do kernel, **adia** Q09. X00 fica mono-domínio (só programação) até Q10.
+
 **Saída esperada:**
 ```
 === README.md (parágrafo 1) ===
@@ -220,11 +316,17 @@
   kinds: noun=15, verb=12, adj=8, conn=7
   pattern: declarative_paragraph
 ```
+
 **RIT:** rodar em 3 READMEs, inspecionar manualmente.
+
 **Promoção:** X00 `--lang` em 3 documentos reais com classificação >70% acerto manual.
----
+
+---
+
 ### Cap. 6 — Q10: Consolidação e preparação de promoção
+
 **Contrato:** X00 é promovível a `src/`. Kernel é extraído para módulo compartilhado.
+
 **Task list:**
 - [ ] Extrair kernel compartilhado: `src/code_classification/lib/` (Engine, Fact, Rule, matcher)
 - [ ] Q00–Q05 mantidos como PoCs históricos (não refatorados — congelados)
@@ -232,14 +334,23 @@
 - [ ] Doc `docs/Research/code_classification/promotion.md` com critérios
 - [ ] Coverage: quantos `%` das funções de `doxcolors`, `error_info`, `aegis` são cobertas?
 - [ ] Decide próximo vetor: Q11 (mais smells), ou W01 (doxarchives lang seed)
+
 **Plano A:** lib mínimo — `Engine`, `Fact`, `Rule`, `substitute`, `unify`, `match_with_negations`, `_Quiet`, `_dbg`. ~200 L. Rules ficam nos PoCs (não compartilhadas).
+
 **Plano B:** lib completo — inclui `extract_facts` AST + Q00–Q05 rules. X00 importa tudo. PoCs usam lib.
+
 **Plano C:** se promoção vira rabbit hole, **congela** Q10 como está. Lib vira Q11.
+
 **Saída esperada:** `all` = 18/18 verde + X00 PASS em 3 diretórios + lib importável.
+
 **RIT:** extração → teste de importação → `all` → `x00 audit` → revisão.
+
 **Promoção:** X00 + lib em `src/`; PoCs históricos mantidos como regression.
----
+
+---
+
 ## 6. Err table consolidada
+
 | ID | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|---|
 | E1 | X00 trava em arquivo com syntax exótica | média | médio | `--skip <pattern>`; catch `SyntaxError` por arquivo |
@@ -249,20 +360,29 @@
 | E5 | Multi-domínio Q09 conflita com Q06 (kernel divergente) | baixa | alto | plano C: adia Q09 |
 | E6 | Consolidação Q10 quebra PoCs históricos | baixa | alto | congelar Q00–Q05; lib só usada por Q06+ e X00 |
 | E7 | X00 vira maintanance burden (rules + baseline por diretório) | média | médio | escopo cresce 1 diretório por iteração, não em batch |
----
+
+---
+
 ## 7. Reversibilidade e domesticabilidade
+
 **Reversibilidade** (ProDeNov "Segurança"):
 - X00 é **read-only**. Nenhuma escrita em código analisado.
 - Baseline versionado em git. `accept` requer commit explícito.
 - Rescue integration pode ser desligada por env (`DOXOADE_X00=0`).
+
 **Domesticabilidade:**
 - Cada FP catalogado em `notes.md` — referência para não regredir.
 - Rule refine tem versão (`X00.1`, `X00.2`) e changelog.
 - FP rate é métrica: reportar por rodada, não apenas por arquivo.
+
 **Domar ≠ zerar:** alguns FPs sempre existirão (código real é diverso). Meta não é 0% mas **<5%** e **documentado**.
----
+
+---
+
 ## 8. Critérios de promoção (X00 vira ferramenta de produção)
+
 X00 vira ferramenta oficial de doxoade quando:
+
 | # | Critério | Como medir |
 |---|---|---|
 | P1 | FP rate < 5% em 3 diretórios | Catalogação em notes.md |
@@ -270,22 +390,32 @@
 | P3 | Integration rescue reduz diagnóstico em crashes reais | Medir em 3 crashes reais |
 | P4 | Não bloqueia CI (X00 roda < 5s em 3 diretórios) | Time via `timeit` |
 | P5 | Baseline versionado e diff-able | `expected_audit_*.txt` por diretório |
+
 Passando P1–P5, X00 sai de `research/` e vira `doxoade/commands/audit_src_cmd.py` (nome reservado — `doxoade audit` já existe).
----
+
+---
+
 ## 9. RIT global (ordem de execução)
+
 ```
 Q06 ─────► X00 MVP ─────► Q07 iter1 ─────► Q08 rescue ─────► Q09 lang ─────► Q10 promote
  │           │               │               │                │              │
  │           │               │               │                │              │
 0.5d        1d              1d              1d               1d             1d
+
 Pré-req:   Fornece         Refina          Valida          Seed           Consolida
           X00 com          rules           integração      multi-dom      kernel
           multi-func
 ```
+
 **Total estimado:** 5–6 dias úteis (sem contar refinamentos imprevistos).
+
 **Cada capítulo tem seu próprio RIT.** Não pular: `discussão → implementação → teste → discussão/fix`.
----
+
+---
+
 ## 10. Glossário interno do Blitzplan
+
 - **X00** — Doxoade Source Auditor (objeto de produção testbed).
 - **Objeto de Produção** — sistema real, controlado e domesticável, usado como testbed para o motor.
 - **FP / FN** — false positive / false negative.
@@ -295,41 +425,68 @@
 - **Escopo MVP** — `doxoade/tools/doxcolors/` (3 arquivos, ~500 LOC).
 - **Chapters** — capítulos do Blitzplan, um por "sonda" (Q06, X00, Q07…).
 - **RIT** — Roteiro de Implementação e Testagem (ProDeNov conceito).
----
+
+---
+
 ## 11. Próximo passo imediato
+
 Escrever este documento como:
+
 ```
 doxoade/research/code_classification/BLITZPLAN_X00_Q10.md
 ```
+
 Salvar, revisar 24h depois (fresh eyes), **só então** começar Q06.
+
 **Não escrever código de Q06 antes de salvar o Blitzplan.** A tentação de "só testar uma coisinha" viola o princípio 5.6.6 (discussão antes de implementação).
----
+
+---
+
 ## 12. Nota — por que não Q06 direto
+
 Q06 direto é **tecnicamente possível** mas **estratégico errado**:
+
 - Q06 vai produzir mais uma sonda sintética.
 - Sem objeto de produção, o "PASS" de Q06 não prova nada sobre código real.
 - X00 é a **primeira** sonda cujo "PASS" **produz valor** (auditoria da base).
+
 Ordem **Q06 → X00** faz Q06 servir a X00. Ordem **X00 sem Q06** faz X00 ficar mono-função, perdendo pattern composto que é justamente o que Doxoade precisa (funções chamam funções).
+
 **Q06 é pré-requisito de X00. Não é sonda independente.**
----
+
+---
+
 Salve como `doxoade/research/code_classification/BLITZPLAN_X00_Q10.md`. Revisão depois — dois ajustes que você provavelmente quer discutir antes de Q06:
+
 1. **Escopo do MVP X00** — `doxcolors` é bom, ou prefere `error_info` (arquivo único, ~200 L, ainda menor)?
 2. **Baseline por diretório** — `expected_audit_<dirname>.txt` (vários) ou `expected_audit.txt` único (centralizado)?
+
 Só depois que concordar nesses dois, escrevemos `audit.py` (Cap. 2) e rodamos Q06 no Cap. 1.
----
+
+---
+
 # Discussão — Arquitetura de Tabelamento de Regras
+
 ## 1. Antes de tudo — três significados de "tabelamento"
+
 O termo tem três interpretações distintas na literatura. Vale separar para não confundir o que você quer com o que você não quer:
+
 | Acepção | Significado | Onde existe |
 |---|---|---|
 | **Tabling (SLG resolution)** | Memoização de subgoals em Prolog tabled (XSB, SWI-Prolog). Evita loops e rederivação. | Prolog, Datalog |
 | **Decision Tables** | Matriz condição → ação. Cada linha é uma regra, colunas são condições. | Sistemas especialistas clássicos |
 | **Rule Catalog / Index** | Tabela organizada de regras consultável por contexto (sua analogia de xadrez). | RETE, CBR, Rule Engines |
+
 **Sua analogia com xadrez aponta para a terceira.** A primeira (tabling) é uma *técnica* — pode ser implementação de suporte. A segunda é um *formato*. A terceira é uma *arquitetura organizacional*, que é o que você parece querer.
+
 Vou tratar das três, com foco na terceira.
----
+
+---
+
 ## 2. Analogia de xadrez — onde ela é honesta e onde engana
+
 A analogia é sedutora e parcialmente verdadeira. Vamos ao mapa real:
+
 | Elemento de xadrez | Estrutura real | Seu equivalente seria |
 |---|---|---|
 | Opening book | Tabela fixa, contexto = primeiros N movimentos | Regras para "cenários conhecidos" |
@@ -337,14 +494,23 @@
 | Tactical patterns | Reconhecimento (fork, pin, skewer) | Padrões (Q03, Q05) |
 | Heuristic evaluation | Função contínua, sem tabela | Complexity (Q02), confidence |
 | **Mid-game search** | **α-β / MCTS, profundidade 20–40** | **Forward chaining irrestrito** |
+
 **Onde a analogia mente:**
+
 Xadrez **não** funciona "só com regras que tem". Stockfish sem busca perde para humano fraco. Opening book + tablebase cobrem **< 10% das posições de uma partida típica**. Os outros 90% são **busca + heurística**.
+
 **Sua intuição correta:** não precisamos prever "milhões de cenários" *exaustivamente*. Motores modernos **podem** usar α-β com pruning agressivo — que é *essencialmente* tabling + heurística.
+
 **Sua intuição arriscada:** "regras que ele tem" cobre todo cenário. Não cobre — cobre **regiões** que a tabela indexa. Fora da região, sem busca ou sem fallback, você tem **falha silenciosa** (exatamente o problema de Q04 antes de retração).
+
 **Portanto:** a arquitetura é viável **com fallback explícito**, não como substituição.
----
+
+---
+
 ## 3. Sketcho arquitetural — o que "Rule Table" significaria concretamente
+
 Proposta mínima, baseada em três camadas de indexação:
+
 ```
 RuleTable
   ├── core_rules        → sempre ativas (defaults, invariantes)
@@ -358,22 +524,27 @@
   │     "wrong_output"  → semantic checks
   └── rules             → dict[rule_id, Rule]  (single source of truth)
 ```
+
 **Ativação** — dada uma cena `(facts, domain, symptoms)`:
 ```
 candidates = core_rules
            ∪ domain_index.get(domain, ∅)
            ∪ ⋃_{s ∈ symptoms} symptom_index.get(s, ∅)
 ```
+
 Forward chaining roda **restrito a `candidates`**. Não roda sobre todas as 20 regras de Q00–Q05; roda sobre 5–8.
+
 **Aprendizado** — cada rule mantém:
 ```
 stats: {fires, unique_conclusions, cycles_used, cost_estimate, fp_rate}
 ```
+
 Refino periódico:
 - **prune** — `fires == 0` após N cenas → desabilitar
 - **split** — `fires alto, precisão baixa` → quebrar em sub-regras
 - **merge** — `A e B sempre juntas` → regra composta
 - **quarantine** — `adicionada recentemente` → confiança baixa por N cenas
+
 **Chaos log** — quando a engine quiesce **sem produzir saída útil** (nenhum `category`, `pattern`, `smell` útil):
 ```
 miss_log.append({
@@ -382,85 +553,125 @@
 })
 ```
 Este log é **o sinal mais valioso do sistema**. Cada entrada é uma lacuna concreta, não uma opinião.
----
+
+---
+
 ## 4. Viabilidade — análise honesta
+
 ### 4.1 Onde é viável
+
 | Cenário | Viável? | Razão |
 |---|---|---|
 | X00 sobre `doxcolors` (3 arquivos, ~500 LOC) | **Sim** | Bounded, domain = "python", symptoms = "smell"/"pattern" |
 | Rescue com X00 em crash | **Sim** | Symptoms = "crash", domínio conhecido |
 | Xadrez ≤ 7 peças (tablebase) | **Sim** | Bounded, exato |
 | Linguagem natural aberta | **Não** | Contexto não classificável em O(k) |
+
 ### 4.2 Onde NÃO é viável (armadilhas)
+
 **Armadilha 1 — o classificador de contexto é recursivo.**
 "Em qual cena estou?" é *ele mesmo* um problema de classificação. Se você resolve com keywords (`_has_magic_number`), quebra em código real (nomes ofuscados, metaprogramação). Se resolve com regras, você precisa de *outra* tabela para classificar o classificador. **Profundidade infinita** se não parar.
+
 **Mitigação:** contexto classificado por **regras core** (tier 0, sempre ativa, sem dependência de domain). Core é **estático**, revisado em code review.
+
 **Armadilha 2 — regra única em duas tabelas diverge.**
 Se a mesma regra aparece em `domain=programming` e `symptom=crash`, alguém edita uma e esquece a outra. Depois de 3 iterações, divergem silenciosamente.
+
 **Mitigação:** `rules: dict[rule_id, Rule]` é **fonte única**. `domain_index` e `symptom_index` guardam só `rule_id`. Se a mesma regra tem dois contextos, usa composite key: `domain="programming"`, `symptom=["crash"]`.
+
 **Armadilha 3 — falha silenciosa.**
 Se a regra correta não está na tabela ativa, engine quiesce **errado** (exatamente Q04a antes de retração). Pior: o output parece plausível (`unknown`).
+
 **Mitigação:** `chaos_log`. Toda quiescência sem `category` útil gera entrada. Sem isso, você não sabe que a tabela está incompleta.
+
 **Armadilha 4 — feedback loop de regra ruim.**
 Regra adicionada por dedução ruim → próxima cena usa → conclusão pior → nova dedução pior. Loop degradante.
+
 **Mitigação:** quarentena. Nova regra entra em `candidate` com confiança inicial baixa. Precisa de N cenas com FP_rate baixo para virar `stable`. `rule_registry` de PASC-6 já cobre isso — só não estava ativo em PoCs.
+
 **Armadilha 5 — custo do classificador > custo da inferência.**
 Se classificar a cena é `O(scenarios × facts)`, você ganhou zero. O classificador tem que ser **O(k)** com `k` constante pequena (keywords, AST depth, hash prefix).
+
 **Mitigação:** classifier de contexto **indexado por hash** — `context_hash = f(domain, symptoms)`; lookup em dict é O(1). Extração do hash é O(facts).
+
 ### 4.3 Veredito de viabilidade
+
 **Viável para domínios bounded (programação, diagnóstico, jogos fechados).**
+
 **Não viável como arquitetura única** para linguagem aberta.
+
 **Correto é híbrido:**
 1. **Tabela** para cenário conhecido (rápido, interpretável)
 2. **Busca restrita** (forward chaining sobre `candidates`) para fora da tabela
 3. **Fallback core** (forward chaining sobre todas) quando candidatos falham
 4. **Chaos log** como sinal de necessidade de expansão
+
 Isso **é** o modelo Stockfish: opening (tabela) → mid-game search (forward) → endgame tablebase (tabela) → fallback heurístico.
----
+
+---
+
 ## 5. Multi-propósito — como generaliza
+
 O ponto crítico: **a tabela é sobre o domínio, não sobre a engine**.
+
 ```python
 # X00 (programação)
 audit_src("file.py", domain="programming", symptoms=["smell","pattern"])
+
 # Rescue + X00 (diagnóstico sobre código)
 diagnose_crash(trace, domain="diagnosis", symptoms=["crash","code_context"])
+
 # Q09 (linguagem)
 classify_text(text, domain="language", symptoms=["ambiguity"])
 ```
+
 **A engine é a mesma.** O que muda: `core_rules` + `domain_index[domain]`. Isso é exatamente o que você quer — "multi-propósito" com custo de *dados*, não de *código*.
+
 **Risco multi-propósito:** domínios interferem. Regra `_has_magic_number` (programação) não deveria disparar em análise de texto. **Boundary explícito:** rule carrega `domain` field. Core pode ter `domain=core` (todos). Nunca inferência em domínio errado.
----
+
+---
+
 ## 6. Sondas propostas — testar viabilidade em 5 passos
+
 Antes de codar a arquitetura completa, provar viabilidade com sondas pequenas. Seguindo o padrão Q00–Q05, uma pergunta binária por sonda.
+
 ### **X01 — Rule Table básico**
 **Pergunta:** tabling por `domain` preserva resultado de Q05?
 **Teste:** `doxcolors` no X00; engine com `domain_index={"programming": Q05_rules}` restrito. Comparar `output.txt` com Q05 baseline.
 **Critério:** PASS byte-a-byte. Se diverge, indexação perdeu regra.
 **Tamanho:** ~80 L.
+
 ### **X02 — Ativação por symptom**
 **Pergunta:** symptom_index reduz cenas de 20 para 5 sem perder resultado?
 **Teste:** 5 cenas sintéticas (crash, slow, wrong_output, valid, empty). Cada cena tem `symptom` tag. Só as rules de symptoms ativos rodam. Compare com full-set.
 **Critério:** resultado igual + `rules_attempted` cai ≥ 50%.
 **Tamanho:** ~100 L.
+
 ### **X03 — Chaos log**
 **Pergunta:** quiescência silenciosa é detectável?
 **Teste:** rodar X00 em `doxoade/tools/doxcolors/` (3 arquivos, ~19 funções). Toda função com `category=unknown` **e** `pattern=None` **e** `smell_*=None` → miss.
 **Critério:** ≥ 3 misses identificadas; cada uma com `facts_hash`, `candidates`, `why_nothing_fired`.
 **Tamanho:** ~60 L.
 **Valor:** primeiros dados de lacuna concreta.
+
 ### **X04 — Refino de regra em cena real**
 **Pergunta:** uma iteração de refino reduz FP rate?
 **Teste:** com X03 misses em mãos, escolher 1 caso. Refinar rule ou adicionar nova. Rodar X00 de novo. Contar quantos misses fecharam, quantos FPs apareceram.
 **Critério:** ≥ 1 miss fechada, ≤ 1 novo FP. Se o saldo é negativo, plano B é congelar refino e revisar arquitetura.
 **Tamanho:** ~40 L.
+
 ### **X05 — Table vs Full-Set**
 **Pergunta:** indexação vale o custo?
 **Teste:** rodar `doxcolors` com tabela e sem tabela. Medir `rules_attempted`, `cycles`, `wall_time`.
 **Critério:** tabela usa ≥ 30% menos `rules_attempted`, não perde resultado.
 **Tamanho:** ~30 L (reusa X01/X02).
+
 **X01–X05 juntos: ~310 L.** Cabe em 1 dia. Se todos passam, **arquitetura viável**; expandir para X06+ (context classifier, quarantine, etc.).
----
+
+---
+
 ## 7. Integração com o que existe
+
 | Componente | Como encaixa |
 |---|---|
 | **Q00–Q05** | Viram `core_rules` + `domain_index["programming"]` |
@@ -470,23 +681,41 @@
 | **Q09 (linguagem)** | Terceiro consumidor (domain="language") — **só se** X01–X05 passarem |
 | **PASC-6 `rule_registry`** | Implementa quarentena/estado (candidate/stable/deprecated) |
 | **TYPHON** | Chaos log vira tabela de erros (já previsto em ProDeNov 5.4) |
----
+
+---
+
 ## 8. Os três riscos arquiteturais que merecem decisão antes de codar
+
 ### **R1 — Classificador de contexto: separado ou embutido?**
+
 **Separado:** `ContextClassifier` é um módulo próprio. Recebe `facts`, retorna `(domain, symptoms, confidence)`. Determinístico, testável isoladamente.
+
 **Embutido:** core rules derivam `(scene, domain, symptom)` como fatos. Engine usa via fact lookup.
+
 **Recomendação:** **separado**, mas o classificador é uma `Rule` especializada (não código hardcoded). Assim segue o vocabulário do motor. Se a classificação falha, você vê no `chaos_log` como regra miss.
+
 ### **R2 — Tabela estática (build-time) ou dinâmica (learn-time)?**
+
 **Estática:** tabelas em YAML/JSON. Versionadas. Determinismo absoluto. Refino é manual (dev). Nenhum risco de feedback loop.
+
 **Dinâmica:** tabela cresce com `chaos_log` e refino. Determinismo depende de versão. Risco real de degradação.
+
 **Recomendação:** **estática no MVP (X01–X05)**. Dinâmica só depois que quarentena estiver provada (X06+).
+
 ### **R3 — Fallback explícito ou erro?**
+
 **Fallback:** se candidates falham, roda full-set. Sempre produz algum output. Risco: performance ruim em chaos, falha silenciosa ainda possível se full-set também não cobre.
+
 **Erro:** se candidates falham, **raise** `NoRuleApplicable`. Diagnóstico honesto, mas quebra automação.
+
 **Recomendação:** **fallback + log**. Full-set roda; se full-set também quiesce sem produzir nada útil, aí sim `miss` no chaos_log. Duas camadas de honestidade.
----
+
+---
+
 ## 9. Próximos passos concretos
+
 Sugiro esta ordem, **discutida antes de implementada**:
+
 1. **Discutir R1/R2/R3** (esta resposta)
 2. **Salvar como `docs/Research/code_classification/BLITZPLAN_X00_RULETABLE.md`** — extensão do BLITZPLAN anterior
 3. **Decidir escopo MVP** (`doxcolors` confirmado? `error_info` como alternativa?)
@@ -494,17 +723,28 @@
 5. Se X01 verde, **X03** (chaos log) antes de X02 — o log ensina mais que a otimização
 6. X04, X02, X05 nesta ordem
 7. **Só então** considerar X06+ (quarentena, refine automático)
+
 **A pergunta que precede tudo:** você quer tabling **como experimento viável** (5 sondas, ~1 dia) ou **como arquitetura de produção** (refatorar Q00–Q05 + X00 agora)? Minha recomendação clara é a **primeira** — testar viabilidade antes de refatorar. A segunda vira rabbit hole se a tabela não ganhar nada.
----
+
+---
+
 ## 10. Uma crítica que precisa ser dita
+
 Sua frase *"ele não prevê milhões de cenários, ele trabalha com as regras que ele tem"* é verdade para **opening/endgame**, mas **falsa** para mid-game. Xadrez sem busca perde. Sistemas simbólicos sem busca falham em código real (você viu isso em Q04, Q05 hoje).
+
 **A tabela não substitui busca.** Ela **restringe** a busca. Isso é bom — mas o framework mental precisa ser:
 - **Tabela é filtro**, não substituto
 - **Forward chaining continua sendo o motor**
 - **Chaos log é o sensor** de lacunas
+
 Se você concorda com isso, X01–X05 fazem sentido. Se você quer "tabela que substitui engine", a arquitetura não é viável — e a discussão fica honesta ao dizer isso agora.
----
+
+---
+
 Diga **"vai X01"** se quiser ver o primeiro probe implementado, ou abra as decisões R1/R2/R3 primeiro. Minha sugestão: **decidir R3 primeiro** (fallback ou erro) — é a decisão que define se X01–X05 testam uma arquitetura útil ou uma quebrada.
+
 R1 separado, R2 por hora estatica, R3 fallback + log, problema sempre vai ter a questão é como vamos aprender com ele. esta linha de pesquia sobre tabelamento é algo particular para o futuro devido a complexidade e viabilidade, por hora vamos proseguir com X01
----
-      
+
+---
+
+

■ doxoade/research/code_classification/README.md
  xml=63 linhas | disco=84 linhas
--- XML:doxoade/research/code_classification/README.md
+++ DISCO:doxoade/research/code_classification/README.md
@@ -1,42 +1,57 @@
+# Code Classification — linha de pesquisa
 
-# Code Classification — linha de pesquisa
 **Status:** iniciando. Q00 verde = primeiro marco.
 **Base:** forward chaining kernel (research/forward_chaining, 12 PoCs, C1-C7).
+
 ## Motivação
+
 O kernel de forward chaining esta provado (C1-C7). A pergunta natural
 agora e: e possivel usa-lo para **descrever e diagnosticar codigo** de
 forma simbolica, sem ML?
+
 Codigo tem propriedades formais que classificacao simbolica captura bem:
 - Categoria funcional (pura, recursiva, effectful)
 - Complexidade ciclomatica (O(1), O(n), O(n^2))
 - Design pattern (factory, visitor, singleton)
 - Code smell (long method, magic number, dead code)
 - Origem de erro (test falha X, classificacao Y -> discrepancia)
+
 Cada uma dessas e uma **regra sobre fatos estruturais**. Nao precisa de
 embedding, nao precisa de corpus gigante.
+
 ## Contratos-alvo
+
 - **DC1 (Extraction)**: `src: str -> set[StructuralFact]`
   Fatos estruturais derivados de AST. "O que o codigo CONTEM."
+
 - **DC2 (Classification)**: `StructuralFact + rules -> CategoryFact`
   Categoria derivada. "O que o codigo E."
+
 - **DC3 (Aggregation)**: `CategoryFacts -> DescriptionFact`
   Composicao. "O que dizer sobre o codigo." (futuro)
+
 - **DC4 (Triangulation)**: `Classification x Observation -> Discrepancy`
   Diagnostico. "O que esta errado." (futuro, depende de DC2)
+
 ## O que cabe (agora)
+
 - Classificacao simbolica por regra
 - Vocabulario controlado (categoria = string fixa)
 - Multiplas dimensoes (categoria + complexidade + smell, sem colisao)
 - Fatos derivados de AST via `ast.parse` (nao comentario, nao string)
 - Determinismo obrigatorio (100 runs = mesmo output)
+
 ## O que NAO cabe (agora)
+
 - ML, embeddings, corpus
 - NLP de comentarios ou nomes de variavel
 - Geracao de codigo (isso e `forward_chaining`, P30b/P31)
 - Analise semantica de runtime (precisa de trace)
 - Backward chaining (deferido em `forward_chaining/research_directions.md`,
   trigger: >100 regras ou explain_negative precisar)
+
 ## Escada de PoCs (proposta inicial, ajustavel)
+
 | PoC | Prova | Contrato |
 |---|---|---|
 | Q00 | 1 funcao -> 1 categoria, 4 regras, default unknown | DC2 |
@@ -45,19 +60,25 @@
 | Q03 | design pattern (factory) | DC2 |
 | Q04 | code smell (long method) | DC2 |
 | Q05 | triangulacao: teste falha x classificacao | DC4 |
+
 Cada PoC prove UM contrato. Q01+ expandem vocabulario; DC4 so entra
 quando DC2 estiver com 3+ dimensoes testadas.
+
 ## Direções deferidas (com gatilho)
+
 - **Backward chaining** — trigger: >100 regras de classificacao, ou
   explain_negative de Q03+ falhar por falta de goal-driven.
 - **Error triangulation (DC4)** — trigger: Q03/Q04 verdes. Antes disso,
   nao ha o que triangular.
 - **Word tree / combinatory** — fora do escopo deste linha.
+
 ## Quando promove
+
 Todos DC1-DC4 com >=1 PoC verde cada. Ai promove para
 `doxoade/code_classification/` (mesma logica de promocao de FC:
 contratos, nao codigo).
+
 ## Nomenclatura
+
 PoCs dessa linha usam prefixo `q` (q00, q01...). Linha de FC usa
 numeros (00, 01...). Sem colisao de nome.
-      

■ doxoade/research/code_classification/poc/q00_baseline_classifier/README.md
  xml=61 linhas | disco=78 linhas
--- XML:doxoade/research/code_classification/poc/q00_baseline_classifier/README.md
+++ DISCO:doxoade/research/code_classification/poc/q00_baseline_classifier/README.md
@@ -1,16 +1,21 @@
+# Q00 - Baseline classifier (DC2)
 
-# Q00 - Baseline classifier (DC2)
 **Contrato:** DC2 (Classification).
 `StructuralFact + rules -> CategoryFact`.
+
 ## O que prova
+
 Toda funcao recebe exatamente UMA categoria:
+
 | Input | Categoria | Regra |
 |---|---|---|
 | `def f(x): return x + 1` | `arithmetic_return` | R_arith |
 | `def g(x): return x` | `identity_return` | R_ident |
 | `def h(): return 42` | `constant_return` | R_const |
 | `def k(x): print(x)` | `unknown` | R_unknown (NAF) |
+
 ## Mecanismo do default
+
 Reusa NAF (P21) + prioridade (P02):
 - R_arith/R_ident/R_const tem prio=10
 - R_unknown tem prio=1 e NAF `NOT (f, category, _)`
@@ -19,14 +24,19 @@
 - Ciclo 2: concreta idempotente; R_unknown nao dispara (NAF falha
   porque categoria existe).
 - Quiesce em 2-3 ciclos.
+
 ## INVARIANTE — depende de:
+
 Todas as 4 regras dependem APENAS de fatos seed (extraidos do AST no
 ciclo 0). Nao ha regra que dependa de fato derivado por outra regra.
+
 Isso elimina **conflito cross-ciclo** (P02 so testa conflito
 within-ciclo). Se uma regra futura depender de fato derivado, pode
 haver `(f, category, X)` em ciclo N e `(f, category, Y)` em ciclo M>N,
 sem deteccao. Q00 evita esse caso por design.
+
 ## O que NAO prova
+
 - Multi-categoria (`(f, category, X)` E `(f, has_docstring, yes)`) —
   Q01.
 - Complexidade — Q02.
@@ -34,14 +44,18 @@
 - Code smell — Q04.
 - Cross-cycle conflict resolution — deixa para Q0X quando regras
   encadeadas emergirem.
+
 ## Err table (ProDeNov 5.4)
+
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
 | Duas categorias ao mesmo tempo | baixa | critico | winners dict + priority |
 | Categoria perdida (nem concreta nem unknown) | baixa | critico | R_unknown como fallback |
 | Cross-cycle conflict | n/a (invariante) | alto | documentado |
 | Categoria nao-deterministica | baixa | alto | Q00e (100 runs) |
+
 ## Planos A / B / C
+
 - **A (implementado):** 4 regras, prioridade + NAF, within-cycle conflict.
 - **B (se multi-categoria):** usar predicates distintos por dimensao
   (`category`, `has_docstring`, `complexity`). Sem conflito por
@@ -49,13 +63,16 @@
 - **C (se cross-cycle conflitar):** extension para cross-cycle conflict
   resolution (matching por subject+predicate no merge, nao so por
   idempotencia exata).
+
 ## Licao
+
 DC2 e o primeiro contrato com **fallback** (unknown). O fallback nao e
 regra especial no engine — e apenas uma regra normal com NAF + prioridade
 baixa. Isso mostra que a arquitetura de C1-C3 ja suporta classification
 sem extensao. Prova de que o kernel promovido e suficiente.
+
 ## Quando Q00 promove
+
 Nao promove isolado. DC2 completo so quando Q01-Q04 existirem e
 provam que classificacao **generaliza** (diferente de rewrite, que foi
 P30b+P31). Por ora, Q00 fica em research.
-      

■ doxoade/research/code_classification/poc/q00_baseline_classifier/engine_q00.py
  xml=424 linhas | disco=545 linhas
--- XML:doxoade/research/code_classification/poc/q00_baseline_classifier/engine_q00.py
+++ DISCO:doxoade/research/code_classification/poc/q00_baseline_classifier/engine_q00.py
@@ -1,14 +1,36 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/code_classification/poc/q00_baseline_classifier/engine_q00.py
+"""
+Q00 - Baseline classifier (DC2) com debug estruturado.
+
+Contrato: DC2 (Classification).
+    StructuralFact + rules -> CategoryFact.
+
+Modo debug:
+    py engine_q00.py --debug
+    Dumpa [DEBUG] em stderr (nao polui output.txt, que e o contrato).
+    Por funcao: seed facts, matches por regra, winners, shadowed,
+    idempotent, timing. No fim: agregado (rules_attempted, por regra,
+    total_cycles, avg_cycles, tempos).
+
+Uso primario:
+    doxoade retro-forward run q00
+    doxoade retro-forward run q00 --debug
+    doxoade retro-forward trace q00
+"""
 from __future__ import annotations
+
 import ast
 import dataclasses
 import logging
 import sys
 import time
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
 DEBUG = "--debug" in sys.argv
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc_q00")
     if logger.handlers:
@@ -18,8 +40,13 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class _Quiet:
+    """Context manager que suspende _dbg durante execucoes em massa."""
     __slots__ = ("level",)
     def __init__(self) -> None:
         self.level = 0
@@ -28,17 +55,30 @@
         return self
     def __exit__(self, *exc):
         self.level -= 1
+
+
 QUIET = _Quiet()
+
+
 def _dbg(*parts) -> None:
     if DEBUG and QUIET.level == 0:
         print("[DEBUG]", *parts, file=sys.stderr)
+
+
 class UnsupportedNodeError(RuntimeError):
     pass
+
+
+# ============================================================
+# Kernel inline (~160 L)
+# ============================================================
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 class _Wild:
     _instance = None
     def __new__(cls):
@@ -47,9 +87,13 @@
         return cls._instance
     def __repr__(self) -> str:
         return "_"
+
+
 WILD = _Wild()
 Term = str | Var | _Wild
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class Triple:
     s: str
@@ -58,10 +102,14 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
     def render(self) -> str:
         return f"({self.s}, {self.p}, {self.o})"
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -69,12 +117,15 @@
     conclusion: Pattern
     negations: tuple[Pattern, ...] = ()
     priority: int = 0
+
     def conclusion_fact(self, bindings, cycle):
         r = substitute(self.conclusion, bindings)
         if r is None:
             return None
         s, p, o = r
         return Triple(s, p, o, source="derived", rule_id=self.id, cycle=cycle)
+
+
 def unify_term(pattern, value, bindings):
     if isinstance(pattern, _Wild):
         return bindings
@@ -83,6 +134,8 @@
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern, fact_triple, bindings):
     b = bindings
     for p_t, f_v in zip(pattern, fact_triple):
@@ -90,6 +143,8 @@
         if b is None:
             return None
     return b
+
+
 def substitute(pattern, bindings):
     out = []
     for t in pattern:
@@ -102,8 +157,11 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_with_negations(conditions, negations, facts):
     results = []
+
     def recurse(conds, binds, wit):
         if not conds:
             for neg in negations:
@@ -119,8 +177,11 @@
             if b is None:
                 continue
             recurse(rest, b, wit + [f.to_tuple()])
+
     recurse(conditions, {}, [])
     return results
+
+
 class Engine:
     def __init__(self, max_cycles=100):
         self.max_cycles = max_cycles
@@ -130,6 +191,7 @@
         self.rule_attempts: dict[str, int] = {}
         self.shadowed: list[tuple[str, tuple]] = []
         self.cycle_history: list[dict] = []
+
     def run(self, initial_facts, rules):
         facts = list(initial_facts)
         ordered = sorted(rules, key=lambda r: -r.priority)
@@ -168,6 +230,7 @@
                     cycle_info["candidates"].append(
                         (rule.id, rule.priority, cf.to_tuple())
                     )
+
             winners = {}
             for rule, cf, wit in candidates:
                 key = (cf.s, cf.p)
@@ -190,14 +253,18 @@
                     self.shadowed.append(
                         (rule.id, cf.to_tuple())
                     )
+
             for (s, p), (rule, cf, wit) in winners.items():
                 cycle_info["winners"].append(
                     (rule.id, rule.priority, cf.to_tuple())
                 )
+
             self.cycle_history.append(cycle_info)
+
             if not winners:
                 self.cycles_used = cycles
                 return facts, cycles
+
             for (s, p), (rule, cf, wit) in winners.items():
                 facts.append(cf)
                 self.trace.append({
@@ -207,6 +274,11 @@
                     "derived_from": wit,
                 })
         raise RuntimeError(f"max_cycles={self.max_cycles}")
+
+
+# ============================================================
+# DC1 - AST -> structural facts
+# ============================================================
 def extract_facts(src: str) -> list[Triple]:
     tree = ast.parse(src)
     if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
@@ -227,6 +299,11 @@
                 func.name, "return_expr_kind", type(first.value).__name__
             ))
     return facts
+
+
+# ============================================================
+# DC2 - Classification rules
+# ============================================================
 F = Var("F")
 RULES = [
     Rule("R_arith",
@@ -253,6 +330,11 @@
          conclusion=(F, "category", "unknown"),
          priority=1),
 ]
+
+
+# ============================================================
+# classify + debug helpers
+# ============================================================
 def _dbg_cycle(cycle_info):
     _dbg(f"  cycle {cycle_info['cycle']}:")
     matches_str = " ".join(
@@ -269,14 +351,18 @@
         _dbg(f"    idempotent: {rid} -> {fact}")
     if not cycle_info["winners"]:
         _dbg("    quiescence")
+
+
 def classify(src: str) -> dict:
     t0 = time.perf_counter()
     seed = extract_facts(src)
     t_extract = (time.perf_counter() - t0) * 1000
+
     t0 = time.perf_counter()
     eng = Engine()
     result_facts, cycles = eng.run(seed, RULES)
     t_infer = (time.perf_counter() - t0) * 1000
+
     categories = sorted(f.o for f in result_facts if f.p == "category")
     return {
         "input": src,
@@ -293,9 +379,15 @@
             "t_infer_ms": t_infer,
         },
     }
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 def _classify_and_debug(label, src):
     r = classify(src)
     m = r["metrics"]
+
     _dbg(f"--- {label}: {src!r} ---")
     _dbg(f"  extract: {len(m['seed'])} seed facts in {m['t_extract_ms']:.3f}ms")
     for fact in m["seed"]:
@@ -309,14 +401,24 @@
          f"total={(m['t_extract_ms'] + m['t_infer_ms']):.3f}ms")
     _dbg("")
     return r
+
+
 def run_q00a() -> dict:
     return _classify_and_debug("Q00a", "def f(x): return x + 1")
+
+
 def run_q00b() -> dict:
     return _classify_and_debug("Q00b", "def g(x): return x")
+
+
 def run_q00c() -> dict:
     return _classify_and_debug("Q00c", "def h(): return 42")
+
+
 def run_q00d() -> dict:
     return _classify_and_debug("Q00d", "def k(x): print(x)")
+
+
 def run_q00e() -> dict:
     t0 = time.perf_counter()
     outs = set()
@@ -324,6 +426,7 @@
         for _ in range(100):
             outs.add(tuple(run_q00a()["categories"]))
     t_total = (time.perf_counter() - t0) * 1000
+
     if DEBUG:
         _dbg("--- Q00e: determinism (100 runs) ---")
         _dbg(f"  runs: 100")
@@ -332,7 +435,10 @@
         _dbg(f"  time_total: {t_total:.3f}ms")
         _dbg(f"  time_per_run: {t_total/100:.3f}ms")
         _dbg("")
+
     return {"n": 100, "unique_count": len(outs)}
+
+
 def _debug_aggregate(results):
     if not DEBUG:
         return
@@ -343,11 +449,13 @@
     total_cycles = sum(r["cycles"] for r in results)
     extract_total = sum(r["metrics"]["t_extract_ms"] for r in results)
     infer_total = sum(r["metrics"]["t_infer_ms"] for r in results)
+
     per_rule: dict[str, int] = {}
     for r in results:
         for rid, n in r["metrics"]["rule_attempts"].items():
             per_rule[rid] = per_rule.get(rid, 0) + n
     per_rule_str = " ".join(f"{k}={v}" for k, v in sorted(per_rule.items()))
+
     n = len(results)
     _dbg("--- aggregate (4 classify calls) ---")
     _dbg(f"  functions: {n}")
@@ -362,14 +470,21 @@
     _dbg(f"  infer_time_total: {infer_total:.3f}ms")
     _dbg(f"  total_time: {(extract_total + infer_total):.3f}ms")
     _dbg("")
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     if DEBUG:
         _dbg("=== engine_q00.py ===")
         _dbg("mode: debug")
         _dbg(f"args: {sys.argv}")
         _dbg("")
+
     lines: list[str] = []
     falhas: list[str] = []
+
     checks = [
         ("Q00a", "def f(x): return x + 1", "arithmetic_return", run_q00a),
         ("Q00b", "def g(x): return x",     "identity_return",   run_q00b),
@@ -390,6 +505,7 @@
                 f"{label}: esperado [{expected_cat!r}], "
                 f"veio {r['categories']}"
             )
+
     lines.append("=== Q00e: determinism (100 runs) ===")
     e = run_q00e()
     lines.append(f"n:            {e['n']}")
@@ -397,7 +513,9 @@
     lines.append("")
     if e["unique_count"] != 1:
         falhas.append(f"Q00e: {e['unique_count']} variacoes")
+
     _debug_aggregate(results_for_agg)
+
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -410,8 +528,10 @@
         resultado = 0
         if DEBUG:
             _dbg("=== done: all checks passed ===")
+
     for ln in lines:
         print(ln)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -419,6 +539,7 @@
         newline="\n",
     )
     return resultado
+
 if __name__ == "__main__":
     sys.exit(main())
-      
+

■ doxoade/research/code_classification/poc/q01_multi_dim/README.md
  xml=54 linhas | disco=72 linhas
--- XML:doxoade/research/code_classification/poc/q01_multi_dim/README.md
+++ DISCO:doxoade/research/code_classification/poc/q01_multi_dim/README.md
@@ -1,31 +1,44 @@
+# Q01 - Multi-dimensional classifier (DC2)
 
-# Q01 - Multi-dimensional classifier (DC2)
 **Contrato:** DC2 (Classification) estendido para 2 dimensoes.
+
 ## O que prova
+
 Duas dimensoes coexistem sem colisao:
+
 | Input | category | has_docstring |
 |---|---|---|
 | `"""Doc."""; return x+1` (dentro da func) | arithmetic_return | yes |
 | `return x+1` | arithmetic_return | no |
 | `"""Doc."""; print(x)` | unknown | yes |
 | `print(x)` | unknown | no |
+
 Por construcao: `category` e `has_docstring` sao predicados distintos.
 Engine faz conflito por `(subject, predicate)`, entao nunca colidem.
+
 ## Desafio tecnico declarado
+
 Docstring muda `body[0]` de `Return` para `Expr(Constant(str))`. Se
 extracao fosse ingenua:
+
 - `body_0_kind=Expr` (por causa do docstring)
 - `R_arith` exige `body_0_kind=Return` -> falharia
 - Funcao com docstring viraria `unknown` incorretamente
+
 **Solucao:** `ast.get_docstring` detecta; `body_stmts = body[1:]` filtra.
 `has_docstring` vira **fato separado**. R_arith continua igual.
+
 Docstring e metadata, nao logica. Extracao respeita isso.
+
 ## O que NAO prova
+
 - 3+ dimensoes simultaneas -> Q02 (complexidade, 3a dim)
 - Dimensoes com valores nao-booleanos -> Q03 (pattern, string)
 - Dimensoes derivadas (nao seed) -> Q03+ quando 2 regras por dim
 - Cross-cycle conflict -> ainda nao exercitado (Q00/Q01 sao single-cycle)
+
 ## Err table (ProDeNov 5.4)
+
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
 | Docstring detectado errado | baixa | critico | `ast.get_docstring` (stdlib) |
@@ -33,22 +46,27 @@
 | Filtragem deixa body vazio | baixa | medio | body_stmts vazio -> R_unknown |
 | Conflito entre dims | nula | critico | predicados distintos |
 | Categoria nao-deterministica | baixa | alto | Q01e (100 runs) |
+
 ## Planos A / B / C
+
 - **A (implementado):** `ast.get_docstring` + filtragem explicita. Rules
   inalteradas de Q00. has_docstring e seed.
 - **B (se Q02 exigir):** Dimensoes como tuplas `(dim_name, dim_value)`
   em vez de predicados flat. Permite N dims sem crescimnto de schema.
 - **C (se cross-cycle conflict):** extension do engine para detectar
   `(s, p, X)` vs `(s, p, Y)` em ciclos diferentes. Vira sonda propria.
+
 ## Licao
+
 DC2 **generaliza** para multi-dim. Duas dimensoes ortogonais coexistem
 sem conflito **porque o engine ja tem a primitiva certa** (chave =
 `(subject, predicate)`). Nao precisa de regra especial.
+
 O que precisa de atencao e **extracao**: docstring e ruido estrutural
 para classificacao, nao sinal. Filtragem no `extract_facts` mantem as
 regras simples e o contrato honesto.
+
 **Promocao:** Q01 nao promove isolado. DC2 esta consolidado com 2 dims
 testadas. Q02 (complexidade) e Q03 (pattern) sao candidatas naturais
 para 3a e 4a dims. DC2 promove so quando 4+ dims provam generalizacao
 sem mudanca de contrato no engine.
-      

■ doxoade/research/code_classification/poc/q01_multi_dim/engine_q01.py
  xml=458 linhas | disco=606 linhas
--- XML:doxoade/research/code_classification/poc/q01_multi_dim/engine_q01.py
+++ DISCO:doxoade/research/code_classification/poc/q01_multi_dim/engine_q01.py
@@ -1,14 +1,50 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/code_classification/poc/q01_multi_dim/engine_q01.py
+"""
+Q01 - Multi-dimensional classifier (DC2).
+
+Contrato: DC2 (Classification) estendido.
+    StructuralFact + rules -> CategoryFact (2 dimensoes simultaneas).
+
+Duas dimensoes ortogonais:
+    dim1: category      (derivada por R_arith/R_ident/R_const/R_unknown)
+    dim2: has_docstring (seed, extraida de ast.get_docstring)
+
+Nao ha conflito por construcao: predicados distintos -> chaves distintas.
+
+DESAFIO TECNICO:
+    Docstring em FunctionDef muda body[0] de Return/Expr(Call) para
+    Expr(Constant(str)). Se extracao fosse ingenua, body_0_kind=Expr
+    faria R_arith falhar em funcao COM docstring - classificacao errada.
+
+    Solucao: extract_facts FILTRA docstring do body logico. has_docstring
+    vira fato separado. R_arith continua funcionando igual.
+
+Q01a - doc + return x+1     -> {arith, yes}
+Q01b - sem doc + return x+1 -> {arith, no}
+Q01c - doc + print(x)       -> {unknown, yes}
+Q01d - sem doc + print(x)   -> {unknown, no}
+Q01e - determinism (100 runs de Q01a)
+
+Debug:
+    py engine_q01.py --debug
+    Mostra por funcao: seed facts, cycles, dims resultantes, timing.
+
+Rodar: doxoade retro-forward run q01
+"""
 from __future__ import annotations
+
 import ast
 import dataclasses
 import logging
 import sys
 import time
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
 DEBUG = "--debug" in sys.argv
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc_q01")
     if logger.handlers:
@@ -18,8 +54,13 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class _Quiet:
+    """Context manager que suspende _dbg durante execucoes em massa."""
     __slots__ = ("level",)
     def __init__(self) -> None:
         self.level = 0
@@ -28,17 +69,30 @@
         return self
     def __exit__(self, *exc):
         self.level -= 1
+
+
 QUIET = _Quiet()
+
+
 def _dbg(*parts) -> None:
     if DEBUG and QUIET.level == 0:
         print("[DEBUG]", *parts, file=sys.stderr)
+
+
 class UnsupportedNodeError(RuntimeError):
     pass
+
+
+# ============================================================
+# Kernel inline (mesmo de Q00)
+# ============================================================
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 class _Wild:
     _instance = None
     def __new__(cls):
@@ -47,9 +101,13 @@
         return cls._instance
     def __repr__(self) -> str:
         return "_"
+
+
 WILD = _Wild()
 Term = str | Var | _Wild
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class Triple:
     s: str
@@ -58,10 +116,14 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
     def render(self) -> str:
         return f"({self.s}, {self.p}, {self.o})"
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -69,12 +131,15 @@
     conclusion: Pattern
     negations: tuple[Pattern, ...] = ()
     priority: int = 0
+
     def conclusion_fact(self, bindings, cycle):
         r = substitute(self.conclusion, bindings)
         if r is None:
             return None
         s, p, o = r
         return Triple(s, p, o, source="derived", rule_id=self.id, cycle=cycle)
+
+
 def unify_term(pattern, value, bindings):
     if isinstance(pattern, _Wild):
         return bindings
@@ -83,6 +148,8 @@
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern, fact_triple, bindings):
     b = bindings
     for p_t, f_v in zip(pattern, fact_triple):
@@ -90,6 +157,8 @@
         if b is None:
             return None
     return b
+
+
 def substitute(pattern, bindings):
     out = []
     for t in pattern:
@@ -102,8 +171,11 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_with_negations(conditions, negations, facts):
     results = []
+
     def recurse(conds, binds, wit):
         if not conds:
             for neg in negations:
@@ -119,8 +191,11 @@
             if b is None:
                 continue
             recurse(rest, b, wit + [f.to_tuple()])
+
     recurse(conditions, {}, [])
     return results
+
+
 class Engine:
     def __init__(self, max_cycles=100):
         self.max_cycles = max_cycles
@@ -130,6 +205,7 @@
         self.rule_attempts: dict[str, int] = {}
         self.shadowed: list[tuple[str, tuple]] = []
         self.cycle_history: list[dict] = []
+
     def run(self, initial_facts, rules):
         facts = list(initial_facts)
         ordered = sorted(rules, key=lambda r: -r.priority)
@@ -146,6 +222,7 @@
                 "winners": [],
                 "shadowed": [],
             }
+
             for rule in ordered:
                 matches = match_with_negations(
                     rule.conditions, rule.negations, facts
@@ -168,6 +245,7 @@
                     cycle_info["candidates"].append(
                         (rule.id, rule.priority, cf.to_tuple())
                     )
+
             winners = {}
             for rule, cf, wit in candidates:
                 key = (cf.s, cf.p)
@@ -190,14 +268,18 @@
                     self.shadowed.append(
                         (rule.id, cf.to_tuple())
                     )
+
             for (s, p), (rule, cf, wit) in winners.items():
                 cycle_info["winners"].append(
                     (rule.id, rule.priority, cf.to_tuple())
                 )
+
             self.cycle_history.append(cycle_info)
+
             if not winners:
                 self.cycles_used = cycles
                 return facts, cycles
+
             for (s, p), (rule, cf, wit) in winners.items():
                 facts.append(cf)
                 self.trace.append({
@@ -207,7 +289,16 @@
                     "derived_from": wit,
                 })
         raise RuntimeError(f"max_cycles={self.max_cycles}")
+
+
+# ============================================================
+# DC1 - AST -> structural facts (com filtragem de docstring)
+# ============================================================
 def extract_facts(src: str) -> list[Triple]:
+    """
+    AST -> facts. Docstring filtrado do body logico; has_docstring
+    vira fato separado.
+    """
     tree = ast.parse(src)
     if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
         raise UnsupportedNodeError(
@@ -215,8 +306,13 @@
             f"{[type(n).__name__ for n in tree.body]}"
         )
     func = tree.body[0]
+
     has_doc = ast.get_docstring(func) is not None
+
+    # ast.get_docstring retorna non-None APENAS quando body[0] e o docstring.
+    # Filtragem e segura: se has_doc, body[0] e Expr(Constant(str)).
     body_stmts = func.body[1:] if has_doc else func.body
+
     facts = [
         Triple(func.name, "kind", "function"),
         Triple(func.name, "has_docstring", "yes" if has_doc else "no"),
@@ -230,6 +326,11 @@
                 func.name, "return_expr_kind", type(first.value).__name__
             ))
     return facts
+
+
+# ============================================================
+# DC2 - Classification rules (dimensao: category)
+# ============================================================
 F = Var("F")
 RULES = [
     Rule("R_arith",
@@ -256,6 +357,11 @@
          conclusion=(F, "category", "unknown"),
          priority=1),
 ]
+
+
+# ============================================================
+# classify + debug
+# ============================================================
 def _dbg_cycle(cycle_info):
     _dbg(f"  cycle {cycle_info['cycle']}:")
     m = cycle_info["matches"]
@@ -270,16 +376,21 @@
         _dbg(f"    idempotent: {rid} -> {fact}")
     if not cycle_info["winners"]:
         _dbg("    quiescence")
+
+
 def classify(src: str) -> dict:
     t0 = time.perf_counter()
     seed = extract_facts(src)
     t_extract = (time.perf_counter() - t0) * 1000
+
     t0 = time.perf_counter()
     eng = Engine()
     result_facts, cycles = eng.run(seed, RULES)
     t_infer = (time.perf_counter() - t0) * 1000
+
     categories = sorted(f.o for f in result_facts if f.p == "category")
     has_doc_vals = sorted(f.o for f in result_facts if f.p == "has_docstring")
+
     return {
         "input": src,
         "category": categories[0] if categories else None,
@@ -296,9 +407,12 @@
             "t_infer_ms": t_infer,
         },
     }
+
+
 def _classify_and_debug(label, src):
     r = classify(src)
     m = r["metrics"]
+
     _dbg(f"--- {label} ---")
     _dbg(f"  input: {src!r}")
     _dbg(f"  extract: {len(m['seed'])} seed facts in {m['t_extract_ms']:.3f}ms")
@@ -317,18 +431,33 @@
          f"total={(m['t_extract_ms'] + m['t_infer_ms']):.3f}ms")
     _dbg("")
     return r
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 SRC_Q01A = 'def f(x):\n    """Doc."""\n    return x + 1'
 SRC_Q01B = "def f(x): return x + 1"
 SRC_Q01C = 'def k(x):\n    """Doc."""\n    print(x)'
 SRC_Q01D = "def k(x): print(x)"
+
+
 def run_q01a():
     return _classify_and_debug("Q01a: doc + return x+1", SRC_Q01A)
+
+
 def run_q01b():
     return _classify_and_debug("Q01b: no doc + return x+1", SRC_Q01B)
+
+
 def run_q01c():
     return _classify_and_debug("Q01c: doc + print(x)", SRC_Q01C)
+
+
 def run_q01d():
     return _classify_and_debug("Q01d: no doc + print(x)", SRC_Q01D)
+
+
 def run_q01e():
     t0 = time.perf_counter()
     outs = set()
@@ -337,6 +466,7 @@
             r = run_q01a()
             outs.add((r["category"], r["has_docstring"]))
     t_total = (time.perf_counter() - t0) * 1000
+
     if DEBUG:
         _dbg("--- Q01e: determinism (100 runs of Q01a) ---")
         _dbg(f"  runs: 100")
@@ -346,6 +476,7 @@
         _dbg(f"  time_per_run: {t_total/100:.3f}ms")
         _dbg("")
     return {"n": 100, "unique_count": len(outs), "pairs": outs}
+
 def run_p02c() -> dict:
     t0 = time.perf_counter()
     results = []
@@ -354,6 +485,7 @@
             r = run_p02a()
             results.append(tuple(r["out_values"]))
     t_total = (time.perf_counter() - t0) * 1000
+
     if DEBUG:
         _dbg("--- P02c: determinismo (100 runs de P02a) ---")
         _dbg(f"  n: 100")
@@ -361,7 +493,9 @@
         _dbg(f"  time_total: {t_total:.3f}ms")
         _dbg(f"  time_per_run: {t_total/100:.3f}ms")
         _dbg("")
+
     return {"n": len(results), "unique_outputs": set(results)}
+
 def _debug_aggregate(results):
     if not DEBUG:
         return
@@ -372,11 +506,13 @@
     total_cycles = sum(r["cycles"] for r in results)
     extract_total = sum(r["metrics"]["t_extract_ms"] for r in results)
     infer_total = sum(r["metrics"]["t_infer_ms"] for r in results)
+
     per_rule: dict[str, int] = {}
     for r in results:
         for rid, k in r["metrics"]["rule_attempts"].items():
             per_rule[rid] = per_rule.get(rid, 0) + k
     per_rule_str = " ".join(f"{k}={v}" for k, v in sorted(per_rule.items()))
+
     _dbg("--- aggregate (4 classify calls) ---")
     _dbg(f"  functions: {n}")
     _dbg(f"  total_seed_facts: {total_seed}")
@@ -389,14 +525,21 @@
     _dbg(f"  infer_time_total: {infer_total:.3f}ms")
     _dbg(f"  total_time: {(extract_total + infer_total):.3f}ms")
     _dbg("")
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     if DEBUG:
         _dbg("=== engine_q01.py ===")
         _dbg("mode: debug")
         _dbg(f"args: {sys.argv}")
         _dbg("")
+
     lines: list[str] = []
     falhas: list[str] = []
+
     checks = [
         ("Q01a", SRC_Q01A, "arithmetic_return", "yes", run_q01a),
         ("Q01b", SRC_Q01B, "arithmetic_return", "no",  run_q01b),
@@ -424,6 +567,7 @@
                 f"{label}: esperado has_docstring={exp_doc!r}, "
                 f"veio {r['has_docstring']!r}"
             )
+
     lines.append("=== Q01e: determinism (100 runs of Q01a) ===")
     e = run_q01e()
     lines.append(f"n:            {e['n']}")
@@ -431,7 +575,9 @@
     lines.append("")
     if e["unique_count"] != 1:
         falhas.append(f"Q01e: {e['unique_count']} variacoes")
+
     _debug_aggregate(results_for_agg)
+
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -444,8 +590,10 @@
         resultado = 0
         if DEBUG:
             _dbg("=== done: all checks passed ===")
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -453,6 +601,6 @@
         newline="\n",
     )
     return resultado
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/code_classification/poc/q02_complexity/README.md
  xml=77 linhas | disco=100 linhas
--- XML:doxoade/research/code_classification/poc/q02_complexity/README.md
+++ DISCO:doxoade/research/code_classification/poc/q02_complexity/README.md
@@ -1,9 +1,12 @@
+# Q02 - Complexity as 3rd dimension (DC2)
 
-# Q02 - Complexity as 3rd dimension (DC2)
 **Contrato:** DC2 (Classification) estendido para 3 dimensoes ortogonais.
+
 ## O que prova
+
 Tres dimensoes coexistem sem colisao, com valor nao-booleano pela
 primeira vez:
+
 | Input | category | has_docstring | complexity |
 |---|---|---|---|
 | `return x+1` | arithmetic_return | no | 1 |
@@ -13,9 +16,12 @@
 | `if x: if x>0: for i in range(x): ...` | unknown | no | 3 |
 | 4+ branches | unknown | no | 4+ |
 | `"""Doc."""; if x>0: return x+1` | unknown | yes | 2 |
+
 ## Bucketing declarado
+
 `branch_count = N` (contagem exata de If/For/AsyncFor/While/Try/ExceptHandler
 no body, recursivo, sem docstring):
+
 | N | complexity | rule |
 |---|---|---|
 | 0 | 1 | R_c_1 |
@@ -23,31 +29,43 @@
 | 2 | 3 | R_c_3a |
 | 3 | 3 | R_c_3b |
 | >= 4 | 4+ | R_c_4plus |
+
 **Por que 2 e 3 compartilham "3":** evita proliferacao de buckets sem
 agregar valor ao estimador de complexidade. A diferenca entre 2 e 3
 branches e menos informativa que entre 0-1, 1-2, 3-4+.
+
 **Por que "4+" e range marker:** extractor emite `branch_count_ge_4=yes`
 quando N>=4. Hint estrutural honesto — nao classificacao. Evita enumerar
 4, 5, 6, ..., infinitas rules.
+
 ## Desafio tecnico declarado
+
 **Primeira dim com valor nao-booleano.** Q00/Q01 tiveram dims com valores
 em conjuntos finitos `{yes, no}` e `{arith, ident, const, unknown}`.
 Complexity tem valor `{1, 2, 3, 4+}` — o "4+" nao e inteiro.
+
 Extractor lida com isso emitindo DOIS fatos:
 - `(F, branch_count, N)` — exato, para rules que precisam do numero
 - `(F, branch_count_ge_4, "yes")` — hint, para rule do bucket `4+`
+
 Isso mantem as rules puramente simbólicas (sem OR, sem comparacao
 numerica), e o extractor faz a unica aritmetica necessaria.
+
 ## Interacao com dims anteriores
+
 `has_docstring` continua filtrado do body (Q01). Em Q02g, a funcao tem
 docstring + 1 branch. `branch_count=1` (nao conta docstring), `has_docstring=yes`,
 `category=unknown` (body_0 e If, nao Return). Todas as 3 dims coexistem.
+
 ## O que NAO prova
+
 - 4+ dims -> Q03 (design pattern) ou Q04 (code smell)
 - Complexity em nested functions -> fora do escopo Q02
 - Comprehension complexity -> intencionalmente nao conta If/For internos
 - Cyclomatic exato (E - N + 2P) -> Q02 e "branch count", nao cyclomatic
+
 ## Err table (ProDeNov 5.4)
+
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
 | `ast.walk` duplo conta nos aninhados | media | alto | walk recursivo unico por stmt top-level |
@@ -55,7 +73,9 @@
 | Bucket 4+ nao emite hint | baixa | critico | teste Q02f com 4 branches |
 | Complexity null em funcao sem body | baixa | medio | body vazio -> branch_count=0 -> "1" |
 | Determinismo afetado por walk | baixa | alto | Q02h (100 runs) |
+
 ## Planos A / B / C
+
 - **A (implementado):** extractor emite `branch_count` exato + hint
   `branch_count_ge_4=yes`; 5 rules mapeiam buckets.
 - **B (se Q03 precisar de granularidade):** extractor emite buckets ja
@@ -65,13 +85,16 @@
   formula (E - N + 2P) com extractor computando E, N, P. Custo: muito
   mais complexo, e cyclomatic ja cobre funcoes com 20+ branches —
   fora do escopo Q02.
+
 ## Licao
+
 DC2 generaliza para valores **nao-booleanos** porque o engine ja aceita
 `str` como valor de fato. Nenhuma mudanca em C1/C3 foi necessaria.
+
 O unico ajuste foi **extractor fazer a unica aritmetica necessaria**
 (`>= 4`) e expor como hint estrutural. Rules continuam puras: match
 strings exatas, sem comparacao numerica.
+
 Isso valida a separacao C2/C3: numeros e comparacoes ficam em C2
 (adaptacao), simbolos e conflito em C3 (expressividade). Se Q03
 precisar de "contagem de parametros > 3", mesmo padrao se aplica.
-      

■ doxoade/research/code_classification/poc/q02_complexity/engine_q02.py
  xml=507 linhas | disco=668 linhas
--- XML:doxoade/research/code_classification/poc/q02_complexity/engine_q02.py
+++ DISCO:doxoade/research/code_classification/poc/q02_complexity/engine_q02.py
@@ -1,14 +1,58 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/code_classification/poc/q02_complexity/engine_q02.py
+"""
+Q02 - Complexity as 3rd dimension (DC2).
+
+Contrato: DC2 (Classification) estendido.
+    StructuralFact + rules -> CategoryFact (3 dimensoes simultaneas).
+
+3 dimensoes ortogonais:
+    dim1: category       (Q00/Q01 - derivada de R_arith/R_ident/R_const/R_unknown)
+    dim2: has_docstring  (Q01 - seed)
+    dim3: complexity     (Q02 - derivada de branch_count)
+
+Branch count:
+    Conta nos de controle de fluxo recursivamente no body (sem docstring):
+    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler.
+    Nao conta IfExp (ternary), comprehensions (If/For internos).
+
+Bucketing:
+    branch_count = 0     -> complexity = "1"
+    branch_count = 1     -> complexity = "2"
+    branch_count = 2     -> complexity = "3"
+    branch_count = 3     -> complexity = "3"
+    branch_count >= 4    -> complexity = "4+"
+
+Por que buckets 2 e 3 compartilham "3": evita proliferacao de buckets
+sem agregar valor ao estimador de complexidade.
+
+Por que "4+" e range marker: extractor emite `branch_count_ge_4=yes`
+quando N>=4 — hint estrutural honesto, nao classificacao.
+
+Q02a - return x+1                              -> {arith, no, "1"}
+Q02b - if x>0: return x / return 0            -> {unknown, no, "2"}
+Q02c - for x in xs: print(x) / return len(xs) -> {unknown, no, "2"}
+Q02d - if x>0: for i in range(x): print(i)     -> {unknown, no, "3"}
+Q02e - if x: if x>0: for i in range(x): ...   -> {unknown, no, "3"}
+Q02f - 4+ branches                            -> {unknown, no, "4+"}
+Q02g - doc + if x>0: return x+1               -> {unknown, yes, "2"}
+Q02h - determinism (100 runs de Q02a)
+
+Rodar: doxoade retro-forward run q02
+"""
 from __future__ import annotations
+
 import ast
 import dataclasses
 import logging
 import sys
 import time
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
 DEBUG = "--debug" in sys.argv
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc_q02")
     if logger.handlers:
@@ -18,7 +62,11 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class _Quiet:
     __slots__ = ("level",)
     def __init__(self) -> None:
@@ -28,17 +76,30 @@
         return self
     def __exit__(self, *exc):
         self.level -= 1
+
+
 QUIET = _Quiet()
+
+
 def _dbg(*parts) -> None:
     if DEBUG and QUIET.level == 0:
         print("[DEBUG]", *parts, file=sys.stderr)
+
+
 class UnsupportedNodeError(RuntimeError):
     pass
+
+
+# ============================================================
+# Kernel inline (mesmo de Q00/Q01)
+# ============================================================
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 class _Wild:
     _instance = None
     def __new__(cls):
@@ -47,9 +108,13 @@
         return cls._instance
     def __repr__(self) -> str:
         return "_"
+
+
 WILD = _Wild()
 Term = str | Var | _Wild
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class Triple:
     s: str
@@ -58,10 +123,14 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
     def render(self) -> str:
         return f"({self.s}, {self.p}, {self.o})"
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -69,12 +138,15 @@
     conclusion: Pattern
     negations: tuple[Pattern, ...] = ()
     priority: int = 0
+
     def conclusion_fact(self, bindings, cycle):
         r = substitute(self.conclusion, bindings)
         if r is None:
             return None
         s, p, o = r
         return Triple(s, p, o, source="derived", rule_id=self.id, cycle=cycle)
+
+
 def unify_term(pattern, value, bindings):
     if isinstance(pattern, _Wild):
         return bindings
@@ -83,6 +155,8 @@
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern, fact_triple, bindings):
     b = bindings
     for p_t, f_v in zip(pattern, fact_triple):
@@ -90,6 +164,8 @@
         if b is None:
             return None
     return b
+
+
 def substitute(pattern, bindings):
     out = []
     for t in pattern:
@@ -102,8 +178,11 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_with_negations(conditions, negations, facts):
     results = []
+
     def recurse(conds, binds, wit):
         if not conds:
             for neg in negations:
@@ -119,8 +198,11 @@
             if b is None:
                 continue
             recurse(rest, b, wit + [f.to_tuple()])
+
     recurse(conditions, {}, [])
     return results
+
+
 class Engine:
     def __init__(self, max_cycles=100):
         self.max_cycles = max_cycles
@@ -130,6 +212,7 @@
         self.rule_attempts: dict[str, int] = {}
         self.shadowed: list[tuple[str, tuple]] = []
         self.cycle_history: list[dict] = []
+
     def run(self, initial_facts, rules):
         facts = list(initial_facts)
         ordered = sorted(rules, key=lambda r: -r.priority)
@@ -146,6 +229,7 @@
                 "winners": [],
                 "shadowed": [],
             }
+
             for rule in ordered:
                 matches = match_with_negations(
                     rule.conditions, rule.negations, facts
@@ -168,6 +252,7 @@
                     cycle_info["candidates"].append(
                         (rule.id, rule.priority, cf.to_tuple())
                     )
+
             winners = {}
             for rule, cf, wit in candidates:
                 key = (cf.s, cf.p)
@@ -190,14 +275,18 @@
                     self.shadowed.append(
                         (rule.id, cf.to_tuple())
                     )
+
             for (s, p), (rule, cf, wit) in winners.items():
                 cycle_info["winners"].append(
                     (rule.id, rule.priority, cf.to_tuple())
                 )
+
             self.cycle_history.append(cycle_info)
+
             if not winners:
                 self.cycles_used = cycles
                 return facts, cycles
+
             for (s, p), (rule, cf, wit) in winners.items():
                 facts.append(cf)
                 self.trace.append({
@@ -207,9 +296,16 @@
                     "derived_from": wit,
                 })
         raise RuntimeError(f"max_cycles={self.max_cycles}")
+
+
+# ============================================================
+# DC1 - AST -> facts (com branch count)
+# ============================================================
 BRANCH_NODE_TYPES = (
     ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler,
 )
+
+
 def _count_branches(body: list) -> int:
     count = 0
     for node in body:
@@ -217,6 +313,8 @@
             if isinstance(sub, BRANCH_NODE_TYPES):
                 count += 1
     return count
+
+
 def extract_facts(src: str) -> list[Triple]:
     tree = ast.parse(src)
     if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
@@ -227,7 +325,9 @@
     func = tree.body[0]
     has_doc = ast.get_docstring(func) is not None
     body_stmts = func.body[1:] if has_doc else func.body
+
     branch_count = _count_branches(body_stmts)
+
     facts = [
         Triple(func.name, "kind", "function"),
         Triple(func.name, "has_docstring", "yes" if has_doc else "no"),
@@ -244,7 +344,13 @@
                 func.name, "return_expr_kind", type(first.value).__name__
             ))
     return facts
+
+
+# ============================================================
+# DC2 - Rules (categoria + complexidade)
+# ============================================================
 F = Var("F")
+
 CATEGORY_RULES = [
     Rule("R_arith",
          conditions=((F, "kind", "function"),
@@ -270,6 +376,7 @@
          conclusion=(F, "category", "unknown"),
          priority=1),
 ]
+
 COMPLEXITY_RULES = [
     Rule("R_c_1",
          conditions=((F, "branch_count", "0"),),
@@ -292,7 +399,13 @@
          conclusion=(F, "complexity", "4+"),
          priority=15),
 ]
+
 RULES = CATEGORY_RULES + COMPLEXITY_RULES
+
+
+# ============================================================
+# classify + debug
+# ============================================================
 def _dbg_cycle(cycle_info):
     _dbg(f"  cycle {cycle_info['cycle']}:")
     m = cycle_info["matches"]
@@ -307,17 +420,22 @@
         _dbg(f"    idempotent: {rid} -> {fact}")
     if not cycle_info["winners"]:
         _dbg("    quiescence")
+
+
 def classify(src: str) -> dict:
     t0 = time.perf_counter()
     seed = extract_facts(src)
     t_extract = (time.perf_counter() - t0) * 1000
+
     t0 = time.perf_counter()
     eng = Engine()
     result_facts, cycles = eng.run(seed, RULES)
     t_infer = (time.perf_counter() - t0) * 1000
+
     categories = sorted(f.o for f in result_facts if f.p == "category")
     has_doc_vals = sorted(f.o for f in result_facts if f.p == "has_docstring")
     complexities = sorted(f.o for f in result_facts if f.p == "complexity")
+
     return {
         "input": src,
         "category": categories[0] if categories else None,
@@ -335,9 +453,12 @@
             "t_infer_ms": t_infer,
         },
     }
+
+
 def _classify_and_debug(label, src):
     r = classify(src)
     m = r["metrics"]
+
     _dbg(f"--- {label} ---")
     _dbg(f"  input: {src!r}")
     _dbg(f"  extract: {len(m['seed'])} seed facts in {m['t_extract_ms']:.3f}ms")
@@ -359,6 +480,11 @@
          f"total={(m['t_extract_ms'] + m['t_infer_ms']):.3f}ms")
     _dbg("")
     return r
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 SRC_Q02A = "def f(x): return x + 1"
 SRC_Q02B = "def g(x):\n    if x > 0:\n        return x\n    return 0"
 SRC_Q02C = "def h(xs):\n    for x in xs:\n        print(x)\n    return len(xs)"
@@ -372,20 +498,36 @@
             "    while x:\n        x -= 1\n    return x")
 SRC_Q02G = ('def p(x):\n    """Doc."""\n    if x > 0:\n'
             '        return x + 1\n    return 0')
+
+
 def run_q02a():
     return _classify_and_debug("Q02a: return x+1", SRC_Q02A)
+
+
 def run_q02b():
     return _classify_and_debug("Q02b: if x>0: return x / return 0", SRC_Q02B)
+
+
 def run_q02c():
     return _classify_and_debug("Q02c: for x in xs: print(x) / return", SRC_Q02C)
+
+
 def run_q02d():
     return _classify_and_debug("Q02d: if + for", SRC_Q02D)
+
+
 def run_q02e():
     return _classify_and_debug("Q02e: if + if + for", SRC_Q02E)
+
+
 def run_q02f():
     return _classify_and_debug("Q02f: 4+ branches", SRC_Q02F)
+
+
 def run_q02g():
     return _classify_and_debug("Q02g: doc + if", SRC_Q02G)
+
+
 def run_q02h():
     t0 = time.perf_counter()
     outs = set()
@@ -394,6 +536,7 @@
             r = run_q02a()
             outs.add((r["category"], r["has_docstring"], r["complexity"]))
     t_total = (time.perf_counter() - t0) * 1000
+
     if DEBUG:
         _dbg("--- Q02h: determinism (100 runs of Q02a) ---")
         _dbg(f"  runs: 100")
@@ -403,6 +546,8 @@
         _dbg(f"  time_per_run: {t_total/100:.3f}ms")
         _dbg("")
     return {"n": 100, "unique_count": len(outs), "triples": outs}
+
+
 def _debug_aggregate(results):
     if not DEBUG:
         return
@@ -413,11 +558,13 @@
     total_cycles = sum(r["cycles"] for r in results)
     extract_total = sum(r["metrics"]["t_extract_ms"] for r in results)
     infer_total = sum(r["metrics"]["t_infer_ms"] for r in results)
+
     per_rule: dict[str, int] = {}
     for r in results:
         for rid, k in r["metrics"]["rule_attempts"].items():
             per_rule[rid] = per_rule.get(rid, 0) + k
     per_rule_str = " ".join(f"{k}={v}" for k, v in sorted(per_rule.items()))
+
     _dbg("--- aggregate (7 classify calls) ---")
     _dbg(f"  functions: {n}")
     _dbg(f"  total_seed_facts: {total_seed}")
@@ -430,14 +577,21 @@
     _dbg(f"  infer_time_total: {infer_total:.3f}ms")
     _dbg(f"  total_time: {(extract_total + infer_total):.3f}ms")
     _dbg("")
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     if DEBUG:
         _dbg("=== engine_q02.py ===")
         _dbg("mode: debug")
         _dbg(f"args: {sys.argv}")
         _dbg("")
+
     lines: list[str] = []
     falhas: list[str] = []
+
     checks = [
         ("Q02a", SRC_Q02A, "arithmetic_return", "no",  "1",  run_q02a),
         ("Q02b", SRC_Q02B, "unknown",           "no",  "2",  run_q02b),
@@ -447,6 +601,7 @@
         ("Q02f", SRC_Q02F, "unknown",           "no",  "4+", run_q02f),
         ("Q02g", SRC_Q02G, "unknown",           "yes", "2",  run_q02g),
     ]
+
     results_for_agg = []
     for label, src, exp_cat, exp_doc, exp_cplx, fn in checks:
         r = fn()
@@ -473,6 +628,7 @@
                 f"{label}: complexity={r['complexity']!r}, "
                 f"esperado {exp_cplx!r}"
             )
+
     lines.append("=== Q02h: determinism (100 runs of Q02a) ===")
     h = run_q02h()
     lines.append(f"n:            {h['n']}")
@@ -480,7 +636,9 @@
     lines.append("")
     if h["unique_count"] != 1:
         falhas.append(f"Q02h: {h['unique_count']} variacoes")
+
     _debug_aggregate(results_for_agg)
+
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -493,8 +651,10 @@
         resultado = 0
         if DEBUG:
             _dbg("=== done: all checks passed ===")
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -502,6 +662,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/code_classification/poc/q03_pattern/README.md
  xml=73 linhas | disco=95 linhas
--- XML:doxoade/research/code_classification/poc/q03_pattern/README.md
+++ DISCO:doxoade/research/code_classification/poc/q03_pattern/README.md
@@ -1,10 +1,13 @@
+# Q03 - Pattern detection + cross-cycle chaining (DC2)
 
-# Q03 - Pattern detection + cross-cycle chaining (DC2)
 **Contrato:** DC2 (Classification) com 4 dimensoes ortogonais.
+
 ## Diferenca qualitativa de Q00-Q02
+
 Ate Q02, **todas as rules matchavam apenas fatos seed** (extraidos do AST).
 Q03 forca uma rule a matchar em **fatos derivados por outras rules** — o
 motor compoe em camadas.
+
 Cadeia (Q03a):
 ```
 cycle 1 (seed):   name_prefix=create       (extraido)
@@ -15,39 +18,54 @@
                   (le has_naming + has_behavior derivados no cycle 1)
 cycle 3:          quiescencia
 ```
+
 Se Q03 passa, C1+C3 compoem — base para deteccao de padroes reais.
+
 ## Targets
+
 | Pattern | Condicoes | Exemplo |
 |---|---|---|
 | `factory` | `name_prefix=create` AND `return_kind=Call` | `def create_user(n): return User(n)` |
 | `accessor` | `name_prefix=get` AND `return_kind=Name` | `def get_x(x): return x` |
 | `predicate` | `name_prefix=is` AND `return_kind=Compare` | `def is_valid(x): return x > 0` |
 | (nenhum) | qualquer outro | `def foo(x): return bar(x)` |
+
 `name_prefix` ∈ `{create, get, is, other}` — extraido do nome via `startswith`.
+
 ## SEM default "utility" — decisao de design
+
 Q00 usou NAF para default `unknown`. Q03 **nao pode** aplicar o mesmo padrao:
+
 ```
 cycle 1: R_utility        -> pattern=utility  (NAF passa, nada ainda)
 cycle 2: R_factory        -> pattern=factory  (hints presentes)
          CONFLITO: (F, pattern, utility) vs (F, pattern, factory)
 ```
+
 Ambos ficariam em `facts` — WM e monotonico, sem retracao cross-cycle.
 Engine atual resolve conflito **within-cycle** (via priorities), mas nao
 **cross-cycle**.
+
 **Decisao:** sem default. Ausencia de `pattern` fact = `pattern=None`.
 Honesto sobre limitacao. Deixa retracao cross-cycle para Q04+.
+
 ## O que Q03 prova
+
 1. **Cross-cycle chaining funciona.** Rules leem fatos derivados no cycle anterior.
 2. **4 dims coexistem** sem colisao (Q03a-e tem 4 dims; Q03d/e tem 3, `pattern=None`).
 3. **Partial matches nao disparam pattern.**
    - Q03e: naming=create mas behavior=Constant (nao Call) -> None
    - Q03f: naming=is mas behavior=Call (nao Compare) -> None
 4. **Determinismo** com 4 dims (Q03g, 100 runs).
+
 ## O que NAO prova
+
 - Retracao cross-cycle (utility default) -> Q04+
 - Multi-entity patterns (factory que chama outra funcao) -> fora do escopo Q03
 - Padroes estruturais complexos (visitor, strategy) -> requerem multi-funcao
+
 ## Err table (ProDeNov 5.4)
+
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
 | R_factory dispara em cycle 1 (sem hints) | baixa | critico | snapshot semantics (B) impede |
@@ -55,7 +73,9 @@
 | Prefix `other` dispara algo | baixa | medio | R_create/get/is prefix so com `startswith` explicito |
 | Cross-cycle conflict | baixa | alto | ausencia de default elimina fonte |
 | Determinismo em 4 dims | baixa | alto | Q03g (100 runs) |
+
 ## Planos A / B / C
+
 - **A (implementado):** cross-cycle via facts derivados; sem default; prefixo
   estruturado.
 - **B (se Q04 precisar de default):** adicionar retracao cross-cycle no engine
@@ -63,11 +83,13 @@
   Custo: engine mais complexo (remocao de facts em facts).
 - **C (se multi-funcao for necessario):** Q05 introduz fatos com shape
   `(func_a, calls, func_b)`. Engine atual ja suporta (sujeito = funcao).
+
 ## Licao
+
 C1+C3 **compoem em camadas**. Rules no cycle N+1 leem o que cycle N
 derivou. Isso ja estava no motor (P02/P20 desde o inicio) mas nunca
 exercitado em `code_classification`.
+
 O ponto critico e **nao usar default via NAF quando hints intermediarias
 sao derivadas em camadas** — o NAF dispara cedo demais e o resultado se
 prende. Documentar essa armadilha evita que Q04 repita o erro.
-      

■ doxoade/research/code_classification/poc/q03_pattern/engine_q03.py
  xml=562 linhas | disco=729 linhas
--- XML:doxoade/research/code_classification/poc/q03_pattern/engine_q03.py
+++ DISCO:doxoade/research/code_classification/poc/q03_pattern/engine_q03.py
@@ -1,13 +1,58 @@
 
+# -*- coding: utf-8 -*-
+# doxoade/research/code_classification/poc/q03_pattern/engine_q03.py
+"""
+Q03 - Pattern detection as 4th dim, cross-cycle chaining (DC2).
+
+Contrato: DC2 (Classification) estendido.
+    4 dimensoes: category, has_docstring, complexity, pattern.
+
+DIFERENCA QUALITATIVA de Q00-Q02:
+    Ate Q02, todas as rules matchavam apenas fatos SEED (extraidos do AST).
+    Q03 forca uma rule a matchar em fatos DERIVADOS por outras rules — o
+    motor compoe em camadas (cycle N+1 le o que cycle N derivou).
+
+Cadeia de derivacao:
+    Cycle 1 (seed):  name_prefix=create       (extraido)
+                     return_expr_kind=Call    (extraido)
+    Cycle 1 (rules): R_create_prefix  -> has_naming=create
+                     R_returns_call   -> has_behavior=returns_call
+    Cycle 2 (rules): R_factory        -> pattern=factory  (le has_naming + has_behavior)
+    Cycle 3: quiesce
+
+SEM default "utility":
+    NAF (Q00) nao funciona aqui. R_utility disparia em cycle 1 (antes das
+    hints) e ficaria preso em facts — WM e monotonico, sem retracao
+    cross-cycle. Decisao: sem default. Ausencia de `pattern` = None.
+
+Targets Q03:
+    factory   = name_prefix=create  AND return_kind=Call
+    accessor  = name_prefix=get     AND return_kind=Name
+    predicate = name_prefix=is      AND return_kind=Compare
+
+Q03a - create_user + Call  -> factory
+Q03b - get_x + Name        -> accessor
+Q03c - is_valid + Compare  -> predicate
+Q03d - foo + Call          -> None (Call sem naming)
+Q03e - create_data + Const -> None (naming sem behavior)
+Q03f - is_ready + Call     -> None (naming is + behavior Call: mismatch)
+Q03g - determinism (100 runs de Q03a)
+
+Rodar: doxoade retro-forward run q03
+"""
 from __future__ import annotations
+
 import ast
 import dataclasses
 import logging
 import sys
 import time
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
 DEBUG = "--debug" in sys.argv
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc_q03")
     if logger.handlers:
@@ -17,7 +62,11 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class _Quiet:
     __slots__ = ("level",)
     def __init__(self) -> None:
@@ -27,17 +76,30 @@
         return self
     def __exit__(self, *exc):
         self.level -= 1
+
+
 QUIET = _Quiet()
+
+
 def _dbg(*parts) -> None:
     if DEBUG and QUIET.level == 0:
         print("[DEBUG]", *parts, file=sys.stderr)
+
+
 class UnsupportedNodeError(RuntimeError):
     pass
+
+
+# ============================================================
+# Kernel inline
+# ============================================================
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 class _Wild:
     _instance = None
     def __new__(cls):
@@ -46,9 +108,13 @@
         return cls._instance
     def __repr__(self) -> str:
         return "_"
+
+
 WILD = _Wild()
 Term = str | Var | _Wild
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class Triple:
     s: str
@@ -57,10 +123,14 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
     def render(self) -> str:
         return f"({self.s}, {self.p}, {self.o})"
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -68,12 +138,15 @@
     conclusion: Pattern
     negations: tuple[Pattern, ...] = ()
     priority: int = 0
+
     def conclusion_fact(self, bindings, cycle):
         r = substitute(self.conclusion, bindings)
         if r is None:
             return None
         s, p, o = r
         return Triple(s, p, o, source="derived", rule_id=self.id, cycle=cycle)
+
+
 def unify_term(pattern, value, bindings):
     if isinstance(pattern, _Wild):
         return bindings
@@ -82,6 +155,8 @@
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern, fact_triple, bindings):
     b = bindings
     for p_t, f_v in zip(pattern, fact_triple):
@@ -89,6 +164,8 @@
         if b is None:
             return None
     return b
+
+
 def substitute(pattern, bindings):
     out = []
     for t in pattern:
@@ -101,8 +178,11 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_with_negations(conditions, negations, facts):
     results = []
+
     def recurse(conds, binds, wit):
         if not conds:
             for neg in negations:
@@ -118,8 +198,11 @@
             if b is None:
                 continue
             recurse(rest, b, wit + [f.to_tuple()])
+
     recurse(conditions, {}, [])
     return results
+
+
 class Engine:
     def __init__(self, max_cycles=100):
         self.max_cycles = max_cycles
@@ -129,6 +212,7 @@
         self.rule_attempts: dict[str, int] = {}
         self.shadowed: list[tuple[str, tuple]] = []
         self.cycle_history: list[dict] = []
+
     def run(self, initial_facts, rules):
         facts = list(initial_facts)
         ordered = sorted(rules, key=lambda r: -r.priority)
@@ -145,6 +229,7 @@
                 "winners": [],
                 "shadowed": [],
             }
+
             for rule in ordered:
                 matches = match_with_negations(
                     rule.conditions, rule.negations, facts
@@ -167,6 +252,7 @@
                     cycle_info["candidates"].append(
                         (rule.id, rule.priority, cf.to_tuple())
                     )
+
             winners = {}
             for rule, cf, wit in candidates:
                 key = (cf.s, cf.p)
@@ -189,14 +275,18 @@
                     self.shadowed.append(
                         (rule.id, cf.to_tuple())
                     )
+
             for (s, p), (rule, cf, wit) in winners.items():
                 cycle_info["winners"].append(
                     (rule.id, rule.priority, cf.to_tuple())
                 )
+
             self.cycle_history.append(cycle_info)
+
             if not winners:
                 self.cycles_used = cycles
                 return facts, cycles
+
             for (s, p), (rule, cf, wit) in winners.items():
                 facts.append(cf)
                 self.trace.append({
@@ -206,9 +296,16 @@
                     "derived_from": wit,
                 })
         raise RuntimeError(f"max_cycles={self.max_cycles}")
+
+
+# ============================================================
+# DC1 - AST -> facts (name + name_prefix)
+# ============================================================
 BRANCH_NODE_TYPES = (
     ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler,
 )
+
+
 def _count_branches(body: list) -> int:
     count = 0
     for node in body:
@@ -216,6 +313,8 @@
             if isinstance(sub, BRANCH_NODE_TYPES):
                 count += 1
     return count
+
+
 def _name_prefix(name: str) -> str:
     if name.startswith("create_"):
         return "create"
@@ -224,6 +323,8 @@
     if name.startswith("is_"):
         return "is"
     return "other"
+
+
 def extract_facts(src: str) -> list[Triple]:
     tree = ast.parse(src)
     if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
@@ -235,6 +336,7 @@
     has_doc = ast.get_docstring(func) is not None
     body_stmts = func.body[1:] if has_doc else func.body
     branch_count = _count_branches(body_stmts)
+
     facts = [
         Triple(func.name, "kind", "function"),
         Triple(func.name, "name", func.name),
@@ -253,7 +355,13 @@
                 func.name, "return_expr_kind", type(first.value).__name__
             ))
     return facts
+
+
+# ============================================================
+# DC2 - Rules (categoria + complexidade + pattern via chaining)
+# ============================================================
 F = Var("F")
+
 CATEGORY_RULES = [
     Rule("R_arith",
          conditions=((F, "kind", "function"),
@@ -279,6 +387,7 @@
          conclusion=(F, "category", "unknown"),
          priority=1),
 ]
+
 COMPLEXITY_RULES = [
     Rule("R_c_1",
          conditions=((F, "branch_count", "0"),),
@@ -301,6 +410,8 @@
          conclusion=(F, "complexity", "4+"),
          priority=15),
 ]
+
+# LAYER 1: naming_hint (from seed)
 NAMING_RULES = [
     Rule("R_create_prefix",
          conditions=((F, "name_prefix", "create"),),
@@ -315,6 +426,8 @@
          conclusion=(F, "has_naming", "is"),
          priority=10),
 ]
+
+# LAYER 1: behavior_hint (from seed)
 BEHAVIOR_RULES = [
     Rule("R_returns_call",
          conditions=((F, "return_expr_kind", "Call"),),
@@ -329,6 +442,8 @@
          conclusion=(F, "has_behavior", "returns_compare"),
          priority=10),
 ]
+
+# LAYER 2: pattern (from derived hints) - CROSS-CYCLE CHAINING
 PATTERN_RULES = [
     Rule("R_factory",
          conditions=((F, "has_naming", "create"),
@@ -346,8 +461,14 @@
          conclusion=(F, "pattern", "predicate"),
          priority=20),
 ]
+
 RULES = (CATEGORY_RULES + COMPLEXITY_RULES +
          NAMING_RULES + BEHAVIOR_RULES + PATTERN_RULES)
+
+
+# ============================================================
+# classify + debug
+# ============================================================
 def _dbg_cycle(cycle_info):
     _dbg(f"  cycle {cycle_info['cycle']}:")
     m = cycle_info["matches"]
@@ -362,18 +483,23 @@
         _dbg(f"    idempotent: {rid} -> {fact}")
     if not cycle_info["winners"]:
         _dbg("    quiescence")
+
+
 def classify(src: str) -> dict:
     t0 = time.perf_counter()
     seed = extract_facts(src)
     t_extract = (time.perf_counter() - t0) * 1000
+
     t0 = time.perf_counter()
     eng = Engine()
     result_facts, cycles = eng.run(seed, RULES)
     t_infer = (time.perf_counter() - t0) * 1000
+
     categories = sorted(f.o for f in result_facts if f.p == "category")
     has_doc_vals = sorted(f.o for f in result_facts if f.p == "has_docstring")
     complexities = sorted(f.o for f in result_facts if f.p == "complexity")
     patterns = sorted(f.o for f in result_facts if f.p == "pattern")
+
     return {
         "input": src,
         "category": categories[0] if categories else None,
@@ -392,9 +518,12 @@
             "t_infer_ms": t_infer,
         },
     }
+
+
 def _classify_and_debug(label, src):
     r = classify(src)
     m = r["metrics"]
+
     _dbg(f"--- {label} ---")
     _dbg(f"  input: {src!r}")
     _dbg(f"  extract: {len(m['seed'])} seed facts in {m['t_extract_ms']:.3f}ms")
@@ -418,24 +547,43 @@
          f"total={(m['t_extract_ms'] + m['t_infer_ms']):.3f}ms")
     _dbg("")
     return r
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 SRC_Q03A = "def create_user(name): return User(name)"
 SRC_Q03B = "def get_x(x): return x"
 SRC_Q03C = "def is_valid(x): return x > 0"
 SRC_Q03D = "def foo(x): return bar(x)"
 SRC_Q03E = "def create_data(): return 42"
 SRC_Q03F = "def is_ready(x): return helper(x)"
+
+
 def run_q03a():
     return _classify_and_debug("Q03a: create_user + Call", SRC_Q03A)
+
+
 def run_q03b():
     return _classify_and_debug("Q03b: get_x + Name", SRC_Q03B)
+
+
 def run_q03c():
     return _classify_and_debug("Q03c: is_valid + Compare", SRC_Q03C)
+
+
 def run_q03d():
     return _classify_and_debug("Q03d: foo + Call (sem naming)", SRC_Q03D)
+
+
 def run_q03e():
     return _classify_and_debug("Q03e: create_data + Constant (naming sem behavior)", SRC_Q03E)
+
+
 def run_q03f():
     return _classify_and_debug("Q03f: is_ready + Call (mismatch naming/behavior)", SRC_Q03F)
+
+
 def run_q03g():
     t0 = time.perf_counter()
     outs = set()
@@ -445,6 +593,7 @@
             outs.add((r["category"], r["has_docstring"],
                       r["complexity"], r["pattern"]))
     t_total = (time.perf_counter() - t0) * 1000
+
     if DEBUG:
         _dbg("--- Q03g: determinism (100 runs of Q03a) ---")
         _dbg(f"  runs: 100")
@@ -454,6 +603,8 @@
         _dbg(f"  time_per_run: {t_total/100:.3f}ms")
         _dbg("")
     return {"n": 100, "unique_count": len(outs), "quads": outs}
+
+
 def _debug_aggregate(results):
     if not DEBUG:
         return
@@ -464,11 +615,13 @@
     total_cycles = sum(r["cycles"] for r in results)
     extract_total = sum(r["metrics"]["t_extract_ms"] for r in results)
     infer_total = sum(r["metrics"]["t_infer_ms"] for r in results)
+
     per_rule: dict[str, int] = {}
     for r in results:
         for rid, k in r["metrics"]["rule_attempts"].items():
             per_rule[rid] = per_rule.get(rid, 0) + k
     per_rule_str = " ".join(f"{k}={v}" for k, v in sorted(per_rule.items()))
+
     _dbg("--- aggregate (6 classify calls) ---")
     _dbg(f"  functions: {n}")
     _dbg(f"  total_seed_facts: {total_seed}")
@@ -481,14 +634,21 @@
     _dbg(f"  infer_time_total: {infer_total:.3f}ms")
     _dbg(f"  total_time: {(extract_total + infer_total):.3f}ms")
     _dbg("")
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     if DEBUG:
         _dbg("=== engine_q03.py ===")
         _dbg("mode: debug")
         _dbg(f"args: {sys.argv}")
         _dbg("")
+
     lines: list[str] = []
     falhas: list[str] = []
+
     checks = [
         ("Q03a", SRC_Q03A, "unknown",           "no", "1", "factory",   run_q03a),
         ("Q03b", SRC_Q03B, "identity_return",   "no", "1", "accessor",  run_q03b),
@@ -497,6 +657,7 @@
         ("Q03e", SRC_Q03E, "constant_return",   "no", "1", None,        run_q03e),
         ("Q03f", SRC_Q03F, "unknown",           "no", "1", None,        run_q03f),
     ]
+
     results_for_agg = []
     for label, src, exp_cat, exp_doc, exp_cplx, exp_pat, fn in checks:
         r = fn()
@@ -528,6 +689,7 @@
             falhas.append(
                 f"{label}: pattern={r['pattern']!r}, esperado {exp_pat!r}"
             )
+
     lines.append("=== Q03g: determinism (100 runs of Q03a) ===")
     g = run_q03g()
     lines.append(f"n:            {g['n']}")
@@ -535,7 +697,9 @@
     lines.append("")
     if g["unique_count"] != 1:
         falhas.append(f"Q03g: {g['unique_count']} variacoes")
+
     _debug_aggregate(results_for_agg)
+
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -548,8 +712,10 @@
         resultado = 0
         if DEBUG:
             _dbg("=== done: all checks passed ===")
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -557,6 +723,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/code_classification/poc/q04_retraction/README.md
  xml=77 linhas | disco=100 linhas
--- XML:doxoade/research/code_classification/poc/q04_retraction/README.md
+++ DISCO:doxoade/research/code_classification/poc/q04_retraction/README.md
@@ -1,10 +1,14 @@
+# Q04 - Cross-cycle retraction (engine upgrade)
 
-# Q04 - Cross-cycle retraction (engine upgrade)
 **Contrato:** C1 (Inferencia) estendido com retracao.
+
 ## Mecanismo declarado
+
 `Fact` ganha campo `priority` (herdado da rule que derivou). Engine
 ganha `retracted: set[(s,p,o)]` e `retracted_history: list[dict]`.
+
 Na fase de merge (apos winners within-cycle):
+
 ```
 para cada winner (s, p, o_new, P_new):
   para cada fato vivo (s, p, o_old, P_old):
@@ -14,40 +18,54 @@
     se P_new < ef_prio: shadow o_new
     se P_new == ef_prio: shadow o_new (tie-break first-wins)
 ```
+
 **Seeds protegidos.** `source="seed"` tem prio efetiva infinito, nunca
 retratados.
+
 **Retracao monotona.** Fato retratado nao ressuscita. Filtro em
 `snapshot`/`existing`. NAF sobre vivo.
+
 **Cross-cycle only.** Conflito within-cycle continua como P02 (prioridade
 + tie-break within).
+
 ## O que Q04 prova
+
 ### Q04a — retração happy path
 R_utility (prio 1, NAF default) dispara cycle 1 → pattern=utility.
 R_factory (prio 20) dispara cycle 2 → pattern=factory. Retração:
 utility sai, factory entra. Final: pattern=factory, retracted=1.
+
 **Sem Q04, WM teria `(create_user, pattern, utility)` E
 `(create_user, pattern, factory)`** — contradição em `pattern`.
 Resolvido por retração.
+
 ### Q04b — sem conflito
 R_utility sozinha (nao ha R_factory aplicavel). pattern=utility
 permanece. retracted=0.
+
 ### Q04c — tie prio cross-cycle
 R_a_low (prio 10) dispara cycle 1 → pattern=first_fired.
 R_b_low (prio 10) dispara cycle 2 → pattern=second_fired. Tie 10=10
 cross-cycle. Shadow novo (first wins). retracted=0.
+
 ### Q04d — higher fires first, lower cross
 R_a_high (prio 20) dispara cycle 1 → pattern=high.
 R_b_low (prio 10) + R_b_verylow (prio 1) disparam cycle 2. Existing
 high prio 20. Novos prio 10 e 1 < 20. Shadow ambos. retracted=0,
 pattern=high preservado.
+
 ### Q04e — determinismo
 100 runs de Q04a → mesmo resultado (pattern=factory, retracted=1).
+
 ## O que NAO prova
+
 - Retração em cascata (A retrai B, C retrai A) -> Q05+
 - Seeds em conflito com derivados -> protegido por design, nao testado
 - Retração com multi-valued predicates -> assumido single-valued
 - Performance com >1000 facts -> Q04 tem ~10 facts, O(n) scan e trivial
+
 ## Err table (ProDeNov 5.4)
+
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
 | Seed retratado por engano | nula | critico | check `source == "seed"` -> prio 999999 |
@@ -55,7 +73,9 @@
 | Retracao dispara em ciclo errado | baixa | alto | trace + Q04e |
 | Cross-cycle loop (A retrai B, B refire) | baixa | critico | NAF sobre vivo previne (utility nao refire com factory presente) |
 | Tie-break nao deterministico | baixa | alto | Q04c + rule order |
+
 ## Planos A / B / C
+
 - **A (implementado):** prioridade por fato, retracao monotona, seed
   protegido, NAF sobre vivo.
 - **B (se cascata for necessaria):** `retracted_by: dict[(s,p,o),
@@ -64,14 +84,17 @@
 - **C (se multi-valued for necessaria):** `Fact.multi_valued: bool` +
   retracao so para single-valued. Custo: schema de fato mais rico,
   rules declaram cardinalidade.
+
 ## Licao
+
 **Prioridade nao resolve cross-cycle conflict sozinha.** Sem retracao,
 R_utility (cycle 1) + R_factory (cycle 2) coexistem — engine
 within-cycle nao atua em fatos de ciclos distintos.
+
 **Retracao monotona e minimalista.** Nao tenta des-retracoes em
 cascata, nao tem rollback, nao reativa fatos. Isso mantem o engine
 previsivel. Se Q05 precisar de cascata, e upgrade B explicito.
+
 **NAF sobre vivo previne refire.** Apos retracao de pattern=utility,
 NAF de R_utility falha (factory esta em WM). Sem esse detalhe, utility
 refiraria cycle 3, factory retrataria cycle 4, loop infinito.
-      

■ doxoade/research/code_classification/poc/q04_retraction/engine_q04.py
  xml=624 linhas | disco=784 linhas
--- XML:doxoade/research/code_classification/poc/q04_retraction/engine_q04.py
+++ DISCO:doxoade/research/code_classification/poc/q04_retraction/engine_q04.py
@@ -1,13 +1,48 @@
 
+# -*- coding: utf-8 -*-
+# doxoade/research/code_classification/poc/q04_retraction/engine_q04.py
+"""
+Q04 - Cross-cycle retraction (engine upgrade).
+
+Contrato: C1 (Inferencia) estendido com retracao.
+    Fatos derivados podem ser retratados por fatos de prioridade maior,
+    mesmo em ciclos posteriores.
+
+Diferenca de Q03:
+    Q03 nao tinha retracao. R_utility (default via NAF) e R_factory
+    coexistiam em `pattern` = contradicao. Q04 adiciona retracao por
+    prioridade. Seeds sao protegidos.
+
+Mecanismo:
+    Fact ganha priority (herdada da rule que derivou).
+    Engine.run() apos merge de winners:
+      - Se novo (s,p,o_new) prio P_new > existente (s,p,o_old) prio P_old
+        -> retrata o_old, adiciona o_new.
+      - Se P_new < P_old -> shadow novo (nao retrata).
+      - Se P_new == P_old -> shadow novo (tie-break first-wins).
+      - Seeds (source="seed") tem prio efetiva infinito -> nunca retratados.
+
+Q04a - utility (prio 1) retratada por factory (prio 20). Assert retracted=1.
+Q04b - utility sozinha. Assert retracted=0, pattern=utility.
+Q04c - tie prio (10=10, cross-cycle). Assert retracted=0, pattern=first_fired.
+Q04d - higher fires first, lower crosses next. Assert retracted=0, pattern=high.
+Q04e - determinism (100 runs de Q04a).
+
+Rodar: doxoade retro-forward run q04
+"""
 from __future__ import annotations
+
 import ast
 import dataclasses
 import logging
 import sys
 import time
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
 DEBUG = "--debug" in sys.argv
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc_q04")
     if logger.handlers:
@@ -17,7 +52,11 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class _Quiet:
     __slots__ = ("level",)
     def __init__(self) -> None:
@@ -27,17 +66,30 @@
         return self
     def __exit__(self, *exc):
         self.level -= 1
+
+
 QUIET = _Quiet()
+
+
 def _dbg(*parts) -> None:
     if DEBUG and QUIET.level == 0:
         print("[DEBUG]", *parts, file=sys.stderr)
+
+
 class UnsupportedNodeError(RuntimeError):
     pass
+
+
+# ============================================================
+# Kernel (Q04: retraction-aware)
+# ============================================================
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 class _Wild:
     _instance = None
     def __new__(cls):
@@ -46,9 +98,13 @@
         return cls._instance
     def __repr__(self) -> str:
         return "_"
+
+
 WILD = _Wild()
 Term = str | Var | _Wild
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class Fact:
     s: str
@@ -58,10 +114,14 @@
     rule_id: str | None = None
     cycle: int = 0
     priority: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
     def render(self) -> str:
         return f"({self.s}, {self.p}, {self.o})"
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -69,6 +129,7 @@
     conclusion: Pattern
     negations: tuple[Pattern, ...] = ()
     priority: int = 0
+
     def conclusion_fact(self, bindings, cycle):
         r = substitute(self.conclusion, bindings)
         if r is None:
@@ -76,6 +137,8 @@
         s, p, o = r
         return Fact(s, p, o, source="derived",
                     rule_id=self.id, cycle=cycle, priority=self.priority)
+
+
 def unify_term(pattern, value, bindings):
     if isinstance(pattern, _Wild):
         return bindings
@@ -84,6 +147,8 @@
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern, fact_triple, bindings):
     b = bindings
     for p_t, f_v in zip(pattern, fact_triple):
@@ -91,6 +156,8 @@
         if b is None:
             return None
     return b
+
+
 def substitute(pattern, bindings):
     out = []
     for t in pattern:
@@ -103,8 +170,11 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_with_negations(conditions, negations, live_facts):
     results = []
+
     def recurse(conds, binds, wit):
         if not conds:
             for neg in negations:
@@ -120,8 +190,11 @@
             if b is None:
                 continue
             recurse(rest, b, wit + [f.to_tuple()])
+
     recurse(conditions, {}, [])
     return results
+
+
 class Engine:
     def __init__(self, max_cycles=100):
         self.max_cycles = max_cycles
@@ -133,12 +206,14 @@
         self.rules_attempted = 0
         self.rule_attempts: dict[str, int] = {}
         self.cycle_history: list[dict] = []
+
     def run(self, initial_facts, rules):
         facts = list(initial_facts)
         ordered = sorted(rules, key=lambda r: -r.priority)
         cycles = 0
         while cycles < self.max_cycles:
             cycles += 1
+            # live = facts not retracted
             live_facts = [f for f in facts if f.to_tuple() not in self.retracted]
             existing = set(f.to_tuple() for f in live_facts)
             candidates = []
@@ -151,6 +226,7 @@
                 "shadowed": [],
                 "retracted": [],
             }
+
             for rule in ordered:
                 matches = match_with_negations(
                     rule.conditions, rule.negations, live_facts
@@ -173,6 +249,8 @@
                     cycle_info["candidates"].append(
                         (rule.id, rule.priority, cf.to_tuple())
                     )
+
+            # Within-cycle winners (mesmo de P02/Q00-Q03)
             winners = {}
             for rule, cf, wit in candidates:
                 key = (cf.s, cf.p)
@@ -195,6 +273,8 @@
                     self.shadowed.append(
                         (rule.id, cf.to_tuple())
                     )
+
+            # Q04: cross-cycle retraction check + merge
             for (s, p), (rule, cf, wit) in winners.items():
                 to_retract: list[Fact] = []
                 shadow_new = False
@@ -202,6 +282,7 @@
                     if ef.s != s or ef.p != p:
                         continue
                     if ef.o == cf.o:
+                        # exato mesmo valor, idempotente
                         cycle_info["idempotent"].append(
                             (rule.id, cf.to_tuple())
                         )
@@ -213,10 +294,12 @@
                     else:
                         shadow_new = True
                         break
+
                 if shadow_new:
                     cycle_info["shadowed"].append((rule.id, cf.to_tuple()))
                     self.shadowed.append((rule.id, cf.to_tuple()))
                     continue
+
                 for ef in to_retract:
                     self.retracted.add(ef.to_tuple())
                     self.retracted_history.append({
@@ -228,6 +311,7 @@
                     cycle_info["retracted"].append(
                         (ef.rule_id, ef.to_tuple(), rule.id)
                     )
+
                 facts.append(cf)
                 self.trace.append({
                     "cycle": cycles,
@@ -238,14 +322,24 @@
                 cycle_info["winners"].append(
                     (rule.id, rule.priority, cf.to_tuple())
                 )
+
             self.cycle_history.append(cycle_info)
+
             if not cycle_info["winners"]:
                 self.cycles_used = cycles
                 return facts, cycles
+
         raise RuntimeError(f"max_cycles={self.max_cycles}")
+
+
+# ============================================================
+# DC1 - AST -> facts
+# ============================================================
 BRANCH_NODE_TYPES = (
     ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler,
 )
+
+
 def _count_branches(body: list) -> int:
     count = 0
     for node in body:
@@ -253,6 +347,8 @@
             if isinstance(sub, BRANCH_NODE_TYPES):
                 count += 1
     return count
+
+
 def _name_prefix(name: str) -> str:
     if name.startswith("create_"):
         return "create"
@@ -261,6 +357,8 @@
     if name.startswith("is_"):
         return "is"
     return "other"
+
+
 def extract_facts(src: str) -> list[Fact]:
     tree = ast.parse(src)
     if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
@@ -272,6 +370,7 @@
     has_doc = ast.get_docstring(func) is not None
     body_stmts = func.body[1:] if has_doc else func.body
     branch_count = _count_branches(body_stmts)
+
     facts = [
         Fact(func.name, "kind", "function"),
         Fact(func.name, "name", func.name),
@@ -290,7 +389,13 @@
                 func.name, "return_expr_kind", type(first.value).__name__
             ))
     return facts
+
+
+# ============================================================
+# DC2 - Rules
+# ============================================================
 F = Var("F")
+
 CATEGORY_RULES = [
     Rule("R_arith",
          conditions=((F, "kind", "function"),
@@ -316,6 +421,7 @@
          conclusion=(F, "category", "unknown"),
          priority=1),
 ]
+
 COMPLEXITY_RULES = [
     Rule("R_c_1",
          conditions=((F, "branch_count", "0"),),
@@ -338,6 +444,7 @@
          conclusion=(F, "complexity", "4+"),
          priority=15),
 ]
+
 NAMING_RULES = [
     Rule("R_create_prefix",
          conditions=((F, "name_prefix", "create"),),
@@ -352,6 +459,7 @@
          conclusion=(F, "has_naming", "is"),
          priority=10),
 ]
+
 BEHAVIOR_RULES = [
     Rule("R_returns_call",
          conditions=((F, "return_expr_kind", "Call"),),
@@ -366,6 +474,7 @@
          conclusion=(F, "has_behavior", "returns_compare"),
          priority=10),
 ]
+
 PATTERN_RULES = [
     Rule("R_factory",
          conditions=((F, "has_naming", "create"),
@@ -383,6 +492,8 @@
          conclusion=(F, "pattern", "predicate"),
          priority=20),
 ]
+
+# Q04-specific rules for retraction tests
 RETRACTION_RULES = [
     Rule("R_utility",
          conditions=((F, "kind", "function"),),
@@ -410,8 +521,14 @@
          conclusion=(F, "pattern", "low"),
          priority=1),
 ]
+
 RULES = (CATEGORY_RULES + COMPLEXITY_RULES +
          NAMING_RULES + BEHAVIOR_RULES + PATTERN_RULES + RETRACTION_RULES)
+
+
+# ============================================================
+# classify + debug
+# ============================================================
 def _dbg_cycle(cycle_info):
     _dbg(f"  cycle {cycle_info['cycle']}:")
     m = cycle_info["matches"]
@@ -428,19 +545,24 @@
         _dbg(f"    idempotent: {rid} -> {fact}")
     if not cycle_info["winners"]:
         _dbg("    quiescence")
+
+
 def classify(src, seed=None, rules=None) -> dict:
     t0 = time.perf_counter()
     facts = seed if seed is not None else extract_facts(src)
     t_extract = (time.perf_counter() - t0) * 1000
+
     t0 = time.perf_counter()
     eng = Engine()
     result_facts, cycles = eng.run(facts, rules if rules is not None else RULES)
     t_infer = (time.perf_counter() - t0) * 1000
+
     live = [f for f in result_facts if f.to_tuple() not in eng.retracted]
     categories = sorted(f.o for f in live if f.p == "category")
     has_doc_vals = sorted(f.o for f in live if f.p == "has_docstring")
     complexities = sorted(f.o for f in live if f.p == "complexity")
     patterns = sorted(f.o for f in live if f.p == "pattern")
+
     return {
         "input": src,
         "category": categories[0] if categories else None,
@@ -461,9 +583,12 @@
             "t_infer_ms": t_infer,
         },
     }
+
+
 def _classify_and_debug(label, src=None, seed=None, rules=None):
     r = classify(src, seed=seed, rules=rules)
     m = r["metrics"]
+
     _dbg(f"--- {label} ---")
     if src:
         _dbg(f"  input: {src!r}")
@@ -492,30 +617,47 @@
          f"total={(m['t_extract_ms'] + m['t_infer_ms']):.3f}ms")
     _dbg("")
     return r
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 SRC_Q04A = "def create_user(name): return User(name)"
 SRC_Q04B = "def foo(x): return x"
+
 SEED_Q04C = [
     Fact("f", "kind", "function"),
     Fact("f", "trigger_c", "yes"),
     Fact("f", "trigger_b_stub", "yes"),
 ]
+
 SEED_Q04D = [
     Fact("f", "kind", "function"),
     Fact("f", "trigger_d", "yes"),
     Fact("f", "trigger_b_stub", "yes"),
 ]
+
+
 def run_q04a():
     return _classify_and_debug("Q04a: utility (prio 1) retratada por factory (prio 20)",
                                src=SRC_Q04A)
+
+
 def run_q04b():
     return _classify_and_debug("Q04b: utility sozinha (sem factory)",
                                src=SRC_Q04B)
+
+
 def run_q04c():
     return _classify_and_debug("Q04c: tie prio 10=10, cross-cycle",
                                seed=SEED_Q04C)
+
+
 def run_q04d():
     return _classify_and_debug("Q04d: higher fires cycle 1, lower cycle 2",
                                seed=SEED_Q04D)
+
+
 def run_q04e():
     t0 = time.perf_counter()
     outs = set()
@@ -524,6 +666,7 @@
             r = run_q04a()
             outs.add((r["pattern"], r["retractions"]))
     t_total = (time.perf_counter() - t0) * 1000
+
     if DEBUG:
         _dbg("--- Q04e: determinism (100 runs of Q04a) ---")
         _dbg(f"  runs: 100")
@@ -533,6 +676,8 @@
         _dbg(f"  time_per_run: {t_total/100:.3f}ms")
         _dbg("")
     return {"n": 100, "unique_count": len(outs), "values": outs}
+
+
 def _debug_aggregate(results):
     if not DEBUG:
         return
@@ -542,6 +687,7 @@
     total_retracted = sum(r["retractions"] for r in results)
     total_attempts = sum(r["metrics"]["rules_attempted"] for r in results)
     total_cycles = sum(r["cycles"] for r in results)
+
     _dbg("--- aggregate (4 classify calls) ---")
     _dbg(f"  functions: {n}")
     _dbg(f"  total_seed_facts: {total_seed}")
@@ -551,14 +697,21 @@
     _dbg(f"  total_cycles: {total_cycles}")
     _dbg(f"  avg_cycles: {total_cycles/n:.2f}")
     _dbg("")
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     if DEBUG:
         _dbg("=== engine_q04.py ===")
         _dbg("mode: debug")
         _dbg(f"args: {sys.argv}")
         _dbg("")
+
     lines: list[str] = []
     falhas: list[str] = []
+
     checks = [
         ("Q04a", "utility retratada por factory", run_q04a,
          {"pattern": "factory", "retractions": 1}),
@@ -569,6 +722,7 @@
         ("Q04d", "higher fires cycle 1, lower cycle 2", run_q04d,
          {"pattern": "high", "retractions": 0}),
     ]
+
     results_for_agg = []
     for label, desc, fn, expect in checks:
         r = fn()
@@ -590,6 +744,7 @@
                 falhas.append(
                     f"{label}: {k}={r[k]!r}, esperado {v!r}"
                 )
+
     lines.append("=== Q04e: determinism (100 runs of Q04a) ===")
     e = run_q04e()
     lines.append(f"n:            {e['n']}")
@@ -597,7 +752,9 @@
     lines.append("")
     if e["unique_count"] != 1:
         falhas.append(f"Q04e: {e['unique_count']} variacoes")
+
     _debug_aggregate(results_for_agg)
+
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -610,8 +767,10 @@
         resultado = 0
         if DEBUG:
             _dbg("=== done: all checks passed ===")
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -619,6 +778,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/code_classification/poc/q05_smell/README.md
  xml=78 linhas | disco=96 linhas
--- XML:doxoade/research/code_classification/poc/q05_smell/README.md
+++ DISCO:doxoade/research/code_classification/poc/q05_smell/README.md
@@ -1,27 +1,35 @@
+# Q05 - Code smell detection (DC2, domain expansion)
 
-# Q05 - Code smell detection (DC2, domain expansion)
 **Contrato:** DC2 (Classification) com 5 dimensoes.
 **NAO faz upgrade de engine.** Q04 kernel inlined sem mudanca.
+
 ## Por que Q05 nao mexe no engine
+
 Q04 fechou a lacuna tecnica real (retraction cross-cycle). Q05 testa
 o engine em cenario real, sem expandir. Isso valida **Plan B** da
 ProDeNov 1.2.1: quando feature pode ser expressada com o vocabulario
 existente, nao se adiciona feature ao engine.
+
 Q05 explora **retraction em contexto real**: aggregate default
 `has_any_smell=none` (prio 1, NAF) e retratado por specific
 `has_any_smell=dirty` (prio 20) quando qualquer smell_* aparece.
+
 ## Smells declarados
+
 | Smell | Condicao | Regra | Escopo |
 |---|---|---|---|
 | `magic_number` | Constant int ∉ {0,1,-1} em `Compare.comparators` | R_magic | Apenas Compare |
 | `long_method` | `body_len >= 4` (apos docstring) | R_long | Threshold 4 |
 | `dead_code` | `Return` no body-level seguido por outro stmt | R_dead | Body-level apenas |
+
 **Nao detecta** (fora do escopo Q05):
 - Magic em `Assign`/`If`/`BinOp` (so `Compare`)
 - Dead nested (Return dentro de `If`)
 - Long method com threshold diferente de 4
 - Smells estilo OO (god class, feature envy)
+
 ## Estrutura de derivacao
+
 ```
 seed:      has_magic_number, long_body, dead_after_return
             (extracted, prio 0 = seed)
@@ -35,11 +43,15 @@
   R_dirty_long  → has_any_smell=dirty  (prio 20, idempotente)
   R_dirty_dead  → has_any_smell=dirty  (prio 20, idempotente)
 ```
+
 Smells sao **ortogonais** — predicados distintos (`smell_magic_number`
 vs `smell_long_method` vs `smell_dead_code`). Coexistem sem colisao.
+
 Aggregate `has_any_smell` e **single-valued** — `none` ou `dirty`.
 Retraction de Q04 atua aqui: `none` sai quando `dirty` entra.
+
 ## O que Q05 prova
+
 1. **Domain expansion sem engine upgrade.** Q04 kernel inlined,
    nenhuma linha alterada.
 2. **Retraction em contexto real.** Nao mais artificial como Q04a
@@ -50,7 +62,9 @@
 4. **Smells ortogonais nao colidem.** Q05e tem 3 smells simultaneos
    sem conflito — predicados distintos.
 5. **Clean nao dispara retraction** (Q05a, retr=0).
+
 ## Err table (ProDeNov 5.4)
+
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
 | `has_magic_number` em Assign falso positivo | nula (check so Compare) | critico | funcao `_has_magic_number` restrita |
@@ -58,7 +72,9 @@
 | 3 smells colidirem | nula | critico | predicados ortogonais |
 | `has_any_smell=none` nao retratado | baixa | critico | Q05b/c/d/e verificam retr=1 |
 | Clean retrata por engano | baixa | alto | Q05a verifica retr=0 |
+
 ## Planos A / B / C
+
 - **A (implementado):** 3 smells com predicados ortogonais, aggregate
   `has_any_smell` single-valued via retraction.
 - **B (se Q06 precisar de smells OO):** schema de fato enriquecido
@@ -66,13 +82,15 @@
   ponderada.
 - **C (se smells precisarem de multiplas dimensoes de threshold):**
   bucket como Q02 (`smell_long_severity=mild|moderate|severe`).
+
 ## Licao
+
 **Domain expansion sem feature de engine.** Q04 fechou o gap tecnico.
 Q05 nao precisou adicionar nada — a combinacao de retraction (Q04) +
 NAF (P21) + prioridade (P02) + ortogonalidade de predicados resolve
 "clean vs dirty" naturalmente.
+
 **Retraction deixa de ser artificial.** Q04 exercitou retraction com
 rules stub (Q04a-c-d). Q05 usa retraction em cenario onde ela tem
 proposito real: default `none` precisa sair quando specifics aparecem.
 Se Q05 falhasse aqui, Q04 nao serviria para aplicacoes reais.
-      

■ doxoade/research/code_classification/poc/q05_smell/engine_q05.py
  xml=548 linhas | disco=709 linhas
--- XML:doxoade/research/code_classification/poc/q05_smell/engine_q05.py
+++ DISCO:doxoade/research/code_classification/poc/q05_smell/engine_q05.py
@@ -1,14 +1,50 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/code_classification/poc/q05_smell/engine_q05.py
+"""
+Q05 - Code smell detection as 5th dim (DC2, domain expansion).
+
+Contrato: DC2 (Classification) com 5 dimensoes.
+    category, has_docstring, complexity, pattern (herdados de Q04)
+    + has_any_smell (derivado, aggregate com retracao)
+
+NAO faz upgrade de engine. Q04 kernel inlined (retraction-aware).
+Q05 testa Q04 retraction em cenario real: aggregate default
+"has_any_smell=none" (prio 1, NAF) retratado por "has_any_smell=dirty"
+(prio 20) quando qualquer smell_* aparece.
+
+Smells (ortogonais, predicados distintos):
+    smell_magic_number : Constant int nao-trivial em Compare
+    smell_long_method  : body_len >= 4 (apos docstring)
+    smell_dead_code    : Return no body-level seguido por stmt
+
+NAO detecta (fora de escopo Q05):
+    - Magic em Assign/If/BinOp (so Compare)
+    - Dead nested (Return dentro de If)
+    - Long method com threshold != 4
+    - Smells estilo-oriented (god class, feature envy)
+
+Q05a - clean                          -> has_any_smell=none, retr=0
+Q05b - magic (x > 42)                 -> smell_magic_number=yes, dirty, retr=1
+Q05c - long body (4 stmts)            -> smell_long_method=yes, dirty, retr=1
+Q05d - dead (return x; print)         -> smell_dead_code=yes, dirty, retr=1
+Q05e - 3 smells coexistem             -> 3 smells, dirty (retr=1)
+Q05f - determinism (100 runs de Q05b)
+
+Rodar: doxoade retro-forward run q05
+"""
 from __future__ import annotations
+
 import ast
 import dataclasses
 import logging
 import sys
 import time
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
 DEBUG = "--debug" in sys.argv
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc_q05")
     if logger.handlers:
@@ -18,7 +54,11 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class _Quiet:
     __slots__ = ("level",)
     def __init__(self) -> None:
@@ -28,17 +68,30 @@
         return self
     def __exit__(self, *exc):
         self.level -= 1
+
+
 QUIET = _Quiet()
+
+
 def _dbg(*parts) -> None:
     if DEBUG and QUIET.level == 0:
         print("[DEBUG]", *parts, file=sys.stderr)
+
+
 class UnsupportedNodeError(RuntimeError):
     pass
+
+
+# ============================================================
+# Kernel (Q04 inlined, unchanged)
+# ============================================================
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 class _Wild:
     _instance = None
     def __new__(cls):
@@ -47,9 +100,13 @@
         return cls._instance
     def __repr__(self) -> str:
         return "_"
+
+
 WILD = _Wild()
 Term = str | Var | _Wild
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class Fact:
     s: str
@@ -59,8 +116,11 @@
     rule_id: str | None = None
     cycle: int = 0
     priority: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -68,6 +128,7 @@
     conclusion: Pattern
     negations: tuple[Pattern, ...] = ()
     priority: int = 0
+
     def conclusion_fact(self, bindings, cycle):
         r = substitute(self.conclusion, bindings)
         if r is None:
@@ -75,6 +136,8 @@
         s, p, o = r
         return Fact(s, p, o, source="derived",
                     rule_id=self.id, cycle=cycle, priority=self.priority)
+
+
 def unify_term(pattern, value, bindings):
     if isinstance(pattern, _Wild):
         return bindings
@@ -83,6 +146,8 @@
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern, fact_triple, bindings):
     b = bindings
     for p_t, f_v in zip(pattern, fact_triple):
@@ -90,6 +155,8 @@
         if b is None:
             return None
     return b
+
+
 def substitute(pattern, bindings):
     out = []
     for t in pattern:
@@ -102,8 +169,11 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_with_negations(conditions, negations, live_facts):
     results = []
+
     def recurse(conds, binds, wit):
         if not conds:
             for neg in negations:
@@ -119,8 +189,11 @@
             if b is None:
                 continue
             recurse(rest, b, wit + [f.to_tuple()])
+
     recurse(conditions, {}, [])
     return results
+
+
 class Engine:
     def __init__(self, max_cycles=100):
         self.max_cycles = max_cycles
@@ -132,6 +205,7 @@
         self.rules_attempted = 0
         self.rule_attempts: dict[str, int] = {}
         self.cycle_history: list[dict] = []
+
     def run(self, initial_facts, rules):
         facts = list(initial_facts)
         ordered = sorted(rules, key=lambda r: -r.priority)
@@ -145,6 +219,7 @@
                 "cycle": cycles, "matches": {}, "idempotent": [],
                 "candidates": [], "winners": [], "shadowed": [], "retracted": [],
             }
+
             for rule in ordered:
                 matches = match_with_negations(
                     rule.conditions, rule.negations, live_facts
@@ -165,6 +240,7 @@
                     cycle_info["candidates"].append(
                         (rule.id, rule.priority, cf.to_tuple())
                     )
+
             winners = {}
             for rule, cf, wit in candidates:
                 key = (cf.s, cf.p)
@@ -179,6 +255,7 @@
                 else:
                     cycle_info["shadowed"].append((rule.id, cf.to_tuple()))
                     self.shadowed.append((rule.id, cf.to_tuple()))
+
             for (s, p), (rule, cf, wit) in winners.items():
                 to_retract = []
                 shadow_new = False
@@ -195,10 +272,12 @@
                     else:
                         shadow_new = True
                         break
+
                 if shadow_new:
                     cycle_info["shadowed"].append((rule.id, cf.to_tuple()))
                     self.shadowed.append((rule.id, cf.to_tuple()))
                     continue
+
                 for ef in to_retract:
                     self.retracted.add(ef.to_tuple())
                     self.retracted_history.append({
@@ -208,20 +287,29 @@
                     cycle_info["retracted"].append(
                         (ef.rule_id, ef.to_tuple(), rule.id)
                     )
+
                 facts.append(cf)
                 self.trace.append({
                     "cycle": cycles, "rule_id": rule.id,
                     "fact": cf.to_tuple(), "derived_from": wit,
                 })
                 cycle_info["winners"].append((rule.id, rule.priority, cf.to_tuple()))
+
             self.cycle_history.append(cycle_info)
             if not cycle_info["winners"]:
                 self.cycles_used = cycles
                 return facts, cycles
         raise RuntimeError(f"max_cycles={self.max_cycles}")
+
+
+# ============================================================
+# DC1 - AST -> facts
+# ============================================================
 BRANCH_NODE_TYPES = (
     ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler,
 )
+
+
 def _count_branches(body):
     count = 0
     for node in body:
@@ -229,6 +317,8 @@
             if isinstance(sub, BRANCH_NODE_TYPES):
                 count += 1
     return count
+
+
 def _name_prefix(name):
     if name.startswith("create_"):
         return "create"
@@ -237,7 +327,10 @@
     if name.startswith("is_"):
         return "is"
     return "other"
+
+
 def _has_magic_number(body):
+    """Constant int (nao 0, 1, -1, nao bool) em Compare.comparators."""
     for stmt in body:
         for sub in ast.walk(stmt):
             if isinstance(sub, ast.Compare):
@@ -248,13 +341,21 @@
                             and comp.value not in (0, 1, -1)):
                         return True
     return False
+
+
 def _is_long_body(body):
+    """body_len >= 4."""
     return len(body) >= 4
+
+
 def _has_dead_after_return(body):
+    """Return no body-level seguido por outro stmt (body-level only)."""
     for stmt in body[:-1]:
         if isinstance(stmt, ast.Return):
             return True
     return False
+
+
 def extract_facts(src: str) -> list[Fact]:
     tree = ast.parse(src)
     if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
@@ -266,6 +367,7 @@
     has_doc = ast.get_docstring(func) is not None
     body_stmts = func.body[1:] if has_doc else func.body
     branch_count = _count_branches(body_stmts)
+
     facts = [
         Fact(func.name, "kind", "function"),
         Fact(func.name, "name", func.name),
@@ -290,7 +392,13 @@
                 func.name, "return_expr_kind", type(first.value).__name__
             ))
     return facts
+
+
+# ============================================================
+# DC2 - Rules
+# ============================================================
 F = Var("F")
+
 CATEGORY_RULES = [
     Rule("R_arith",
          conditions=((F, "kind", "function"),
@@ -312,6 +420,7 @@
          negations=((F, "category", WILD),),
          conclusion=(F, "category", "unknown"), priority=1),
 ]
+
 COMPLEXITY_RULES = [
     Rule("R_c_1",
          conditions=((F, "branch_count", "0"),),
@@ -329,6 +438,8 @@
          conditions=((F, "branch_count_ge_4", "yes"),),
          conclusion=(F, "complexity", "4+"), priority=15),
 ]
+
+# Smell specifics (cycle 1, from seed)
 SMELL_RULES = [
     Rule("R_magic",
          conditions=((F, "has_magic_number", "yes"),),
@@ -340,12 +451,16 @@
          conditions=((F, "dead_after_return", "yes"),),
          conclusion=(F, "smell_dead_code", "yes"), priority=15),
 ]
+
+# Aggregate default (cycle 1, NAF all smell_*)
 CLEAN_RULE = Rule("R_clean",
     conditions=((F, "kind", "function"),),
     negations=((F, "smell_magic_number", WILD),
                (F, "smell_long_method", WILD),
                (F, "smell_dead_code", WILD)),
     conclusion=(F, "has_any_smell", "none"), priority=1)
+
+# Aggregate specific (cycle 2, from derived smell_*)
 DIRTY_RULES = [
     Rule("R_dirty_magic",
          conditions=((F, "smell_magic_number", "yes"),),
@@ -357,8 +472,14 @@
          conditions=((F, "smell_dead_code", "yes"),),
          conclusion=(F, "has_any_smell", "dirty"), priority=20),
 ]
+
 RULES = (CATEGORY_RULES + COMPLEXITY_RULES +
          SMELL_RULES + [CLEAN_RULE] + DIRTY_RULES)
+
+
+# ============================================================
+# classify + debug
+# ============================================================
 def _dbg_cycle(cycle_info):
     _dbg(f"  cycle {cycle_info['cycle']}:")
     m = cycle_info["matches"]
@@ -375,18 +496,24 @@
         _dbg(f"    RETRACTED: {ef_rid} -> {ef_pair} (by {by_rid})")
     if not cycle_info["winners"]:
         _dbg("    quiescence")
+
+
 def classify(src: str) -> dict:
     t0 = time.perf_counter()
     seed = extract_facts(src)
     t_extract = (time.perf_counter() - t0) * 1000
+
     t0 = time.perf_counter()
     eng = Engine()
     result_facts, cycles = eng.run(seed, RULES)
     t_infer = (time.perf_counter() - t0) * 1000
+
     live = [f for f in result_facts if f.to_tuple() not in eng.retracted]
+
     def live_val(pred):
         vals = sorted(f.o for f in live if f.p == pred)
         return vals[0] if vals else None
+
     return {
         "input": src,
         "category": live_val("category"),
@@ -407,9 +534,12 @@
             "t_infer_ms": t_infer,
         },
     }
+
+
 def _classify_and_debug(label, src):
     r = classify(src)
     m = r["metrics"]
+
     _dbg(f"--- {label} ---")
     _dbg(f"  input: {src!r}")
     _dbg(f"  seed: {len(m['seed'])} fatos in {m['t_extract_ms']:.3f}ms")
@@ -431,6 +561,11 @@
          f"infer={m['t_infer_ms']:.3f}ms")
     _dbg("")
     return r
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 SRC_Q05A = "def f(x): return x + 1"
 SRC_Q05B = "def f(x): return x > 42"
 SRC_Q05C = ("def f(x):\n"
@@ -440,16 +575,28 @@
 SRC_Q05E = ("def f(x):\n"
             "    a = 1\n    b = 2\n    if x > 42:\n"
             "        return x\n    return 0\n    print(x)")
+
+
 def run_q05a():
     return _classify_and_debug("Q05a: clean (return x+1)", SRC_Q05A)
+
+
 def run_q05b():
     return _classify_and_debug("Q05b: magic (x > 42)", SRC_Q05B)
+
+
 def run_q05c():
     return _classify_and_debug("Q05c: long body (4 stmts)", SRC_Q05C)
+
+
 def run_q05d():
     return _classify_and_debug("Q05d: dead (return x; print)", SRC_Q05D)
+
+
 def run_q05e():
     return _classify_and_debug("Q05e: 3 smells coexistem", SRC_Q05E)
+
+
 def run_q05f():
     t0 = time.perf_counter()
     outs = set()
@@ -459,6 +606,7 @@
             outs.add((r["has_any_smell"], r["smell_magic_number"],
                       r["retractions"]))
     t_total = (time.perf_counter() - t0) * 1000
+
     if DEBUG:
         _dbg("--- Q05f: determinism (100 runs of Q05b) ---")
         _dbg(f"  runs: 100")
@@ -468,14 +616,21 @@
         _dbg(f"  time_per_run: {t_total/100:.3f}ms")
         _dbg("")
     return {"n": 100, "unique_count": len(outs), "values": outs}
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     if DEBUG:
         _dbg("=== engine_q05.py ===")
         _dbg("mode: debug")
         _dbg(f"args: {sys.argv}")
         _dbg("")
+
     lines: list[str] = []
     falhas: list[str] = []
+
     checks = [
         ("Q05a", "clean", run_q05a,
          {"has_any_smell": "none", "retractions": 0,
@@ -495,6 +650,7 @@
           "smell_magic_number": "yes", "smell_long_method": "yes",
           "smell_dead_code": "yes"}),
     ]
+
     for label, desc, fn, expect in checks:
         r = fn()
         lines.append(f"=== {label} ===")
@@ -517,6 +673,7 @@
         for k, v in expect.items():
             if r[k] != v:
                 falhas.append(f"{label}: {k}={r[k]!r}, esperado {v!r}")
+
     lines.append("=== Q05f: determinism (100 runs of Q05b) ===")
     f = run_q05f()
     lines.append(f"n:            {f['n']}")
@@ -524,6 +681,7 @@
     lines.append("")
     if f["unique_count"] != 1:
         falhas.append(f"Q05f: {f['unique_count']} variacoes")
+
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -536,13 +694,16 @@
         resultado = 0
         if DEBUG:
             _dbg("=== done: all checks passed ===")
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/code_classification/poc/x01_ruletable/README.md
  xml=67 linhas | disco=88 linhas
--- XML:doxoade/research/code_classification/poc/x01_ruletable/README.md
+++ DISCO:doxoade/research/code_classification/poc/x01_ruletable/README.md
@@ -1,14 +1,19 @@
+# X01 — Rule Table por domain (probe)
 
-# X01 — Rule Table por domain (probe)
 **Pergunta:** tabling por `domain` preserva resultado?
+
 **Resposta (se PASS):** sim. `RuleTable` filtra rules por domain sem
 perder, mangle ou reordenar semanticamente. Engine continua o mesmo.
+
 ## Contexto
+
 Probe mínimo da arquitetura de tabelamento discutida em
 `BLITZPLAN_X00_RULETABLE.md`. **Não é X00.** X00 é o Source Auditor
 completo (que vem depois). X01 é pré-requisito: prova que a abstracao
 `RuleTable` não mente.
+
 ## Decisoes R1/R2/R3 (aplicadas)
+
 - **R1 Classificador separado** — `RuleTable` é módulo próprio.
   Classifica por `domain` (estático, explícito). Classificador dinâmico
   de contexto fica para X03+.
@@ -16,10 +21,13 @@
   vira YAML/JSON em X02+. Sem aprendizado automático ainda.
 - **R3 Fallback + log** — X01 não exercita fallback ainda (todo cenario
   tem rules aplicáveis). Fallback e chaos log ficam para X03.
+
 ## O que prova
+
 ### X01a — rules expostas == rules esperadas
 `table.domain_rules("programming")` retorna exatamente as 4 rules de
 `RULES_PROGRAMMING`. Prova que indexação não perde.
+
 ### X01b — run(raw) == run(tab)
 Mesmo seed, mesma engine, rules passadas por caminhos diferentes
 (lista direta vs. via `RuleTable`). Compara:
@@ -28,15 +36,21 @@
 - `retractions` (quantas retrações ocorreram)
 - `trace_len` (tamanho do trace)
 - `rules_attempted` (esforço total)
+
 Todos 5 idênticos. Prova que `RuleTable` é transparente.
+
 ### X01c — boundary enforced
 Programing run: `status=b_active`, sem `diagnostic`.
 Diagnosis run: `diagnostic=yes`, sem `status`, sem `b_flag`.
+
 Prova que domain filtration funciona: rules de outro domain **não** vazam.
+
 ### X01d — determinism
 100 runs de X01b. Mesmo `(identical, live_tuples, cycles, retractions)`
 todas as vezes.
+
 ## O que NAO prova
+
 - **Fallback** (o que acontece se domain não cobre cena). X03.
 - **Chaos log** (detecção de miss silenciosa). X03.
 - **Symptom index** (ativação por sintoma). X02.
@@ -44,7 +58,9 @@
   X02.
 - **Refino de rule** (prune, split, merge). X04.
 - **Performance** (tabela vale o custo?). X05.
+
 ## Err table (ProDeNov 5.4)
+
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
 | Rule em duas tabelas diverge | baixa | critico | fonte unica (`_rules: dict`), indices so guardam ids |
@@ -52,16 +68,21 @@
 | Boundary viola (domain vaza) | media | alto | X01c detecta |
 | Ordem de rules afeta resultado | baixa | alto | engine usa priority (stable sort) |
 | Determinismo quebra com retracao | baixa | critico | X01d (100 runs) |
+
 ## Tamanho
+
 - **Hoje:** ~480 L (kernel inline + RuleTable + sub-sondas).
 - **Pós-Q10 (consolidação):** ~80 L (kernel compartilhado via `lib/`).
+
 Tamanho alto é dívida conhecida do padrão "PoC independente". Não é bug.
+
 ## Licao (se PASS)
+
 `RuleTable` é uma **abstração fina** sobre `dict` — nada mágico. Sua
 viabilidade depende de:
 1. **Fonte única** (`_rules`) — sem duplicação.
 2. **Índices só de ids** — sem estado duplicado.
 3. **Sem reordenação** — engine já ordena por priority.
+
 Próximo teste real: **X02 (symptom index + multi-domain)** — mais
 desafiador porque duas chaves combinam.
-      

■ doxoade/research/code_classification/poc/x01_ruletable/engine_x01.py
  xml=408 linhas | disco=556 linhas
--- XML:doxoade/research/code_classification/poc/x01_ruletable/engine_x01.py
+++ DISCO:doxoade/research/code_classification/poc/x01_ruletable/engine_x01.py
@@ -1,13 +1,57 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/code_classification/poc/x01_ruletable/engine_x01.py
+"""
+X01 - Rule Table basico (domain index preserves result).
+
+Pergunta: tabling por `domain` preserva resultado?
+
+Teste:
+  X01a - rules_for("programming") expoe exatamente o ruleset esperado
+  X01b - run(raw) == run(via table, domain="programming") byte-a-byte
+  X01c - boundary: programming != diagnosis (stub isolado por domain)
+  X01d - determinism (100 runs de X01b)
+
+Kernel: Q04 inlined (retraction-aware). Sem modificacao.
+RuleTable: nova abstracao — filtro por domain preserva rules.
+
+Fixture:
+  seed: (f, kind, function), (f, has_signal, yes)
+
+Rules em domain="programming":
+  R_a         (prio 10): kind=function          -> a_flag=yes
+  R_b         (prio 15): has_signal=yes         -> b_flag=yes
+  R_default   (prio 1) : kind=function, NAF b_flag -> status=default
+  R_b_override(prio 20): b_flag=yes             -> status=b_active (retrai default)
+
+Stub em domain="diagnosis":
+  R_stub      (prio 10): kind=function          -> diagnostic=yes
+
+Cenario:
+  Cycle 1 (programming): R_a, R_b, R_default (via NAF). 3 winners.
+  Cycle 2: R_default bloqueada (NAF falha); R_b_override retrai default.
+  Cycle 3: quiescencia.
+  Final: a_flag, b_flag, status=b_active, default retratado.
+  Retractions: 1. Cycles: 3. Trace: 4.
+
+Cenario:
+  Cycle 1 (diagnosis): R_stub. 1 winner.
+  Cycle 2: quiescencia.
+  Final: diagnostic=yes. Retractions: 0. Cycles: 2. Trace: 1.
+
+Rodar: doxoade retro-forward run x01
+"""
 from __future__ import annotations
+
 import dataclasses
 import logging
 import sys
 import time
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
 DEBUG = "--debug" in sys.argv
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc_x01")
     if logger.handlers:
@@ -17,7 +61,11 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class _Quiet:
     __slots__ = ("level",)
     def __init__(self) -> None:
@@ -27,15 +75,26 @@
         return self
     def __exit__(self, *exc):
         self.level -= 1
+
+
 QUIET = _Quiet()
+
+
 def _dbg(*parts) -> None:
     if DEBUG and QUIET.level == 0:
         print("[DEBUG]", *parts, file=sys.stderr)
+
+
+# ============================================================
+# Kernel (Q04 inlined, unchanged)
+# ============================================================
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 class _Wild:
     _instance = None
     def __new__(cls):
@@ -44,9 +103,13 @@
         return cls._instance
     def __repr__(self) -> str:
         return "_"
+
+
 WILD = _Wild()
 Term = str | Var | _Wild
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class Fact:
     s: str
@@ -56,8 +119,11 @@
     rule_id: str | None = None
     cycle: int = 0
     priority: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -65,6 +131,7 @@
     conclusion: Pattern
     negations: tuple[Pattern, ...] = ()
     priority: int = 0
+
     def conclusion_fact(self, bindings, cycle):
         r = substitute(self.conclusion, bindings)
         if r is None:
@@ -72,6 +139,8 @@
         s, p, o = r
         return Fact(s, p, o, source="derived",
                     rule_id=self.id, cycle=cycle, priority=self.priority)
+
+
 def unify_term(pattern, value, bindings):
     if isinstance(pattern, _Wild):
         return bindings
@@ -80,6 +149,8 @@
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern, fact_triple, bindings):
     b = bindings
     for p_t, f_v in zip(pattern, fact_triple):
@@ -87,6 +158,8 @@
         if b is None:
             return None
     return b
+
+
 def substitute(pattern, bindings):
     out = []
     for t in pattern:
@@ -99,8 +172,11 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_with_negations(conditions, negations, live_facts):
     results = []
+
     def recurse(conds, binds, wit):
         if not conds:
             for neg in negations:
@@ -116,8 +192,11 @@
             if b is None:
                 continue
             recurse(rest, b, wit + [f.to_tuple()])
+
     recurse(conditions, {}, [])
     return results
+
+
 class Engine:
     def __init__(self, max_cycles=100):
         self.max_cycles = max_cycles
@@ -128,6 +207,7 @@
         self.cycles_used = 0
         self.rules_attempted = 0
         self.rule_attempts: dict[str, int] = {}
+
     def run(self, initial_facts, rules):
         facts = list(initial_facts)
         ordered = sorted(rules, key=lambda r: -r.priority)
@@ -152,6 +232,7 @@
                     if cf.to_tuple() in existing:
                         continue
                     candidates.append((rule, cf, wit))
+
             winners = {}
             for rule, cf, wit in candidates:
                 key = (cf.s, cf.p)
@@ -164,6 +245,7 @@
                     winners[key] = (rule, cf, wit)
                 else:
                     self.shadowed.append((rule.id, cf.to_tuple()))
+
             fired_this_cycle = False
             for (s, p), (rule, cf, wit) in winners.items():
                 to_retract = []
@@ -195,15 +277,34 @@
                     "fact": cf.to_tuple(),
                 })
                 fired_this_cycle = True
+
             if not fired_this_cycle:
                 self.cycles_used = cycles
                 return facts, cycles
         raise RuntimeError(f"max_cycles={self.max_cycles}")
+
+
+# ============================================================
+# RuleTable (novo em X01)
+# ============================================================
 class RuleTable:
+    """Index de regras por domain e symptom. Fonte unica de truth.
+
+    Layout:
+      rules: dict[rule_id, Rule]
+      domain_index: dict[domain, list[rule_id]]
+      symptom_index: dict[symptom, list[rule_id]]
+
+    rules_for(domain, symptoms) retorna rules de domain + rules de cada
+    symptom, dedup por rule_id. Ordem nao importa: engine ordena por
+    priority (stable sort).
+    """
+
     def __init__(self, rules, domain_index=None, symptom_index=None):
         self._rules = {r.id: r for r in rules}
         self._domain_index = domain_index or {}
         self._symptom_index = symptom_index or {}
+
     def rules_for(self, domain=None, symptoms=None) -> list[Rule]:
         ids = set()
         if domain and domain in self._domain_index:
@@ -212,12 +313,20 @@
             if s in self._symptom_index:
                 ids.update(self._symptom_index[s])
         return [self._rules[i] for i in ids if i in self._rules]
+
     def domain_rules(self, domain) -> list[Rule]:
         return [self._rules[i] for i in self._domain_index.get(domain, [])
                 if i in self._rules]
+
     def known_domains(self) -> list[str]:
         return sorted(self._domain_index.keys())
+
+
+# ============================================================
+# Fixture (rules Q05-style, reducao minima)
+# ============================================================
 F = Var("F")
+
 RULES_PROGRAMMING = [
     Rule("R_a",
          conditions=((F, "kind", "function"),),
@@ -237,16 +346,20 @@
          conclusion=(F, "status", "b_active"),
          priority=20),
 ]
+
 RULES_DIAGNOSIS = [
     Rule("R_stub",
          conditions=((F, "kind", "function"),),
          conclusion=(F, "diagnostic", "yes"),
          priority=10),
 ]
+
 SEED = [
     Fact("f", "kind", "function"),
     Fact("f", "has_signal", "yes"),
 ]
+
+
 def build_table():
     return RuleTable(
         rules=RULES_PROGRAMMING + RULES_DIAGNOSIS,
@@ -255,6 +368,11 @@
             "diagnosis": [r.id for r in RULES_DIAGNOSIS],
         },
     )
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 def _run_and_snapshot(rules, seed):
     eng = Engine()
     facts, cycles = eng.run(list(seed), rules)
@@ -267,12 +385,16 @@
         "trace_len": len(eng.trace),
         "rules_attempted": eng.rules_attempted,
     }
+
+
 def _has(live_tuples, s, p, o=None):
     for t in live_tuples:
         if t[0] == s and t[1] == p:
             if o is None or t[2] == o:
                 return True
     return False
+
+
 def run_x01a():
     table = build_table()
     programming_rules = table.domain_rules("programming")
@@ -283,6 +405,8 @@
         "raw_ids": raw_ids,
         "identical": prog_ids == raw_ids,
     }
+
+
 def run_x01b():
     raw = _run_and_snapshot(RULES_PROGRAMMING, SEED)
     table = build_table()
@@ -295,15 +419,19 @@
         and raw["rules_attempted"] == via["rules_attempted"]
     )
     return {"raw": raw, "tab": via, "identical": identical}
+
+
 def run_x01c():
     table = build_table()
     prog = _run_and_snapshot(table.rules_for(domain="programming"), SEED)
     diag = _run_and_snapshot(table.rules_for(domain="diagnosis"), SEED)
+
     prog_status_b_active = _has(prog["live_tuples"], "f", "status", "b_active")
     prog_has_diagnostic = _has(prog["live_tuples"], "f", "diagnostic")
     diag_has_diagnostic = _has(diag["live_tuples"], "f", "diagnostic", "yes")
     diag_has_status = _has(diag["live_tuples"], "f", "status")
     diag_has_b_flag = _has(diag["live_tuples"], "f", "b_flag")
+
     boundary_ok = (
         prog_status_b_active
         and diag_has_diagnostic
@@ -319,6 +447,8 @@
         "diag_has_b_flag": diag_has_b_flag,
         "boundary_ok": boundary_ok,
     }
+
+
 def run_x01d():
     t0 = time.perf_counter()
     outs = set()
@@ -333,14 +463,22 @@
     if DEBUG:
         _dbg(f"  X01d time_total: {t_total:.3f}ms")
     return {"n": 100, "unique_count": len(outs), "unique": outs}
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     if DEBUG:
         _dbg("=== engine_x01.py ===")
         _dbg("mode: debug")
         _dbg(f"args: {sys.argv}")
         _dbg("")
+
     lines: list[str] = []
     falhas: list[str] = []
+
+    # --- X01a ---
     lines.append("=== X01a: programming domain rules == raw rules ===")
     a = run_x01a()
     lines.append(f"programming_rules_ids: {a['programming_ids']}")
@@ -349,6 +487,8 @@
     lines.append("")
     if not a["identical"]:
         falhas.append("X01a: rule sets divergem")
+
+    # --- X01b ---
     lines.append("=== X01b: programming run == raw run ===")
     b = run_x01b()
     lines.append(f"identical:        {b['identical']}")
@@ -366,6 +506,8 @@
         falhas.append("X01b: raw e tab divergem")
     if b["raw"]["retractions"] != 1:
         falhas.append(f"X01b: esperado 1 retracao, veio {b['raw']['retractions']}")
+
+    # --- X01c ---
     lines.append("=== X01c: domain boundary enforced ===")
     c = run_x01c()
     lines.append("programming:")
@@ -379,6 +521,8 @@
     lines.append("")
     if not c["boundary_ok"]:
         falhas.append("X01c: boundary violado")
+
+    # --- X01d ---
     lines.append("=== X01d: determinism (100 runs of X01b) ===")
     d = run_x01d()
     lines.append(f"n:            {d['n']}")
@@ -386,6 +530,7 @@
     lines.append("")
     if d["unique_count"] != 1:
         falhas.append(f"X01d: {d['unique_count']} variacoes")
+
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -396,13 +541,16 @@
         lines.append("X01 PASS")
         LOG.info("X01 PASS")
         resultado = 0
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/00_fizzbuzz/README.md
  xml=130 linhas | disco=162 linhas
--- XML:doxoade/research/forward_chaining/poc/00_fizzbuzz/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/00_fizzbuzz/README.md
@@ -1,18 +1,21 @@
-
 # doxoade/research/forward_chaining/poc/00_fizzbuzz/README.md
 # P00 — FizzBuzz smoke test
+
 **Contrato:** C1 (Inferência). Prova que MATCH → SELECT → FIRE → quiescência
 **termina, deriva e rastreia** sobre 100 inputs com regras positivas apenas.
+
 ## O que prova
 - Terminação em quiescência (`fired_this_cycle = False` → break).
 - Derivação correta (`out` == oráculo em 100/100).
 - Rastreio (`trace` contém regra, condições, conclusão, ciclo).
 - Prioridades respeitadas na varredura (stable sort por `-priority`).
+
 ## O que NÃO prova (deixa para as próximas)
 - Ciclos reais → **P01** (`max_cycles` aqui é rede de segurança, não teste).
 - Conflito entre regras → **P02** (FizzBuzz particiona div3/div5; nunca há disputa).
 - Unificação / variáveis → **P20** (`out=X` copiaria `n` para `out`).
 - Negação como falha → **P21** (aqui usamos `div5=no`, não `NOT`).
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|
@@ -20,38 +23,50 @@
 | Regra dispara sem match | baixa | alto | `Rule.match` testada em teste de mesa |
 | Trace incompleto | baixa | médio | `trace` comparada a `expected.txt` |
 | `except` silencioso | nula | alto | todo ponto crítico loga em `logging.txt` |
+
 ## Plano A / B / C (ProDeNov 1.2.1)
 - **A (implementado):** varredura `sorted(-priority)` por ciclo, `out` idempotente.
 - **B (se não termina em `max_cycles`):** adicionar `_fired_signatures: set[(rule_id, frozenset(fact_pairs_used))]` e pular combinações já disparadas. É o que P01 formaliza.
 - **C (se B ainda falha):** bug no matcher → parar a escada, revisar `Rule.match`.
+
 ## Ciclo de vida
 Passa → anotar lição em `docs/research/poc_notes.md`, **descartar o código**.
 Nada migra para `src/`. O que sobrevive é `Fact` / `Rule` / `Engine.run(trace)`
 como **contrato C1**.
+
 ---
+
 # P01 — Terminação em ciclo e falha loud
+
 **Contrato:** C1 (Inferência) — extensão de P00.
+
 ## O que prova
+
 ### P01a — ciclo de regras quiesce via idempotência
 Seed `x=1`; regras `x→y→z→x`. R3 tenta derivar `x=1` no ciclo 1, mas
 o fato já existe. Idempotência + monotonicidade garantem quiescência
 em 2 ciclos, sem `CycleLimitError`.
+
 ### P01b — cadeia > `max_cycles` falha explicitamente
 6 regras em cadeia com `max_cycles=3`. O engine **não** para em silêncio:
 levanta `CycleLimitError` com contagem de trace. `logging.txt` registra
 o erro.
+
 ## O que NÃO prova (deixa para as próximas)
 - Conflito real entre regras → **P02** (aqui R1/R2/R3 nunca disputam).
 - Unificação → **P20** (`out=X` copiaria `n`).
 - Negação como falha → **P21** (não usada aqui).
+
 ## Mecanismo de terminação — declarado
 Duas condições garantem quiescência:
 1. **Monotonicidade:** `facts` só cresce, nunca remove.
 2. **Idempotência:** `if any(f.to_pair() == new_fact.to_pair())` skip.
+
 Essas duas juntas implicam: cada regra dispara no máximo `|conclusão|`
 vezes. Como o conjunto de conclusões é finito, o motor termina — a menos
 que `max_cycles` seja atingido por cadeia longa, caso em que P01b
 demonstra falha loud.
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|
@@ -59,54 +74,70 @@
 | `CycleLimitError` não levantado | baixa | alto | teste em `run_p01b` |
 | Trace incompleto | baixa | médio | `trace_len` verificado |
 | Loop com regra nova a cada ciclo | baixa | alto | fora do escopo de C1; exigiria unificação (P20) |
+
 ## Planos A / B / C
 - **A (implementado):** monotonicidade + idempotência.
 - **B (se B falha):** `_fired_signatures: set[(rule_id, frozenset(fact_pairs))]`
   — impede re-fire mesmo se P00 for relaxado.
 - **C (se A e B falham):** `max_cycles` muito baixo → investigar quantos
   ciclos são realmente necessários, não mascarar.
+
 ## Lição
 "Ciclo de regras" não causa loop porque o engine é **monotônico**. A falha
 loud (`CycleLimitError`) é o que importa: `max_cycles` não é uma rede de
 segurança silenciosa, é uma *condição de falha declarada*.
+
 ---
+
 # P01 — Terminação em ciclo e falha loud
+
 **Contrato:** C1 (Inferência), extensão de P00.
+
 ## Semântica de ciclo — DECLARADA
+
 Um **ciclo** é uma rodada de match sobre um **snapshot congelado** da
 memória de trabalho, seguida de fire dos novos fatos.
+
 Consequências:
 1. Regras do mesmo ciclo **não veem** fatos derivados por outras regras
    do mesmo ciclo.
 2. Ordem de iteração das regras é **irrelevante** para o resultado.
 3. Cadeias lineares `a0→a1→...→aN` exigem N ciclos.
 4. `max_cycles` conta **rodadas de match**, não disparos.
+
 Isso contrasta com a semântica "varredura contínua" (sem snapshot),
 na qual a cadeia propaga em 1 rodada. Essa escolha foi feita porque
 ordem de iteração em varredura contínua produz resultado **dependente
 de ordem** — o que é não-determinismo acidental.
+
 ## O que prova
+
 ### P01a — ciclo de regras quiesce via idempotência
 Seed `x=1`; R1: x→y, R2: y→z, R3: z→x.
 - Ciclo 1 dispara R1 (y=1).
 - Ciclo 2 dispara R2 (z=1).
 - Ciclo 3 tenta R3 (x=1), mas x=1 já existe → quiesce.
 Total: 3 ciclos, 2 entradas em trace.
+
 ### P01b — cadeia > `max_cycles` falha explicitamente
 Cadeia de 6 regras com `max_cycles=3`. Ciclos 1–3 disparam R_00, R_01, R_02
 e o limite corta antes da quiescência. `CycleLimitError` é levantado com
 mensagem explícita. Trace tem 3 entradas — o que foi derivado antes do erro.
+
 ## O que NÃO prova (deixa para as próximas)
 - Conflito real entre regras → **P02**.
 - Unificação → **P20**.
 - Negação como falha → **P21**.
+
 ## Mecanismo de terminação — declarado
 1. **Snapshot congelado:** match nunca depende de ordem.
 2. **Monotonicidade:** `facts` só cresce.
 3. **Idempotência:** `pair in existing or pair in seen_in_cycle` skip.
+
 Isso garante: cada regra dispara no máximo uma vez por fato; a memória
 cresce finitamente; a menos que `max_cycles` corte por cadeia longa
 (que é justamente o que P01b testa).
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|
@@ -114,12 +145,14 @@
 | `CycleLimitError` não levantado | baixa | alto | teste em `run_p01b` |
 | Ordem de iteração afetar resultado | nula | alto | snapshot elimina por construção |
 | Trace incompleto | baixa | médio | `trace_len` verificado |
+
 ## Planos A / B / C
 - **A (implementado):** snapshot + idempotência + monotonicidade.
 - **B (se B falha):** `fired_signatures: set[(rule_id, frozenset(fact_pairs))]`
   como cache extra. Custo: memória O(R × F). Só se A não bastar.
 - **C (se A e B falham):** `max_cycles` foi mal calibrado — investigar
   cadeia real, não mascarar.
+
 ## Lição (descoberta durante a sonda)
 A pergunta "o que é um ciclo?" **não é detalhe de implementação**. É a
 primeira decisão de contrato do motor. Sem snapshot, ordem importa; com
@@ -127,4 +160,3 @@
 semânticas porque suas cadeias eram curtas. P01b forçou a escolha.
 Foi preciso **reescrever o expected** depois de reconhecer a ambiguidade
 — o que é o comportamento correto quando o contrato não estava claro.
-      

■ doxoade/research/forward_chaining/poc/00_fizzbuzz/engine_p00.py
  xml=252 linhas | disco=336 linhas
--- XML:doxoade/research/forward_chaining/poc/00_fizzbuzz/engine_p00.py
+++ DISCO:doxoade/research/forward_chaining/poc/00_fizzbuzz/engine_p00.py
@@ -1,13 +1,26 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/00_fizzbuzz/engine_p00.py
+"""
+P00 - FizzBuzz (C1) com debug estruturado.
+
+Debug:
+    py engine_p00.py --debug
+    Emite [DEBUG] em stderr. stdout/output.txt inalterados.
+    Mostra: bulk aggregate (100 casos) + trace completo (n=15),
+    cycle-by-cycle, timing.
+"""
 from __future__ import annotations
+
 import dataclasses
 import logging
 import sys
 import time
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
 DEBUG = "--debug" in sys.argv
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc00")
     if logger.handlers:
@@ -17,12 +30,20 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 def _dbg(*parts) -> None:
     if DEBUG:
         print("[DEBUG]", *parts, file=sys.stderr)
+
+
 class CycleLimitError(RuntimeError):
-    pass
+    """Motor nao atingiu quiescencia dentro de max_cycles."""
+
+
 @dataclasses.dataclass(frozen=True)
 class Fact:
     key: str
@@ -30,8 +51,11 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_pair(self) -> tuple[str, str]:
         return (self.key, self.value)
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -39,13 +63,26 @@
     conclusion: tuple[str, str]
     priority: int = 0
     description: str = ""
+
     def match(self, facts: list[Fact]) -> bool:
         pairs = {f.to_pair() for f in facts}
         return all(c in pairs for c in self.conditions)
+
     def conclusion_fact(self, cycle: int) -> Fact:
         k, v = self.conclusion
         return Fact(k, v, source="derived", rule_id=self.id, cycle=cycle)
+
+
 class ForwardChainingEngine:
+    """
+    Varredura continua (semantica A: sem snapshot).
+
+    Cada ciclo varre regras em ordem decrescente de prioridade. Fatos
+    derivados durante o ciclo ficam visiveis para regras seguintes.
+    Para FizzBuzz (trigger exclusivo), A e B sao equivalentes.
+    P01+ usam B (snapshot).
+    """
+
     def __init__(self, max_cycles: int = 100):
         self.max_cycles = max_cycles
         self.trace: list[dict] = []
@@ -53,6 +90,7 @@
         self.rules_attempted = 0
         self.rule_attempts: dict[str, int] = {}
         self.cycle_history: list[dict] = []
+
     def run(self, initial_facts: list[Fact], rules: list[Rule]) -> list[Fact]:
         facts = list(initial_facts)
         ordered = sorted(rules, key=lambda r: -r.priority)
@@ -67,18 +105,22 @@
                 "idempotent": [],
                 "quiescence": False,
             }
+
             for rule in ordered:
                 self.rules_attempted += 1
                 self.rule_attempts[rule.id] = self.rule_attempts.get(rule.id, 0) + 1
+
                 if not rule.match(facts):
                     cycle_info["matches"][rule.id] = False
                     continue
                 cycle_info["matches"][rule.id] = True
+
                 new_fact = rule.conclusion_fact(cycle=cycles)
                 pair = new_fact.to_pair()
                 if any(f.to_pair() == pair for f in facts):
                     cycle_info["idempotent"].append((rule.id, pair))
                     continue
+
                 cycle_info["candidates"].append((rule.id, rule.priority, pair))
                 facts.append(new_fact)
                 self.trace.append({
@@ -88,13 +130,18 @@
                     "conclusion": pair,
                 })
                 fired_this_cycle = True
+
             if not fired_this_cycle:
                 cycle_info["quiescence"] = True
                 self.cycle_history.append(cycle_info)
                 self.cycles_used = cycles
                 return facts
+
             self.cycle_history.append(cycle_info)
+
         raise CycleLimitError(f"max_cycles={self.max_cycles} sem quiescencia")
+
+
 RULES: list[Rule] = [
     Rule("R_fizzbuzz",
          conditions=(("div3", "yes"), ("div5", "yes")),
@@ -109,20 +156,28 @@
          conclusion=("out", "buzz"),
          priority=20),
 ]
+
+
 def facts_for(n: int) -> list[Fact]:
     return [
         Fact("div3", "yes" if n % 3 == 0 else "no"),
         Fact("div5", "yes" if n % 5 == 0 else "no"),
     ]
+
+
 def solve_with_engine(n: int) -> tuple[str, ForwardChainingEngine]:
     engine = ForwardChainingEngine()
     facts = engine.run(facts_for(n), RULES)
     outs = [f for f in facts if f.key == "out"]
     result = outs[0].value if outs else str(n)
     return result, engine
+
+
 def solve(n: int) -> str:
     result, _ = solve_with_engine(n)
     return result
+
+
 def reference(n: int) -> str:
     if n % 15 == 0:
         return "fizzbuzz"
@@ -131,6 +186,8 @@
     if n % 5 == 0:
         return "buzz"
     return str(n)
+
+
 def _dbg_cycle_p00(cycle_info: dict) -> None:
     _dbg(f"  cycle {cycle_info['cycle']}:")
     m = cycle_info["matches"]
@@ -141,26 +198,34 @@
         _dbg(f"    idempotent: {rid} -> {fact}")
     if cycle_info["quiescence"]:
         _dbg("    quiescence")
+
+
 def _debug_bulk_aggregate(bulk_metrics: list[dict], t_total: float) -> None:
     _dbg("--- bulk: 100 FizzBuzz ---")
     _dbg("  n: 100")
     _dbg("  oracle_matches: 100/100")
+
     hist: dict[int, int] = {}
     for m in bulk_metrics:
         hist[m["cycles"]] = hist.get(m["cycles"], 0) + 1
     _dbg(f"  cycles_histogram: {dict(sorted(hist.items()))}")
+
     total_attempts = sum(m["rules_attempted"] for m in bulk_metrics)
     max_attempts = max(m["rules_attempted"] for m in bulk_metrics)
     _dbg(f"  rules_attempted_total: {total_attempts}")
     _dbg(f"  rules_attempted_max_per_n: {max_attempts}")
+
     per_rule: dict[str, int] = {}
     for m in bulk_metrics:
         for rid, cnt in m["rule_attempts"].items():
             per_rule[rid] = per_rule.get(rid, 0) + cnt
     _dbg("  per_rule_attempts: " + " ".join(f"{k}={v}" for k, v in sorted(per_rule.items())))
+
     _dbg(f"  time_total: {t_total:.3f}ms")
     _dbg(f"  time_per_n_avg: {t_total/100:.3f}ms")
     _dbg("")
+
+
 def main() -> int:
     if DEBUG:
         _dbg("=== engine_p00.py ===")
@@ -168,6 +233,8 @@
         _dbg("engine_semantics: A (continuous scan, no snapshot)")
         _dbg(f"args: {sys.argv}")
         _dbg("")
+
+    # Bulk 100 FizzBuzz
     t_bulk_start = time.perf_counter()
     answers: list[str] = []
     bulk_metrics: list[dict] = []
@@ -185,6 +252,7 @@
                 "rule_attempts": dict(engine.rule_attempts),
             })
     t_bulk = (time.perf_counter() - t_bulk_start) * 1000
+
     refs = [reference(n) for n in range(1, 101)]
     if answers != refs:
         mismatches = [
@@ -197,12 +265,16 @@
             print(f"  n={n}: motor={a!r} oraculo={r!r}", file=sys.stderr)
         LOG.error("divergencia do oraculo: %d casos", len(mismatches))
         return 1
+
     if DEBUG:
         _debug_bulk_aggregate(bulk_metrics, t_bulk)
+
+    # Trace case
     t0 = time.perf_counter()
     engine = ForwardChainingEngine()
     engine.run(facts_for(15), RULES)
     t_trace = (time.perf_counter() - t0) * 1000
+
     if DEBUG:
         _dbg("--- trace case: n=15 ---")
         seed = facts_for(15)
@@ -212,8 +284,11 @@
         _dbg(f"  trace_len: {len(engine.trace)}")
         _dbg(f"  timing: {t_trace:.3f}ms")
         _dbg("")
+
+    # Output canonico
     lines: list[str] = ["=== FIZZBUZZ 1..100 ==="]
     lines.extend(answers)
+
     lines.append("=== TRACE n=15 ===")
     for step in engine.trace:
         conds = ", ".join(f"{k}={v}" for k, v in step["conditions"])
@@ -222,19 +297,24 @@
             f"ciclo {step['cycle']}: {step['rule_id']} "
             f"[{conds}] -> {k}={v}"
         )
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
         encoding="utf-8",
         newline="\n",
     )
+
     if DEBUG:
         _dbg("=== done: all checks passed ===")
     LOG.info("P00 PASS: 100/100")
     return 0
+
 class _Quiet:
+    """Context manager que suspende _dbg durante execucoes em massa."""
     __slots__ = ("level",)
     def __init__(self) -> None:
         self.level = 0
@@ -243,10 +323,14 @@
         return self
     def __exit__(self, *exc):
         self.level -= 1
+
+
 QUIET = _Quiet()
+
+
 def _dbg(*parts) -> None:
     if DEBUG and QUIET.level == 0:
         print("[DEBUG]", *parts, file=sys.stderr)
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/01_cycle/README.md
  xml=164 linhas | disco=209 linhas
--- XML:doxoade/research/forward_chaining/poc/01_cycle/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/01_cycle/README.md
@@ -1,18 +1,21 @@
-
 # doxoade/research/forward_chaining/poc/00_fizzbuzz/README.md
 # P00 — FizzBuzz smoke test
+
 **Contrato:** C1 (Inferência). Prova que MATCH → SELECT → FIRE → quiescência
 **termina, deriva e rastreia** sobre 100 inputs com regras positivas apenas.
+
 ## O que prova
 - Terminação em quiescência (`fired_this_cycle = False` → break).
 - Derivação correta (`out` == oráculo em 100/100).
 - Rastreio (`trace` contém regra, condições, conclusão, ciclo).
 - Prioridades respeitadas na varredura (stable sort por `-priority`).
+
 ## O que NÃO prova (deixa para as próximas)
 - Ciclos reais → **P01** (`max_cycles` aqui é rede de segurança, não teste).
 - Conflito entre regras → **P02** (FizzBuzz particiona div3/div5; nunca há disputa).
 - Unificação / variáveis → **P20** (`out=X` copiaria `n` para `out`).
 - Negação como falha → **P21** (aqui usamos `div5=no`, não `NOT`).
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|
@@ -20,38 +23,50 @@
 | Regra dispara sem match | baixa | alto | `Rule.match` testada em teste de mesa |
 | Trace incompleto | baixa | médio | `trace` comparada a `expected.txt` |
 | `except` silencioso | nula | alto | todo ponto crítico loga em `logging.txt` |
+
 ## Plano A / B / C (ProDeNov 1.2.1)
 - **A (implementado):** varredura `sorted(-priority)` por ciclo, `out` idempotente.
 - **B (se não termina em `max_cycles`):** adicionar `_fired_signatures: set[(rule_id, frozenset(fact_pairs_used))]` e pular combinações já disparadas. É o que P01 formaliza.
 - **C (se B ainda falha):** bug no matcher → parar a escada, revisar `Rule.match`.
+
 ## Ciclo de vida
 Passa → anotar lição em `docs/research/poc_notes.md`, **descartar o código**.
 Nada migra para `src/`. O que sobrevive é `Fact` / `Rule` / `Engine.run(trace)`
 como **contrato C1**.
----
+
+---
+
 # P01 — Terminação em ciclo e falha loud
+
 **Contrato:** C1 (Inferência) — extensão de P00.
-## O que prova
+
+## O que prova
+
 ### P01a — ciclo de regras quiesce via idempotência
 Seed `x=1`; regras `x→y→z→x`. R3 tenta derivar `x=1` no ciclo 1, mas
 o fato já existe. Idempotência + monotonicidade garantem quiescência
 em 2 ciclos, sem `CycleLimitError`.
+
 ### P01b — cadeia > `max_cycles` falha explicitamente
 6 regras em cadeia com `max_cycles=3`. O engine **não** para em silêncio:
 levanta `CycleLimitError` com contagem de trace. `logging.txt` registra
 o erro.
+
 ## O que NÃO prova (deixa para as próximas)
 - Conflito real entre regras → **P02** (aqui R1/R2/R3 nunca disputam).
 - Unificação → **P20** (`out=X` copiaria `n`).
 - Negação como falha → **P21** (não usada aqui).
+
 ## Mecanismo de terminação — declarado
 Duas condições garantem quiescência:
 1. **Monotonicidade:** `facts` só cresce, nunca remove.
 2. **Idempotência:** `if any(f.to_pair() == new_fact.to_pair())` skip.
+
 Essas duas juntas implicam: cada regra dispara no máximo `|conclusão|`
 vezes. Como o conjunto de conclusões é finito, o motor termina — a menos
 que `max_cycles` seja atingido por cadeia longa, caso em que P01b
 demonstra falha loud.
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|
@@ -59,54 +74,70 @@
 | `CycleLimitError` não levantado | baixa | alto | teste em `run_p01b` |
 | Trace incompleto | baixa | médio | `trace_len` verificado |
 | Loop com regra nova a cada ciclo | baixa | alto | fora do escopo de C1; exigiria unificação (P20) |
+
 ## Planos A / B / C
 - **A (implementado):** monotonicidade + idempotência.
 - **B (se B falha):** `_fired_signatures: set[(rule_id, frozenset(fact_pairs))]`
   — impede re-fire mesmo se P00 for relaxado.
 - **C (se A e B falham):** `max_cycles` muito baixo → investigar quantos
   ciclos são realmente necessários, não mascarar.
+
 ## Lição
 "Ciclo de regras" não causa loop porque o engine é **monotônico**. A falha
 loud (`CycleLimitError`) é o que importa: `max_cycles` não é uma rede de
 segurança silenciosa, é uma *condição de falha declarada*.
----
+
+---
+
 # P01 — Terminação em ciclo e falha loud
+
 **Contrato:** C1 (Inferência), extensão de P00.
+
 ## Semântica de ciclo — DECLARADA
+
 Um **ciclo** é uma rodada de match sobre um **snapshot congelado** da
 memória de trabalho, seguida de fire dos novos fatos.
+
 Consequências:
 1. Regras do mesmo ciclo **não veem** fatos derivados por outras regras
    do mesmo ciclo.
 2. Ordem de iteração das regras é **irrelevante** para o resultado.
 3. Cadeias lineares `a0→a1→...→aN` exigem N ciclos.
 4. `max_cycles` conta **rodadas de match**, não disparos.
+
 Isso contrasta com a semântica "varredura contínua" (sem snapshot),
 na qual a cadeia propaga em 1 rodada. Essa escolha foi feita porque
 ordem de iteração em varredura contínua produz resultado **dependente
 de ordem** — o que é não-determinismo acidental.
-## O que prova
+
+## O que prova
+
 ### P01a — ciclo de regras quiesce via idempotência
 Seed `x=1`; R1: x→y, R2: y→z, R3: z→x.
 - Ciclo 1 dispara R1 (y=1).
 - Ciclo 2 dispara R2 (z=1).
 - Ciclo 3 tenta R3 (x=1), mas x=1 já existe → quiesce.
 Total: 3 ciclos, 2 entradas em trace.
+
 ### P01b — cadeia > `max_cycles` falha explicitamente
 Cadeia de 6 regras com `max_cycles=3`. Ciclos 1–3 disparam R_00, R_01, R_02
 e o limite corta antes da quiescência. `CycleLimitError` é levantado com
 mensagem explícita. Trace tem 3 entradas — o que foi derivado antes do erro.
+
 ## O que NÃO prova (deixa para as próximas)
 - Conflito real entre regras → **P02**.
 - Unificação → **P20**.
 - Negação como falha → **P21**.
+
 ## Mecanismo de terminação — declarado
 1. **Snapshot congelado:** match nunca depende de ordem.
 2. **Monotonicidade:** `facts` só cresce.
 3. **Idempotência:** `pair in existing or pair in seen_in_cycle` skip.
+
 Isso garante: cada regra dispara no máximo uma vez por fato; a memória
 cresce finitamente; a menos que `max_cycles` corte por cadeia longa
 (que é justamente o que P01b testa).
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|
@@ -114,12 +145,14 @@
 | `CycleLimitError` não levantado | baixa | alto | teste em `run_p01b` |
 | Ordem de iteração afetar resultado | nula | alto | snapshot elimina por construção |
 | Trace incompleto | baixa | médio | `trace_len` verificado |
+
 ## Planos A / B / C
 - **A (implementado):** snapshot + idempotência + monotonicidade.
 - **B (se B falha):** `fired_signatures: set[(rule_id, frozenset(fact_pairs))]`
   como cache extra. Custo: memória O(R × F). Só se A não bastar.
 - **C (se A e B falham):** `max_cycles` foi mal calibrado — investigar
   cadeia real, não mascarar.
+
 ## Lição (descoberta durante a sonda)
 A pergunta "o que é um ciclo?" **não é detalhe de implementação**. É a
 primeira decisão de contrato do motor. Sem snapshot, ordem importa; com
@@ -127,38 +160,50 @@
 semânticas porque suas cadeias eram curtas. P01b forçou a escolha.
 Foi preciso **reescrever o expected** depois de reconhecer a ambiguidade
 — o que é o comportamento correto quando o contrato não estava claro.
----
+
+---
+
 # P01 - Terminacao em ciclo e falha loud
+
 **Contrato:** C1 (Inferencia) - extensao de P00.
+
 ## Semantica de ciclo - DECLARADA
+
 Um ciclo e uma rodada de match sobre SNAPSHOT congelado, seguida de fire.
 Regras do mesmo ciclo nao veem fatos derivados por outras regras do
 mesmo ciclo. Ordem de iteracao das regras e irrelevante para o resultado.
+
 Cadeias lineares `a0 -> a1 -> ... -> aN` exigem N ciclos.
 `max_cycles` conta rodadas de match, nao disparos.
-## O que prova
+
+## O que prova
+
 ### P01a - ciclo de regras quiesce via idempotencia
 Seed `x=1`; R1: x->y, R2: y->z, R3: z->x.
 - Ciclo 1 dispara R1 (y=1).
 - Ciclo 2 dispara R2 (z=1).
 - Ciclo 3 tenta R3 (x=1), mas x=1 ja existe -> quiesce.
 Total: 3 ciclos, 2 entradas em trace.
+
 ### P01b - cadeia > max_cycles falha explicitamente
 Cadeia de 6 regras com `max_cycles=3`. Ciclos 1-3 disparam R_00, R_01,
 R_02 e o limite corta antes da quiescencia. `CycleLimitError` levantado
 com mensagem explicita. Trace tem 3 entradas - o que foi derivado antes
 do erro.
+
 ## O que NAO prova
 - Conflito entre regras -> P02.
 - Unificacao -> P20.
 - Negacao como falha -> P21.
+
 ## Mecanismo de terminacao - declarado
 1. Snapshot congelado: match nunca depende de ordem.
 2. Monotonicidade: `facts` so cresce.
 3. Idempotencia: `pair in existing or pair in seen_in_cycle` skip.
+
 ## Lição
 "Ciclo" e decisao de contrato, nao detalhe. Sem snapshot, ordem importa;
 com snapshot, ordem nao importa. P00 e P01a nao distinguiam as duas
 semanticas. P01b forcou a escolha.
----
-      
+
+---

■ doxoade/research/forward_chaining/poc/01_cycle/engine_p01.py
  xml=259 linhas | disco=352 linhas
--- XML:doxoade/research/forward_chaining/poc/01_cycle/engine_p01.py
+++ DISCO:doxoade/research/forward_chaining/poc/01_cycle/engine_p01.py
@@ -1,13 +1,31 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/01_cycle/engine_p01.py
+"""
+P01 - Terminacao em ciclos e falha explicita, com debug estruturado.
+
+Debug:
+    py engine_p01.py --debug
+    Emite [DEBUG] em stderr. stdout/output.txt inalterados.
+
+P01a - ciclo de regras quiesce via idempotencia.
+P01b - cadeia > max_cycles levanta CycleLimitError explicito.
+
+O debug mostra:
+- P01a: cycle-by-cycle (matches, candidates, idempotent, quiescence).
+- P01b: cycle-by-cycle ATE o limite, momento da falha, trace preservado.
+"""
 from __future__ import annotations
+
 import dataclasses
 import logging
 import sys
 import time
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
 DEBUG = "--debug" in sys.argv
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc01")
     if logger.handlers:
@@ -17,12 +35,20 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 def _dbg(*parts) -> None:
     if DEBUG:
         print("[DEBUG]", *parts, file=sys.stderr)
+
+
 class CycleLimitError(RuntimeError):
-    pass
+    """Motor nao atingiu quiescencia dentro de max_cycles."""
+
+
 @dataclasses.dataclass(frozen=True)
 class Fact:
     key: str
@@ -30,8 +56,11 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_pair(self) -> tuple[str, str]:
         return (self.key, self.value)
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -39,12 +68,23 @@
     conclusion: tuple[str, str]
     priority: int = 0
     description: str = ""
+
     def match(self, snapshot: frozenset[tuple[str, str]]) -> bool:
         return all(c in snapshot for c in self.conditions)
+
     def conclusion_fact(self, cycle: int) -> Fact:
         k, v = self.conclusion
         return Fact(k, v, source="derived", rule_id=self.id, cycle=cycle)
+
+
 class ForwardChainingEngine:
+    """
+    Snapshot por ciclo (semantica B estrita).
+
+    Ciclo = rodada de match sobre snapshot congelado + fire.
+    Cadeias lineares exigem N ciclos. max_cycles conta rodadas.
+    """
+
     def __init__(self, max_cycles: int = 100):
         self.max_cycles = max_cycles
         self.trace: list[dict] = []
@@ -53,6 +93,7 @@
         self.rules_attempted = 0
         self.rule_attempts: dict[str, int] = {}
         self.limit_reached = False
+
     def run(self, initial_facts: list[Fact], rules: list[Rule]) -> list[Fact]:
         facts: list[Fact] = list(initial_facts)
         ordered_rules = sorted(rules, key=lambda r: -r.priority)
@@ -65,6 +106,7 @@
             existing: set[tuple[str, str]] = set(snapshot)
             new_facts: list[Fact] = []
             seen_in_cycle: set[tuple[str, str]] = set()
+
             cycle_info = {
                 "cycle": cycles,
                 "matches": {},
@@ -72,26 +114,33 @@
                 "idempotent": [],
                 "quiescence": False,
             }
+
             for rule in ordered_rules:
                 self.rules_attempted += 1
                 self.rule_attempts[rule.id] = self.rule_attempts.get(rule.id, 0) + 1
+
                 matched = rule.match(snapshot)
                 cycle_info["matches"][rule.id] = matched
                 if not matched:
                     continue
+
                 new_fact = rule.conclusion_fact(cycle=cycles)
                 pair = new_fact.to_pair()
                 if pair in existing or pair in seen_in_cycle:
                     cycle_info["idempotent"].append((rule.id, pair))
                     continue
+
                 cycle_info["candidates"].append((rule.id, rule.priority, pair))
                 new_facts.append(new_fact)
                 seen_in_cycle.add(pair)
+
             self.cycle_history.append(cycle_info)
+
             if not new_facts:
                 cycle_info["quiescence"] = True
                 self.cycles_used = cycles
                 return facts
+
             for nf in new_facts:
                 facts.append(nf)
                 self.trace.append({
@@ -99,16 +148,24 @@
                     "rule_id": nf.rule_id,
                     "conclusion": nf.to_pair(),
                 })
+
         self.limit_reached = True
         raise CycleLimitError(
             f"max_cycles={self.max_cycles} sem quiescencia "
             f"(trace tem {len(self.trace)} entrada(s))"
         )
+
+
+# ============================================================
+# P01a - ciclo de regras
+# ============================================================
 RULES_P01A: list[Rule] = [
     Rule("R1", conditions=(("x", "1"),), conclusion=("y", "1")),
     Rule("R2", conditions=(("y", "1"),), conclusion=("z", "1")),
     Rule("R3", conditions=(("z", "1"),), conclusion=("x", "1")),
 ]
+
+
 def _dbg_cycle(cycle_info: dict) -> None:
     _dbg(f"  cycle {cycle_info['cycle']}:")
     matches_str = " ".join(
@@ -121,6 +178,8 @@
         _dbg(f"    idempotent: {rid} -> {fact}")
     if cycle_info["quiescence"]:
         _dbg("    quiescence")
+
+
 def run_p01a() -> dict:
     seed = [Fact("x", "1")]
     if DEBUG:
@@ -128,22 +187,30 @@
         _dbg(f"  seed_facts: {[f.to_pair() for f in seed]}")
         _dbg(f"  rules: {[r.id for r in RULES_P01A]} "
              f"(priorities: {[r.priority for r in RULES_P01A]})")
+
     t0 = time.perf_counter()
     engine = ForwardChainingEngine(max_cycles=10)
     facts = engine.run(seed, RULES_P01A)
     t_ms = (time.perf_counter() - t0) * 1000
+
     if DEBUG:
         for ci in engine.cycle_history:
             _dbg_cycle(ci)
         _dbg(f"  result: cycles={engine.cycles_used} trace_len={len(engine.trace)}")
         _dbg(f"  timing: {t_ms:.3f}ms")
         _dbg("")
+
     return {
         "terminou": True,
         "ciclos": engine.cycles_used,
         "trace": engine.trace,
         "fatos_finais": sorted(f"{f.key}={f.value}" for f in facts),
     }
+
+
+# ============================================================
+# P01b - cadeia > max_cycles
+# ============================================================
 def build_chain(n: int) -> list[Rule]:
     return [
         Rule(f"R_{i:02d}",
@@ -151,16 +218,20 @@
              conclusion=(f"a{i+1}", "ok"))
         for i in range(n)
     ]
+
+
 def run_p01b() -> dict:
     chain_len = 6
     max_cycles = 3
     rules = build_chain(chain_len)
     seed = [Fact("a0", "ok")]
+
     if DEBUG:
         _dbg("--- P01b: cadeia > max_cycles ---")
         _dbg(f"  seed_facts: {[f.to_pair() for f in seed]}")
         _dbg(f"  chain_length: {chain_len} (rules: {[r.id for r in rules]})")
         _dbg(f"  max_cycles: {max_cycles}")
+
     t0 = time.perf_counter()
     engine = ForwardChainingEngine(max_cycles=max_cycles)
     try:
@@ -183,6 +254,11 @@
         return {"levantou_erro": True, "erro": str(e), "trace": engine.trace}
     LOG.error("P01b: NAO levantou CycleLimitError - engine mentiu")
     return {"levantou_erro": False, "erro": None, "trace": engine.trace}
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     if DEBUG:
         _dbg("=== engine_p01.py ===")
@@ -190,8 +266,11 @@
         _dbg("engine_semantics: B (snapshot per cycle)")
         _dbg(f"args: {sys.argv}")
         _dbg("")
+
     lines: list[str] = []
     falhas: list[str] = []
+
+    # ---------- P01a ----------
     lines.append("=== P01a: ciclo de regras ===")
     a = run_p01a()
     lines.append(f"terminou: {a['terminou']}")
@@ -202,10 +281,13 @@
         lines.append(f"  ciclo {s['cycle']}: {s['rule_id']} -> {k}={v}")
     lines.append(f"fatos_finais: {a['fatos_finais']}")
     lines.append("")
+
     if len(a["trace"]) != 2:
         falhas.append(f"P01a: esperado 2 entradas no trace, veio {len(a['trace'])}")
     if a["ciclos"] != 3:
         falhas.append(f"P01a: esperado 3 ciclos, veio {a['ciclos']}")
+
+    # ---------- P01b ----------
     lines.append("=== P01b: cadeia > max_cycles ===")
     b = run_p01b()
     lines.append(f"levantou_erro: {b['levantou_erro']}")
@@ -216,10 +298,13 @@
         k, v = s["conclusion"]
         lines.append(f"  ciclo {s['cycle']}: {s['rule_id']} -> {k}={v}")
     lines.append("")
+
     if not b["levantou_erro"]:
         falhas.append("P01b: esperado CycleLimitError, nao foi levantado")
     if len(b["trace"]) != 3:
         falhas.append(f"P01b: esperado 3 entradas no trace, veio {len(b['trace'])}")
+
+    # ---------- veredito ----------
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -232,8 +317,10 @@
         resultado = 0
         if DEBUG:
             _dbg("=== done: all checks passed ===")
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -241,7 +328,9 @@
         newline="\n",
     )
     return resultado
+
 class _Quiet:
+    """Context manager que suspende _dbg durante execucoes em massa."""
     __slots__ = ("level",)
     def __init__(self) -> None:
         self.level = 0
@@ -250,10 +339,14 @@
         return self
     def __exit__(self, *exc):
         self.level -= 1
+
+
 QUIET = _Quiet()
+
+
 def _dbg(*parts) -> None:
     if DEBUG and QUIET.level == 0:
         print("[DEBUG]", *parts, file=sys.stderr)
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/02_conflict/README.md
  xml=40 linhas | disco=49 linhas
--- XML:doxoade/research/forward_chaining/poc/02_conflict/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/02_conflict/README.md
@@ -1,24 +1,32 @@
+# P02 — Conflito real e determinismo
 
-# P02 — Conflito real e determinismo
 **Contrato:** C1 (Inferência) estendido com resolução de contradição por prioridade.
+
 ## Semântica de conflito — DECLARADA
+
 Duas regras que produzem fatos com a **mesma key** e **valores diferentes**
 no mesmo ciclo constituem conflito. Política:
+
 1. Maior prioridade vence.
 2. Empate → primeira regra em `rules` vence (tie-break por ordem de definição).
 3. Perdedor vai para `shadowed` — nunca re-entra no WM.
 4. Cada resolução gera entrada em `conflicts` (rastreável).
+
 Sem essa política, WM ganharia `out=X` **e** `out=Y` — contradição silenciosa.
 P02 é o teste de que a política existe e é determinística.
+
 ## O que prova
+
 - **P02a:** conflito real, prioridade 10 vs 1 → só `out=Y` no WM, 1 conflito logado.
 - **P02b:** chaves distintas, ambas disparam, 0 conflitos.
 - **P02c:** 100 runs de P02a → saída byte-a-byte idêntica.
 - **P02d:** empate de prioridade → ordem em `rules` decide (`first` na ordem A, `second` na ordem B).
+
 ## O que NÃO prova (deixa para as próximas)
 - Confiança / decay → **P23** (confidence engine, futuro).
 - Remoção de fato / "unshadowing" → fora de escopo.
 - Unificação → **P20**.
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|
@@ -26,6 +34,7 @@
 | Não-determinismo por ordem | baixa | alto | P02c com 100 runs |
 | Tie-break implícito | média | alto | P02d com duas ordens |
 | Perdedor re-tenta todo ciclo | média | médio | `shadowed` persiste |
+
 ## Planos A / B / C
 - **A (implementado):** resolução por prioridade + tie-break por ordem.
 - **B (se A falha):** `confidence` numérica substitui prioridade
@@ -33,8 +42,8 @@
 - **C (se A e B falham):** replanejar contrato — conflito pode não ser
   detectável por key isolada (ex: `temp=high` vs `temp=low` são opostos
   semânticos, não sintáticos).
+
 ## Lição
 Conflito **não** é bug do motor. É o motor **funcionando**. O teste correto
 é que o resultado é único, rastreável e determinístico — não que "não há
 conflito". Engines que nunca logam conflito estão mentindo.
-      

■ doxoade/research/forward_chaining/poc/02_conflict/engine_p02.py
  xml=346 linhas | disco=453 linhas
--- XML:doxoade/research/forward_chaining/poc/02_conflict/engine_p02.py
+++ DISCO:doxoade/research/forward_chaining/poc/02_conflict/engine_p02.py
@@ -1,13 +1,31 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/02_conflict/engine_p02.py
+"""
+P02 - Conflito e determinismo (C1) com debug estruturado.
+
+Debug:
+    py engine_p02.py --debug
+    Emite [DEBUG] em stderr. stdout/output.txt inalterados.
+    Mostra: per-sonda, cycle-by-cycle, resolucao de conflito com
+    reason explicito, timing.
+
+P02a - conflito (prioridade decide)
+P02b - sem conflito (chaves distintas)
+P02c - determinismo (100 runs) - debug so do run 1 + agregado
+P02d - tie-break por ordem de definicao
+"""
 from __future__ import annotations
+
 import dataclasses
 import logging
 import sys
 import time
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
 DEBUG = "--debug" in sys.argv
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc02")
     if logger.handlers:
@@ -17,8 +35,13 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class _Quiet:
+    """Context manager que suspende _dbg durante execucoes em massa."""
     __slots__ = ("level",)
     def __init__(self) -> None:
         self.level = 0
@@ -27,12 +50,20 @@
         return self
     def __exit__(self, *exc):
         self.level -= 1
+
+
 QUIET = _Quiet()
+
+
 def _dbg(*parts) -> None:
     if DEBUG and QUIET.level == 0:
         print("[DEBUG]", *parts, file=sys.stderr)
+
+
 class CycleLimitError(RuntimeError):
     pass
+
+
 @dataclasses.dataclass(frozen=True)
 class Fact:
     key: str
@@ -40,8 +71,11 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_pair(self) -> tuple[str, str]:
         return (self.key, self.value)
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -49,12 +83,21 @@
     conclusion: tuple[str, str]
     priority: int = 0
     description: str = ""
+
     def match(self, snapshot: frozenset[tuple[str, str]]) -> bool:
         return all(c in snapshot for c in self.conditions)
+
     def conclusion_fact(self, cycle: int) -> Fact:
         k, v = self.conclusion
         return Fact(k, v, source="derived", rule_id=self.id, cycle=cycle)
+
+
 class ForwardChainingEngine:
+    """
+    Snapshot por ciclo + resolucao de conflito por prioridade.
+    Fato perdedor vai para `shadowed` (nunca re-entra).
+    """
+
     def __init__(self, max_cycles: int = 100):
         self.max_cycles = max_cycles
         self.trace: list[dict] = []
@@ -64,6 +107,7 @@
         self.cycle_history: list[dict] = []
         self.rules_attempted = 0
         self.rule_attempts: dict[str, int] = {}
+
     def run(self, initial_facts: list[Fact], rules: list[Rule]) -> list[Fact]:
         facts: list[Fact] = list(initial_facts)
         ordered = sorted(
@@ -85,14 +129,17 @@
                 "shadowed_this_cycle": [],
                 "quiescence": False,
             }
+
             candidates: list[tuple[Rule, Fact]] = []
             for rule in ordered:
                 self.rules_attempted += 1
                 self.rule_attempts[rule.id] = self.rule_attempts.get(rule.id, 0) + 1
+
                 if not rule.match(snapshot):
                     cycle_info["matches"][rule.id] = 0
                     continue
                 cycle_info["matches"][rule.id] = 1
+
                 new_fact = rule.conclusion_fact(cycle=cycles)
                 pair = new_fact.to_pair()
                 if pair in existing:
@@ -103,11 +150,13 @@
                     continue
                 candidates.append((rule, new_fact))
                 cycle_info["candidates"].append((rule.id, rule.priority, pair))
+
             if not candidates:
                 cycle_info["quiescence"] = True
                 self.cycle_history.append(cycle_info)
                 self.cycles_used = cycles
                 return facts
+
             winners: dict[str, tuple[Rule, Fact, str]] = {}
             for rule, fact in candidates:
                 k = fact.key
@@ -132,8 +181,10 @@
                     cycle_info["shadowed_this_cycle"].append(
                         (rule.id, fact.to_pair(), reason)
                     )
+
             for k, (rule, fact, reason) in winners.items():
                 cycle_info["winners"][k] = (rule.id, rule.priority, fact.to_pair(), reason)
+
             for k, (rule, fact, _) in winners.items():
                 facts.append(fact)
                 self.trace.append({
@@ -141,8 +192,11 @@
                     "rule_id": rule.id,
                     "conclusion": fact.to_pair(),
                 })
+
             self.cycle_history.append(cycle_info)
+
         raise CycleLimitError(f"max_cycles={self.max_cycles}")
+
     def _log_conflict(self, cycle, key, winner_rule, winner_fact,
                       loser_rule, loser_fact, reason):
         self.conflicts.append({
@@ -154,6 +208,8 @@
             "loser_pair": loser_fact.to_pair(),
             "reason": reason,
         })
+
+
 def _dbg_cycle_p02(cycle_info: dict) -> None:
     _dbg(f"  cycle {cycle_info['cycle']}:")
     m = cycle_info["matches"]
@@ -170,6 +226,8 @@
         _dbg(f"    already_shadowed: {rid} -> {fact}")
     if cycle_info["quiescence"]:
         _dbg("    quiescence")
+
+
 def _dbg_engine(name: str, engine: ForwardChainingEngine,
                 seed: list[Fact], t_ms: float) -> None:
     _dbg(f"--- {name} ---")
@@ -180,6 +238,11 @@
          f"conflicts={len(engine.conflicts)}")
     _dbg(f"  timing: {t_ms:.3f}ms")
     _dbg("")
+
+
+# ============================================================
+# P02a - conflito (prioridade decide)
+# ============================================================
 def run_p02a() -> dict:
     rules = [
         Rule("R_high", conditions=(("trigger", "yes"),),
@@ -200,6 +263,11 @@
         "conflicts": engine.conflicts,
         "out_values": [f.value for f in facts if f.key == "out"],
     }
+
+
+# ============================================================
+# P02b - sem conflito
+# ============================================================
 def run_p02b() -> dict:
     rules = [
         Rule("R_a", conditions=(("trigger", "yes"),),
@@ -222,6 +290,11 @@
             (f.to_pair() for f in facts if f.source == "derived")
         ),
     }
+
+
+# ============================================================
+# P02c - determinismo
+# ============================================================
 def run_p02c() -> dict:
     t0 = time.perf_counter()
     results = []
@@ -230,6 +303,7 @@
             r = run_p02a()
             results.append(tuple(r["out_values"]))
     t_total = (time.perf_counter() - t0) * 1000
+
     if DEBUG:
         _dbg("--- P02c: determinismo (100 runs de P02a) ---")
         _dbg(f"  n: 100")
@@ -237,7 +311,13 @@
         _dbg(f"  time_total: {t_total:.3f}ms")
         _dbg(f"  time_per_run: {t_total/100:.3f}ms")
         _dbg("")
+
     return {"n": len(results), "unique_outputs": set(results)}
+
+
+# ============================================================
+# P02d - tie-break por ordem
+# ============================================================
 def _run_order(order_name: str, rules: list[Rule]) -> tuple[list[str], ForwardChainingEngine]:
     seed = [Fact("trigger", "yes")]
     t0 = time.perf_counter()
@@ -246,28 +326,41 @@
     t_ms = (time.perf_counter() - t0) * 1000
     _dbg_engine(f"P02d/{order_name}", engine, seed, t_ms)
     return [f.value for f in facts if f.key == "out"], engine
+
+
 def run_p02d() -> dict:
     r_first = Rule("R_first", conditions=(("trigger", "yes"),),
                    conclusion=("out", "first"), priority=5)
     r_second = Rule("R_second", conditions=(("trigger", "yes"),),
                     conclusion=("out", "second"), priority=5)
+
     if DEBUG:
         _dbg("--- P02d: tie-break por ordem de definicao ---")
         _dbg(f"  rules: R_first prio=5, R_second prio=5")
+
     out1, _ = _run_order("order_a=[R_first,R_second]", [r_first, r_second])
     out2, _ = _run_order("order_b=[R_second,R_first]", [r_second, r_first])
+
     return {
         "order_a_winner": out1,
         "order_b_winner": out2,
     }
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     if DEBUG:
         _dbg("=== engine_p02.py ===")
         _dbg("mode: debug")
         _dbg(f"args: {sys.argv}")
         _dbg("")
+
     lines: list[str] = []
     falhas: list[str] = []
+
+    # P02a
     lines.append("=== P02a: conflito (prioridade decide) ===")
     a = run_p02a()
     lines.append(f"terminou: {a['terminou']}")
@@ -284,6 +377,7 @@
         )
     lines.append(f"out_values: {a['out_values']}")
     lines.append("")
+
     if a["trace"] != [{"cycle": 1, "rule_id": "R_high",
                        "conclusion": ("out", "Y")}]:
         falhas.append(f"P02a: trace inesperado: {a['trace']}")
@@ -291,6 +385,8 @@
         falhas.append(f"P02a: esperado 1 conflito, veio {len(a['conflicts'])}")
     if a["out_values"] != ["Y"]:
         falhas.append(f"P02a: esperado ['Y'], veio {a['out_values']}")
+
+    # P02b
     lines.append("=== P02b: sem conflito (chaves distintas) ===")
     b = run_p02b()
     lines.append(f"ciclos_usados: {b['ciclos']}")
@@ -298,28 +394,36 @@
     lines.append(f"conflicts_len: {len(b['conflicts'])}")
     lines.append(f"out_pairs: {b['out_pairs']}")
     lines.append("")
+
     if len(b["trace"]) != 2:
         falhas.append(f"P02b: esperado 2 no trace, veio {len(b['trace'])}")
     if len(b["conflicts"]) != 0:
         falhas.append(f"P02b: esperado 0 conflitos, veio {len(b['conflicts'])}")
     if b["out_pairs"] != ["out_a=1", "out_b=2"]:
         falhas.append(f"P02b: out_pairs inesperado: {b['out_pairs']}")
+
+    # P02c
     lines.append("=== P02c: determinismo (100 runs) ===")
     c = run_p02c()
     lines.append(f"n: {c['n']}")
     lines.append(f"unique_outputs: {sorted(c['unique_outputs'])}")
     lines.append("")
+
     if c["unique_outputs"] != {("Y",)}:
         falhas.append(f"P02c: nao-deterministico: {c['unique_outputs']}")
+
+    # P02d
     lines.append("=== P02d: tie-break por ordem de definicao ===")
     d = run_p02d()
     lines.append(f"order_a_winner: {d['order_a_winner']}")
     lines.append(f"order_b_winner: {d['order_b_winner']}")
     lines.append("")
+
     if d["order_a_winner"] != ["first"]:
         falhas.append(f"P02d: ordem A deveria dar 'first', veio {d['order_a_winner']}")
     if d["order_b_winner"] != ["second"]:
         falhas.append(f"P02d: ordem B deveria dar 'second', veio {d['order_b_winner']}")
+
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for f in falhas:
@@ -332,8 +436,10 @@
         resultado = 0
         if DEBUG:
             _dbg("=== done: all checks passed ===")
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -341,6 +447,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/10_ast_to_facts/README.md
  xml=37 linhas | disco=47 linhas
--- XML:doxoade/research/forward_chaining/poc/10_ast_to_facts/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/10_ast_to_facts/README.md
@@ -1,8 +1,11 @@
+# P10 — AST -> fatos (C2, sem engine)
 
-# P10 — AST -> fatos (C2, sem engine)
 **Contrato:** C2 (Adaptação). `src: str → frozenset[FactPair]`.
+
 ## Subset declarado
+
 P10 aceita **apenas** `x = a + b` (Assign + BinOp + Name × 2). 6 fatos:
+
 | Fato | Origem |
 |---|---|
 | `stmt=Assign` | tipo do nó raiz |
@@ -11,16 +14,21 @@
 | `binop.op=Add` | `type(node.value.op).__name__` |
 | `binop.left=a` | `Name.id` de `left` |
 | `binop.right=b` | `Name.id` de `right` |
+
 Outros shapes → erro explícito. P11/P12/P13 expandem o subset.
+
 ## O que prova
+
 - **P10a:** `extract("x = a + b") == EXPECTED_P10A` (6 fatos, comparação por conjunto).
 - **P10b:** 100 extrações → serialização byte-a-byte idêntica (`|` como separador interno).
 - **P10c:** `"x = "` → `SyntaxError` propagado (não silencioso).
 - **P10d:** `"pass"` → `UnsupportedNodeError` (parsable, fora do subset).
+
 ## O que NÃO prova
 - Unificação sobre os fatos → **P20**.
 - Múltiplos statements / funções → **P11**.
 - Dados externos (CSV/JSON) → **P12 / P13**.
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|
@@ -28,10 +36,12 @@
 | Serialização não-determinística | baixa | alto (diff quebra) | `sorted_lines` + P10b |
 | Erro engolido (`except: pass`) | baixa | crítico | P10c + P10d exigem type específico |
 | Múltiplos statements aceitos | baixa | médio | `parse_single` rejeita > 1 |
+
 ## Planos A / B / C
 - **A (implementado):** whitelist explícita de `ast.Assign + ast.BinOp + ast.Name`.
 - **B (se A falha em expandir para P11):** trocar whitelist por visitor pattern com dispatch por tipo. Custo: mais código, menos contrato.
 - **C (se B falha):** abandonar subset declarado, aceitar qualquer AST e serializar genericamente (`type(node).__name__` como tipo). Custo: perde tipagem estrutural que P20 vai precisar.
+
 ## Lição (confirmar ao rodar)
 Serializer **sem engine** é pré-requisito testável. Se `frozenset` extraído diverge do esperado, nenhuma inferência downstream é confiável. Separar C2 de C1 permite diagnosticar isso antes de P20 — que é onde o custo do erro seria alto.
-      
+

■ doxoade/research/forward_chaining/poc/10_ast_to_facts/engine_p10.py
  xml=168 linhas | disco=270 linhas
--- XML:doxoade/research/forward_chaining/poc/10_ast_to_facts/engine_p10.py
+++ DISCO:doxoade/research/forward_chaining/poc/10_ast_to_facts/engine_p10.py
@@ -1,11 +1,35 @@
-
-﻿
+﻿# -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/10_ast_to_facts/engine_p10.py
+"""
+P10 â€” AST -> fatos (C2). Sem engine.
+
+Contrato provado: C2 (Adaptacao)
+    Fonte (str) -> frozenset[FactPair]
+
+SUBSET DECLARADO (contrato do PoC, nao do sistema):
+    Aceita APENAS "x = a + b" (Assign + BinOp + Name em ambos os lados).
+    Qualquer outro shape -> UnsupportedNodeError explicito.
+    Fonte malformada -> SyntaxError explicito (herdado de ast.parse).
+
+P10a â€” 'x = a + b' -> frozenset exato de 6 fatos.
+P10b â€” 100 extracoes -> serializacao determinista (diffavel).
+P10c â€” 'x = ' (malformado) -> SyntaxError explicito, nao silencioso.
+P10d â€” 'pass' (parsable, fora do subset) -> UnsupportedNodeError explicito.
+
+NAO usa: engine (C1 nao entra aqui). Unificacao (P20).
+
+Rodar: run.bat / run.ps1
+"""
 from __future__ import annotations
+
 import ast
 import logging
 import sys
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc10")
     if logger.handlers:
@@ -15,26 +39,49 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
+# ---------- Erros (ProDeNov 5.2) ----------
 class UnsupportedNodeError(RuntimeError):
+    """AST node fora do subset declarado para esta PoC."""
+
+
 class AstShapeError(RuntimeError):
+    """Fonte parseavel, mas fora do contrato de 1 statement."""
+
+
 FactPair = tuple[str, str]
+
+
+# ---------- Serializer ----------
 SUPPORTED_NODES = (ast.Assign,)
 SUPPORTED_VALUE_NODES = (ast.BinOp,)
 SUPPORTED_LEAVES = (ast.Name,)
+
+
 def parse_single(src: str) -> ast.stmt:
+    """Extrai 1 statement. Multi-statement -> AstShapeError."""
     tree = ast.parse(src)
     if len(tree.body) != 1:
         raise AstShapeError(
             f"esperado 1 statement, veio {len(tree.body)}"
         )
     return tree.body[0]
+
+
 def serialize_stmt(node: ast.stmt) -> frozenset[FactPair]:
+    """Extrai fatos do subset. Fora do subset -> UnsupportedNodeError."""
     if not isinstance(node, SUPPORTED_NODES):
         raise UnsupportedNodeError(
             f"node tipo {type(node).__name__} fora do subset"
         )
+
     facts: set[FactPair] = {("stmt", type(node).__name__)}
+
+    # Assign: exige 1 target Name, value BinOp
     if len(node.targets) != 1:
         raise UnsupportedNodeError(
             f"Assign com {len(node.targets)} targets; subset exige 1"
@@ -45,6 +92,7 @@
             f"Assign target {type(tgt).__name__} fora do subset"
         )
     facts.add(("assign.target", tgt.id))
+
     val = node.value
     if not isinstance(val, SUPPORTED_VALUE_NODES):
         raise UnsupportedNodeError(
@@ -52,19 +100,31 @@
         )
     facts.add(("assign.value", type(val).__name__))
     facts.add(("binop.op", type(val.op).__name__))
+
     for side_name, side_node in (("left", val.left), ("right", val.right)):
         if not isinstance(side_node, SUPPORTED_LEAVES):
             raise UnsupportedNodeError(
                 f"BinOp.{side_name} {type(side_node).__name__} fora do subset"
             )
         facts.add((f"binop.{side_name}", side_node.id))
+
     return frozenset(facts)
+
+
 def extract(src: str) -> frozenset[FactPair]:
+    """Fonte -> frozenset[FactPair]. Falha loud em qualquer desvio."""
     node = parse_single(src)
     return serialize_stmt(node)
+
+
 def sorted_lines(facts: frozenset[FactPair]) -> list[str]:
+    """Serializacao determinista (para diff de output.txt)."""
     return sorted(f"{k}={v}" for k, v in facts)
+
+
+# ---------- Caso de teste canonico ----------
 INPUT_P10A = "x = a + b"
+
 EXPECTED_P10A: frozenset[FactPair] = frozenset({
     ("stmt", "Assign"),
     ("assign.target", "x"),
@@ -73,14 +133,29 @@
     ("binop.left", "a"),
     ("binop.right", "b"),
 })
+
+
+# ============================================================
+# P10a â€” extracao exata
+# ============================================================
 def run_p10a() -> dict:
     facts = extract(INPUT_P10A)
     return {"input": INPUT_P10A, "facts": facts, "lines": sorted_lines(facts)}
+
+
+# ============================================================
+# P10b â€” determinismo de serializacao
+# ============================================================
 def run_p10b() -> dict:
     serialized: set[str] = set()
     for _ in range(100):
         serialized.add("|".join(sorted_lines(extract(INPUT_P10A))))
     return {"n": 100, "unique": serialized}
+
+
+# ============================================================
+# P10c â€” input malformado
+# ============================================================
 def run_p10c() -> dict:
     try:
         extract("x = ")
@@ -89,6 +164,11 @@
     except Exception as e:
         return {"levantou_erro": True, "type": type(e).__name__}
     return {"levantou_erro": False, "type": None}
+
+
+# ============================================================
+# P10d â€” node fora do subset
+# ============================================================
 def run_p10d() -> dict:
     try:
         extract("pass")
@@ -97,9 +177,16 @@
     except Exception as e:
         return {"levantou_erro": True, "type": type(e).__name__}
     return {"levantou_erro": False, "type": None}
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     lines: list[str] = []
     falhas: list[str] = []
+
+    # ---------- P10a ----------
     lines.append("=== P10a: 'x = a + b' -> fatos ===")
     a = run_p10a()
     lines.append(f"input: {a['input']!r}")
@@ -108,6 +195,7 @@
     for line in a["lines"]:
         lines.append(f"  {line}")
     lines.append("")
+
     if a["facts"] != EXPECTED_P10A:
         extras = a["facts"] - EXPECTED_P10A
         missing = EXPECTED_P10A - a["facts"]
@@ -115,35 +203,46 @@
             f"P10a: conjunto divergente (extras={sorted(extras)}, "
             f"missing={sorted(missing)})"
         )
+
+    # ---------- P10b ----------
     lines.append("=== P10b: determinismo de serializacao (100 runs) ===")
     b = run_p10b()
     lines.append(f"n: {b['n']}")
     lines.append(f"unique_outputs: {sorted(b['unique'])}")
     lines.append("")
+
     if len(b["unique"]) != 1:
         falhas.append(
             f"P10b: serializacao nao-deterministica ({len(b['unique'])} variacoes)"
         )
+
+    # ---------- P10c ----------
     lines.append("=== P10c: input malformado -> SyntaxError explicito ===")
     c = run_p10c()
     lines.append("input: 'x = '")
     lines.append(f"levantou_erro: {c['levantou_erro']}")
     lines.append(f"type: {c['type']}")
     lines.append("")
+
     if not c["levantou_erro"]:
         falhas.append("P10c: input malformado nao levantou erro")
     if c["type"] != "SyntaxError":
         falhas.append(f"P10c: esperado SyntaxError, veio {c['type']}")
+
+    # ---------- P10d ----------
     lines.append("=== P10d: node fora do subset -> UnsupportedNodeError explicito ===")
     d = run_p10d()
     lines.append("input: 'pass'")
     lines.append(f"levantou_erro: {d['levantou_erro']}")
     lines.append(f"type: {d['type']}")
     lines.append("")
+
     if not d["levantou_erro"]:
         falhas.append("P10d: node fora do subset nao levantou erro")
     if d["type"] != "UnsupportedNodeError":
         falhas.append(f"P10d: esperado UnsupportedNodeError, veio {d['type']}")
+
+    # ---------- veredito ----------
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for f in falhas:
@@ -154,8 +253,10 @@
         lines.append("P10 PASS")
         LOG.info("P10 PASS")
         resultado = 0
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -163,6 +264,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/11_ast_function/engine_p11.py
  xml=217 linhas | disco=312 linhas
--- XML:doxoade/research/forward_chaining/poc/11_ast_function/engine_p11.py
+++ DISCO:doxoade/research/forward_chaining/poc/11_ast_function/engine_p11.py
@@ -1,11 +1,42 @@
-
-﻿
+﻿# -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/11_ast_function/engine_p11.py
+"""
+P11 â€” AST de funcao simples -> fatos (C2). Sem engine.
+
+Contrato provado: C2 (Adaptacao), extensao de P10.
+
+SUBSET DECLARADO (contrato do PoC):
+    Aceita APENAS "def NAME(PARAM): return PARAM + INT_LITERAL"
+    - FunctionDef com 1 arg (ast.arg)
+    - 1 body stmt (Return)
+    - Return.expr = BinOp(op=Add)
+    - BinOp.left = Name
+    - BinOp.right = Constant com valor int
+
+Qualquer variacao -> UnsupportedNodeError explicito.
+Assign (de P10) -> UnsupportedNodeError em P11 (subset distinto).
+
+P11a â€” def f(x): return x + 1 -> frozenset exato de 11 fatos.
+P11b â€” def g(n): return n + 42 -> 11 fatos (nao hardcoded).
+P11c â€” 100 runs sobre P11a -> serializacao determinista.
+P11d â€” def f(): return 42 (0 args) -> UnsupportedNodeError.
+P11e â€” def f(x): return x (Return sem BinOp) -> UnsupportedNodeError.
+P11f â€” x = a + b (Assign de P10) -> UnsupportedNodeError.
+
+NAO usa: engine (C1 nao entra aqui).
+
+Rodar: run.bat / run.ps1
+"""
 from __future__ import annotations
+
 import ast
 import logging
 import sys
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc11")
     if logger.handlers:
@@ -15,18 +46,34 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class UnsupportedNodeError(RuntimeError):
+    """AST node fora do subset declarado para esta PoC."""
+
+
 class AstShapeError(RuntimeError):
+    """Fonte parseavel, mas fora do contrato de 1 statement."""
+
+
 FactPair = tuple[str, str]
 SUPPORTED_STMTS = (ast.FunctionDef,)
+
+
 def parse_single(src: str) -> ast.stmt:
     tree = ast.parse(src)
     if len(tree.body) != 1:
         raise AstShapeError(f"esperado 1 statement, veio {len(tree.body)}")
     return tree.body[0]
+
+
 def serialize_function(node: ast.FunctionDef) -> frozenset[FactPair]:
     facts: set[FactPair] = {("stmt", "FunctionDef"), ("func.name", node.name)}
+
+    # --- args: exatamente 1 ---
     if len(node.args.args) != 1:
         raise UnsupportedNodeError(
             f"FunctionDef com {len(node.args.args)} args; subset exige 1"
@@ -34,6 +81,8 @@
     arg = node.args.args[0]
     facts.add(("func.args_len", "1"))
     facts.add(("func.arg", arg.arg))
+
+    # --- body: exatamente 1 stmt Return ---
     if len(node.body) != 1:
         raise UnsupportedNodeError(
             f"FunctionDef com {len(node.body)} body stmts; subset exige 1"
@@ -44,6 +93,7 @@
             f"FunctionDef body {type(body_stmt).__name__}; subset exige Return"
         )
     facts.add(("func.body.kind", "Return"))
+
     if body_stmt.value is None:
         raise UnsupportedNodeError("Return sem expressao; subset exige expr")
     expr = body_stmt.value
@@ -57,12 +107,16 @@
         )
     facts.add(("func.body.expr", "BinOp"))
     facts.add(("binop.op", "Add"))
+
+    # --- BinOp.left: Name ---
     if not isinstance(expr.left, ast.Name):
         raise UnsupportedNodeError(
             f"BinOp.left {type(expr.left).__name__}; subset exige Name"
         )
     facts.add(("binop.left.kind", "Name"))
     facts.add(("binop.left.name", expr.left.id))
+
+    # --- BinOp.right: Constant int ---
     if not isinstance(expr.right, ast.Constant):
         raise UnsupportedNodeError(
             f"BinOp.right {type(expr.right).__name__}; subset exige Constant"
@@ -73,7 +127,10 @@
         )
     facts.add(("binop.right.kind", "Constant"))
     facts.add(("binop.right.value", str(expr.right.value)))
+
     return frozenset(facts)
+
+
 def extract(src: str) -> frozenset[FactPair]:
     node = parse_single(src)
     if not isinstance(node, SUPPORTED_STMTS):
@@ -82,8 +139,13 @@
             f"(P11 aceita apenas FunctionDef)"
         )
     return serialize_function(node)
+
+
 def sorted_lines(facts: frozenset[FactPair]) -> list[str]:
     return sorted(f"{k}={v}" for k, v in facts)
+
+
+# ---------- casos canonicos ----------
 INPUT_P11A = "def f(x): return x + 1"
 EXPECTED_P11A: frozenset[FactPair] = frozenset({
     ("stmt", "FunctionDef"),
@@ -98,6 +160,7 @@
     ("binop.right.kind", "Constant"),
     ("binop.right.value", "1"),
 })
+
 INPUT_P11B = "def g(n): return n + 42"
 EXPECTED_P11B: frozenset[FactPair] = frozenset({
     ("stmt", "FunctionDef"),
@@ -112,17 +175,25 @@
     ("binop.right.kind", "Constant"),
     ("binop.right.value", "42"),
 })
+
+
 def run_p11a() -> dict:
     facts = extract(INPUT_P11A)
     return {"input": INPUT_P11A, "facts": facts, "lines": sorted_lines(facts)}
+
+
 def run_p11b() -> dict:
     facts = extract(INPUT_P11B)
     return {"input": INPUT_P11B, "facts": facts, "lines": sorted_lines(facts)}
+
+
 def run_p11c() -> dict:
     serialized: set[str] = set()
     for _ in range(100):
         serialized.add("|".join(sorted_lines(extract(INPUT_P11A))))
     return {"n": 100, "unique": serialized}
+
+
 def _expect_error(src: str, expected_type: str) -> dict:
     try:
         extract(src)
@@ -130,18 +201,28 @@
         return {"levantou_erro": True, "type": type(e).__name__,
                 "matches_expected": type(e).__name__ == expected_type}
     return {"levantou_erro": False, "type": None, "matches_expected": False}
+
+
 def run_p11d() -> dict:
     return {"input": "def f(): return 42",
             **_expect_error("def f(): return 42", "UnsupportedNodeError")}
+
+
 def run_p11e() -> dict:
     return {"input": "def f(x): return x",
             **_expect_error("def f(x): return x", "UnsupportedNodeError")}
+
+
 def run_p11f() -> dict:
     return {"input": "x = a + b",
             **_expect_error("x = a + b", "UnsupportedNodeError")}
+
+
 def main() -> int:
     lines: list[str] = []
     falhas: list[str] = []
+
+    # ---------- P11a ----------
     lines.append("=== P11a: 'def f(x): return x + 1' -> fatos ===")
     a = run_p11a()
     lines.append(f"input: {a['input']!r}")
@@ -150,6 +231,7 @@
     for line in a["lines"]:
         lines.append(f"  {line}")
     lines.append("")
+
     if a["facts"] != EXPECTED_P11A:
         extras = a["facts"] - EXPECTED_P11A
         missing = EXPECTED_P11A - a["facts"]
@@ -157,6 +239,8 @@
             f"P11a: conjunto divergente (extras={sorted(extras)}, "
             f"missing={sorted(missing)})"
         )
+
+    # ---------- P11b ----------
     lines.append("=== P11b: 'def g(n): return n + 42' -> fatos ===")
     b = run_p11b()
     lines.append(f"input: {b['input']!r}")
@@ -165,6 +249,7 @@
     for line in b["lines"]:
         lines.append(f"  {line}")
     lines.append("")
+
     if b["facts"] != EXPECTED_P11B:
         extras = b["facts"] - EXPECTED_P11B
         missing = EXPECTED_P11B - b["facts"]
@@ -172,15 +257,20 @@
             f"P11b: conjunto divergente (extras={sorted(extras)}, "
             f"missing={sorted(missing)})"
         )
+
+    # ---------- P11c ----------
     lines.append("=== P11c: determinismo de serializacao (100 runs) ===")
     c = run_p11c()
     lines.append(f"n: {c['n']}")
     lines.append(f"unique_outputs: {sorted(c['unique'])}")
     lines.append("")
+
     if len(c["unique"]) != 1:
         falhas.append(
             f"P11c: serializacao nao-deterministica ({len(c['unique'])} variacoes)"
         )
+
+    # ---------- P11d-f ----------
     for label, runner in (("P11d", run_p11d), ("P11e", run_p11e),
                           ("P11f", run_p11f)):
         r = runner()
@@ -193,6 +283,8 @@
             falhas.append(f"{label}: input nao levantou erro")
         if not r["matches_expected"]:
             falhas.append(f"{label}: esperado UnsupportedNodeError, veio {r['type']}")
+
+    # ---------- veredito ----------
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for f in falhas:
@@ -203,8 +295,10 @@
         lines.append("P11 PASS")
         LOG.info("P11 PASS")
         resultado = 0
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -212,6 +306,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/20_unification/README.md
  xml=50 linhas | disco=60 linhas
--- XML:doxoade/research/forward_chaining/poc/20_unification/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/20_unification/README.md
@@ -1,15 +1,20 @@
+# P20 — Unificação sobre triplas (C1 + C3)
 
-# P20 — Unificação sobre triplas (C1 + C3)
 **Contrato:** C1 (Inferência) + C3 (Expressividade com variáveis).
 **Mudança de contrato:** fatos passam de `(key, value)` para `(s, p, o)`.
+
 ## Modelo
+
 | Termo | Casa com | Liga |
 |---|---|---|
 | `str` | igualdade estrita | não |
 | `Var(name)` | qualquer string | sim (consistente entre condições) |
+
 `match_conditions` faz backtracking exaustivo: para cada condição, tenta
 todos os fatos, acumula bindings, propaga. Retorna **todas** as soluções.
+
 ## O que prova
+
 - **P20a:** transitividade `pai(X,Y) ∧ pai(Y,Z) → avo(X,Z)`.
 - **P20b:** var repetida `r(X,X)` casa só com self-loops — `(a,r,b)` não
   produz `(a,self,b)`.
@@ -19,16 +24,20 @@
 - **P20e:** determinismo em 100 runs (set de derivações idêntico).
 - **P20f:** transitividade em grafo cíclico quiesce — `(a,r,b),(b,r,a)`
   produz só `(a,trans,a)` e `(b,trans,b)`, sem explosão.
+
 ## Por que triplas (mudança de contrato)
+
 P10/P11 usaram `(key, value)` — unário. Relações binárias em unário exigem
 encoding comprimido (`key="pai.a", value="b"`), que viola o princípio C-verb.
 Triplas são o formato natural para unificação. P10/P11 continuam válidos
 como sondas de extração; o engine de P20 é independente. Reconciliar em P70.
+
 ## O que NÃO prova
 - Negação como falha → **P21** (falta mecanismo de "não casa").
 - Indexação → **P70** (aqui é força bruta `O(|facts|^|conds|)`).
 - Conflito entre regras com vars → herda P02, mas não testado aqui.
 - Extração de AST → já em P10/P11.
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|
@@ -37,14 +46,15 @@
 | Backtracking explodir em |facts| grande | alta (fora de PoC) | aceito em PoC; indexação em P70 |
 | Ciclo transitivo explodir | média | alto | idempotência + monotonicidade (P01) |
 | Determinismo afetado por ordem | baixa | alto | `new_facts` coletados, sorted depois |
+
 ## Planos A / B / C
 - **A (implementado):** backtracking exaustivo, sem índice.
 - **B (se A não escalar em P30):** índice `facts_by_predicate: dict[p, list[fact]]`.
 - **C (se B ainda lento):** RETE parcial — alpha network por condição. Custo alto.
+
 ## Lição
 Unificação separa brinquedo de engine útil. P00–P02 provam que o motor
 **termina**; P20 prova que ele **compõe** — fatos derivados alimentam
 regras seguintes via bindings, não via reescrita. A tripla é o formato
 que torna isso natural. Manter `(key, value)` para relações binárias
 seria compressão prematura — exatamente o que C-verb proíbe.
-      

■ doxoade/research/forward_chaining/poc/20_unification/engine_p20.py
  xml=305 linhas | disco=433 linhas
--- XML:doxoade/research/forward_chaining/poc/20_unification/engine_p20.py
+++ DISCO:doxoade/research/forward_chaining/poc/20_unification/engine_p20.py
@@ -1,11 +1,45 @@
-
-﻿
+﻿# -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/20_unification/engine_p20.py
+"""
+P20 â€” Unificacao sobre triplas (C1 estendido).
+
+Contrato: C1 (Inferencia) + C3 (Expressividade com variaveis).
+
+MUDANCA DE CONTRATO em relacao a P00-P02:
+    Fatos passam de (key, value) para (subject, predicate, object).
+    Motivo: unificacao precisa de relacoes binarias. Encoding comprimido
+    viola o principio C-verb (verbosidade = controle).
+
+MODELO:
+    Var(name)    -> variavel, casa com qualquer string e liga
+    str          -> constante, casa so com igual
+    TripleFact   -> (s, p, o) + metadados
+
+MATCHER: backtracking exaustivo (todas as solucoes), sem indexacao.
+    Complexidade: O(|facts|^|conditions|). Aceitavel em PoC, alvo de
+    otimizacao em P70.
+
+P20a â€” transitividade: pai(X,Y) AND pai(Y,Z) -> avo(X,Z).
+P20b â€” var repetida: r(X,X) -> self(X,X). Only self-loops casam.
+P20c â€” duas regras compondo sem conflito.
+P20d â€” falha de unificacao (nenhum match).
+P20e â€” determinismo (100 runs de P20a).
+P20f â€” ciclo via trans: (a,r,b),(b,r,a) quiesce sem explodir.
+
+NAO usa: indexacao (P70), negacao (P21), AST aqui (P10/P11).
+
+Rodar: run.bat / run.ps1
+"""
 from __future__ import annotations
+
 import dataclasses
 import logging
 import sys
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc20")
     if logger.handlers:
@@ -15,16 +49,28 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class CycleLimitError(RuntimeError):
     pass
+
+
 @dataclasses.dataclass(frozen=True)
 class Var:
+    """Variavel: casa com qualquer string e liga. Nome unico por escopo de regra."""
     name: str
+
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 Term = str | Var
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class TripleFact:
     s: str
@@ -33,10 +79,14 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
     def render(self) -> str:
         return f"({self.s}, {self.p}, {self.o})"
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -44,6 +94,7 @@
     conclusion: Pattern
     priority: int = 0
     description: str = ""
+
     def conclusion_fact(self, bindings: dict[str, str], cycle: int) -> TripleFact | None:
         resolved = substitute(self.conclusion, bindings)
         if resolved is None:
@@ -51,13 +102,19 @@
         s, p, o = resolved
         return TripleFact(s, p, o, source="derived",
                           rule_id=self.id, cycle=cycle)
+
+
+# ---------- Unificacao ----------
 def unify_term(pattern: Term, value: str,
                bindings: dict[str, str]) -> dict[str, str] | None:
+    """Retorna bindings estendidos ou None se inconsistente."""
     if isinstance(pattern, Var):
         if pattern.name in bindings:
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern: Pattern, fact: TripleFact,
           bindings: dict[str, str]) -> dict[str, str] | None:
     b = bindings
@@ -69,6 +126,8 @@
         return None
     b = unify_term(pattern[2], fact.o, b)
     return b
+
+
 def substitute(pattern: Pattern,
                bindings: dict[str, str]) -> tuple[str, str, str] | None:
     out: list[str] = []
@@ -80,10 +139,13 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_conditions(conditions: tuple[Pattern, ...],
                      facts: list[TripleFact],
                      bindings: dict[str, str] | None = None
                      ) -> list[dict[str, str]]:
+    """Backtracking: retorna TODAS as bindings que satisfazem todas as condicoes."""
     if bindings is None:
         bindings = {}
     if not conditions:
@@ -96,11 +158,15 @@
             continue
         results.extend(match_conditions(tuple(rest), facts, b))
     return results
+
+
+# ---------- Engine ----------
 class ForwardChainingEngine:
     def __init__(self, max_cycles: int = 100):
         self.max_cycles = max_cycles
         self.trace: list[dict] = []
         self.cycles_used: int = 0
+
     def run(self, initial_facts: list[TripleFact],
             rules: list[Rule]) -> list[TripleFact]:
         facts: list[TripleFact] = list(initial_facts)
@@ -108,11 +174,13 @@
         cycles = 0
         LOG.info("run: %d fatos, %d regras, max_cycles=%d",
                  len(facts), len(ordered), self.max_cycles)
+
         while cycles < self.max_cycles:
             cycles += 1
             existing = frozenset(f.to_tuple() for f in facts)
             new_facts: list[TripleFact] = []
             seen_in_cycle: set[tuple[str, str, str]] = set()
+
             for rule in ordered:
                 for bindings in match_conditions(rule.conditions, facts):
                     cf = rule.conclusion_fact(bindings, cycle=cycles)
@@ -125,10 +193,12 @@
                         continue
                     new_facts.append(cf)
                     seen_in_cycle.add(key)
+
             if not new_facts:
                 self.cycles_used = cycles
                 LOG.info("quiescencia em %d ciclo(s)", cycles)
                 return facts
+
             for nf in new_facts:
                 facts.append(nf)
                 self.trace.append({
@@ -138,15 +208,26 @@
                 })
                 LOG.debug("ciclo %d: %s -> %s",
                           cycles, nf.rule_id, nf.render())
+
         raise CycleLimitError(
             f"max_cycles={self.max_cycles} sem quiescencia "
             f"(trace tem {len(self.trace)} entrada(s))"
         )
+
+
+# ---------- Helpers de teste ----------
 def F(s: str, p: str, o: str) -> TripleFact:
     return TripleFact(s, p, o)
+
+
 def fact_set(facts: list[TripleFact], filter_source: str | None = None) -> list[str]:
     items = facts if filter_source is None else [f for f in facts if f.source == filter_source]
     return sorted(f.render() for f in items)
+
+
+# ============================================================
+# P20a â€” transitividade
+# ============================================================
 def run_p20a() -> dict:
     X, Y, Z = Var("X"), Var("Y"), Var("Z")
     rules = [
@@ -163,6 +244,11 @@
         "derived": fact_set(result, filter_source="derived"),
         "all": fact_set(result),
     }
+
+
+# ============================================================
+# P20b â€” variavel repetida
+# ============================================================
 def run_p20b() -> dict:
     X = Var("X")
     rules = [Rule("R_self", conditions=((X, "r", X),), conclusion=(X, "self", X))]
@@ -173,6 +259,11 @@
         "ciclos": eng.cycles_used,
         "derived": fact_set(result, filter_source="derived"),
     }
+
+
+# ============================================================
+# P20c â€” duas regras compondo
+# ============================================================
 def run_p20c() -> dict:
     X, Y = Var("X"), Var("Y")
     rules = [
@@ -186,6 +277,11 @@
         "ciclos": eng.cycles_used,
         "derived": fact_set(result, filter_source="derived"),
     }
+
+
+# ============================================================
+# P20d â€” falha de unificacao
+# ============================================================
 def run_p20d() -> dict:
     X, Y, Z = Var("X"), Var("Y"), Var("Z")
     rules = [
@@ -193,18 +289,28 @@
              conditions=((X, "r", Y), (Y, "r", Z)),
              conclusion=(X, "trans", Z)),
     ]
-    facts = [F("a", "r", "b")]  
+    facts = [F("a", "r", "b")]  # b nao tem 'r' saindo
     eng = ForwardChainingEngine(max_cycles=10)
     result = eng.run(facts, rules)
     return {
         "ciclos": eng.cycles_used,
         "derived": fact_set(result, filter_source="derived"),
     }
+
+
+# ============================================================
+# P20e â€” determinismo
+# ============================================================
 def run_p20e() -> dict:
     runs = set()
     for _ in range(100):
         runs.add(tuple(run_p20a()["derived"]))
     return {"n": 100, "unique": runs}
+
+
+# ============================================================
+# P20f â€” ciclo via trans
+# ============================================================
 def run_p20f() -> dict:
     X, Y, Z = Var("X"), Var("Y"), Var("Z")
     rules = [
@@ -220,9 +326,16 @@
         "trace_len": len(eng.trace),
         "derived": fact_set(result, filter_source="derived"),
     }
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     lines: list[str] = []
     falhas: list[str] = []
+
+    # ---------- P20a ----------
     lines.append("=== P20a: transitividade ===")
     a = run_p20a()
     lines.append(f"ciclos_usados: {a['ciclos']}")
@@ -236,6 +349,8 @@
     lines.append("")
     if a["derived"] != ["(joao, avo, pedro)"]:
         falhas.append(f"P20a: derived inesperado: {a['derived']}")
+
+    # ---------- P20b ----------
     lines.append("=== P20b: var repetida r(X,X) ===")
     b = run_p20b()
     lines.append(f"ciclos_usados: {b['ciclos']}")
@@ -246,6 +361,8 @@
     esperado_b = ["(a, self, a)", "(b, self, b)"]
     if b["derived"] != esperado_b:
         falhas.append(f"P20b: derived inesperado: {b['derived']} (esperado {esperado_b})")
+
+    # ---------- P20c ----------
     lines.append("=== P20c: duas regras compondo ===")
     c = run_p20c()
     lines.append(f"ciclos_usados: {c['ciclos']}")
@@ -256,6 +373,8 @@
     esperado_c = ["(a, r_sym, b)", "(b, r_inv, a)"]
     if c["derived"] != esperado_c:
         falhas.append(f"P20c: derived inesperado: {c['derived']} (esperado {esperado_c})")
+
+    # ---------- P20d ----------
     lines.append("=== P20d: falha de unificacao ===")
     d = run_p20d()
     lines.append(f"ciclos_usados: {d['ciclos']}")
@@ -263,6 +382,8 @@
     lines.append("")
     if d["derived"] != []:
         falhas.append(f"P20d: derived deveria ser vazio, veio {d['derived']}")
+
+    # ---------- P20e ----------
     lines.append("=== P20e: determinismo (100 runs) ===")
     e = run_p20e()
     lines.append(f"n: {e['n']}")
@@ -270,6 +391,8 @@
     lines.append("")
     if e["unique"] != {("(joao, avo, pedro)",)}:
         falhas.append(f"P20e: nao-deterministico: {e['unique']}")
+
+    # ---------- P20f ----------
     lines.append("=== P20f: ciclo via trans ===")
     f = run_p20f()
     lines.append(f"ciclos_usados: {f['ciclos']}")
@@ -281,6 +404,8 @@
     esperado_f = ["(a, trans, a)", "(b, trans, b)"]
     if f["derived"] != esperado_f:
         falhas.append(f"P20f: derived inesperado: {f['derived']} (esperado {esperado_f})")
+
+    # ---------- veredito ----------
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for item in falhas:
@@ -291,8 +416,10 @@
         lines.append("P20 PASS")
         LOG.info("P20 PASS")
         resultado = 0
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -300,6 +427,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/21_negation_as_failure/README.md
  xml=69 linhas | disco=82 linhas
--- XML:doxoade/research/forward_chaining/poc/21_negation_as_failure/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/21_negation_as_failure/README.md
@@ -1,17 +1,22 @@
+# P21 — Negation as failure (C3, aquecimento)
 
-# P21 — Negation as failure (C3, aquecimento)
 **Contrato:** C1 (Inferência) + C3 (Expressividade com negação).
+
 ## Semântica — DECLARADA
+
 `NOT C` significa "C **não é derivável** do WM atual".
 - C é um **único padrão** nesta PoC (composto → P22).
 - Avaliado contra o **snapshot do ciclo** (herança de P01/P02/P20).
 - Múltiplas negações numa regra = conjunção (todas devem falhar para derivar).
 - Wildcard `_` casa com qualquer valor, **não liga** variável.
+
 **Snapshot é essencial.** Sem ele, `IF NOT done THEN done` entra em loop
 (a negação continua passando depois de derivar `done`). Com snapshot:
 ciclo 1 não tem `done` → deriva; ciclo 2 tem `done` → negação falha.
 P21e testa esse caso.
+
 ## O que prova
+
 - **P21a:** NAF básico — deriva se não há blocker.
 - **P21b:** blocker presente → não deriva.
 - **P21c:** NAF avalia por binding de `X`, não por par `(X,Y)`.
@@ -22,7 +27,9 @@
 - **P21e:** self-defeating quiesce via snapshot (ciclo 2 bloqueia).
 - **P21f:** duas negações conjuntas — 4 sub-casos (none/bad/ugly/both).
 - **P21g:** determinismo em 100 runs.
+
 ## Diferença de P22 (futuro)
+
 | Aspecto | P21 (NAF) | P22 (negação explícita) |
 |---|---|---|
 | Significado | "não provável agora" | "provado que é falso" |
@@ -31,9 +38,11 @@
 | Contradição | impossível | possível (X r Y ∧ X ¬r Y) |
 | Precedente | Prolog, sistemas especialistas | lógica estendida (Well-Founded, ASP) |
 | Custo | baixo | alto (semânticas de contradição) |
+
 NAF cobre ~90% dos casos práticos. P22 fica registrado como direção
 no README, com gatilho: **quando P30 (rewrite) precisar expressar
 "esta construção é proibida"** — ex: "não use `eval()`".
+
 ## O que NÃO prova
 - Negação composta (conjunção interna) → P22.
 - Fatos negativos explícitos → P22.
@@ -42,6 +51,7 @@
   É construto separado. Exemplo: "derivar `(X,not_self,Y)` só se X≠Y"
   exige `X != Y` como builtin, não `NOT (X,r,X)`. Direção candidata a P22
   ou a builtin do matcher. Registrado em `research_directions.md`.
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigação |
 |---|---|---|---|
@@ -50,20 +60,23 @@
 | Wildcard em conclusão | média | alto | `substitute` retorna None |
 | Negação silenciosamente bloqueia | baixa | médio | `LOG.debug` de blocker |
 | Conjunção interpretada como disjunção | média | alto | P21f 4 sub-casos |
+
 ## Planos A / B / C
 - **A (implementado):** NAF por padrão singular, contra snapshot.
 - **B (se NAF não cobrir P30):** NAF composto (conjunção interna). Custo: `unify` recursivo.
 - **C (se B falhar):** migrar para P22 (negação explícita com fatos negativos).
+
 ## Lição
 NAF + snapshot é a combinação minimalista que evita 90% dos loops de
 negação. O ponto sutil: NAF **depende** do estado, e o snapshot é o que
 fixa "qual estado" está sendo consultado. Sem snapshot, NAF é não-monotônica
 e o engine perde a garantia de terminação de P01. P21e é a sonda que separa
 "motor que termina" de "motor que trava em `IF NOT done THEN done`".
+
 NAF e `X != Y` são construtos distintos que costumam ser confundidos:
 - `NOT (X,r,X)` → "não há self-loop em X" (procedural, sobre fatos).
 - `X != Y` → "X e Y têm valores diferentes" (constraint, sobre bindings).
+
 P21c originalmente assumia o segundo, mas o motor implementa o primeiro.
 Teste reformulado para provar o primeiro, e o segundo fica registrado como
 gap — honestamente. Sem essa distinção, P22 herdaria ambiguidade.
-      

■ doxoade/research/forward_chaining/poc/21_negation_as_failure/engine_p21.py
  xml=345 linhas | disco=505 linhas
--- XML:doxoade/research/forward_chaining/poc/21_negation_as_failure/engine_p21.py
+++ DISCO:doxoade/research/forward_chaining/poc/21_negation_as_failure/engine_p21.py
@@ -1,11 +1,44 @@
-
-﻿
+﻿# -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/21_negation_as_failure/engine_p21.py
+"""
+P21 â€” Negation as failure (C3, aquecimento).
+
+Contrato: C1 (Inferencia) + C3 (Expressividade).
+
+NAF: "NOT C" significa "C nao e derivavel do WM atual".
+    - C e um unico padrao (nao composto, nesta PoC).
+    - Avaliado contra o SNAPSHOT do ciclo (consistente com P01/P02/P20).
+    - Multiplas negacoes numa regra = conjuncao.
+    - Wildcard "_" casa com qualquer valor, nao liga.
+
+Snapshot e essencial: sem ele, "IF NOT done THEN done" entra em loop.
+P21e testa esse caso explicitamente.
+
+P21a â€” NAF basico: deriva quando nao ha blocker.
+P21b â€” NAF bloqueia: blocker presente, nao deriva.
+P21c â€” NAF com var repetida: (X,r,X) como negacao exclui self-loops.
+P21d â€” NAF em grafo ciclico: nega a reciproca, nada deriva.
+P21e â€” self-defeating: "IF NOT done THEN done" quiesce via snapshot.
+P21f â€” duas negacoes (conjuncao): ambas devem falhar para derivar.
+P21g â€” determinismo (100 runs de P21a).
+
+DIFERENCA vs P22 (futuro):
+    P21 = NAF (procedural: "nao provavel agora").
+    P22 = negacao explicita (declarativa: "provado que e falso").
+    A distincao vira relevante quando houver fatos negativos.
+
+Rodar: run.bat / run.ps1
+"""
 from __future__ import annotations
+
 import dataclasses
 import logging
 import sys
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc21")
     if logger.handlers:
@@ -15,25 +48,43 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class CycleLimitError(RuntimeError):
     pass
+
+
 class _Wild:
+    """Wildcard: casa com qualquer valor, nao liga variavel."""
     _instance = None
+
     def __new__(cls):
         if cls._instance is None:
             cls._instance = super().__new__(cls)
         return cls._instance
+
     def __repr__(self) -> str:
         return "_"
+
+
 WILD = _Wild()
+
+
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
+
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 Term = str | Var | _Wild
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class TripleFact:
     s: str
@@ -42,10 +93,14 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
     def render(self) -> str:
         return f"({self.s}, {self.p}, {self.o})"
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
@@ -54,6 +109,7 @@
     negations: tuple[Pattern, ...] = ()
     priority: int = 0
     description: str = ""
+
     def conclusion_fact(self, bindings: dict[str, str], cycle: int) -> TripleFact | None:
         resolved = substitute(self.conclusion, bindings)
         if resolved is None:
@@ -61,6 +117,9 @@
         s, p, o = resolved
         return TripleFact(s, p, o, source="derived",
                           rule_id=self.id, cycle=cycle)
+
+
+# ---------- Unificacao ----------
 def unify_term(pattern: Term, value: str,
                bindings: dict[str, str]) -> dict[str, str] | None:
     if isinstance(pattern, _Wild):
@@ -70,6 +129,8 @@
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern: Pattern, fact: TripleFact,
           bindings: dict[str, str]) -> dict[str, str] | None:
     b = bindings
@@ -81,12 +142,14 @@
         return None
     b = unify_term(pattern[2], fact.o, b)
     return b
+
+
 def substitute(pattern: Pattern,
                bindings: dict[str, str]) -> tuple[str, str, str] | None:
     out: list[str] = []
     for t in pattern:
         if isinstance(t, _Wild):
-            return None  
+            return None  # wildcard nao pode ir para conclusao
         if isinstance(t, Var):
             if t.name not in bindings:
                 return None
@@ -94,6 +157,8 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_conditions(conditions: tuple[Pattern, ...],
                      facts: list[TripleFact],
                      bindings: dict[str, str] | None = None
@@ -110,10 +175,16 @@
             continue
         results.extend(match_conditions(tuple(rest), facts, b))
     return results
+
+
 def negation_blocks(neg: Pattern, facts: list[TripleFact],
                     bindings: dict[str, str]) -> bool:
+    """True se o padrao negado encontra QUALQUER match sob bindings."""
     return any(unify(neg, f, bindings) is not None for f in facts)
+
+
 def match_rule(rule: Rule, facts: list[TripleFact]) -> list[dict[str, str]]:
+    """Retorna bindings que satisfazem positivos E todas as negacoes."""
     results: list[dict[str, str]] = []
     for bindings in match_conditions(rule.conditions, facts):
         blocked = False
@@ -126,11 +197,15 @@
         if not blocked:
             results.append(bindings)
     return results
+
+
+# ---------- Engine ----------
 class ForwardChainingEngine:
     def __init__(self, max_cycles: int = 100):
         self.max_cycles = max_cycles
         self.trace: list[dict] = []
         self.cycles_used: int = 0
+
     def run(self, initial_facts: list[TripleFact],
             rules: list[Rule]) -> list[TripleFact]:
         facts: list[TripleFact] = list(initial_facts)
@@ -138,11 +213,15 @@
         cycles = 0
         LOG.info("run: %d fatos, %d regras, max_cycles=%d",
                  len(facts), len(ordered), self.max_cycles)
+
         while cycles < self.max_cycles:
             cycles += 1
             existing = frozenset(f.to_tuple() for f in facts)
+            # Snapshot: negacoes avaliadas sobre `facts` (nao incluindo
+            # derivados deste ciclo). Sem isso, P21e entraria em loop.
             new_facts: list[TripleFact] = []
             seen_in_cycle: set[tuple[str, str, str]] = set()
+
             for rule in ordered:
                 for bindings in match_rule(rule, facts):
                     cf = rule.conclusion_fact(bindings, cycle=cycles)
@@ -155,10 +234,12 @@
                         continue
                     new_facts.append(cf)
                     seen_in_cycle.add(key)
+
             if not new_facts:
                 self.cycles_used = cycles
                 LOG.info("quiescencia em %d ciclo(s)", cycles)
                 return facts
+
             for nf in new_facts:
                 facts.append(nf)
                 self.trace.append({
@@ -168,14 +249,24 @@
                 })
                 LOG.debug("ciclo %d: %s -> %s",
                           cycles, nf.rule_id, nf.render())
+
         raise CycleLimitError(
             f"max_cycles={self.max_cycles} sem quiescencia "
             f"(trace tem {len(self.trace)} entrada(s))"
         )
+
+
 def F(s: str, p: str, o: str) -> TripleFact:
     return TripleFact(s, p, o)
+
+
 def derived_set(facts: list[TripleFact]) -> list[str]:
     return sorted(f.render() for f in facts if f.source == "derived")
+
+
+# ============================================================
+# P21a â€” NAF basico (deriva)
+# ============================================================
 def run_p21a() -> dict:
     X, Y = Var("X"), Var("Y")
     rules = [Rule("R_ok",
@@ -186,6 +277,11 @@
     eng = ForwardChainingEngine(max_cycles=10)
     result = eng.run(facts, rules)
     return {"ciclos": eng.cycles_used, "derived": derived_set(result)}
+
+
+# ============================================================
+# P21b â€” NAF bloqueia
+# ============================================================
 def run_p21b() -> dict:
     X, Y = Var("X"), Var("Y")
     rules = [Rule("R_ok",
@@ -196,7 +292,26 @@
     eng = ForwardChainingEngine(max_cycles=10)
     result = eng.run(facts, rules)
     return {"ciclos": eng.cycles_used, "derived": derived_set(result)}
+
+
+# ============================================================
+# P21c â€” NAF avalia por binding de X, nao por par (X,Y)
+# ============================================================
 def run_p21c() -> dict:
+    """
+    Fatos: (a,r,a), (a,r,b), (b,r,c).
+    Regra: IF (X,r,Y) AND NOT (X,r,X) THEN (X,not_self,Y).
+
+    NAF 'NOT (X,r,X)' significa: "nao existe fato (v,r,v) para o valor
+    de X". E por SUJEITO, nao por par (X,Y).
+
+    - (a,r,a): X=a. Existe (a,r,a) -> BLOCK.
+    - (a,r,b): X=a. Existe (a,r,a) -> BLOCK.
+    - (b,r,c): X=b. Existe (b,r,b)? Nao -> DERIVE (b,not_self,c).
+
+    Isto prova NAF correto. NAO prova exclusao de Y==X (que exigiria
+    constraint X != Y â€” direcao futura, ver README).
+    """
     X, Y = Var("X"), Var("Y")
     rules = [Rule("R_ns",
                   conditions=((X, "r", Y),),
@@ -206,6 +321,11 @@
     eng = ForwardChainingEngine(max_cycles=10)
     result = eng.run(facts, rules)
     return {"ciclos": eng.cycles_used, "derived": derived_set(result)}
+
+
+# ============================================================
+# P21d â€” NAF em grafo ciclico
+# ============================================================
 def run_p21d() -> dict:
     X, Y = Var("X"), Var("Y")
     rules = [Rule("R_oneway",
@@ -216,6 +336,11 @@
     eng = ForwardChainingEngine(max_cycles=10)
     result = eng.run(facts, rules)
     return {"ciclos": eng.cycles_used, "derived": derived_set(result)}
+
+
+# ============================================================
+# P21e â€” self-defeating quiesce via snapshot
+# ============================================================
 def run_p21e() -> dict:
     X = Var("X")
     rules = [Rule("R_done",
@@ -230,12 +355,18 @@
         "trace_len": len(eng.trace),
         "derived": derived_set(result),
     }
+
+
+# ============================================================
+# P21f â€” duas negacoes (conjuncao)
+# ============================================================
 def run_p21f() -> dict:
     X, Y = Var("X"), Var("Y")
     rules = [Rule("R_super",
                   conditions=((X, "r", Y),),
                   negations=((X, "is_bad", WILD), (X, "is_ugly", WILD)),
                   conclusion=(X, "super_ok", Y))]
+
     cases = {}
     for name, extra in (
         ("none", []),
@@ -247,14 +378,26 @@
         result = eng.run([F("a", "r", "b"), *extra], rules)
         cases[name] = derived_set(result)
     return cases
+
+
+# ============================================================
+# P21g â€” determinismo
+# ============================================================
 def run_p21g() -> dict:
     runs: set[tuple[str, ...]] = set()
     for _ in range(100):
         runs.add(tuple(run_p21a()["derived"]))
     return {"n": 100, "unique": runs}
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     lines: list[str] = []
     falhas: list[str] = []
+
+    # ---------- P21a ----------
     lines.append("=== P21a: NAF basico (deriva) ===")
     a = run_p21a()
     lines.append(f"ciclos_usados: {a['ciclos']}")
@@ -264,6 +407,8 @@
     lines.append("")
     if a["derived"] != ["(a, ok, b)"]:
         falhas.append(f"P21a: derived inesperado: {a['derived']}")
+
+    # ---------- P21b ----------
     lines.append("=== P21b: NAF bloqueia ===")
     b = run_p21b()
     lines.append(f"ciclos_usados: {b['ciclos']}")
@@ -271,6 +416,8 @@
     lines.append("")
     if b["derived"] != []:
         falhas.append(f"P21b: derived deveria ser vazio, veio {b['derived']}")
+
+    # ---------- P21c ----------
     lines.append("=== P21c: NAF avalia por binding de X, nao por par (X,Y) ===")
     c = run_p21c()
     lines.append(f"ciclos_usados: {c['ciclos']}")
@@ -282,6 +429,8 @@
         falhas.append(f"P21c: derived inesperado: {c['derived']}")
     if c["derived"] != ["(b, not_self, c)"]:
         falhas.append(f"P21c: derived inesperado: {c['derived']}")
+
+    # ---------- P21d ----------
     lines.append("=== P21d: NAF em grafo ciclico ===")
     d = run_p21d()
     lines.append(f"ciclos_usados: {d['ciclos']}")
@@ -289,6 +438,8 @@
     lines.append("")
     if d["derived"] != []:
         falhas.append(f"P21d: derived deveria ser vazio, veio {d['derived']}")
+
+    # ---------- P21e ----------
     lines.append("=== P21e: self-defeating quiesce via snapshot ===")
     e = run_p21e()
     lines.append(f"ciclos_usados: {e['ciclos']}")
@@ -301,6 +452,8 @@
         falhas.append(f"P21e: derived inesperado: {e['derived']}")
     if e["trace_len"] != 1:
         falhas.append(f"P21e: esperado trace_len 1, veio {e['trace_len']}")
+
+    # ---------- P21f ----------
     lines.append("=== P21f: duas negacoes (conjuncao) ===")
     f = run_p21f()
     for case, outs in f.items():
@@ -314,6 +467,8 @@
         falhas.append(f"P21f(ugly_only): deveria bloquear, veio {f['ugly_only']}")
     if f["both"] != []:
         falhas.append(f"P21f(both): deveria bloquear, veio {f['both']}")
+
+    # ---------- P21g ----------
     lines.append("=== P21g: determinismo (100 runs) ===")
     g = run_p21g()
     lines.append(f"n: {g['n']}")
@@ -321,6 +476,8 @@
     lines.append("")
     if g["unique"] != {("(a, ok, b)",)}:
         falhas.append(f"P21g: nao-deterministico: {g['unique']}")
+
+    # ---------- veredito ----------
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for item in falhas:
@@ -331,8 +488,10 @@
         lines.append("P21 PASS")
         LOG.info("P21 PASS")
         resultado = 0
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -340,6 +499,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/30a_if_return_detect/README.md
  xml=11 linhas | disco=12 linhas
--- XML:doxoade/research/forward_chaining/poc/30a_if_return_detect/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/30a_if_return_detect/README.md
@@ -1,11 +1,12 @@
+# P30a - AST real -> fatos -> inferencia (C2+C3)
 
-# P30a - AST real -> fatos -> inferencia (C2+C3)
 **Contrato:** C2 (Adaptacao) + C3 (Expressividade) sobre AST Python **real**.
 **Nao faz** rewrite (C4). Isso e P30b.
+
 ## Subset declarado
+
 ```
 def NAME(PARAM):
     if COND:
         return VALUE
     return FALLBACK
-      

■ doxoade/research/forward_chaining/poc/30a_if_return_detect/engine_p30a.py
  xml=261 linhas | disco=360 linhas
--- XML:doxoade/research/forward_chaining/poc/30a_if_return_detect/engine_p30a.py
+++ DISCO:doxoade/research/forward_chaining/poc/30a_if_return_detect/engine_p30a.py
@@ -1,11 +1,39 @@
-
+# doxoade/research/forward_chaining/poc/30a_if_return_detect/engine_p30a.py
+"""
+P30a - AST real -> fatos -> inferencia (C2+C3, SEM rewrite).
+
+Contrato: C2 (Adaptacao) + C3 (Expressividade) sobre AST Python real.
+NAO faz rewrite (C4). Isso e P30b.
+
+Subset declarado:
+    def NAME(PARAM):
+        if COND:
+            return VALUE
+        return FALLBACK
+
+    Exatamente: FunctionDef com body de 2 stmts. stmt[0] = If com 1
+    body stmt Return. stmt[1] = Return. Qualquer desvio ->
+    UnsupportedNodeError.
+
+P30a - 'def f(x): if x > 0: return x\\n    return None' deriva
+        (f, pattern, if_return_guard).
+P30b - 'def f(): return 42' -> UnsupportedNodeError.
+P30c - 'x = a + b' -> UnsupportedNodeError (Assign nao e FunctionDef).
+P30d - determinismo (100 runs).
+
+Rodar: run_30a.bat
+"""
 from __future__ import annotations
+
 import ast
 import dataclasses
 import logging
 import sys
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc30a")
     if logger.handlers:
@@ -15,16 +43,27 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class UnsupportedNodeError(RuntimeError):
-    pass
+    """AST node fora do subset declarado."""
+
+
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
+
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 Term = str | Var
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class TripleFact:
     s: str
@@ -33,16 +72,21 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
     def render(self) -> str:
         return f"({self.s}, {self.p}, {self.o})"
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
     conditions: tuple[Pattern, ...]
     conclusion: Pattern
     priority: int = 0
+
     def conclusion_fact(self, bindings: dict[str, str], cycle: int) -> TripleFact | None:
         r = substitute(self.conclusion, bindings)
         if r is None:
@@ -50,6 +94,8 @@
         s, p, o = r
         return TripleFact(s, p, o, source="derived",
                           rule_id=self.id, cycle=cycle)
+
+
 def unify_term(pattern: Term, value: str,
                bindings: dict[str, str]) -> dict[str, str] | None:
     if isinstance(pattern, Var):
@@ -57,6 +103,8 @@
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern: Pattern, fact: TripleFact,
           bindings: dict[str, str]) -> dict[str, str] | None:
     b = bindings
@@ -65,6 +113,8 @@
         if b is None:
             return None
     return b
+
+
 def substitute(pattern: Pattern, bindings: dict[str, str]) -> tuple[str, str, str] | None:
     out: list[str] = []
     for t in pattern:
@@ -75,6 +125,8 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_conditions(conditions: tuple[Pattern, ...],
                      facts: list[TripleFact],
                      bindings: dict[str, str] | None = None) -> list[dict[str, str]]:
@@ -90,11 +142,14 @@
             continue
         results.extend(match_conditions(tuple(rest), facts, b))
     return results
+
+
 class ForwardChainingEngine:
     def __init__(self, max_cycles: int = 100):
         self.max_cycles = max_cycles
         self.trace: list[dict] = []
         self.cycles_used: int = 0
+
     def run(self, initial_facts: list[TripleFact],
             rules: list[Rule]) -> list[TripleFact]:
         facts: list[TripleFact] = list(initial_facts)
@@ -125,9 +180,18 @@
                     "fact": nf.to_tuple(),
                 })
         raise CycleLimitError(f"max_cycles={self.max_cycles}")
+
+
 class CycleLimitError(RuntimeError):
     pass
+
+
+# ============================================================
+# C2 - AST -> fatos
+# ============================================================
+
 def extract_facts(src: str) -> list[TripleFact]:
+    """AST -> fatos. Fora do subset -> UnsupportedNodeError."""
     tree = ast.parse(src)
     if len(tree.body) != 1:
         raise UnsupportedNodeError(f"esperado 1 stmt, veio {len(tree.body)}")
@@ -156,6 +220,7 @@
         raise UnsupportedNodeError(
             f"esperado Return em body[1], veio {type(func.body[1]).__name__}"
         )
+
     f = func.name
     return [
         TripleFact(f, "body_len", str(len(func.body))),
@@ -164,6 +229,12 @@
         TripleFact(f, "if_body_0_kind", type(func.body[0].body[0]).__name__),
         TripleFact(f, "body_1_kind", type(func.body[1]).__name__),
     ]
+
+
+# ============================================================
+# C3 - regra que deriva pattern
+# ============================================================
+
 RULES: list[Rule] = [
     Rule("R_if_return_guard",
          conditions=(
@@ -175,6 +246,12 @@
          ),
          conclusion=(Var("F"), "pattern", "if_return_guard")),
 ]
+
+
+# ============================================================
+# sub-sondas
+# ============================================================
+
 def run_p30a() -> dict:
     src = "def f(x):\n    if x > 0:\n        return x\n    return None"
     facts = extract_facts(src)
@@ -187,6 +264,8 @@
         "derived": derived,
         "ciclos": eng.cycles_used,
     }
+
+
 def _expect_error(src: str) -> dict:
     try:
         extract_facts(src)
@@ -195,20 +274,33 @@
     except Exception as e:
         return {"levantou_erro": True, "type": type(e).__name__}
     return {"levantou_erro": False, "type": None}
+
+
 def run_p30b() -> dict:
     src = "def f(): return 42"
     return {"input": src, **_expect_error(src)}
+
+
 def run_p30c() -> dict:
     src = "x = a + b"
     return {"input": src, **_expect_error(src)}
+
+
 def run_p30d() -> dict:
     outs: set[tuple[str, ...]] = set()
     for _ in range(100):
         outs.add(tuple(run_p30a()["derived"]))
     return {"n": 100, "unique": outs}
+
+
+# ============================================================
+# main
+# ============================================================
+
 def main() -> int:
     lines: list[str] = []
     falhas: list[str] = []
+
     lines.append("=== P30a: AST real -> pattern fatos ===")
     a = run_p30a()
     lines.append(f"input: {a['input']!r}")
@@ -218,8 +310,10 @@
     for d in a["derived"]:
         lines.append(f"  {d}")
     lines.append("")
+
     if a["derived"] != ["(f, pattern, if_return_guard)"]:
         falhas.append(f"P30a: derived inesperado: {a['derived']}")
+
     for label, runner in (("P30b", run_p30b), ("P30c", run_p30c)):
         r = runner()
         lines.append(f"=== {label}: input {r['input']!r} ===")
@@ -230,6 +324,7 @@
             falhas.append(f"{label}: esperado erro, veio OK")
         if r["type"] != "UnsupportedNodeError":
             falhas.append(f"{label}: esperado UnsupportedNodeError, veio {r['type']}")
+
     lines.append("=== P30d: determinismo (100 runs) ===")
     d = run_p30d()
     lines.append(f"n: {d['n']}")
@@ -237,6 +332,7 @@
     lines.append("")
     if d["unique"] != {("(f, pattern, if_return_guard)",)}:
         falhas.append(f"P30d: nao-deterministico: {d['unique']}")
+
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -247,8 +343,10 @@
         lines.append("P30a PASS")
         LOG.info("P30a PASS")
         resultado = 0
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -256,6 +354,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/30b_if_return_rewrite/README.md
  xml=43 linhas | disco=52 linhas
--- XML:doxoade/research/forward_chaining/poc/30b_if_return_rewrite/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/30b_if_return_rewrite/README.md
@@ -1,8 +1,10 @@
+# P30b - Rewrite de AST (C4, puro)
 
-# P30b - Rewrite de AST (C4, puro)
 **Contrato:** C4 (Atuacao). AST + fato -> AST nova via `ast.unparse`.
 **Nao faz:** re-parse do output, re-inferencia, multi-pattern.
+
 ## O que prova
+
 - **P30b-1:** `def f(x): if x > 0: return x\n    return None` vira
   `def f(x): return x if x > 0 else None` (via ast.unparse).
 - **P30b-2:** idempotencia - `rewrite(rewrite(x)) == rewrite(x)` porque
@@ -11,19 +13,25 @@
   (nao levanta erro - nao-match e comportamento valido).
 - **P30b-4:** output compila com `compile()` - codigo emitido e Python valido.
 - **P30b-5:** 100 runs byte-a-byte identicos.
+
 ## Por que idempotencia via nao-match e suficiente
+
 Existem 2 estrategias de idempotencia:
 - **Anotacao**: marcar node com `_rewritten = True` antes de emitir.
 - **Nao-match natural**: apos rewrite, o pattern deixa de casar.
+
 Nao-match e mais simples e prova-se correta: se a transformacao remove
 a condicao de match, reaplicar nao pode disparar. Testado em P30b-2.
+
 Anotacao seria necessaria se o output ainda casasse com o pattern (loop
 de rewrite). Aqui nao acontece - a AST nova nao tem `If` como body[0].
+
 ## O que NAO prova
 - Multi-pattern (for-range-len -> iteracao direta) -> P31.
 - Rewrite sobre AST invalida -> cada `ast.parse` levanta `SyntaxError`,
   testado em P10c.
 - Optimizacao de rewrite (aplicar N regras num passo) -> depois de P31.
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
@@ -31,13 +39,14 @@
 | Nao idempotente | media | critico | P30b-2 rewrite-duplo |
 | Perde informacao no passthrough | media | alto | P30b-3 baseline |
 | Diferenca de unparse entre versoes 3.12.x | media | medio | comentario em expected |
+
 ## Planos A / B / C
 - **A (implementado):** rewrite + unparse + idempotencia via nao-match.
 - **B (se idempotencia falhar em P31):** adicionar `_rewritten` marker.
 - **C (se unparse reformatar demais):** usar `astor` ou `lib2to3` para
   preservar comentarios e formatacao original.
+
 ## Lição
 C4 e o primeiro contrato que produz **artefato externo** (codigo, nao so
 fatos). O teste chave nao e "produziu algo", e "produziu algo que compila
 e que pode ser reprocessado sem mudar". P30b-2 e P30b-4 juntos provam isso.
-      

■ doxoade/research/forward_chaining/poc/30b_if_return_rewrite/engine_p30b.py
  xml=146 linhas | disco=240 linhas
--- XML:doxoade/research/forward_chaining/poc/30b_if_return_rewrite/engine_p30b.py
+++ DISCO:doxoade/research/forward_chaining/poc/30b_if_return_rewrite/engine_p30b.py
@@ -1,10 +1,41 @@
 
+# -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/30b_if_return_rewrite/engine_p30b.py
+"""
+P30b - Rewrite de AST (C4, puro).
+
+Contrato: C4 (Atuacao). AST + fato -> AST nova.
+
+NAO faz:
+- re-parse do output
+- re-inferencia (o fato ja foi derivado por P30a)
+- multi-pattern (so if_return_guard)
+
+Faz:
+- recebe src, detecta padrao if_return_guard
+- reescreve body: [If[Return], Return] -> [Return[IfExp]]
+- ast.unparse -> str
+- idempotencia: rewrite(rewrite(x)) == rewrite(x) via nao-match natural
+- passthrough: input sem padrao fica inalterado
+
+P30b-1 - rewrite de "if x>0: return x\\nreturn None" -> "return x if x>0 else None"
+P30b-2 - idempotencia: 2 rewrites = 1 rewrite
+P30b-3 - passthrough: "def f(x): return x+1" inalterado
+P30b-4 - output compila com compile()
+P30b-5 - determinismo (100 runs)
+
+Rodar: run_30b.bat
+"""
 from __future__ import annotations
+
 import ast
 import logging
 import sys
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc30b")
     if logger.handlers:
@@ -14,9 +45,18 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class RewriteError(RuntimeError):
-    pass
+    """Rewrite encontrou estado invalido (nao deveria acontecer)."""
+
+
+# ============================================================
+# Pattern detection (identico a P30a, inlined)
+# ============================================================
 def is_if_return_guard(func: ast.FunctionDef) -> bool:
     if len(func.body) != 2:
         return False
@@ -29,35 +69,60 @@
     if not isinstance(func.body[1], ast.Return):
         return False
     return True
+
+
+# ============================================================
+# Rewrite (C4)
+# ============================================================
 def rewrite_if_return_guard(src: str) -> str:
+    """
+    Aplica rewrite se pattern casar. Senao, retorna unparse do original.
+    Nao levanta para nao-matches - passthrough e comportamento correto.
+    """
     tree = ast.parse(src)
     if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
         return ast.unparse(tree)
+
     func = tree.body[0]
     if not is_if_return_guard(func):
         return ast.unparse(tree)
+
     if_node = func.body[0]
     then_ret = if_node.body[0]
     else_ret = func.body[1]
+
     new_ifexp = ast.IfExp(
         test=if_node.test,
         body=then_ret.value,
         orelse=else_ret.value,
     )
     new_return = ast.Return(value=new_ifexp)
+
     func.body = [new_return]
     ast.fix_missing_locations(func)
+
     LOG.debug("rewrite aplicado em '%s'", func.name)
     return ast.unparse(tree)
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 SRC_GUARD = "def f(x):\n    if x > 0:\n        return x\n    return None"
 SRC_PASSTHROUGH = "def f(x): return x + 1"
+
+
 def run_p30b_1() -> dict:
     out = rewrite_if_return_guard(SRC_GUARD)
     return {"input": SRC_GUARD, "output": out}
+
+
 def run_p30b_2() -> dict:
     once = rewrite_if_return_guard(SRC_GUARD)
     twice = rewrite_if_return_guard(once)
     return {"once": once, "twice": twice, "idempotent": once == twice}
+
+
 def run_p30b_3() -> dict:
     out = rewrite_if_return_guard(SRC_PASSTHROUGH)
     baseline = ast.unparse(ast.parse(SRC_PASSTHROUGH))
@@ -67,6 +132,8 @@
         "baseline": baseline,
         "passthrough": out == baseline,
     }
+
+
 def run_p30b_4() -> dict:
     out = rewrite_if_return_guard(SRC_GUARD)
     try:
@@ -74,14 +141,23 @@
         return {"output": out, "compiles": True, "error": None}
     except SyntaxError as e:
         return {"output": out, "compiles": False, "error": str(e)}
+
+
 def run_p30b_5() -> dict:
     outs: set[str] = set()
     for _ in range(100):
         outs.add(rewrite_if_return_guard(SRC_GUARD))
     return {"n": 100, "unique": outs}
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     lines: list[str] = []
     falhas: list[str] = []
+
+    # ---------- P30b-1 ----------
     lines.append("=== P30b-1: rewrite if_return_guard -> ternary ===")
     r1 = run_p30b_1()
     lines.append(f"input: {r1['input']!r}")
@@ -89,39 +165,54 @@
     for ln in r1["output"].splitlines():
         lines.append(f"  {ln}")
     lines.append("")
+
     expected_1 = "def f(x):\n    return x if x > 0 else None"
     if r1["output"] != expected_1:
         falhas.append(f"P30b-1: output inesperado: {r1['output']!r}")
+
+    # ---------- P30b-2 ----------
     lines.append("=== P30b-2: idempotencia ===")
     r2 = run_p30b_2()
     lines.append(f"idempotent: {r2['idempotent']}")
     lines.append("")
+
     if not r2["idempotent"]:
         falhas.append(f"P30b-2: nao idempotente (once={r2['once']!r}, twice={r2['twice']!r})")
+
+    # ---------- P30b-3 ----------
     lines.append("=== P30b-3: passthrough (sem pattern) ===")
     r3 = run_p30b_3()
     lines.append(f"input: {r3['input']!r}")
     lines.append(f"passthrough: {r3['passthrough']}")
     lines.append("")
+
     if not r3["passthrough"]:
         falhas.append(
             f"P30b-3: nao preservou (out={r3['output']!r}, base={r3['baseline']!r})"
         )
+
+    # ---------- P30b-4 ----------
     lines.append("=== P30b-4: output compila ===")
     r4 = run_p30b_4()
     lines.append(f"compiles: {r4['compiles']}")
     if r4["error"]:
         lines.append(f"error: {r4['error']}")
     lines.append("")
+
     if not r4["compiles"]:
         falhas.append(f"P30b-4: output nao compila: {r4['error']}")
+
+    # ---------- P30b-5 ----------
     lines.append("=== P30b-5: determinismo (100 runs) ===")
     r5 = run_p30b_5()
     lines.append(f"n: {r5['n']}")
     lines.append(f"unique_count: {len(r5['unique'])}")
     lines.append("")
+
     if len(r5["unique"]) != 1:
         falhas.append(f"P30b-5: {len(r5['unique'])} variacoes")
+
+    # ---------- veredito ----------
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -132,8 +223,10 @@
         lines.append("P30b PASS")
         LOG.info("P30b PASS")
         resultado = 0
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -141,6 +234,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/31_for_range_len/README.md
  xml=61 linhas | disco=78 linhas
--- XML:doxoade/research/forward_chaining/poc/31_for_range_len/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/31_for_range_len/README.md
@@ -1,19 +1,27 @@
+# P31 - for-range-len -> iteracao direta (C4 generaliza?)
 
-# P31 - for-range-len -> iteracao direta (C4 generaliza?)
 **Contrato:** C4 (Atuacao). AST + padrao -> AST nova via ast.unparse.
+
 **Diferenca de P30b:** P31 **nao usa engine**. P30a/b provou que C2+C3->C4
 compõem. P31 isola se C4 generaliza ou e one-shot.
+
 ## Subset declarado
+
 Aceita **apenas**:
+
 ```
 for IDX in range(len(SEQ)):
     <body onde toda ocorrencia de IDX esta dentro de SEQ[IDX]>
 ```
+
 Exatamente: `For.target=Name`, `For.iter=range(len(Name))`, body onde
 `IDX` aparece **somente** como indice de `SEQ`. Qualquer uso livre de
 `IDX` (ex: `print(i)`) -> passthrough.
+
 Nome derivado: `f"{SEQ}_item"` (deterministico, evita colisao com SEQ).
+
 ## O que prova
+
 - **P31a:** rewrite basico. `for i in range(len(x)): print(x[i])` vira
   `for x_item in x: print(x_item)`.
 - **P31b:** idempotencia. Segunda aplicacao e no-op (pattern nao casa mais).
@@ -24,21 +32,29 @@
   de SEQ diferente.
 - **P31f:** output compila.
 - **P31g:** determinismo (100 runs).
+
 ## Por que P31 nao passa pelo engine
+
 Seria possivel derivar `(g, pattern, for_range_len)` via engine e depois
 rewrite no padrao de P30a/b. Mas:
+
 1. C2+C3->C4 ja foi provado em P30a/b.
 2. Adicionar deteccao via engine aqui dobra o custo sem provar nada novo.
 3. A pergunta de P31 e diferente: **C4 generaliza?**
+
 Se no futuro quizermos multi-pattern via engine (ex: `pattern(authority)`
 derivado uma vez, N rewrites), P31 ganha deteccao. Por ora, inline.
+
 ## Limitacao conhecida
+
 `SEQ_item` pode colidir com variavel ja usada no escopo externo. P31
 aceita isso por determinismo. Deteccao de colisao fica para producao.
+
 ## O que NAO prova
 - Range com multiplos args (`range(a, b)`) -> fora do subset.
 - Enumerate patterns (`for i, x in enumerate(...)`) -> futuro.
 - Deteccao de padrao via engine -> nao necessario aqui.
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
@@ -47,6 +63,7 @@
 | Nao idempotente | media | critico | P31b |
 | Output nao compila | baixa | critico | P31f |
 | Mutacao nao-deterministica | baixa | alto | P31g |
+
 ## Planos A / B / C
 - **A (implementado):** rewrite inline, sem engine.
 - **B (se multi-pattern):** padroes viram fatos via engine, rewrite
@@ -54,8 +71,8 @@
 - **C (se P31 falhar em caso real):** abandonar `range-len` - Python
   moderno prefere `enumerate` ou comprehension direta. P31 pode nao
   valer o custo de producao.
+
 ## Licao
 P31 responde a pergunta que P30b deixou em aberto: "C4 e rewrite
 especifico ou mecanismo parametrico?". Se P30b so passou por hardcode,
 P31 expoe. Se P31 passa, a arquitetura suporta N padroes.
-      

■ doxoade/research/forward_chaining/poc/31_for_range_len/engine_p31.py
  xml=232 linhas | disco=338 linhas
--- XML:doxoade/research/forward_chaining/poc/31_for_range_len/engine_p31.py
+++ DISCO:doxoade/research/forward_chaining/poc/31_for_range_len/engine_p31.py
@@ -1,11 +1,40 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/31_for_range_len/engine_p31.py
+"""
+P31 - Segundo padrao de rewrite (C4 puro, sem engine).
+
+Contrato: C4 (Atuacao). AST + padrao -> AST nova via ast.unparse.
+
+Diferenca de P30b:
+    P30b usava fato derivado por P30a. P31 NAO usa engine.
+    Pergunta distinta: C4 generaliza ou e one-shot?
+
+Padrao: for IDX in range(len(SEQ)): <body>  ->  for SEQ_item in SEQ: <body'>
+    - Substitui SEQ[IDX] por SEQ_item em todo o body.
+    - Nome derivado: f"{SEQ}_item" (deterministico).
+    - Validade: toda ocorrencia de IDX deve estar DENTRO de SEQ[IDX].
+    - Uso livre de IDX (ex: print(i)) -> passthrough (nao levanta).
+
+P31a - rewrite basico.
+P31b - idempotencia (rewrite de rewrite = no-op).
+P31c - passthrough: "for x in y: print(x)" nao casa.
+P31d - passthrough: "for i in range(len(x)): print(i)" usa IDX como valor.
+P31e - passthrough: "for i in range(len(x)): print(y[i])" indices diferentes.
+P31f - output compila.
+P31g - determinismo (100 runs).
+
+Rodar: doxoade retro-forward run 31
+"""
 from __future__ import annotations
+
 import ast
 import logging
 import sys
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc31")
     if logger.handlers:
@@ -15,8 +44,16 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
+# ============================================================
+# Padrao: for IDX in range(len(SEQ)):
+# ============================================================
 def _is_range_len_iter(iter_node: ast.AST) -> tuple[str, str] | None:
+    """Retorna (seq_name, index_name) se for range(len(SEQ)), senao None."""
     if not isinstance(iter_node, ast.Call):
         return None
     if not (isinstance(iter_node.func, ast.Name) and iter_node.func.id == "range"):
@@ -33,13 +70,18 @@
     seq_arg = inner.args[0]
     if not isinstance(seq_arg, ast.Name):
         return None
-    return seq_arg.id  
+    return seq_arg.id  # so o seq_name; index vem do target
+
+
 class _BodyChecker(ast.NodeVisitor):
+    """Valida: toda ocorrencia de IDX (Load) esta em SEQ[IDX]."""
+
     def __init__(self, seq_name: str, index_name: str):
         self.seq_name = seq_name
         self.index_name = index_name
         self.free_index_use = False
         self.subscript_count = 0
+
     def visit_Subscript(self, node: ast.Subscript):
         if (
             isinstance(node.value, ast.Name)
@@ -48,21 +90,29 @@
             and node.slice.id == self.index_name
         ):
             self.subscript_count += 1
-            return  
+            return  # consome: nao recursa em SEQ nem em IDX
         self.generic_visit(node)
+
     def visit_Name(self, node: ast.Name):
         if node.id == self.index_name and isinstance(node.ctx, ast.Load):
             self.free_index_use = True
+
+
 def _body_is_valid(body: list[ast.stmt], seq_name: str, index_name: str) -> bool:
     checker = _BodyChecker(seq_name, index_name)
     for stmt in body:
         checker.visit(stmt)
     return not checker.free_index_use and checker.subscript_count > 0
+
+
 class _SeqIndexSubstituter(ast.NodeTransformer):
+    """Substitui SEQ[IDX] por item_name."""
+
     def __init__(self, seq_name: str, index_name: str, item_name: str):
         self.seq_name = seq_name
         self.index_name = index_name
         self.item_name = item_name
+
     def visit_Subscript(self, node: ast.Subscript):
         if (
             isinstance(node.value, ast.Name)
@@ -75,12 +125,23 @@
                 node,
             )
         return self.generic_visit(node)
+
+
+# ============================================================
+# Rewrite (C4)
+# ============================================================
 def rewrite_for_range_len(src: str) -> tuple[str, bool]:
+    """
+    Retorna (new_src, applied).
+    applied=True se algum For foi reescrito; False se passthrough total.
+    """
     try:
         tree = ast.parse(src)
     except SyntaxError:
         return src, False
+
     applied_any = False
+
     for node in ast.walk(tree):
         if not isinstance(node, ast.For):
             continue
@@ -90,12 +151,14 @@
         if seq_name is None:
             continue
         index_name = node.target.id
+
         if not _body_is_valid(node.body, seq_name, index_name):
             LOG.debug(
                 "for range-len com IDX '%s' usado livremente; passthrough",
                 index_name,
             )
             continue
+
         item_name = f"{seq_name}_item"
         subst = _SeqIndexSubstituter(seq_name, index_name, item_name)
         node.body = [subst.visit(stmt) for stmt in node.body]
@@ -104,9 +167,15 @@
         ast.fix_missing_locations(node)
         applied_any = True
         LOG.debug("rewrite aplicado: %s -> %s", index_name, item_name)
+
     if not applied_any:
         return ast.unparse(tree), False
     return ast.unparse(tree), True
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 SRC_P31A = (
     "def g(x):\n"
     "    for i in range(len(x)):\n"
@@ -123,9 +192,13 @@
     "    for i in range(len(x)):\n"
     "        print(y[i])"
 )
+
+
 def run_p31a() -> dict:
     out, applied = rewrite_for_range_len(SRC_P31A)
     return {"input": SRC_P31A, "output": out, "applied": applied}
+
+
 def run_p31b() -> dict:
     once, applied1 = rewrite_for_range_len(SRC_P31A)
     twice, applied2 = rewrite_for_range_len(once)
@@ -135,6 +208,8 @@
         "idempotent": once == twice,
         "applied_2nd": applied2,
     }
+
+
 def _passthrough(src: str) -> dict:
     out, applied = rewrite_for_range_len(src)
     baseline = ast.unparse(ast.parse(src))
@@ -143,12 +218,20 @@
         "passthrough": (out == baseline) and (applied is False),
         "applied": applied,
     }
+
+
 def run_p31c() -> dict:
     return _passthrough(SRC_P31C)
+
+
 def run_p31d() -> dict:
     return _passthrough(SRC_P31D)
+
+
 def run_p31e() -> dict:
     return _passthrough(SRC_P31E)
+
+
 def run_p31f() -> dict:
     out, _ = rewrite_for_range_len(SRC_P31A)
     try:
@@ -156,15 +239,24 @@
         return {"compiles": True, "error": None}
     except SyntaxError as e:
         return {"compiles": False, "error": str(e)}
+
+
 def run_p31g() -> dict:
     outs: set[str] = set()
     for _ in range(100):
         out, _ = rewrite_for_range_len(SRC_P31A)
         outs.add(out)
     return {"n": 100, "unique": outs}
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     lines: list[str] = []
     falhas: list[str] = []
+
+    # ---------- P31a ----------
     lines.append("=== P31a: for-range-len -> direct iteration ===")
     a = run_p31a()
     lines.append(f"input: {a['input']!r}")
@@ -172,11 +264,14 @@
     for ln in a["output"].splitlines():
         lines.append(f"  {ln}")
     lines.append("")
+
     expected_a = "def g(x):\n    for x_item in x:\n        print(x_item)"
     if a["output"] != expected_a:
         falhas.append(f"P31a: output inesperado: {a['output']!r}")
     if not a["applied"]:
         falhas.append("P31a: applied deveria ser True")
+
+    # ---------- P31b ----------
     lines.append("=== P31b: idempotencia ===")
     b = run_p31b()
     lines.append(f"idempotent: {b['idempotent']}")
@@ -186,6 +281,8 @@
         falhas.append("P31b: nao idempotente")
     if b["applied_2nd"]:
         falhas.append("P31b: segunda aplicacao deveria ser no-op")
+
+    # ---------- P31c, P31d, P31e ----------
     for label, fn in (("P31c", run_p31c), ("P31d", run_p31d), ("P31e", run_p31e)):
         r = fn()
         lines.append(f"=== {label}: passthrough ===")
@@ -195,12 +292,16 @@
         lines.append("")
         if not r["passthrough"]:
             falhas.append(f"{label}: deveria ser passthrough")
+
+    # ---------- P31f ----------
     lines.append("=== P31f: output compila ===")
     f = run_p31f()
     lines.append(f"compiles: {f['compiles']}")
     lines.append("")
     if not f["compiles"]:
         falhas.append(f"P31f: output nao compila: {f['error']}")
+
+    # ---------- P31g ----------
     lines.append("=== P31g: determinismo (100 runs) ===")
     g = run_p31g()
     lines.append(f"n: {g['n']}")
@@ -208,6 +309,8 @@
     lines.append("")
     if len(g["unique"]) != 1:
         falhas.append(f"P31g: {len(g['unique'])} variacoes")
+
+    # ---------- veredito ----------
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -218,8 +321,10 @@
         lines.append("P31 PASS")
         LOG.info("P31 PASS")
         resultado = 0
+
     for line in lines:
         print(line)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -227,6 +332,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/50_explain/README.md
  xml=55 linhas | disco=67 linhas
--- XML:doxoade/research/forward_chaining/poc/50_explain/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/50_explain/README.md
@@ -1,11 +1,15 @@
+# P50 - Explainability (C5): positive + negative
 
-# P50 - Explainability (C5): positive + negative
 **Contrato:** C5 (Explicacao).
 `Fatos + Regras + Trace -> Cadeia legivel`.
+
 ## Extensao sobre P20/P21
+
 `TraceEntry` ganha `derived_from: list[tuple]` — os fatos exatos usados
 em cada derivacao. Sem isso, explain() nao pode reconstruir a cadeia.
+
 ## O que prova
+
 - **P50a:** explain(avo(joao,pedro)) -> {rule: R_trans, cycle: 1,
   parents: [pai(joao,maria), pai(maria,pedro)]}.
 - **P50b:** explain_chain(bisavo(joao,ana)) — arvore de 2 niveis:
@@ -17,20 +21,26 @@
 - **P50f:** completeness: 3 derived, 3 trace; todos parents sao seed
   ou derived (grafo fechado).
 - **P50g:** determinismo (100 runs).
+
 ## Limitacao conhecida
+
 `explain_chain` mostra **uma** derivacao (a primeira cronologica). Se um
 fato tem duas derivacoes, so a primeira e exibida. Extensao para "todas
 as derivacoes" fica para producao.
+
 ## why_not e aproximado
+
 `match_with_diagnostic` reporta o **ponto mais profundo** onde todas as
 extensoes morrem. Isso e util para debug mas nao e prova completa: uma
 condicao pode falhar em um caminho mas ter match em outro. Como o
 backtracking explora todos os caminhos, "deepest fail" e o limite
 inferior (garantido insatisfativel quando reportado).
+
 ## O que NAO prova
 - Explicacao de fato com multiplas derivacoes (so a primeira).
 - Explicacao de falha em regra com negacao (P21 nao usado aqui).
 - Explicacao em linguagem natural (fora do escopo C5).
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
@@ -38,6 +48,7 @@
 | explain() em fato nao derivado | media | medio | source=unknown |
 | why_not com deepest_fail impreciso | media | alto | documentado como aproximacao |
 | Grafo quebrado (orfao) | baixa | critico | P50f completeness |
+
 ## Planos A / B / C
 - **A (implementado):** trace com derived_from + explain / explain_chain
   / why_not.
@@ -45,11 +56,12 @@
   fato; explain_chain ganha flag `all_paths=True`.
 - **C (se why_not mais preciso):** backward chaining completo (goal-driven)
   em vez de diagnostic forward. Alinha com `research_directions.md`.
+
 ## Licao
 C5 separa "motor que deriva" de "motor que explica". A diferenca mora no
 trace: saber *que* um fato foi derivado e trivial (basta olhar `facts`);
 saber *como* exige `derived_from`. E explicar *por que nao* exige um
 caminho distinto — backtracking com diagnostico.
+
 Depois de P50, C1-C5 estao cobertos. Falta C6 (mensuracao) e C7
 (substitutibilidade).
-      

■ doxoade/research/forward_chaining/poc/50_explain/engine_p50.py
  xml=429 linhas | disco=583 linhas
--- XML:doxoade/research/forward_chaining/poc/50_explain/engine_p50.py
+++ DISCO:doxoade/research/forward_chaining/poc/50_explain/engine_p50.py
@@ -1,11 +1,47 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/50_explain/engine_p50.py
+"""
+P50 - Explainability (C5): positive + negative.
+
+Contrato: C5 (Explicacao).
+    Fatos + Regras + Trace -> Cadeia legivel.
+
+Extensao sobre P20/P21: TraceEntry ganha derived_from (fatos usados
+em cada derivacao). Com isso:
+
+- explain(F): "F foi derivado pela regra R no ciclo C, a partir de [...]"
+- explain_chain(F): arvore recursiva ate fatos seed
+- why_not(F): "F nao foi derivado. Para cada regra que casaria a
+  conclusao, dizemos qual condicao falhou e com quais bindings."
+
+P50a - explain(avo(joao, pedro))
+P50b - explain_chain(bisavo(joao, ana)) -> arvore 2 niveis
+P50c - why_not(avo(joao, ana)) -> R_trans falha em cond[1]
+P50d - explain(seed) -> source=seed
+P50e - explain(unknown) -> source=unknown
+P50f - completeness: derived tem trace; parents sao seed ou derived
+P50g - determinism (100 runs)
+
+Cenario:
+    Fatos: pai(joao,maria), pai(maria,pedro), pai(pedro,ana)
+    R_trans: pai(X,Y) AND pai(Y,Z) -> avo(X,Z)
+    R_bisavo: avo(X,Y) AND pai(Y,Z) -> bisavo(X,Z)
+
+    Ciclo 1: avo(joao,pedro), avo(maria,ana)
+    Ciclo 2: bisavo(joao,ana)
+
+Rodar: doxoade retro-forward run 50
+"""
 from __future__ import annotations
+
 import dataclasses
 import logging
 import sys
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc50")
     if logger.handlers:
@@ -15,14 +51,22 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class CycleLimitError(RuntimeError):
     pass
+
+
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 @dataclasses.dataclass(frozen=True)
 class Triple:
     s: str
@@ -31,43 +75,61 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
     conditions: tuple
     conclusion: tuple
+
     def conclusion_fact(self, bindings, cycle):
         r = substitute(self.conclusion, bindings)
         if r is None:
             return None
         s, p, o = r
         return Triple(s, p, o, source="derived", rule_id=self.id, cycle=cycle)
+
+
 @dataclasses.dataclass
 class TraceEntry:
     cycle: int
     rule_id: str
     fact: tuple
     derived_from: list
+
+
+# ---------- rendering ----------
 def render_term(t):
     if isinstance(t, Var):
         return t.name
     return str(t)
+
+
 def render(t) -> str:
     return f"({render_term(t[0])}, {render_term(t[1])}, {render_term(t[2])})"
+
+
 def render_bindings(bindings) -> str:
     if not bindings:
         return "{}"
     return "{" + ", ".join(
         f"{k}={v}" for k, v in sorted(bindings.items())
     ) + "}"
+
+
+# ---------- unificacao ----------
 def unify_term(pattern, value, bindings):
     if isinstance(pattern, Var):
         if pattern.name in bindings:
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern, fact_tuple, bindings):
     b = bindings
     for p_t, f_v in zip(pattern, fact_tuple):
@@ -75,6 +137,8 @@
         if b is None:
             return None
     return b
+
+
 def substitute(pattern, bindings):
     out = []
     for t in pattern:
@@ -85,6 +149,8 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
 def match_conditions(conditions, facts, bindings=None):
     if bindings is None:
         bindings = {}
@@ -99,7 +165,10 @@
             continue
         results.extend(match_conditions(rest, facts, b))
     return results
+
+
 def match_with_facts(conditions, facts, bindings=None):
+    """Backtracking com witnesses: [(bindings, [facts_usados_em_ordem])]."""
     if bindings is None:
         bindings = {}
     if not conditions:
@@ -114,10 +183,14 @@
         for sub_b, sub_used in match_with_facts(rest, facts, b):
             results.append((sub_b, [f.to_tuple()] + sub_used))
     return results
+
+
+# ---------- engine ----------
 class Engine:
     def __init__(self, max_cycles=100):
         self.max_cycles = max_cycles
         self.trace: list[TraceEntry] = []
+
     def run(self, initial_facts, rules):
         self.trace = []
         facts = list(initial_facts)
@@ -148,11 +221,16 @@
                     derived_from=used,
                 ))
         raise CycleLimitError(f"max_cycles={self.max_cycles}")
+
+
+# ---------- explicacao positiva ----------
 def find_trace(fact_tuple, trace):
     for entry in trace:
         if entry.fact == fact_tuple:
             return entry
     return None
+
+
 def explain(fact_tuple, trace, seed_tuples) -> dict:
     entry = find_trace(fact_tuple, trace)
     if entry is not None:
@@ -165,6 +243,8 @@
     if fact_tuple in seed_tuples:
         return {"source": "seed"}
     return {"source": "unknown"}
+
+
 def _render_chain(fact_tuple, trace, seed_tuples, indent, lines):
     prefix = "  " * indent
     entry = find_trace(fact_tuple, trace)
@@ -179,11 +259,17 @@
         lines.append(f"{prefix}{render(fact_tuple)} [seed]")
         return
     lines.append(f"{prefix}{render(fact_tuple)} [unknown]")
+
+
 def explain_chain(fact_tuple, trace, seed_tuples) -> list[str]:
     lines: list[str] = []
     _render_chain(fact_tuple, trace, seed_tuples, 0, lines)
     return lines
+
+
+# ---------- explicacao negativa ----------
 def unify_conclusion(conclusion, target_triple):
+    """Unifica conclusao (com Vars) com target (strings). Bindings ou None."""
     bindings: dict[str, str] = {}
     for term, value in zip(conclusion, target_triple):
         if isinstance(term, Var):
@@ -196,9 +282,17 @@
             if term != value:
                 return None
     return bindings
+
+
 def match_with_diagnostic(conditions, fact_tuples, initial_bindings):
+    """Backtracking com diagnostico: (matches, deepest_fail).
+
+    deepest_fail = (idx, cond, bindings) no nivel mais profundo onde
+    todas as extensoes morreram.
+    """
     matches: list = []
     deepest_fail: list = [None]
+
     def recurse(idx, binds):
         if idx == len(conditions):
             matches.append(binds)
@@ -213,10 +307,13 @@
         if not extended:
             if deepest_fail[0] is None or idx > deepest_fail[0][0]:
                 deepest_fail[0] = (idx, conditions[idx], binds)
+
     recurse(0, initial_bindings)
     if matches:
         return matches, None
     return [], deepest_fail[0]
+
+
 def why_not(target_tuple, rules, all_facts, seed_tuples) -> dict:
     fact_tuples = [f.to_tuple() for f in all_facts]
     if target_tuple in fact_tuples:
@@ -243,6 +340,9 @@
     if not explanations:
         return {"status": "no_rule_matches"}
     return {"status": "not_derived", "explanations": explanations}
+
+
+# ---------- completeness ----------
 def check_completeness(facts, trace, seed_tuples) -> dict:
     fact_tuples = {f.to_tuple() for f in facts}
     trace_facts = {e.fact for e in trace}
@@ -261,9 +361,15 @@
         "derived_count": len(derived),
         "trace_count": len(trace),
     }
+
+
+# ============================================================
+# Cenario
+# ============================================================
 X = Var("X")
 Y = Var("Y")
 Z = Var("Z")
+
 RULES = [
     Rule("R_trans",
          conditions=((X, "pai", Y), (Y, "pai", Z)),
@@ -272,34 +378,55 @@
          conditions=((X, "avo", Y), (Y, "pai", Z)),
          conclusion=(X, "bisavo", Z)),
 ]
+
 SEED_FACTS = [
     Triple("joao", "pai", "maria"),
     Triple("maria", "pai", "pedro"),
     Triple("pedro", "pai", "ana"),
 ]
+
 SEED_TUPLES = {(f.s, f.p, f.o) for f in SEED_FACTS}
+
+
 def run_scenario():
     engine = Engine()
     facts, cycles = engine.run(SEED_FACTS, RULES)
     return facts, engine.trace, cycles
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 def run_p50a() -> dict:
     _, trace, _ = run_scenario()
     return explain(("joao", "avo", "pedro"), trace, SEED_TUPLES)
+
+
 def run_p50b() -> list[str]:
     _, trace, _ = run_scenario()
     return explain_chain(("joao", "bisavo", "ana"), trace, SEED_TUPLES)
+
+
 def run_p50c() -> dict:
     facts, _, _ = run_scenario()
     return why_not(("joao", "avo", "ana"), RULES, facts, SEED_TUPLES)
+
+
 def run_p50d() -> dict:
     _, trace, _ = run_scenario()
     return explain(("joao", "pai", "maria"), trace, SEED_TUPLES)
+
+
 def run_p50e() -> dict:
     _, trace, _ = run_scenario()
     return explain(("zed", "avo", "yan"), trace, SEED_TUPLES)
+
+
 def run_p50f() -> dict:
     facts, trace, _ = run_scenario()
     return check_completeness(facts, trace, SEED_TUPLES)
+
+
 def run_p50g() -> dict:
     sigs: set = set()
     for _ in range(100):
@@ -307,9 +434,16 @@
         sig = tuple(sorted((e.rule_id, e.fact) for e in trace))
         sigs.add(sig)
     return {"n": 100, "unique_count": len(sigs)}
+
+
+# ============================================================
+# main
+# ============================================================
 def main() -> int:
     lines: list[str] = []
     falhas: list[str] = []
+
+    # ---------- P50a ----------
     lines.append("=== P50a: explain(avo(joao, pedro)) ===")
     a = run_p50a()
     lines.append(f"fact: {render(('joao', 'avo', 'pedro'))}")
@@ -321,6 +455,7 @@
         for p in a["derived_from"]:
             lines.append(f"  - {render(p)}")
     lines.append("")
+
     if a.get("rule_id") != "R_trans" or a.get("cycle") != 1:
         falhas.append(f"P50a: inesperado: {a}")
     if a.get("derived_from") != [
@@ -328,11 +463,14 @@
         ("maria", "pai", "pedro"),
     ]:
         falhas.append(f"P50a: parents inesperados: {a.get('derived_from')}")
+
+    # ---------- P50b ----------
     lines.append("=== P50b: explain_chain(bisavo(joao, ana)) ===")
     b_result = run_p50b()
     for ln in b_result:
         lines.append(ln)
     lines.append("")
+
     expected_b = [
         "(joao, bisavo, ana) <- R_bisavo @ c2",
         "  (joao, avo, pedro) <- R_trans @ c1",
@@ -342,6 +480,8 @@
     ]
     if b_result != expected_b:
         falhas.append(f"P50b: chain inesperada: {b_result}")
+
+    # ---------- P50c ----------
     lines.append("=== P50c: why_not(avo(joao, ana)) ===")
     c = run_p50c()
     lines.append(f"status: {c['status']}")
@@ -355,6 +495,7 @@
             else:
                 lines.append(f"rule {expl['rule_id']}: {expl['status']}")
     lines.append("")
+
     if c["status"] != "not_derived":
         falhas.append(f"P50c: status inesperado: {c['status']}")
     else:
@@ -369,6 +510,8 @@
                 falhas.append(f"P50c: failed_at idx={idx}, esperado 1")
             if binds != {"X": "joao", "Y": "maria", "Z": "ana"}:
                 falhas.append(f"P50c: bindings inesperados: {binds}")
+
+    # ---------- P50d ----------
     lines.append("=== P50d: explain(seed) ===")
     d = run_p50d()
     lines.append(f"fact: {render(('joao', 'pai', 'maria'))}")
@@ -376,6 +519,8 @@
     lines.append("")
     if d["source"] != "seed":
         falhas.append(f"P50d: source={d['source']}")
+
+    # ---------- P50e ----------
     lines.append("=== P50e: explain(unknown) ===")
     e = run_p50e()
     lines.append(f"fact: {render(('zed', 'avo', 'yan'))}")
@@ -383,6 +528,8 @@
     lines.append("")
     if e["source"] != "unknown":
         falhas.append(f"P50e: source={e['source']}")
+
+    # ---------- P50f ----------
     lines.append("=== P50f: completeness ===")
     f = run_p50f()
     lines.append(f"all_derived_have_trace: {f['all_derived_have_trace']}")
@@ -398,6 +545,8 @@
         falhas.append(f"P50f: derived_count={f['derived_count']}")
     if f["trace_count"] != 3:
         falhas.append(f"P50f: trace_count={f['trace_count']}")
+
+    # ---------- P50g ----------
     lines.append("=== P50g: determinism (100 runs) ===")
     g = run_p50g()
     lines.append(f"n: {g['n']}")
@@ -405,6 +554,8 @@
     lines.append("")
     if g["unique_count"] != 1:
         falhas.append(f"P50g: {g['unique_count']} variacoes")
+
+    # ---------- veredito ----------
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -415,8 +566,10 @@
         lines.append("P50 PASS")
         LOG.info("P50 PASS")
         resultado = 0
+
     for ln in lines:
         print(ln)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -424,6 +577,7 @@
         newline="\n",
     )
     return resultado
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/70_substitutable_matcher/README.md
  xml=64 linhas | disco=82 linhas
--- XML:doxoade/research/forward_chaining/poc/70_substitutable_matcher/README.md
+++ DISCO:doxoade/research/forward_chaining/poc/70_substitutable_matcher/README.md
@@ -1,45 +1,61 @@
+# P70 - Substitutibilidade de matcher (C7) + mensuracao (C6)
 
-# P70 - Substitutibilidade de matcher (C7) + mensuracao (C6)
 **Contrato:** C7 (Substitutibilidade) com C6 (Mensuracao) embutido.
+
 ## Pergunta
+
 Se eu troco o matcher ingenuo por um indexado, o comportamento observavel
 (trace + fatos finais) muda? Se muda, "modular" e teatro.
+
 ## Interface dos matchers
+
 ```python
 match(conditions, negations, facts) -> list[(bindings, witnesses)]
 ```
+
 Dois matchers, mesmo contrato:
 - **NaiveMatcher**: backtracking forcabruto sobre todos os fatos.
 - **IndexedMatcher**: `facts_by_predicate` bucket.
+
 `IndexedMatcher` cai para `facts` inteiro quando predicado e `Var` (nao
 da para indexar sem saber o predicado).
+
 ## O que prova
+
 - **P70a-d:** trace hash identico em 4 cenarios (FizzBuzz-like, transitive,
   NAF, mixed). Nenhum dos dois matchers produz resultado divergente.
 - **P70e:** indexed reduz lookups em cenario com muitos fatos irrelevantes
   (100 labels + 2 seeds). Speedup medido.
 - **P70f:** 100 runs determinam hash estavel nos dois matchers.
+
 ## C6 embutido (mensuracao)
+
 Toda sub-sonda reporta:
 - `cycles`: quantos ciclos ate quiescencia
 - `derived`: quantos fatos derivados
 - `rules_fired`: quantas aplicacoes de regra
 - `lookups`: quantos fatos o matcher examinou (proxy de custo)
+
 C6 nao e sonda separada porque a **metrica e o argumento** de que C7
 importa. Separar seria fragmentar a prova.
+
 ## O que C7 prova
+
 C7 **nao** prova que o indexed e correto em todos os casos possiveis.
 Prova que:
 1. Em cenarios representativos de C1-C6, os matchers sao **observacionalmente
    equivalentes**.
 2. O indexed e **mensuravelmente mais barato** quando ha muitos fatos.
+
 Se um novo PoC introduzir padrao onde os matchers divergem, P70 falha. A
 implementacao do novo matcher precisa respeitar o contrato C7 para entrar.
+
 ## O que NAO prova
 - Correcao do indexed em predicado `Var` (cai para `facts` inteiro, mas
   nao ha teste especifico - `mixed` nao exercita).
 - Substituicao de *outros* componentes (fact store, trace, explain).
   P70 e sobre o matcher.
+
 ## Err table (ProDeNov 5.4)
 | Risco | Prob. | Impacto | Mitigacao |
 |---|---|---|---|
@@ -47,18 +63,20 @@
 | Indexed fica MAIS lento em caso Var | media | medio | P70e mede; se inverter, falha |
 | Trace signature colide (hash) | baixa | alto | SHA-256 de 16 hex chars |
 | Cenario trivial demais | media | alto | mixed_many_facts forca indexacao |
+
 ## Planos A / B / C
 - **A (implementado):** dois matchers, interface comum, 4 cenarios.
 - **B (se cenario novo divergir):** adicionar cenario a lista. C7 falha ate
   matcher ser ajustado.
 - **C (se matchers nao puderem ser equivalentes):** contrato C7 abandona
   "substituibilidade total"; cada PoC declara qual matcher usa.
+
 ## Licao
 C7 e o ultimo contrato porque **e o unico que depende dos outros**.
 Substitutibilidade sem C1-C6 testado nao tem contra o que comparar.
 Apos P70, o kernel esta pronto para promocao.
+
 **Promocao**: o que sobrevive para `src/` nao e nenhum engine de PoC -
 e o **contrato** `Matcher.match(conditions, negations, facts) -> results`.
 A escolha naive vs indexed vira configuracao de producao, nao decisao
 de PoC.
-      

■ doxoade/research/forward_chaining/poc/70_substitutable_matcher/engine_p70.py
  xml=429 linhas | disco=602 linhas
--- XML:doxoade/research/forward_chaining/poc/70_substitutable_matcher/engine_p70.py
+++ DISCO:doxoade/research/forward_chaining/poc/70_substitutable_matcher/engine_p70.py
@@ -1,12 +1,44 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/70_substitutable_matcher/engine_p70.py
+"""
+P70 - Substitutibilidade de matcher (C7) + mensuracao (C6).
+
+Contrato: C7 (Substitutibilidade).
+    Contrato + 2 implementacoes -> mesmo comportamento.
+
+C6 embutido: toda sub-sonda reporta metricas (cycles, facts_derived,
+rules_fired, lookups). O argumento de que indexar vale a pena E a metrica.
+
+INTERFACE DOS MATCHERS:
+    match(conditions, negations, facts) -> list[(bindings, witnesses)]
+
+Dois matchers, mesmo contrato:
+    NaiveMatcher   - backtracking forcabruto sobre todos os fatos
+    IndexedMatcher - bucket por predicado (facts_by_predicate)
+
+P70a - FizzBuzz-like: trace identico nos 2 matchers.
+P70b - Transitive: trace identico.
+P70c - NAF: trace identico (negations tambem indexadas).
+P70d - Mixed predicates (many facts): trace identico.
+P70e - Indexed reduz lookups em P70d (metrico).
+P70f - Determinismo: 100 runs, hash do trace estavel.
+
+Se P70 falha, "modular" e teatro. Se passa, C1-C7 cobertos e a arquitetura
+pode promover para src/.
+
+Rodar: doxoade retro-forward run 70
+"""
 from __future__ import annotations
+
 import dataclasses
 import hashlib
 import logging
 import sys
 from pathlib import Path
+
 LOG_PATH = Path(__file__).parent / "logging.txt"
+
+
 def setup_logging() -> logging.Logger:
     logger = logging.getLogger("poc70")
     if logger.handlers:
@@ -16,16 +48,30 @@
     fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
     logger.addHandler(fh)
     return logger
+
+
 LOG = setup_logging()
+
+
 class CycleLimitError(RuntimeError):
     pass
+
+
+# ============================================================
+# Tipos comuns
+# ============================================================
 @dataclasses.dataclass(frozen=True)
 class Var:
     name: str
+
     def __repr__(self) -> str:
         return f"Var({self.name})"
+
+
 Term = str | Var
 Pattern = tuple[Term, Term, Term]
+
+
 @dataclasses.dataclass(frozen=True)
 class Triple:
     s: str
@@ -34,28 +80,40 @@
     source: str = "seed"
     rule_id: str | None = None
     cycle: int = 0
+
     def to_tuple(self) -> tuple[str, str, str]:
         return (self.s, self.p, self.o)
+
     def render(self) -> str:
         return f"({self.s}, {self.p}, {self.o})"
+
+
 @dataclasses.dataclass(frozen=True)
 class Rule:
     id: str
     conditions: tuple[Pattern, ...]
     conclusion: Pattern
     negations: tuple[Pattern, ...] = ()
+
     def conclusion_fact(self, bindings, cycle):
         r = substitute(self.conclusion, bindings)
         if r is None:
             return None
         s, p, o = r
         return Triple(s, p, o, source="derived", rule_id=self.id, cycle=cycle)
+
+
 @dataclasses.dataclass
 class TraceEntry:
     cycle: int
     rule_id: str
     fact: tuple
     derived_from: list
+
+
+# ============================================================
+# Unificacao (compartilhada pelos dois matchers)
+# ============================================================
 def unify_term(pattern: Term, value: str,
                bindings: dict) -> dict | None:
     if isinstance(pattern, Var):
@@ -63,6 +121,8 @@
             return bindings if bindings[pattern.name] == value else None
         return {**bindings, pattern.name: value}
     return bindings if pattern == value else None
+
+
 def unify(pattern: Pattern, fact_tuple: tuple,
           bindings: dict) -> dict | None:
     b = bindings
@@ -71,6 +131,8 @@
         if b is None:
             return None
     return b
+
+
 def substitute(pattern: Pattern, bindings: dict):
     out = []
     for t in pattern:
@@ -81,15 +143,27 @@
         else:
             out.append(t)
     return (out[0], out[1], out[2])
+
+
+# ============================================================
+# MATCHER 1: naive (backtracking forcabruto)
+# ============================================================
 class NaiveMatcher:
+    """
+    Backtracking que varre TODOS os fatos para cada condicao.
+    Negation as failure tambem varre todos os fatos.
+    """
     name = "naive"
+
     def __init__(self):
         self.fact_lookups = 0
+
     def match(self, conditions, negations, facts):
         self.fact_lookups = 0
         results: list[tuple[dict, list]] = []
         self._recurse(conditions, negations, facts, {}, [], results)
         return results
+
     def _recurse(self, conds, negs, facts, bindings, witnesses, out):
         if not conds:
             for neg in negs:
@@ -108,14 +182,28 @@
                 continue
             self._recurse(rest, negs, facts, b,
                           witnesses + [f.to_tuple()], out)
+
     def stats(self):
         return {"fact_lookups": self.fact_lookups}
+
+
+# ============================================================
+# MATCHER 2: indexed (bucket por predicado)
+# ============================================================
 class IndexedMatcher:
+    """
+    Backtracking com indice facts_by_predicate. Rule.get_conditions com
+    predicado fixo so varre o bucket; predicado com Var cai para todos.
+
+    NAF tambem usa bucket do predicado negado.
+    """
     name = "indexed"
+
     def __init__(self):
         self.fact_lookups = 0
         self._index: dict[str, list] = {}
         self._signature: tuple | None = None
+
     def _ensure_index(self, facts):
         sig = tuple(f.to_tuple() for f in facts)
         if sig == self._signature:
@@ -125,17 +213,20 @@
             idx.setdefault(f.p, []).append(f)
         self._index = idx
         self._signature = sig
+
     def _candidates(self, pattern: Pattern, facts):
         pred = pattern[1]
         if isinstance(pred, Var):
             return facts
         return self._index.get(pred, [])
+
     def match(self, conditions, negations, facts):
         self.fact_lookups = 0
         self._ensure_index(facts)
         results: list[tuple[dict, list]] = []
         self._recurse(conditions, negations, facts, {}, [], results)
         return results
+
     def _recurse(self, conds, negs, facts, bindings, witnesses, out):
         if not conds:
             for neg in negs:
@@ -156,14 +247,21 @@
                 continue
             self._recurse(rest, negs, facts, b,
                           witnesses + [f.to_tuple()], out)
+
     def stats(self):
         return {"fact_lookups": self.fact_lookups}
+
+
+# ============================================================
+# Engine (identico para ambos matchers)
+# ============================================================
 class Engine:
     def __init__(self, matcher, max_cycles: int = 100):
         self.matcher = matcher
         self.max_cycles = max_cycles
         self.trace: list[TraceEntry] = []
         self.rules_fired = 0
+
     def run(self, initial_facts, rules):
         self.trace = []
         self.rules_fired = 0
@@ -198,6 +296,11 @@
                     derived_from=used,
                 ))
         raise CycleLimitError(f"max_cycles={self.max_cycles}")
+
+
+# ============================================================
+# Cenario helper
+# ============================================================
 def run_scenario(facts_builder, rules_builder, matcher):
     facts, rules = facts_builder(), rules_builder()
     eng = Engine(matcher)
@@ -210,13 +313,21 @@
         "rules_fired": eng.rules_fired,
         "lookups": stats["fact_lookups"],
     }
+
+
 def trace_signature(trace: list[TraceEntry]) -> str:
+    """Hash canonico do trace - usado para comparacao entre matchers."""
     parts = []
     for e in trace:
         parts.append(
             f"{e.cycle}|{e.rule_id}|{e.fact}|{tuple(e.derived_from)}"
         )
     return hashlib.sha256(";;".join(parts).encode("utf-8")).hexdigest()[:16]
+
+
+# ============================================================
+# Cenarios (inline, espelhando P00/P20/P21 e stress)
+# ============================================================
 def scenario_fizzbuzz_facts():
     return [
         Triple("n", "div3", "yes"),
@@ -228,6 +339,8 @@
         Triple("n", "div3", "no"),
         Triple("n", "div5", "yes"),
     ]
+
+
 def scenario_fizzbuzz_rules():
     return [
         Rule("R_fb",
@@ -240,13 +353,19 @@
              conditions=(("n", "div3", "no"), ("n", "div5", "yes")),
              conclusion=("n", "out", "buzz")),
     ]
+
+
 X, Y, Z = Var("X"), Var("Y"), Var("Z")
+
+
 def scenario_transitive_facts():
     return [
         Triple("joao", "pai", "maria"),
         Triple("maria", "pai", "pedro"),
         Triple("pedro", "pai", "ana"),
     ]
+
+
 def scenario_transitive_rules():
     return [
         Rule("R_trans",
@@ -256,12 +375,16 @@
              conditions=((X, "avo", Y), (Y, "pai", Z)),
              conclusion=(X, "bisavo", Z)),
     ]
+
+
 def scenario_naf_facts():
     return [
         Triple("a", "r", "b"),
         Triple("c", "r", "d"),
         Triple("c", "is_bad", "yes"),
     ]
+
+
 def scenario_naf_rules():
     return [
         Rule("R_ok",
@@ -269,6 +392,8 @@
              negations=((X, "is_bad", "yes"),),
              conclusion=(X, "ok", Y)),
     ]
+
+
 def scenario_mixed_facts():
     base = [Triple(f"ent_{i}", "label", "x") for i in range(100)]
     base += [
@@ -276,6 +401,8 @@
         Triple("seed", "input", "data"),
     ]
     return base
+
+
 def scenario_mixed_rules():
     return [
         Rule("R_1",
@@ -285,16 +412,26 @@
              conditions=(("seed", "input", "data"),),
              conclusion=("seed", "processed", "yes")),
     ]
+
+
 SCENARIOS = [
     ("fizzbuzz", scenario_fizzbuzz_facts, scenario_fizzbuzz_rules),
     ("transitive", scenario_transitive_facts, scenario_transitive_rules),
     ("naf", scenario_naf_facts, scenario_naf_rules),
     ("mixed_many_facts", scenario_mixed_facts, scenario_mixed_rules),
 ]
+
+
 def run_both(facts_builder, rules_builder):
+    """Roda o mesmo cenario nos dois matchers. Retorna (naive_result, indexed_result)."""
     n = run_scenario(facts_builder, rules_builder, NaiveMatcher())
     i = run_scenario(facts_builder, rules_builder, IndexedMatcher())
     return n, i
+
+
+# ============================================================
+# Sub-sondas
+# ============================================================
 def run_identity_sonda(label, facts_builder, rules_builder) -> dict:
     n, i = run_both(facts_builder, rules_builder)
     n_sig = trace_signature(n["trace"])
@@ -307,23 +444,34 @@
         "naive": n,
         "indexed": i,
     }
+
+
 def run_p70a():
     return run_identity_sonda("fizzbuzz",
                               scenario_fizzbuzz_facts,
                               scenario_fizzbuzz_rules)
+
+
 def run_p70b():
     return run_identity_sonda("transitive",
                               scenario_transitive_facts,
                               scenario_transitive_rules)
+
+
 def run_p70c():
     return run_identity_sonda("naf",
                               scenario_naf_facts,
                               scenario_naf_rules)
+
+
 def run_p70d():
     return run_identity_sonda("mixed_many_facts",
                               scenario_mixed_facts,
                               scenario_mixed_rules)
+
+
 def run_p70e() -> dict:
+    """Indexed reduz lookups em cenario com muitos fatos irrelevantes."""
     n, i = run_both(scenario_mixed_facts, scenario_mixed_rules)
     speedup = (n["lookups"] / i["lookups"]) if i["lookups"] > 0 else 0.0
     return {
@@ -332,7 +480,10 @@
         "speedup": round(speedup, 2),
         "strictly_fewer": i["lookups"] < n["lookups"],
     }
+
+
 def run_p70f() -> dict:
+    """Determinismo: 100 runs do cenario transitive, hash estavel."""
     sigs_naive = set()
     sigs_indexed = set()
     for _ in range(100):
@@ -346,6 +497,11 @@
         "naive_sig": next(iter(sigs_naive)) if len(sigs_naive) == 1 else None,
         "indexed_sig": next(iter(sigs_indexed)) if len(sigs_indexed) == 1 else None,
     }
+
+
+# ============================================================
+# main
+# ============================================================
 def render_stats_line(label, r):
     n = r["naive"]
     i = r["indexed"]
@@ -355,10 +511,15 @@
         f"rules_fired={n['rules_fired']:<3} "
         f"lookups(N/I)={n['lookups']}/{i['lookups']}"
     )
+
+
 def main() -> int:
     lines: list[str] = []
     falhas: list[str] = []
+
     sonda_results = []
+
+    # ---------- identidade em cada cenario ----------
     identity_sondas = [
         ("P70a", "fizzbuzz-like", run_p70a),
         ("P70b", "transitive", run_p70b),
@@ -370,9 +531,11 @@
         sonda_results.append(r)
         lines.append(f"=== {label}: identity em '{name}' ===")
         lines.append(f"identical: {r['identical']}")
+        # sigs vao para logging.txt, nao para stdout
         LOG.info("%s naive_sig=%s indexed_sig=%s",
                  r["label"], r["naive_sig"], r["indexed_sig"])
         if not r["identical"]:
+            # se divergir, EMITE as sigs no stdout para debug
             lines.append(f"  naive_sig:   {r['naive_sig']}")
             lines.append(f"  indexed_sig: {r['indexed_sig']}")
             n_tr = r["naive"]["trace"]
@@ -382,10 +545,14 @@
         lines.append("")
         if not r["identical"]:
             falhas.append(f"{label}: traces divergem em '{name}'")
+
+    # ---------- C6: mensuracao ----------
     lines.append("=== C6: mensuracao por cenario (naive vs indexed) ===")
     for r in sonda_results:
         lines.append(render_stats_line(r["label"], r))
     lines.append("")
+
+    # ---------- P70e: indexed ganha em muitos fatos ----------
     lines.append("=== P70e: indexed reduz lookups (mixed_many_facts) ===")
     e = run_p70e()
     lines.append(f"strictly_fewer: {e['strictly_fewer']}")
@@ -395,6 +562,8 @@
     lines.append("")
     if not e["strictly_fewer"]:
         falhas.append("P70e: indexed NAO reduziu lookups - indexacao inutil")
+
+    # ---------- P70f: determinismo ----------
     lines.append("=== P70f: determinismo (100 runs de transitive) ===")
     f = run_p70f()
     lines.append(f"n:              {f['n']}")
@@ -405,6 +574,8 @@
         falhas.append(f"P70f: naive {f['naive_unique']} variacoes")
     if f["indexed_unique"] != 1:
         falhas.append(f"P70f: indexed {f['indexed_unique']} variacoes")
+
+    # ---------- veredito ----------
     if falhas:
         lines.append(f"FAIL: {len(falhas)} falha(s)")
         for x in falhas:
@@ -415,8 +586,10 @@
         lines.append("P70 PASS")
         LOG.info("P70 PASS")
         resultado = 0
+
     for ln in lines:
         print(ln)
+
     output_path = Path(__file__).parent / "output.txt"
     output_path.write_text(
         "\n".join(lines) + "\n",
@@ -424,6 +597,6 @@
         newline="\n",
     )
     return resultado
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc/CONVENTIONS.md
  xml=66 linhas | disco=92 linhas
--- XML:doxoade/research/forward_chaining/poc/CONVENTIONS.md
+++ DISCO:doxoade/research/forward_chaining/poc/CONVENTIONS.md
@@ -1,7 +1,9 @@
+# Convenções de PoC — forward chaining
 
-# Convenções de PoC — forward chaining
 ## Estrutura fixa por PoC
+
 Cada PoC vive em `poc/XX_name/`:
+
 | Arquivo | Papel | Versionado? |
 |---|---|---|
 | `engine_pXX.py` | código do PoC (entrada única) | sim |
@@ -10,57 +12,81 @@
 | `README.md` | contrato, err table, planos A/B/C | sim |
 | `output.txt` | gerado por engine_pXX.py | **não** (runtime) |
 | `logging.txt` | gerado por engine_pXX.py | **não** (runtime) |
+
 ## Regras
+
 - **Nunca** `run.py` / `run.bat` genéricos. Sempre `engine_pXX` / `run_XX`.
 - Orquestração **apenas** por `.bat` (Windows) ou Python. **Sem `.ps1`, `.sh`.**
 - `expected.txt` **sempre LF** — `engine_pXX.py` escreve `output.txt` em LF, e `fc` compara.
 - `output.txt` e `logging.txt` no `.gitignore` (runtime, não contrato).
 - Sem `__init__.py` por PoC — engines não são importados como módulos.
+
 ## Por que o nome embute o número
+
 `run.bat` genérico funciona em isolamento mas quebra quando se alterna entre pastas em `cmd`. `run_21.bat` diz qual PoC rodou mesmo fora de contexto. Custo: renomear em cada PoC. Ganho: `P21 PASS` no terminal é univocamente rastreável.
+
 ## Rastreio
+
 - `poc/run_all.bat` executa todos os PoCs e reporta PASS/FAIL.
 - `docs/research/poc_notes.md` registra lições por PoC.
 - `docs/Research/forward_chaining/research_directions.md` registra direções deferidas com gatilhos objetivos.
+
 ---
+
 ## ASCII-only em output
+
 `print()` e `expected.txt` **não usam caracteres não-ASCII**. Sem `→`, `ã`, `ê`, `ç`.
+
 Motivo: `cmd`'s codepage (cp850/cp1252) não exibe UTF-8; `fc` compara bytes
 brutos e falha mesmo quando o conteúdo é semanticamente idêntico. `->` em
 vez de `→`. `quiescencia` em vez de `quiescência`. `joao` em vez de `joão`.
+
 Regra técnica: se precisa passar pelo terminal Windows, use ASCII.
 Exceção: se o script escreve direto em arquivo via `write_text(..., encoding="utf-8")`
 e NUNCA imprime na tela, aí UTF-8 é seguro — mas `expected.txt` ainda precisa
 ser ASCII para `fc` funcionar. Simplificação: ASCII sempre.
+
 ---
+
 ## Doctor
+
 `poc/_doctor.py` — utilitario permanente, nao e PoC.
+
 | Comando | Comportamento | Exit code |
 |---|---|---|
 | `py -3.12 _doctor.py` | diagnostico (read-only) | 0 sempre |
 | `py -3.12 _doctor.py --fix` | corrige `run_XX.bat` automaticamente | 0 sempre |
 | `py -3.12 _doctor.py --check` | pre-flight | 1 se problemas |
+
 **O que verifica:**
 1. Estrutura: `engine_pXX.py`, `run_XX.bat`, `expected.txt` existem.
 2. Coerencia: `run_XX.bat` chama `engine_pXX.py` correto.
 3. Conteudo: `engine_pXX.py` contem tokens caracteristicos do PoC (heuristico).
 4. Encoding: `expected.txt` e ASCII-only.
+
 **O que NAO verifica** (deixa para `run_all.bat`):
 - Se `engine_pXX.py` executa sem erro.
 - Se `output.txt` bate com `expected.txt`.
+
 Esses dois ficam com `run_XX.bat` — o doctor valida **estrutura**, nao semantica.
+
 ## Regras operacionais
+
 - **Antes de `copy`/`move`/`ren` entre pastas**: rodar `_doctor.py` primeiro.
 - **Antes de rodar PoC que falhou**: rodar `_doctor.py` primeiro.
 - **Apos reorganizar pastas**: rodar `_doctor.py --fix`.
 - **`run_all.bat` chama `_doctor.py --check` como pre-flight.** Nao desabilitar.
+
 ---
+
 ## Sobre `accept`
+
 `accept` regenera expected.txt a partir de output.txt. Use quando:
 - Output mudou legitimamente (refactor, otimizacao, novo comportamento).
 - Primeiro run de um PoC novo (expected ainda nao existia ou tinha placeholders).
+
 NAO use quando:
 - Voce nao entendeu a divergencia.
 - O engine foi alterado e voce nao sabe por que output mudou.
+
 Antes de `accept`, sempre veja o diff. Antes de commitar, `git diff expected.txt`.
-      

■ doxoade/research/forward_chaining/poc/_doctor.py
  xml=132 linhas | disco=179 linhas
--- XML:doxoade/research/forward_chaining/poc/_doctor.py
+++ DISCO:doxoade/research/forward_chaining/poc/_doctor.py
@@ -1,10 +1,33 @@
+# -*- coding: utf-8 -*-
+# doxoade/research/forward_chaining/poc/_doctor.py
+"""
+Doctor - diagnostico, fix e pre-flight para PoCs de forward chaining.
 
-# -*- coding: utf-8 -*-
+Uso:
+    py -3.12 _doctor.py            # diagnostico (read-only)
+    py -3.12 _doctor.py --fix      # corrige .bat automaticamente
+    py -3.12 _doctor.py --check    # pre-flight (exit 1 se problemas)
+
+Detecta:
+1. Estrutura: engine_pXX.py, run_XX.bat, expected.txt existem?
+2. Coerencia: run_XX.bat chama engine_pXX.py correto?
+3. Conteudo: engine_pXX.py contem tokens caracteristicos de PXX?
+4. Encoding: expected.txt e ASCII-only?
+
+--fix corrige apenas (2). (3) e (4) exigem intervencao humana.
+--check e adequado para uso em run_all.bat como pre-flight.
+"""
 from __future__ import annotations
+
 import re
 import sys
 from pathlib import Path
+
 ROOT = Path(__file__).parent
+
+# (num, folder, tokens_caracteristicos)
+# tokens = strings que DEVEM aparecer no engine_pXX.py correto.
+# Se nao aparecem, o engine provavelmente pertence a outro PoC.
 POCS = [
     ("00", "00_fizzbuzz", ["FIZZBUZZ", "R_fizzbuzz"]),
     ("01", "01_cycle", ["P01a", "CycleLimitError"]),
@@ -16,10 +39,14 @@
     ("30a", "30a_if_return_detect", ["if_return_guard", "P30a"]),
     ("30b", "30b_if_return_rewrite", ["rewrite_if_return_guard", "P30b"]),
 ]
+
+
 def read_text(path: Path, encoding: str = "utf-8") -> str | None:
     if not path.exists():
         return None
     return path.read_text(encoding=encoding, errors="replace")
+
+
 def check_engine(folder: Path, num: str, tokens: list[str]) -> list[str]:
     problems: list[str] = []
     engine_path = folder / f"engine_p{num}.py"
@@ -35,6 +62,8 @@
             f"- se o codigo parece certo, talvez o token esteja errado no doctor"
         )
     return problems
+
+
 def check_bat(folder: Path, num: str, fix: bool) -> list[str]:
     problems: list[str] = []
     bat_path = folder / f"run_{num}.bat"
@@ -42,7 +71,9 @@
     if bat is None:
         problems.append(f"run_{num}.bat FALTANDO")
         return problems
+
     changed = False
+
     m = re.search(r"py -3\.12\s+(\S+)", bat)
     if not m:
         problems.append(f"run_{num}.bat nao chama py -3.12 <script>")
@@ -57,6 +88,7 @@
             changed = True
         else:
             problems.append(f"run_{num}.bat chama '{target}' (esperado '{expected_target}')")
+
     m_echo = re.search(r"echo P(\d+) PASS", bat)
     if m_echo:
         actual_num = m_echo.group(1)
@@ -67,9 +99,11 @@
                 changed = True
             else:
                 problems.append(f"echo diz 'P{actual_num} PASS' (esperado 'P{num} PASS')")
+
     if fix and changed:
         bat_path.write_text(bat, encoding="ascii", newline="\n")
     return problems
+
 def check_expected(folder: Path) -> list[str]:
     problems: list[str] = []
     expected_path = folder / "expected.txt"
@@ -84,32 +118,42 @@
             f"expected.txt nao-ASCII (byte {e.start}): {e.reason}"
         )
     return problems
+
+
 def check_poc(num: str, folder_name: str, tokens: list[str], fix: bool) -> list[str]:
     folder = ROOT / folder_name
     if not folder.exists():
         return [f"pasta {folder_name} nao existe"]
+
     problems: list[str] = []
     problems.extend(check_engine(folder, num, tokens))
     problems.extend(check_bat(folder, num, fix))
     problems.extend(check_expected(folder))
     return problems
+
+
 def main() -> int:
     if "--check" in sys.argv and "--fix" in sys.argv:
         print("ERRO: --check e --fix sao mutuamente exclusivos")
         return 2
     fix = "--fix" in sys.argv
     check_only = "--check" in sys.argv
+
     mode = "FIX" if fix else ("CHECK" if check_only else "DIAG")
     print(f"=== Doctor ({mode}) ===")
     print()
+
     ok_count = 0
     fail_count = 0
     fix_count = 0
+
     for num, folder_name, tokens in POCS:
         problems = check_poc(num, folder_name, tokens, fix)
         print(f"--- {folder_name} ---")
+
         real_problems = [p for p in problems if not p.startswith("[FIX]")]
         fixes = [p for p in problems if p.startswith("[FIX]")]
+
         if not real_problems and not fixes:
             print("  OK")
             ok_count += 1
@@ -120,13 +164,16 @@
                 fail_count += len(real_problems)
             fix_count += len(fixes)
         print()
+
     print(
         f"Resumo: {ok_count}/{len(POCS)} PoCs OK | "
         f"{fail_count} problema(s) | {fix_count} fix(es) aplicado(s)"
     )
+
     if check_only and fail_count > 0:
         return 1
     return 0
+
+
 if __name__ == "__main__":
     sys.exit(main())
-      

■ doxoade/research/forward_chaining/poc_notes.md
  xml=566 linhas | disco=772 linhas
--- XML:doxoade/research/forward_chaining/poc_notes.md
+++ DISCO:doxoade/research/forward_chaining/poc_notes.md
@@ -1,5 +1,5 @@
-
 ## P00 — FizzBuzz (C1) — 2026.11.09YMD
+
 **Pergunta:** o kernel termina, deriva e rastreia sobre 100 inputs?
 **Resultado:** PASS 100/100 em [N] ms.
 **Ciclos máximos observados:** 2 (n=15, n=30, ..., ciclo 1 dispara, ciclo 2 fecha).
@@ -9,8 +9,11 @@
 **Lição:** FizzBuzz é um teste de *terminação + determinismo*, não de conflito.
 Qualquer FizzBuzz que “passa” sem checar o oráculo é teatro — daí o `main()`
 comparar com `reference()` antes de imprimir.
----
+
+---
+
 ## P01 — ciclo e falha loud (C1) — 2026.11.09YMD
+
 **Pergunta:** o kernel termina em ciclo de regras? Falha loud em limite?
 **Resultado:** PASS 2/2 após escolha semântica.
 **Lição:** "ciclo" é decisão de contrato, não detalhe. Adotada semântica B
@@ -20,8 +23,11 @@
 inalterado (saída idêntica). P02 herdará B.
 **Contrato consolidado:** `Engine.run` = { snapshot, match, fire, merge }
 por ciclo. `max_cycles` = rodadas de match.
----
+
+---
+
 ## P02 — conflito e determinismo (C1) — YYYY-MM-DD
+
 **Pergunta:** prioridade resolve conflito? Determinismo em 100 runs?
 **Resultado:** PASS 4/4.
 **Lição operacional:** cópia de `run.bat` precisa de edição explícita do
@@ -32,20 +38,28 @@
 **Contrato consolidado:** C1 fechado em três sondas (P00 terminação,
 P01 ciclo + falha loud, P02 conflito + determinismo). Engine pode ser
 congelado.
----
+
+---
+
 ## Princípio de verbosidade (C-verb)
+
 **Decisão:** verbosidade de fatos, chaves e regras não é problema em
 fase PoC. É controle e qualidade. Abusar.
+
 **Implicações:**
 - Chave discriminada (`.kind`, `.name`, `.value`) é padrão, não exceção.
 - Triplas explícitas `(s, p, o)` preferíveis a encoding comprimido.
 - Variável explícita (`Var("X")`) preferível a convenção de string (`"?X"`).
 - Repetição entre PoCs aceitável; DRY só quando o contrato estabiliza.
 - Custo de LOC é menor que custo de ambiguidade descoberta em P70.
+
 **Escopo:** só fase PoC. Revisão em P70 — a consolidação pode comprimir
 o que a fase de sondas decidiu por verbosidade.
----
+
+---
+
 ## P20 — unificação (C1+C3) — YYYY-MM-DD
+
 **Resultado:** PASS 6/6 após corrigir expected (2 linhas).
 **Lição operacional:** `expected.txt` é uma asserção do contrato, não um
 palpite. P20d e P20f erraram `ciclos_usados` porque escrevi o número que
@@ -54,8 +68,11 @@
 **Contrato consolidado:** triplas `(s,p,o)` + `Var` + `Wildcard` (futuro).
 `Rule.conclusion_fact` retorna None se houver var livre → warning.
 `match_conditions` retorna **todas** as bindings (não só a primeira).
----
+
+---
+
 ## P21 — NAF (C3) — YYYY-MM-DD
+
 **Resultado:** PASS 7/7 após reformular P21c.
 **Lição:** NAF e `X != Y` são construtos distintos. O primeiro consulta
 fatos ("não há self-loop em X"); o segundo consulta bindings ("X ≠ Y").
@@ -64,8 +81,11 @@
 **Segunda lição:** quando a asserção falha, primeiro checar se o teste
 descreve corretamente o contrato. "Motor está errado" é hipótese, não
 conclusão.
----
+
+---
+
 ## Correção 2025-11-09 — encoding + P00/P01
+
 **Problema 1:** `00_fizzbuzz/engine_p00.py` continha código de P01.
 **Problema 2:** `→` e `ê` quebravam `fc` por encoding UTF-8 lido como cp850.
 **Fix:** restaurar FizzBuzz em P00; mover P01 para `01_cycle/`; ASCII-only em output.
@@ -73,12 +93,17 @@
 `expected.txt`. `->` no lugar de `→`, `quiescencia` sem acento.
 **Lição:** `cmd` no Windows 10 não exibe UTF-8 nem normaliza comparações.
 `fc` é byte-a-byte. Sem ASCII, o teste é refém do codepage da sessão.
----
+
+---
+
 ## Correção 2025-11-09 (segunda) — ordem de operações
+
 **Problema:** `copy` de arquivos entre pastas foi feito ANTES de aplicar
 as versões corrigidas de P00 e P01. Resultado: dois arquivos com o mesmo
 conteúdo (o de P01), e `run_XX.bat` chamando `engine_pYY.py` errado.
+
 **Lição operacional (adicionar em CONVENTIONS.md):**
+
 1. Quando uma PoC falha por contrato mal-declarado, o fix vem ANTES de
    copiar/mover arquivos. Copiar primeiro espalha o erro.
 2. Se for necessário mover código de uma pasta para outra, mover o
@@ -86,42 +111,58 @@
 3. `run_XX.bat` não é genérico. Renomear `run_00.bat` para `run_01.bat`
    não funciona se o conteúdo não for atualizado também.
 4. Rodar `diagnose.bat` após qualquer reorganização de pastas.
----
+
+---
+
 ## Doctor - introduzido 2025-11-09
+
 **Motivo:** dois arquivos com conteudo trocado (00_fizzbuzz tinha P01,
 01_cycle tinha P00) passaram despercebidos porque `fc` foi executado
 com `.bat` apontando para arquivos inexistentes.
+
 **Solucao:** `_doctor.py` com 3 modos:
 - `--check`: pre-flight, exit 1 se problemas
 - `--fix`: corrige `run_XX.bat` automaticamente
 - (padrao): diagnostico read-only
+
 **Verifica:**
 1. Estrutura (arquivos existem).
 2. Coerencia (`.bat` chama `engine_pXX.py` correto).
 3. Conteudo (engine tem tokens caracteristicos do PoC).
 4. Encoding (expected ASCII-only).
+
 **Integracao:** `run_all.bat` chama `_doctor.py --check` como primeiro
 passo. Pre-flight bloqueia execucao se doctor falha.
+
 **Licao:** quando o laboratorio cresce (>5 PoCs), integridade estrutural
 nao pode ser checada por inspecao visual. Doctor e ortogonal a `pytest`
 (testes de comportamento) e a `fc` (comparacao de output). Cada um
 verifica uma camada diferente do laboratorio.
----
+
+---
+
 ## Doctor false positive — 2025-11-09
+
 **Bug:** token `R_00` em P01 é gerado por format string `f"R_{i:02d}"`,
 não aparece literal no arquivo. Doctor acusou "conteúdo errado" em
 arquivo correto.
+
 **Fix:** token trocado para `CycleLimitError` (literal). Doctor agora
 mostra `encontrados [...]` e `faltando [...]` — false positive fica
 visível mesmo se o check falhar.
+
 **Lição:** tokens de verificação devem ser **literais** no arquivo.
 Format strings, `f-string`, concatenação dinâmica — nada disso serve.
 Regra: se não aparece em `findstr <token> <arquivo>`, não serve como
 token de doctor.
+
 **Segunda lição:** doctor que só diz "não bate" é um doctor cego.
 Mostrar o que **bateu** transforma diagnóstico em diagnóstico acionável.
----
+
+---
+
 ## Q00 - baseline classifier (DC2) - YYYY-MM-DD
+
 **Resultado:** PASS apos fix de expected (cycles 3 -> 2 em 3 casos).
 **Licao:** "cycles" e a segunda metrica mais dificil de prever a mao
 (a primeira e `trace_len`). O motivo: o ciclo que quiesce tambem conta.
@@ -129,198 +170,277 @@
 verifica e nao acha nada -> retorna cycles_used=2. Nao e "1 ciclo de
 trabalho + 1 de quiescencia = 2", e sim "2 rodadas, a segunda e a de
 confirmacao".
+
 **Regra para proximos PoCs:** quando o engine reporta `cycles`, derivar
 a mao ANTES de rodar. O numero nao e "quantos disparos" — e "quantas
 rodadas de match ate quiescencia".
+
 **Nao usar `accept` para esconder isso.** `accept` e para mudanca
 legitima de comportamento (P70). Aqui era erro de calibracao.
----
+
+---
+
 ## Convenção: expected_<num>.txt
+
 **Decisão 2025-11-10:** expected files levam o num do PoC no nome:
 `expected_00.txt`, `expected_q00.txt`, etc. Generico vira "arquivo
 qualquer" quando ha 13 PoCs na mesma arvore.
+
 **Migracao:** rodada uma vez com `_rename_expected.bat`. `_discover_pocs`
 usa `expected_<num>.txt` estritamente (sem fallback).
+
 **Debug (camada 1):** `doxoade retro-forward run <poc> --debug` mostra
 stdout do engine mesmo em PASS. `trace <poc>` e alias.
+
 **Debug (camada 2, futuro):** cada engine responde a `--debug` em
 `sys.argv` e dumpa trace estruturado (`[DEBUG] cycle N: ...`). Q00
 primeiro, resto incremental.
----
+
+---
+
 ## Convenção: expected_<num>.txt
+
 **Decisão 2025-11-10:** expected files levam o num do PoC no nome:
 `expected_00.txt`, `expected_q00.txt`, etc. Generico vira "arquivo
 qualquer" quando ha 13 PoCs na mesma arvore.
+
 **Migracao:** rodada uma vez com `_rename_expected.bat`. `_discover_pocs`
 usa `expected_<num>.txt` estritamente (sem fallback).
+
 **Debug (camada 1):** `doxoade retro-forward run <poc> --debug` mostra
 stdout do engine mesmo em PASS. `trace <poc>` e alias.
+
 **Debug (camada 2, futuro):** cada engine responde a `--debug` em
 `sys.argv` e dumpa trace estruturado (`[DEBUG] cycle N: ...`). Q00
 primeiro, resto incremental.
----
+
+---
+
 ## Camada 2 — debug estruturado (2025-11-10)
+
 **Decisao:** engines respondem a `--debug` em `sys.argv` e dumpam
 `[DEBUG]` em stderr. Output normal (stdout -> output.txt) nao muda.
 `expected_q00.txt` permanece identico.
+
 **Razao:** PASS binario nao e suficiente — queremos feedback de "dados
 de logistica": quantos fatos, quantas tentativas de match, quais foram
 sombreados, tempos por fase. Tudo em stderr para nao contaminar o
 contrato (output.txt) e nao afetar `fc`.
+
 **Formato:** prefixo `[DEBUG]`, one-line per event, agrupado por
 funcao (sub-sonda) e depois agregado. Estrutura:
 - Header: engine, mode, args
 - Per function: seed facts, cycle history (matches/candidates/winners/
   shadowed/idempotent/quiescence), result, timing
 - Per aggregate: total_* + per_rule_attempts + avg_cycles + total_time
+
 **Integracao com `retro-forward`:**
 - `run <poc> --debug` passa `--debug` ao subprocess e mostra stdout+stderr
 - `trace <poc>` e alias
 - `run <poc>` (sem debug) continua so comparando output.txt
+
 **Incremental:** Q00 primeiro (formato fixado). P00/P02 seguem (kernel
 didatico). P10/P30/P50/P70 depois (menor retorno). Q01+ herdam padrao.
----
+
+---
+
 ## Debug em P00 e P02 (2025-11-10)
+
 **Decisao:** aplicar o padrao de Q00 em P00 (kernel puro) e P02
 (conflito). Ambos sao "didaticos" — quem quer entender o motor ve
 a derivacao ciclo-a-ciclo.
+
 **P00 debug:** bulk aggregate (100 FizzBuzz) + trace completo (n=15).
 Semantica A (continuous scan, sem snapshot) e declarada no header do
 debug para evitar confusao com P01+ (B, snapshot).
+
 **P02 debug:** 4 sub-sondas. Cada uma mostra cycles com candidates,
 winners com `reason` (first_candidate | higher_priority |
 equal_priority_first_wins | outranked_by_higher_priority), shadowed,
 idempotent, already_shadowed. P02d destaca o tie-break mostrando
 as duas ordens lado a lado.
+
 **`reason` como artefato de teste:** cada linha `winner [reason]` do
 debug e um assert implicito. Se um novo caso alterar a razao
 inesperadamente, o diff mostra antes de qualquer teste binario falhar.
+
 **Nao aplicado ainda:** P01 (ciclo + limite), P10/P11/P30a (AST),
 P30b/P31 (rewrite), P50 (explain), P70 (matcher). P00 e P02 sao os
 mais uteis por serem kernel; o resto tem output normal ja explicativo.
 Backfill incremental, um a um, quando util.
----
+
+---
+
 ## Regressão em P02 v2 (2025-11-10)
+
 **Bug:** ao adicionar debug, renomeei o `reason` de `higher_priority`
 para `kept_first_candidate` no branch `else` da resolução de conflito.
 O `output.txt` continuou correto em conteúdo (R_high venceu), mas o
 texto do `reason` mudou. `fc` pegou — expected não bateu.
+
 **Raiz:** `kept_first_candidate` e `higher_priority` não são
 sinônimos no branch else. O `else` cobre dois casos:
 - prioridades iguais → quem veio primeiro vence (por ordem)
 - prioridades diferentes (novo < antigo) → quem já estava vence
   porque tem prioridade MAIOR
+
 No segundo caso, o vencedor venceu por **prioridade**, não por
 "ser o primeiro candidato". Renomear para `kept_first_candidate`
 perde a informação semântica — em produção, ver `kept_first_candidate`
 sugere tie-break quando na verdade foi prioridade.
+
 **Lição:** quando renomear um `reason`/`status`, verificar **todos
 os casos que caem no branch** antes. Um `else` que cobre dois
 caminhos semânticos diferentes não pode ter um único rótulo que
 descreva só um deles.
+
 **ProDeNov 1.3 confirmado:** a revisão de regressão (fc/diff) pegou
 o bug em segundos. Sem ela, a mudança teria passado silenciosamente
 e só apareceria quando alguém dependesse do `reason` em produção.
+
 **Ação:** manter `higher_priority` como `reason` estável. O
 `cycle_history` (debug) pode adicionar refinamento adicional sem
 alterar o texto público do output.
+
 ---
 ## Q01 - multi-dimensional classifier (2025-11-10)
+
 **Resultado:** PASS 5/5.
+
 **Licao principal:** DC2 generaliza para N dimensoes **sem mudar engine**.
 Conflito por `(subject, predicate)` e a primitiva certa. Dimensoes
 distintas nunca colidem.
+
 **Desafio real (nao do engine, da extracao):** docstring muda
 `body[0]` de `Return`/`Expr(Call)` para `Expr(Constant(str))`. Se
 extracao fosse ingenua, R_arith falharia silenciosamente em funcao
 com docstring. `ast.get_docstring` + filtragem explicita resolve.
+
 **Design decision:** has_docstring e SEED, nao derivado. Docstring e
 metadata; extrair como fato separado e mais honesto que derivar com
 regra. `trace_len` reflete isso: 1 (so category e derivada), nao 2.
+
 **Proximo (Q02):** complexidade ciclomatica como 3a dim. Primeira dim
 com valor nao-booleano (inteiro 1..N). Testa se engine suporta
 predicados com valores diversos (deve funcionar - nao ha constraint).
+
 **Backlog debug:** Q00, Q01 tem debug completo. P30b, P31, P50, P70
 tem output normal so. Backfill so quando falharem de forma obscura.
----
+
+---
+
 ## QUIET context manager — 2025-11-10
+
 **Problema:** loops de determinismo (Q00e, Q01e, P02c) chamam a funcao
 principal 100x, e cada chamada emite debug completo. Resultado: 100
 blocos identicos no stderr. Sinal vira ruido.
+
 **Solucao:** context manager `QUIET` que suspende `_dbg` durante o loop.
 Depois do `with QUIET:`, o agregado resume o que importa.
+
 **Aplicado em:** Q00, Q01, P02.
+
 **Nao aplicado em:** P00 (bulk loop ja chama `solve_with_engine` sem
 `_dbg`), P01 (sem loop), P10/P11/P30a/P30b/P31/P50/P70 (sem debug ainda).
+
 **Regra para novos PoCs:** todo loop que chame funcao com `_dbg` deve
 envolver `with QUIET:`. Agregado fora do QUIET. Sem excecao.
----
+
+---
+
 ## QUIET aplicado em P02 (2025-11-10)
+
 **Bug:** `_Quiet` e `QUIET` foram criados em `engine_p02.py`, `_dbg` foi
 modificado para checar `QUIET.level == 0`, mas `run_p02c` ficou sem
 `with QUIET:` envolvendo o loop. Resultado: 100 blocos de P02a no stderr
 mesmo com infraestrutura instalada.
+
 **Causa:** infraestrutura (QUIET + _dbg) e uso (`with QUIET:`) sao duas
 edicoes separadas. Aplicar uma e esquecer a outra da falsa sensacao de
 "ja consertei" — o codigo compila, `run_p02c` funciona, so o ruido
 continua.
+
 **Regra para o proximo `_dbg` refactor:** quando uma correcao envolve
 N arquivos e cada arquivo precisa de **duas** edicoes (infra + uso),
 checar explicitamente cada par. `findstr /C:"with QUIET:"` deve retornar
 pelo menos uma linha por engine que usa loop em massa.
+
 **Nao regride comportamento:** QUIET nao afeta output.txt, so stderr.
 `PASS: 14 | FAIL: 0` se mantem.
----
+
+---
+
 ## QUIET em P02 — pendencia (2025-11-10)
+
 **Estado:** infraestrutura (`_Quiet` + `QUIET` + `_dbg` modificado) e uso
 (`with QUIET:` em `run_p02c`) ainda nao estao em `engine_p02.py`.
 Diagnostico: `findstr /C:"with QUIET:" engine_p02.py` retorna vazio, e
 trace 02 continua com 100 blocos de P02a.
+
 **Fix:** colar bloco 2A (infra) + 2B (run_p02c) no arquivo.
+
 **Verificacao:** `findstr /C:"with QUIET:"` retorna 1 linha apos o fix.
 `doxoade retro-forward trace 02` cai de ~1500 linhas para ~160.
+
 **Nao muda contrato:** `output.txt` inalterado, `PASS: 14` mantem.
----
+
+---
+
 ## QUIET em P02 — fechado 2025-11-10
+
 **Estado final:** infra (`_Quiet` + `QUIET` + `_dbg` modificado) ja estava
 em `engine_p02.py`. Faltava apenas `with QUIET:` envolvendo o `for i in
 range(100)` dentro de `run_p02c`.
+
 **Fix:** uma edicao so — `with QUIET:` + indentacao do `for`. Bloco
 `if DEBUG and i > 0: pass` removido (dead code).
+
 **Verificacao:** `findstr /C:"with QUIET:" engine_p02.py` retorna 1 linha.
 `trace 02` cai de ~1500 para ~160 linhas.
+
 **Licao operacional:** `start cd <path>` abre nova janela; nao muda o
 cwd da sessao atual. Apos `start`, verificar com `cd` puro que esta
 no diretorio certo antes de `findstr`/`type`. O comando falhou antes
 por isso — nao era arquivo ausente.
+
 **Nao regride:** `output.txt` inalterado, `PASS: 14` mantem.
----
+
+---
+
 ## q01 "timeout" — bug real era SyntaxError + rescue interativo
+
 **Sintoma observado:** `retro-forward all` reportou `q01_multi_dim: FAIL
   engine falhou: timeout (60s)`. Nenhum stderr.
+
 **Realidade (descoberta com o patch de partial-output):** `engine_q01.py`
 linha 491 tinha `_dbg(f"  n: 100")a` — um `a` orfao apos o `)`. SyntaxError
 em parse. O rescue interativo do doxoade interceptou, exibiu menu
 "Sua decisao (ex: 34):" e ficou esperando `input()`.
+
 **Por que 60s:** o subprocess esperou o menu. `_run_engine` matou por
 timeout. Diagnostico do tempo era "engine lento" quando na verdade
 era "engine crashou em <1s e o rescue travou em input()".
+
 **Causa raiz:** copy-paste do `run_p02c` (texto `P02c determinismo
 (100 runs de P02a)`) dentro de `engine_q01.py::run_q01e`, com `a`
 extra no fim de `_dbg(f"  n: 100")a`.
+
 **Fixes aplicados:**
 1. `engine_q01.py::run_q01e` restaurado (com `with QUIET:` correto,
    texto `Q01e`/`Q01a`, sem `a` orfao).
 2. `_run_engine` (`retro_forward_cmd.py`) adicionado `stdin=subprocess.DEVNULL`
    para rescue/`input()` falhar rapido em vez de hang 60s.
 3. `run_p02c` em `engine_p02.py` adicionado `with QUIET:`.
+
 **Licao 1 — rescue interativo e hostil a subprocess:** qualquer
 sistema de rescue com `input()` bloqueia automacao. `stdin=DEVNULL`
 e a mitigacao minima; ideal e o rescue detectar `not sys.stdin.isatty()`
 e auto-escolher opcao segura.
+
 **Licao 2 — SyntaxError em engine nao e "engine lento":** o rescue
 transforma um erro de 0.1s num hang de 60s. Diagnostico por timeout
 mascara a causa real. `stdin=DEVNULL` desmascara.
+
 **Licao 3 — copy-paste entre PoCs migra texto errado:** `run_p02c`
 tem texto `P02c`, `run_q01e` deve ter `Q01e`. Se fosse so o `a` orfao
 eu consertaria em 1 linha. Mas como o bloco inteiro era P02 em Q01,
@@ -328,14 +448,19 @@
 QUIET:` em nova funcao, **nao copiar de outro PoC** — digitar o
 texto do PoC correto do zero, e usar `findstr /C:"run_pXX"` para
 verificar o nome.
+
 **Pendencia:** `run_p02c` em `engine_p02.py` ainda sem `with QUIET:`
 (efeito: trace 02 ainda poluido). Fix trivial, aplicar quando
 revisitar P02.
----
+
+---
+
 ## Diagnosis gap no rescue + typo em q01 — 2025-11-10
+
 **Sintoma:** typo em `engine_q01.py:491` (`_dbg(f"  n: 100")a` com `a`
 orfao) bloqueou `q01`. Rescue mostrou `<unknown>:491` mesmo com o
 arquivo em maos.
+
 **Camadas de perda de informacao (ordenadas por gravidade):**
 1. `py -c "ast.parse(open('X.py').read())"` — sem `filename=`, o
    SyntaxError perde o path (`<unknown>`).
@@ -343,6 +468,7 @@
    `open('engine_q01.py', ...)`).
 3. `retro-forward run` bloqueou em `input()` do rescue por 60s
    (`timeout (60s)` disfarcando um crash de 0.1s).
+
 **Fixes:**
 - Fix 1: `_recover_syntax_filename(exc)` em rescue — regex em
   `linecache.getline('<string>', ...)` para achar `open('X.py')`.
@@ -350,217 +476,297 @@
   em EOFError em vez de hang 60s.
 - Fix 3: comando `doxoade check-syntax <file>` — usa `py_compile`
   que **sempre** preserva `filename`.
+
 **Regra nova:** em checagem de sintaxe manual, `py_compile.compile(...,
 doraise=True)` e o padrao. `ast.parse(open(...).read())` **nunca** —
 apaga o path.
+
 **Regra nova 2:** todo rescue com `input()` deve checar
 `sys.stdin.isatty()`; se false, auto-selecionar opcao segura (1 ou 0).
 `stdin=DEVNULL` no chamador e a segunda linha de defesa.
+
 **Estado pos-fix:**
 - `q01_multi_dim: PASS`, 5 sub-sondas corretas, 143ms total.
 - `Q01e` com `with QUIET:` funcional (3 linhas no findstr).
 - `trace q01` legivel (~160 linhas).
+
 **Pendencia:** `run_p02c` em `engine_p02.py` ainda sem `with QUIET:`
 (efeito: trace 02 poluido, ~1500 linhas). Fix trivial, ~6 linhas.
----
+
+---
+
 ## Rescue diagnostics + run_p02c — 2025-11-10
+
 **4 bugs correlacionados, 3 em rescue/infra, 1 em engine.**
+
 ### Bug A: rescue nao recupera filename de open('X.py')
 `ast.parse(source)` sem `filename=` reporta `<unknown>`. Rescue mostrava
 `<unknown>:491` mesmo com o path em frame anterior. Fix: `_recover_syntax_source`
 varre frames por regex `open('X.py')` etc; se achar, substitui `crime['file']`
 e recarrega `crime['code']` do arquivo real.
+
 ### Bug B: rescue hang 60s em subprocess
 `activate_protocol` tem guard `not sys.stdin.isatty()` -> `_direct_report`.
 Mas `subprocess.run(... capture_output=True)` **herda** stdin do pai (TTY),
 fazendo `isatty()` retornar True no subprocess. Menu interativo fica esperando
 input humano. Fix: `stdin=subprocess.DEVNULL` em `_run_engine` -> subprocess
 ve stdin fechado -> `_direct_report` -> exit 1 em ~1s.
+
 ### Bug C: mensagem duplicada "engine falhou: engine falhou:"
 `_run_engine` prefixa "engine falhou:" no timeout, `_run_one` prefixa de novo.
 Fix: `_run_engine` retorna texto sem prefixo, `_run_one` so adiciona `"  "`.
+
 ### Bug D: run_p02c sem `with QUIET:` (pendencia de 3 turnos)
 Fix trivial: envolver `for i in range(100):` em `with QUIET:`.
+
 **Licao 1:** `ast.parse(open(f).read())` e anti-pattern para check-syntax.
 Sempre `ast.parse(source, filename=f)` ou `py_compile.compile(f, doraise=True)`.
+
 **Licao 2:** qualquer sistema com `input()` interativo precisa checar
 `sys.stdin.isatty()` **e** o chamador precisa usar `stdin=DEVNULL` quando
 invocar via subprocess. Duas defesas em camadas.
+
 **Licao 3:** recovery heuristica de filename via regex `open('X.py')` funciona
 para o caso `-c "ast.parse(open(...))"` mas nao para `ast.parse("literal")`
 sem contexto de arquivo. Esses ficam como `<unknown>` legitimo.
+
 **Estado pos-fix:**
 - `q01` PASS, rescue mostra path correto no caso `<unknown>`.
 - `retro-forward` subprocess nao trava em 60s.
 - `trace 02` cai de ~1500 para ~160 linhas.
+
 **Proximo:** Q02 (complexidade como 3a dim) em `code_classification`.
----
+
+---
+
 ## _run_engine: dois bugs coexistindo — 2025-11-10
+
 **Bugs encadeados em `retro_forward_cmd._run_engine`:**
 1. `informative[:200]` (nome inexistente) em branch `returncode != 0`
 2. falta `return True, "", stdout, stderr` no path de sucesso
+
 **Por que um escondia o outro:**
 - q01 broken: returncode != 0 -> bug 1 dispara (NameError)
 - q01 fixed: returncode == 0 -> nao chega ao bug 1, cai no fim -> None
   -> `_run_one` unpack de None -> bug 2 (TypeError)
+
 **Licao:** bugs em paths alternativos (success/failure) do mesmo
 branch sao mutuamente mascarantes. Ao consertar o input que
 disparava o bug A, o fluxo agora passa pelo bug B — que ja estava
 la, so inalcancavel.
+
 **Fix:** `head` no lugar de `informative` + `return True, "", stdout,
 stderr` no fim. Todos os paths do `_run_engine` retornam 4-tupla.
+
 **Regra:** toda funcao que retorna tupla fixa deve ter assertion ou
 implementacao clara dos branches. Nao confiar em "vai cair no if
 else" — verificar visualmente que todo `if/except` tem `return`
 no fim do bloco `finally`-equivalente.
+
 **Nota — rescue funcionou:** mostrou `NameError`/`TypeError`, arquivo,
 linha (147/200) corretos. Unico gap: `Funcao: Unknown` — o ctx do
 frame nao esta sendo passado do `_mine_traceback` para o renderer.
 Pendencia cosmetico.
+
 **Verificacao correta de sintaxe:** `py -m py_compile <file>`.
 `ast.parse(open(f).read())` sem `filename=` apaga o path no
 SyntaxError. Nao usar.
+
 **Estado pos-fix:**
 - `run_p02c` com `with QUIET:` (3 linhas no findstr) ✓
 - `stdin=DEVNULL` no subprocess ✓
 - `_recover_syntax_source` no rescue ✓
 - `_run_engine` retorna 4-tupla em todos os paths ✓
 - `q01`, `all` = 14/14 esperado
+
 **Proximo:** Q02 (complexidade como 3a dim) em code_classification.
----
+
+---
+
 ## Q02 — complexity as 3rd dim (2025-11-10)
+
 **Resultado:** PASS 8/8.
+
 **Licao 1 — primeira dim nao-booleana.** Q00/Q01 tiveram valores de
 dim em conjuntos booleanos ou enumerados pequenos. `complexity` tem
 `{1, 2, 3, 4+}` — o `4+` nao e inteiro. Solucao: extractor emite
 `branch_count` exato + hint `branch_count_ge_4=yes`. Rules continuam
 puramente simbolicas (sem OR, sem comparacao numerica).
+
 **Licao 2 — C2 faz aritmetica, C3 fica pura.** A unica computacao
 numerica (`>= 4`) mora no extractor. Se Q03 precisar de
 `param_count > 3`, mesmo padrao: extractor computa o threshold, rules
 fazem match exato.
+
 **Licao 3 — bucketing por valor nao por threshold.** Buckets 2 e 3
 compartilham "3" porque a diferenca entre 2 e 3 branches e menos
 informativa que entre 0-1, 1-2, 3-4+. Essa decisao de granularidade
 fica em README, nao em codigo.
+
 **Estado:** Q00, Q01, Q02 formam trilogia de classificacao — 3 dims
 simultaneas, uma delas com valor nao-booleano. DC2 generaliza sem
 mudanca em C1/C3.
+
 **Pendencia:** `_parse_engine_error` dead code em
 `retro_forward_cmd.py` — remover ou usar. Recomendado remover.
+
 **Proximo:** Q03 (design pattern como 4a dim) ou Q04 (code smell
 como 4a dim). Ambos testam nova classe de valor (pattern name,
 smell name) — conjunto enumerado maior que `{yes, no}` mas menor
 que int livre.
----
+
+---
+
 ## Q03 — pattern detection + cross-cycle chaining (2025-11-10)
+
 **Resultado:** PASS 7/7.
+
 **Licao principal — C1+C3 compoem em camadas.** Ate Q02, todas as 18
 rules matchavam somente fatos seed. Q03 introduz 3 rules (R_factory,
 R_accessor, R_predicate) que dependem de `has_naming` + `has_behavior`
 — fatos derivados por R_create_prefix/R_returns_call em cycle anterior.
+
 A composicao ja estava no motor desde P02, mas nunca exercitada em
 code_classification. Q03 e o primeiro PoC que mostra "rule le fato
 derivado" no dominio de AST.
+
 **Armadilha — NAF default + cross-cycle = bug silencioso.** Se R_utility
 (default via NAF) disparasse em cycle 1 (antes das hints), `pattern=utility`
 ficaria preso em `facts` — WM monotonico nao retrata. R_factory em
 cycle 2 nao pode shadowar. Contradicao em `pattern`.
+
 Fix: sem default. Ausencia de `pattern` fact = `None`. Honesto.
 Registrar para Q04+ (retracao cross-cycle e o proximo upgrade do engine).
+
 **4 dims coexistem sem colisao** — category, has_docstring, complexity,
 pattern. Q03a-e com pattern; Q03d/e/f sem (None). Dims independentes por
 predicado diferente em `(subject, predicate)`.
+
 **Partial match nao dispara pattern** — Q03e (naming sim, behavior nao),
 Q03f (naming sim, behavior Call vs Compare mismatch). Prova que a
 conjuncao de has_naming + has_behavior e exigida.
+
 **Estado:** Q00-Q03 = trilogia expandida para 4D. Proximo natural e
 retracao cross-cycle (para viabilizar defaults) — vira Q04 com
 `engine.retract()` ou WM seletivo.
----
+
+---
+
 ## Q04 — cross-cycle retraction (2025-11-10)
+
 **Resultado:** PASS 5/5.
+
 **Licao principal — prioridade sozinha nao resolve cross-cycle.**
 Q03 expos: R_utility (cycle 1, prio 1) + R_factory (cycle 2, prio 20)
 coexistem em `pattern` = contradicao silenciosa. Priorities only
 disambiguam within-cycle. Cross-cycle precisa retracao explicita.
+
 **Mecanismo escolhido — retracao monotona por prioridade.** Fact ganha
 `priority`, engine ganha `retracted: set`. Novo fato com P_new > P_old
 retrata old. Seeds protegidos (prio infinita). Fato retratado nao
 ressuscita. NAF sobre vivo.
+
 **Por que nao "backward retraction" (rollback de retratacao).**
 Cascata A retrai B, C retrai A, B deveria voltar — modelo classico de
 TMS (Truth Maintenance System). Complexo e fora do escopo. Q04 e
 minimalista. Se Q05+ exigir, upgrade B explicito com
 `retracted_by: dict` rastreando cadeia.
+
 **Estado:** Q00-Q04 = 5 PoCs em code_classification. DC2 agora com 4
 dims + retracao cross-cycle. C1+C3 validados em camada nova.
+
 **Proximo:** Q05 — retracao em cascata (cadeia A->B->C) OU code smell
 (dead code, magic number) — trilha paralela sem upgrade de engine.
 Recomendo Q05 = code smell, deixa cascata para Q06 se demanda real
 aparecer.
----
+
+---
+
 ## Q05 — code smell como 5a dim (2025-11-10)
+
 **Resultado:** PASS 6/6.
+
 **Licao 1 — domain expansion sem engine upgrade.** Q05 valida Plan B
 de Q04: nao foi preciso tocar o engine. Retraction de Q04 + NAF de P21
 + prioridade de P02 + ortogonalidade de predicados resolvem "clean vs
 dirty" naturalmente.
+
 **Licao 2 — retraction deixa de ser artificial.** Q04 exercitou
 retraction com rules stub. Q05 usa em cenario real: aggregate
 `has_any_smell=none` (prio 1, NAF) precisa ser retratado por
 `has_any_smell=dirty` (prio 20) quando qualquer specific aparece.
 Se Q05 falhasse, Q04 nao serviria para apps reais.
+
 **Licao 3 — ortogonalidade de predicados previne colisao.** 3 smells
 em Q05e coexistem sem conflito porque usam predicados distintos
 (`smell_magic_number` vs `smell_long_method` vs `smell_dead_code`).
 Se fossem `smell=magic|long|dead`, colidiriam e Q02 shadow perderia
 info. Schema de fato e a alavanca.
+
 **Estado:** Q00-Q05 = 6 PoCs em code_classification. DC2 com 5 dims.
 C1+C3+C7 validados em 18 PoCs totais (12 FC + 6 CC).
+
 **Proximo:** Q06 — smells mais ricos (OO, dead nested, magic em
 assign) OU multi-funcao (visitor entre funcoes). Ambos requerem
 schema de fato enriquecido — planejamento antes de codigo.
----
+
+---
+
 ## Q05 — accept por expected errado (2025-11-11)
+
 **Sintoma:** q05_smell FAIL. 65+ divergencias em 68 linhas.
+
 **Realidade:** expected_q05.txt tinha
   (a) 1 linha em branco no inicio (leading \n)
   (b) Q05c: category errado (arithmetic_return vs unknown)
   (c) Q05e: complexity errado (3 vs 2)
+
 Engine estava correto nos 3 casos.
+
 **Q05c** — body[0]=Assign (nao Return), entao R_arith nao casa.
 Correto: unknown.
+
 **Q05e** — 1 If no body. Return dentro de If nao conta como branch.
 branch_count=1 -> complexity=2. Eu confundi "return 0 seguido de print(x)"
 com "2 branches".
+
 **Fix:** accept q05. Diff de 3 linhas + 1 blank.
+
 **Licao — antes de accept, derivar 2 casos manualmente.**
 Se 2 casos derivam corretamente e o resto do output parece coerente,
 accept e aplicavel. Se a divergencia e massa (30+ linhas), esconde bug.
+
 **Licao — leading blank line em expected quebra tudo.** Sempre
 verificar `type expected_XX.txt | findstr /N "^$"` para detectar
 linhas vazias antes de `fc`. Ou salvar via `accept` (que preserva
 o `output.txt` byte-a-byte).
+
 **Cleanup:** 3 artefatos antigos removidos (2x FATAL_CRASH_DUMP.txt,
 1x _rename_expected.bat).
----
+
+---
+
 ## X01 — RuleTable por domain (2025-11-11)
+
 **Resultado:** [PASS/FAIL após executar]
+
 **Licao 1 — tabelamento é abstracao fina.** RuleTable e `dict`
 com dois indices (`domain_index`, `symptom_index`) sobre fonte unica
 (`_rules`). Nada mágico, ~50 L. Se X01 falha, o bug esta na fixture,
 nao no conceito.
+
 **Licao 2 — R1/R2/R3 aplicadas.** Classificador separado (R1),
 tabela estatica (R2), fallback adiado para X03 (R3). X01 testa so a
 transparencia do filtro.
+
 **Licao 3 — 480 L vs 80 L prometido.** Kernel inline domina o
 tamanho. Consolidacao (Q10) resolve para ~80 L. Registrar como
 divida conhecida, nao como red flag.
+
 **Licao 4 — validar antes de accept.** `raw_live_facts` e derivavel
 a mao (5 tuplas). Se output diverge, nao e "accept", e bug. Toda
 PoC com `accept` deve ter derivacao manual anotada.
+
 **Proximo:** X02 (symptom index + multi-domain). Mais desafiador
 porque combina duas chaves (domain + symptoms) e testa ativacao
 dinamica — nao so filtro estatico.
-      

■ doxoade/research/forward_chaining/research_directions.md
  xml=146 linhas | disco=185 linhas
--- XML:doxoade/research/forward_chaining/research_directions.md
+++ DISCO:doxoade/research/forward_chaining/research_directions.md
@@ -1,19 +1,24 @@
+# Direções de pesquisa deferidas — forward chaining
 
-# Direções de pesquisa deferidas — forward chaining
 Registro de áreas identificadas como relevantes mas **deliberadamente
 adiadas**. Nenhuma entra em `poc/` enquanto o gatilho de reavaliação
 não disparar. Ordem de reavaliação: **depois de C7 verde**.
+
 Cada entrada tem:
 - descrição curta
 - por que relevante
 - por que deferido
 - **gatilho de reavaliação** (condição objetiva, não opinião)
 - sonda candidata (para quando o gatilho disparar)
+
 ---
+
 ## Backward chaining
+
 **O que é:** Inferência goal-driven. Parte do objetivo ("é verdade que X?")
 e recua perguntando "o que precisa ser verdade para X?". Contraste com forward
 (que parte dos fatos e deriva tudo).
+
 **Por que relevante:**
 - Forward explora espaço inteiro; backward explora só o caminho do objetivo.
 - Habilita "explicação negativa" (P51): "por que NÃO derivou X" é natural
@@ -22,6 +27,7 @@
   Goal Manager → Backward → Forward → Verificação.
 - Pode reduzir custo de P30 (rewrite): "quero transformar este loop em
   comprehension; o que precisa ser verdade?" — só explora regras relevantes.
+
 **Por que deferido:**
 - Forward resolve P00–P02 sem dificuldade. Backward só é necessário quando
   o espaço de busca é grande (> ~100 regras).
@@ -30,19 +36,25 @@
 - ProDeNov 1.1 exige viabilidade/manutenção/escalabilidade antes de nova
   direção. Backward precisa de Goal Manager (novo componente), não de
   tweak no engine.
+
 **Gatilho de reavaliação:** qualquer um:
 - número de regras em produção passar de 100;
 - tempo de forward chaining perceptível (> 100 ms por run em dados reais);
 - P51 (explicação negativa) falhar por falta de mecanismo de goal.
+
 **Sonda candidata:** `P_B1` — dedução em lógica proposicional (5 fatos,
 5 regras, 1 objetivo). Implementar backward e comparar número de regras
 avaliadas com forward equivalente. Só vale se backward for mensuravelmente
 mais barato em caso real.
+
 ---
+
 ## Combinatory tree (Combinatory Logic)
+
 **O que é:** Representação de expressões em lógica combinatória (SKI),
 sem variáveis. `S`, `K`, `I` como primitivos; qualquer lambda-termo é
 reescrito como aplicação deles.
+
 **Por que relevante:**
 - Rewrites de AST (P30+) podem ser expressas como aplicação de combinadores
   em vez de regras ad-hoc: `S K K x → x` é uma regra universal.
@@ -52,26 +64,33 @@
   invariantes sob substituição por construção.
 - Conexão com word tree: uma é sintaxe (lógica), outra é léxico (palavras).
   Juntas formam base para representação não-embedding.
+
 **Por que deferido:**
 - Adiciona teoria pesada sem resolver problema atual (nenhuma PoC de C1–C7
   exige combinadores).
 - P20 pode ser feito sem combinadores. Combinadores *depois* podem simplificar
   P30 — não antes.
 - Fora do escopo do MVP declarado no paper (Fatos→Regras→Fatos).
+
 **Gatilho de reavaliação:** quando P30 (rewrite de AST) estiver implementado
 com regras ad-hoc e o padrão de rewrite começar a se repetir — mesmo shape
 reescrito de 5+ formas diferentes. Aí vale explorar se combinadores
 unificam as regras.
+
 **Sonda candidata:** `P_C1` — implementar `S K K x → x` como rewrite de
 AST e comparar com versão ad-hoc de P30. Métrica: LOC de regras e número
 de regras disparadas para mesma transformação.
+
 ---
+
 ## Word tree
+
 **O que é:** (Ambíguo — candidatos:)
 - (a) Trie/prefix tree de palavras para lookup rápido
 - (b) Árvore hierárquica de morfologia: palavra → lemma → raiz
 - (c) Árvore de co-ocorrências (n-gramas aninhados)
 - (d) Parse tree gramatical
+
 **Por que relevante:**
 - O paper é explicitamente "gerador de texto sem embeddings". Word tree é
   uma das alternativas estruturais a embeddings — representação
@@ -80,6 +99,7 @@
   fonte no domínio de linguagem natural.
 - Complementa combinatory tree: léxico + sintaxe = base para geração
   não-embedding.
+
 **Por que deferido:**
 - Linguagem natural é o **último** passo da escada histórica da IA
   (jogos → sistemas especialistas → programação → linguagem). O paper
@@ -89,23 +109,32 @@
   projeto ainda não tem.
 - Escolher variante antes de ter caso de uso é exatamente o Long Shot que
   ProDeNov 3.1.6 proíbe.
+
 **Gatilho de reavaliação:** quando C7 estiver verde **e** P50 (representação)
 precisar de estrutura para gerar texto. Antes disso, não escolher variante.
+
 **Sonda candidata:** `P_W1` — dado um conjunto de 20 palavras com
 lemma/raiz conhecidas, construir tree e responder 10 queries
 (e.g., "palavras cuja raiz é X"). Comparar com dict plano. Só vale se tree
 ganhar em alguma métrica mensurável (lookup de raiz, iteração por prefixo).
+
 ---
+
 ## Relação entre as três — ordenação sugerida
+
 | Direção | Custo de integração | Ganho no curto prazo | Prioridade |
 |---|---|---|---|
 | **Backward chaining** | alto (Goal Manager novo) | alto (eficiência + explicação negativa) | **1º** |
 | **Combinatory tree** | médio (informa P30) | médio (universalidade de rewrite) | 2º |
 | **Word tree** | alto (corpus, variante a escolher) | baixo | 3º |
+
 A ordem é **estimativa**. Deve ser reavaliada após C7 com dados reais
 de custo de forward. Não é decreto.
+
 ---
+
 ## Como este arquivo se mantém honesto
+
 Cada entrada tem **gatilho objetivo**. Se o gatilho nunca dispara, a direção
 continua deferida — morre por desnecessária, não por esquecimento.
 Se o gatilho dispara:
@@ -113,21 +142,30 @@
 2. A entrada migra deste arquivo para `poc_notes.md` com status `in_progress`;
 3. Se a PoC falha, `poc_notes.md` registra o "porquê falhou" e a entrada
    volta para cá com gatilho refinado.
+
 A regra é a mesma de toda PoC: **nada entra no sistema principal sem
 sonda que responda pergunta binária.**
+
 ---
+
 ## Negação explícita (P22 candidata)
+
 **Gatilho:** P30 (rewrite) precisar expressar proibição com prova positiva.
 **Diferença de P21:** P21 é NAF (procedural); P22 é negação declarativa
 com fatos `(X, ¬r, Y)` e semântica de contradição.
 **Custo:** alto (modelo de fatos estendido, resolution de X r Y ∧ X ¬r Y).
 **Bloqueante até então:** NAF cobre P21 e 90% de casos práticos.
+
 ---
+
 ## Doctor de producao (pre-flight, semantic checks)
+
 **Estado atual (PoC):** `_doctor.py` implementa diagnostico estrutural,
 fix de `.bat` e pre-flight. Cobre 7 PoCs, ~150 LOC.
+
 **Estado futuro (producao):** quando o sistema tiver dezenas de modulos,
 o doctor precisa cobrir:
+
 - **Coerencia semantica** entre modulos: contrato C1 declarado bate com
   o que o modulo importa?
 - **Compatibilidade de fatos**: `Fact` de P00 e compativel com `TripleFact`
@@ -137,10 +175,11 @@
 - **Integridade de artefatos**: `expected.txt` versionado bate com o
   output atual? Se nao, aviso antes de rodar.
 - **Pre-flight de deploy**: o que precisa estar verde para promover.
+
 **Gatilho:** quando o projeto passar de ~20 PoCs ou quando o primeiro
 modulo for promovido para `src/`. Antes disso, `_doctor.py` e suficiente.
+
 **Nao confundir:** o doctor NAO e o `pytest`. `pytest` testa comportamento;
 doctor testa **estrutura do laboratorio**. Um PoC pode ter 100% pytest
 verde e doctor vermelho (arquivos trocados), ou vice-versa (engine errado
 mas .bat correto). Sao checagens ortogonais.
-      

■ doxoade/commands/retro_forward_cmd.py
  xml=365 linhas | disco=451 linhas
--- XML:doxoade/commands/retro_forward_cmd.py
+++ DISCO:doxoade/commands/retro_forward_cmd.py
@@ -1,16 +1,38 @@
-
 # -*- coding: utf-8 -*-
+# doxoade/commands/retro_forward_cmd.py
+"""
+Orquestrador de PoCs de pesquisa (retro-forward).
+
+Uso:
+    doxoade retro-forward list
+    doxoade retro-forward run <poc> [--debug]
+    doxoade retro-forward trace <poc>     # = run --debug
+    doxoade retro-forward all
+    doxoade retro-forward doctor
+    doxoade retro-forward accept <poc>    # regenera expected_<num>.txt
+"""
 from __future__ import annotations
+
 import re
 import subprocess
 import sys
 from pathlib import Path
+
 import click
+
 from doxoade.tools.doxcolors import Fore, Style
+
+
 POC_BASE = Path(__file__).resolve().parent.parent / "research"
 PLACEHOLDER_RE = re.compile(r"<[A-Z_]+>")
 MAX_DIFF_LINES = 5
+
+
+# ============================================================
+# Descoberta
+# ============================================================
 def _discover_pocs() -> list[dict]:
+    """Descobre PoCs em research/*/poc/. Expected: expected_<num>.txt."""
     if not POC_BASE.is_dir():
         return []
     pocs: list[dict] = []
@@ -47,6 +69,8 @@
                 "has_expected": expected_path.exists(),
             })
     return pocs
+
+
 def _find_poc(name: str, pocs: list[dict]) -> dict | None:
     name = name.strip().lower().rstrip("/")
     for p in pocs:
@@ -55,7 +79,17 @@
         if name in (folder, num, folder.split("_", 1)[0]):
             return p
     return None
+
+
+# ============================================================
+# Execucao e comparacao
+# ============================================================
 def _run_engine(poc: dict, debug: bool = False) -> tuple[bool, str, str, str]:
+    """Executa engine em subprocess. Retorna (ok, err_msg, stdout, stderr).
+
+    Em timeout, retorna stdout/stderr PARCIAIS capturados (nao vazios).
+    Todos os paths retornam 4-tupla; nunca None.
+    """
     cmd = [sys.executable, poc["engine"].name]
     if debug:
         cmd.append("--debug")
@@ -75,10 +109,12 @@
             partial_out = partial_out.decode("utf-8", "replace")
         if isinstance(partial_err, bytes):
             partial_err = partial_err.decode("utf-8", "replace")
+
         out_lines = partial_out.splitlines()
         err_lines = partial_err.splitlines()
         out_tail = "\n".join(out_lines[-10:]) if out_lines else "  (vazio)"
         err_tail = "\n".join(err_lines[-10:]) if err_lines else "  (vazio)"
+
         msg = (
             f"timeout (60s)\n"
             f"  stdout_total: {len(out_lines)} linha(s)\n"
@@ -99,15 +135,19 @@
         return False, msg, partial_out, partial_err
     except Exception as e:
         return False, f"subprocess error: {type(e).__name__}: {e}", "", ""
+
     stdout = result.stdout or ""
     stderr = result.stderr or ""
+
     if result.returncode != 0:
         lines = stderr.strip().splitlines()
         non_debug = [ln for ln in lines if not ln.startswith("[DEBUG]")]
         head = (non_debug[-1] if non_debug else
                 (lines[-1] if lines else "(sem stderr)"))
         return False, f"engine exit {result.returncode}: {head[:200]}", stdout, stderr
+
     return True, "", stdout, stderr
+    
 def _read_outputs(poc: dict) -> tuple[str | None, str | None]:
     output_path = poc["dir"] / "output.txt"
     if not output_path.exists():
@@ -120,6 +160,8 @@
     except Exception as e:
         return None, f"read error: {e}"
     return out.replace("\r\n", "\n"), exp.replace("\r\n", "\n")
+
+
 def _format_diff(out: str, exp: str, poc: dict) -> tuple[str, int, bool]:
     out_lines = out.splitlines()
     exp_lines = exp.splitlines()
@@ -132,6 +174,7 @@
             total += 1
             if len(mismatches) < MAX_DIFF_LINES:
                 mismatches.append((i + 1, e, o))
+
     parts = [
         f"  arquivo esperado: {poc['expected_path']}",
         f"  arquivo atual:    {poc['dir'] / 'output.txt'}",
@@ -150,12 +193,15 @@
             parts.append(f"    out: {o!r}")
     if total > MAX_DIFF_LINES:
         parts.append(f"  ... e mais {total - MAX_DIFF_LINES} divergencia(s)")
+
     has_ph = bool(PLACEHOLDER_RE.search(exp))
     return "\n".join(parts), total, has_ph
+
 def _run_one(poc: dict, debug: bool = False) -> tuple[bool, str, str, str]:
+    """Retorna (ok, msg, stdout, stderr)."""
     ok, err, stdout, stderr = _run_engine(poc, debug=debug)
     if not ok:
-        return False, f"  {err}", stdout, stderr   
+        return False, f"  {err}", stdout, stderr   # <-- era: f"  engine falhou: {err}"
     out, exp_or_err = _read_outputs(poc)
     if out is None:
         return False, f"  {exp_or_err}", stdout, stderr
@@ -169,6 +215,10 @@
             f"        Rode: doxoade retro-forward accept {poc['num']}"
         )
     return False, msg, stdout, stderr
+    
+# ============================================================
+# Doctor
+# ============================================================
 def _doctor_report() -> tuple[list[dict], int]:
     results = []
     total_problems = 0
@@ -185,11 +235,20 @@
         if problems:
             total_problems += 1
     return results, total_problems
+
+
+# ============================================================
+# CLI
+# ============================================================
 @click.group("retro-forward")
 def retro_forward_group():
+    """Orquestrador de PoCs de pesquisa (forward_chaining, code_classification)."""
     pass
+
+
 @retro_forward_group.command("list")
 def cmd_list():
+    """Lista PoCs disponiveis em todas as linhas de pesquisa."""
     pocs = _discover_pocs()
     if not pocs:
         click.secho(f"Nenhum PoC em {POC_BASE}", fg="yellow")
@@ -211,11 +270,14 @@
                     reasons.append(f"sem {p['expected_path'].name}")
                 status = click.style(f" [{', '.join(reasons)}]", fg="red")
             click.echo(f"    {p['name']:<30}{status}")
+
+
 @retro_forward_group.command("run")
 @click.argument("poc_name")
 @click.option("--debug", "-d", is_flag=True,
               help="Mostra stdout completo do engine (mesmo em PASS)")
 def cmd_run(poc_name: str, debug: bool):
+    """Executa um PoC especifico ('30b', 'p30b', 'q00', ou nome completo)."""
     pocs = _discover_pocs()
     poc = _find_poc(poc_name, pocs)
     if poc is None:
@@ -223,6 +285,7 @@
         if pocs:
             click.echo("Disponiveis: " + ", ".join(p["name"] for p in pocs))
         sys.exit(1)
+
     click.secho(f"=== {poc['name']} ===", fg="cyan", bold=True)
     ok, msg, stdout, stderr = _run_one(poc, debug=debug)
     if ok:
@@ -244,13 +307,19 @@
             click.secho("--- engine stdout ---", fg="yellow", bold=True)
             click.echo(stdout)
         sys.exit(1)
+
+
 @retro_forward_group.command("trace")
 @click.argument("poc_name")
 def cmd_trace(poc_name: str):
+    """Alias para 'run <poc> --debug' (mostra derivacao completa)."""
     ctx = click.get_current_context()
     ctx.invoke(cmd_run, poc_name=poc_name, debug=True)
+
+
 @retro_forward_group.command("all")
 def cmd_all():
+    """Pre-flight + todos os PoCs."""
     click.secho("=== Pre-flight: doctor ===", fg="cyan", bold=True)
     results, problems = _doctor_report()
     for r in results:
@@ -264,9 +333,11 @@
             fg="red", bold=True,
         )
         sys.exit(1)
+
     click.secho(f"{len(results)}/{len(results)} PoCs OK", fg="green")
     click.echo()
     click.secho("=== Executando PoCs ===", fg="cyan", bold=True)
+
     pass_count, fail_count = 0, 0
     failed: list[str] = []
     for r in results:
@@ -282,6 +353,7 @@
             click.echo(msg)
             fail_count += 1
             failed.append(poc["name"])
+
     click.echo()
     click.echo("=" * 40)
     if fail_count:
@@ -290,8 +362,11 @@
         click.echo(f"Failed: {' '.join(failed)}")
         sys.exit(1)
     click.secho(f"PASS: {pass_count} | FAIL: 0", fg="green", bold=True)
+
+
 @retro_forward_group.command("doctor")
 def cmd_doctor():
+    """Diagnostico estrutural (sem executar engines)."""
     results, problems = _doctor_report()
     if not results:
         click.secho(f"Nenhum PoC em {POC_BASE}", fg="yellow")
@@ -314,21 +389,27 @@
             f"{problems} problema(s)", fg="red", bold=True,
         )
         sys.exit(1)
+
+
 @retro_forward_group.command("accept")
 @click.argument("poc_name")
 @click.option("--no-diff", is_flag=True, help="Nao mostrar diff antes de aceitar")
 def cmd_accept(poc_name: str, no_diff: bool):
+    """Aceita output.txt atual como novo expected_<num>.txt (regenera)."""
     pocs = _discover_pocs()
     poc = _find_poc(poc_name, pocs)
     if poc is None:
         click.secho(f"PoC '{poc_name}' nao encontrado.", fg="red")
         sys.exit(1)
+
     ok, err, _, _ = _run_engine(poc)
     if not ok:
         click.secho(f"Engine falhou, abortando accept: {err}", fg="red")
         sys.exit(1)
+
     out, exp_or_err = _read_outputs(poc)
     if out is None:
+        # Se expected ainda nao existe, le so output.txt
         output_path = poc["dir"] / "output.txt"
         if output_path.exists():
             out = output_path.read_text(encoding="utf-8", errors="replace")
@@ -336,6 +417,7 @@
         else:
             click.secho(f"Falha lendo output: {exp_or_err}", fg="red")
             sys.exit(1)
+
     if not no_diff:
         old = exp_or_err if isinstance(exp_or_err, str) else ""
         if old and old != out:
@@ -344,14 +426,18 @@
                         fg="yellow", bold=True)
             click.echo(diff_msg)
             click.echo()
+
     output_path = poc["dir"] / "output.txt"
     output_path.replace(poc["expected_path"])
+
     n_lines = out.count("\n")
     click.secho(f"{poc['expected_path'].name} atualizado ({n_lines} linhas)",
                 fg="green")
     click.echo(f"Arquivo: {poc['expected_path']}")
     click.echo("Verifique o diff antes de commitar: git diff")
+
 def _parse_engine_error(stderr: str, poc: dict) -> str:
+    """Extrai SyntaxError/Traceback path do stderr do engine."""
     for line in stderr.splitlines():
         m = re.search(r'File "([^"]+)", line (\d+)', line)
         if m:
@@ -360,6 +446,6 @@
         if m:
             return f"  arquivo: {m.group(1)}\n  linha:   {m.group(2)}"
     return f"  arquivo: {poc['dir'] / poc['engine'].name}"
+
 if __name__ == "__main__":
     retro_forward_group()
-      

■ doxoade/tools/doxcolors.py
  xml=354 linhas | disco=497 linhas
--- XML:doxoade/tools/doxcolors.py
+++ DISCO:doxoade/tools/doxcolors.py
@@ -1,14 +1,20 @@
-
+# doxoade/tools/doxcolors.py
+# -*- coding: utf-8 -*-
+""" Doxcolors Nexus Edition – High-Performance CLI UI Engine
+Versão: 2.1 (Nexus UI - Dynamic Color Force) """
 import os
 import sys
 import builtins
 import time
 import threading
 import atexit
+
 if not hasattr(builtins, '_doxoade_original_print'):
     builtins._doxoade_original_print = builtins.print
 _original_print = builtins._doxoade_original_print
+
 def _force_reset():
+    """Envia o sinal de reset global de forma agressiva."""
     try:
         if os.name == 'nt':
             os.system('')
@@ -18,13 +24,17 @@
         sys.stderr.flush()
     except KeyboardInterrupt:
         pass
+
 def _ansi_enabled():
+    # 🛡️ Suporte universal a variáveis de ambiente de cores forçadas
     if os.environ.get("FORCE_COLOR") == "1" or os.environ.get("CLICOLOR_FORCE") == "1":
         return True
     if os.name != 'nt':
         return sys.stdout.isatty() if hasattr(sys.stdout, 'isatty') else False
     return (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()) or 'ANSICON' in os.environ or 'WT_SESSION' in os.environ or (os.environ.get('TERM_PROGRAM') == 'vscode')
+
 ANSI_ENABLED = _ansi_enabled()
+
 if os.name == 'nt' and ANSI_ENABLED:
     try:
         import ctypes
@@ -35,19 +45,35 @@
         kernel32.SetConsoleMode(handle, mode.value | 4)
     except Exception:
         pass
+
+# 🛡️ CLASSE ÚNICA E DEFINITIVA: NUNCA descarta códigos se FORCE_COLOR estiver ativo
 class AnsiCode(str):
     __slots__ = ()
     def __new__(cls, code: str):
         if not _ansi_enabled():
             return str.__new__(cls, '')
         return str.__new__(cls, f'\x1b[{code}m')
+
+# --- CORE ENGINE ---
+
+# def _ansi_enabled():
+#     if os.name != 'nt':
+#         return sys.stdout.isatty()
+#     return sys.stdout.isatty() or 'ANSICON' in os.environ or 'WT_SESSION' in os.environ or (os.environ.get('TERM_PROGRAM') == 'vscode')
+
+# #ANSI_ENABLED = _ansi_enabled()
+# ANSI_ENABLED = sys.stdout.isatty() if hasattr(sys.stdout, 'isatty') else False
+
 def _ansi_enabled():
+    # 🛡️ Respeita flags universais de forçamento de cor no terminal e subprocessos
     if os.environ.get("FORCE_COLOR") == "1" or os.environ.get("CLICOLOR_FORCE") == "1":
         return True
     if os.name != 'nt':
         return sys.stdout.isatty() if hasattr(sys.stdout, 'isatty') else False
     return (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()) or 'ANSICON' in os.environ or 'WT_SESSION' in os.environ or (os.environ.get('TERM_PROGRAM') == 'vscode')
+
 ANSI_ENABLED = _ansi_enabled()
+
 if os.name == 'nt' and ANSI_ENABLED:
     try:
         import ctypes
@@ -58,12 +84,14 @@
         kernel32.SetConsoleMode(handle, mode.value | 4)
     except Exception:
         pass
+
 class AnsiCode(str):
     __slots__ = ()
     def __new__(cls, code: str):
         if not ANSI_ENABLED: return str.__new__(cls, '')
         return str.__new__(cls, f'\x1b[{code}m')
-class Back: 
+
+class Back: # Adicionado para corrigir o NameError
     BLACK   = AnsiCode('40')
     BLUE    = AnsiCode('44')
     CYAN    = AnsiCode('46')
@@ -73,6 +101,7 @@
     RESET   = AnsiCode('49')
     WHITE   = AnsiCode('47')
     YELLOW  = AnsiCode('43')
+
 class Fore:
     BLACK   = AnsiCode('30')
     BLUE    = AnsiCode('34')
@@ -103,6 +132,7 @@
     STABLE      = AnsiCode('38;2;176;176;176') 
     VOLATILE    = AnsiCode('38;2;255;0;255')   
     XYZ         = AnsiCode('38;2;255;155;0')   
+
 class Style:
     DIM       = AnsiCode('2')
     NORMAL    = AnsiCode('22')
@@ -113,17 +143,27 @@
     ITALIC    = AnsiCode('3')
     HIDDEN    = AnsiCode('?25l')
     SHOW      = AnsiCode('?25h')
+
+# --- UTILS ---
+
 def rgb(r, g, b): return AnsiCode(f'38;2;{r};{g};{b}')
 def hex_to_ansi(hex_code: str):
-    h = hex_code.lstrip('
+    h = hex_code.lstrip('#')
     return rgb(*(int(h[i:i+2], 16) for i in (0, 2, 4)))
+
+# --- NEXUS UI & ANIMATIONS ---
+
 class NexusUI:
-    @staticmethod
-    def gradient_text(text, start_hex="
+    """Motor de Interface Visual do Doxoade."""
+    
+    @staticmethod
+    def gradient_text(text, start_hex="#006CFF", end_hex="#26BC5F"):
+        """Gera um texto com gradiente linear."""
         if not ANSI_ENABLED: return text
-        h1, h2 = start_hex.lstrip('
+        h1, h2 = start_hex.lstrip('#'), end_hex.lstrip('#')
         r1, g1, b1 = (int(h1[i:i+2], 16) for i in (0, 2, 4))
         r2, g2, b2 = (int(h2[i:i+2], 16) for i in (0, 2, 4))
+        
         result = ""
         steps = len(text)
         for i, char in enumerate(text):
@@ -132,11 +172,14 @@
             b = int(b1 + (b2 - b1) * (i / max(1, steps-1)))
             result += f"\x1b[38;2;{r};{g};{b}m{char}"
         return result + "\x1b[0m"
+
     @staticmethod
     def decode_effect(target_text, duration=1.0):
+        """Efeito de decodificação 'Matrix' para revelar texto."""
         import string
         import random
-        chars = string.ascii_letters + string.digits + "!@
+
+        chars = string.ascii_letters + string.digits + "!@#$%^&*"
         start_time = time.time()
         while time.time() - start_time < duration:
             current = "".join(random.choice(chars) for _ in range(len(target_text)))
@@ -144,35 +187,61 @@
             sys.stdout.flush()
             time.sleep(0.05)
         sys.stdout.write(f"\r{NexusUI.gradient_text(target_text)}\n")
-    @staticmethod
-    def pulse(text, hex_color="
+
+    @staticmethod
+    def pulse(text, hex_color="#FF00FF", speed=1.0):
+        """Efeito de pulsar (fade in/out) - Requer terminal com suporte a TrueColor."""
+        # Simulado via alternância de brilho se não houver suporte total
         pass 
+
     @staticmethod
     def play_animation(frames, interval=0.1, loops=2):
+        """
+        Animação multi-linha ultra-estável por contagem de linhas.
+        """
         if not ANSI_ENABLED: return
-        sys.stdout.write("\x1b[?25l") 
+        
+        sys.stdout.write("\x1b[?25l") # Esconde cursor
+        
         try:
             for loop in range(loops):
                 for frame in frames:
+                    # Limpa espaços e divide linhas
                     lines = frame.strip('\n').split('\n')
                     num_lines = len(lines)
+                    
+                    # Desenha o frame linha por linha
                     for line in lines:
+                        # \r volta pro início da linha, \x1b[2K apaga o que tinha antes
                         sys.stdout.write("\r\x1b[2K" + line + "\n")
+                    
                     sys.stdout.flush()
                     time.sleep(interval)
+                    
+                    # SOBE O CURSOR exatamente o número de linhas que imprimimos
+                    # para desenhar o próximo frame por cima
                     sys.stdout.write(f"\x1b[{num_lines}A")
+            
+            # Ao terminar, move o cursor para baixo da animação
             sys.stdout.write(f"\x1b[{num_lines}B\n")
+            
         finally:
-            sys.stdout.write("\x1b[?25h") 
+            sys.stdout.write("\x1b[?25h") # Mostra cursor
             sys.stdout.flush()
+
     @staticmethod
     def apply_tags(text: str) -> str:
+        """Processa tags customizadas «TAG»...«/». Fail-Safe."""
         if not text or not isinstance(text, str):
             return ""
         try:
+            # Lógica de substituição de tags...
+            # (seu código atual de regex)
             return rendered_text
         except Exception:
+            # Se houver erro de sintaxe nas tags, retorna o texto puro
             return text
+
     @staticmethod
     def load_animation(file_path, separator="===FRAME==="):
         try:
@@ -186,28 +255,37 @@
             import logging as _dox_log
             _dox_log.error(f"[INFRA] load_animation: {e}")
             return []
+
     @staticmethod
     def loader(file_path, interval=0.1, debug=False, ping_pong=False, color=""):
         frames = NexusUI.load_animation(file_path)
         return AsyncAnimation(frames, interval, debug=debug, ping_pong=ping_pong, base_color=color)
+
 class Spinner:
+    """Braille Loading Spinner."""
     frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
+    
     def __init__(self, message="Processando"):
         self.message = message
         self.idx = 0
+
     def step(self):
         frame = self.frames[self.idx % len(self.frames)]
         sys.stdout.write(f"\r{Fore.CYAN}{frame}{Fore.RESET} {self.message}...")
         sys.stdout.flush()
         self.idx += 1
+
     def finish(self, success=True):
         symbol = f"{Fore.SUCCESS}✔" if success else f"{Fore.ERROR}✘"
         sys.stdout.write(f"\r{symbol}{Fore.RESET} {self.message} Finalizado.\n")
+
 class ProgressBar:
+    """Barra de progresso semântica."""
     def __init__(self, total, label="Progresso", width=30):
         self.total = total
         self.label = label
         self.width = width
+
     def update(self, current):
         perc = min(100, int((current / self.total) * 100))
         filled = int((self.width * current) // self.total)
@@ -215,9 +293,11 @@
         color = Fore.SUCCESS if perc == 100 else Fore.PRIMARY
         sys.stdout.write(f"\r{self.label} {color}[{bar}] {perc}%{Fore.RESET}")
         sys.stdout.flush()
+
 class AsyncAnimation:
     def __init__(self, frames, interval=0.1, debug=False, ping_pong=False, base_color=""):
         import shutil
+
         self.interval = interval
         self.running = threading.Event()
         self.lock = threading.Lock()
@@ -227,81 +307,121 @@
         self.canvas_height = 0
         self.atomic_frames = [] 
         self._force_redraw = False
+
         if frames:
             term_width = shutil.get_terminal_size().columns
+            # 1. Geometria Fixa: Calcula altura real do canvas
             self.canvas_height = max(len(f.split('\n')) for f in frames)
+            
             for f in frames:
                 lines = f.split('\n')
+                # Normaliza todos os quadros para a mesma altura exata
                 while len(lines) < self.canvas_height:
                     lines.append("")
+                
                 frame_buffer = ""
                 for i, line in enumerate(lines):
                     clean_line = line.rstrip()
+                    # Blindagem de largura (margem maior para segurança)
                     safe_line = clean_line[:term_width - 15]
+                    
                     prefix = f"\x1b[90m{i+1:02} |\x1b[0m " if self.debug else ""
+                    
+                    # \r (Home) + Cor + Conteúdo + \x1b[K (Limpa rastro)
                     frame_buffer += f"\r{prefix}{self.base_color}{safe_line}\x1b[0m\x1b[K"
+                    
+                    # Adiciona nova linha exceto na última do canvas (Proteção de Stacking)
                     if i < self.canvas_height - 1:
                         frame_buffer += "\n"
+                
                 self.atomic_frames.append(frame_buffer)
+
     def _animate(self):
         if hasattr(sys, '_doxoade_current_tracer'):
             sys.settrace(sys._doxoade_current_tracer)
+
+        # Esconde o cursor
         sys.stdout.write("\x1b[?25l")
         sys.stdout.flush()
+        
         idx = 0
         step = 1
         count = len(self.atomic_frames)
         is_first_draw = True
+        
+        # Pre-calcula o comando de subida (Altura - 1)
+        # Usamos \x1b[A porque é o mais compatível universalmente
         up_cmd = f"\x1b[{self.canvas_height - 1}A" if self.canvas_height > 1 else ""
+
         while self.running.is_set():
             frame_data = self.atomic_frames[idx]
             t_start = time.perf_counter()
+            
             try:
                 with self.lock:
+                    # REPOSICIONAMENTO NEXUS
                     if not is_first_draw and not self._force_redraw:
                         sys.stdout.write(up_cmd)
+                    
+                    # Escrita Atômica
                     sys.stdout.write(frame_data)
                     sys.stdout.flush()
+                    
                     is_first_draw = False
                     self._force_redraw = False
             except Exception as e:
                 import logging as _dox_log
                 _dox_log.error(f"[INFRA] _animate: {e}")
                 break
+            
+            # Lógica Ping-Pong
             if self.ping_pong and count > 1:
                 idx += step
                 if idx >= count - 1 or idx <= 0: step *= -1
             else:
                 idx = (idx + 1) % count
+            
+            # Velocidade Dinâmica (usa self.interval atualizado)
             t_elapsed = time.perf_counter() - t_start
             time.sleep(max(0, self.interval - t_elapsed))
+
         self._cleanup_display()
+
     def _cleanup_display(self):
+        """Faxina total via subida relativa."""
         with self.lock:
             try:
                 if self.canvas_height > 0:
+                    # Volta ao topo do canvas
                     sys.stdout.write(f"\r\x1b[{self.canvas_height - 1}A")
+                    # Limpa todas as linhas
                     for i in range(self.canvas_height):
                         sys.stdout.write("\x1b[2K")
                         if i < self.canvas_height - 1:
                             sys.stdout.write("\n")
+                    # Deixa o cursor no topo limpo
                     sys.stdout.write(f"\r\x1b[{self.canvas_height - 1}A")
-                sys.stdout.write("\x1b[?25h") 
+                sys.stdout.write("\x1b[?25h") # Mostra cursor
                 sys.stdout.flush()
             except Exception as e:
                 import logging as _dox_log
                 _dox_log.error(f"[INFRA] _cleanup_display: {e}")
+
     def start(self):
         if not self.atomic_frames: return
         self.running.set()
+        # Thread não-daemon para permitir cleanup no join
         self._thread = threading.Thread(target=self._animate)
         self._thread.start()
+
     def stop(self):
         if self.running.is_set():
             self.running.clear()
             if self._thread and self._thread.is_alive():
                 self._thread.join(timeout=1.0)
+
     def print(self, text):
+        """Injeta log movendo a animação."""
         from .doxcolors import NexusUI
         formatted = NexusUI.apply_tags(text)
         with self.lock:
@@ -313,42 +433,65 @@
             sys.stdout.write(f"{formatted}\n")
             sys.stdout.flush()
             self._force_redraw = True
+
     def __enter__(self):
         self.start()
         return self
+
     def __exit__(self, *args):
         self.stop()
+
+# --- OVERRIDES ---
+
+#_original_print = builtins.print
 def safe_print(*args, **kwargs):
+    """Print seguro com proteção contra recursão."""
     try:
         if ANSI_ENABLED:
-            _original_print('\x1b[0m', end='')  
+            _original_print('\x1b[0m', end='')  # Reset ANSI
+        
         _original_print(*args, **kwargs)
+        
         if ANSI_ENABLED:
-            _original_print('\x1b[0m', end='')  
+            _original_print('\x1b[0m', end='')  # Reset ANSI
     except RecursionError:
+        # Se detectar recursão, usa o print do builtins diretamente
         builtins._doxoade_original_print(*args, **kwargs)
     except Exception:
+        # Fallback para qualquer outro erro
         try:
             builtins._doxoade_original_print(*args, **kwargs)
         except:
-            pass  
+            pass  # Último recurso: silêncio
+
+# Substitui o print global
 builtins.print = safe_print
+
+# --- EXPORTS ---
 class DoxColors:
     Fore = Fore; Back = Back; Style = Style; UI = NexusUI
     rgb = staticmethod(rgb); hex = staticmethod(hex_to_ansi)
     AsyncAnimation = AsyncAnimation
 colors = DoxColors
+
 def init(autoreset=True):
+    """
+    Inicializa o motor de cores.
+    Se autoreset=True, registra a limpeza automática ao sair do programa.
+    """
     if os.name == 'nt' and ANSI_ENABLED:
         try:
             import ctypes
             kernel32 = ctypes.windll.kernel32
+            # Habilita VIRTUAL_TERMINAL_PROCESSING
             handle = kernel32.GetStdHandle(-11)
             mode = ctypes.c_ulong()
             if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                 kernel32.SetConsoleMode(handle, mode.value | 4)
         except Exception as e:
+            # Silencioso, mas evita o crash do fluxo de I/O
             pass
+
     if autoreset:
+        # Registra a função de limpeza automática
         atexit.register(_force_reset)
-      

--- Resumo: 45 comparados, 45 divergentes ---
[0m
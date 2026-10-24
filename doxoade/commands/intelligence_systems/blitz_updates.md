## 📌 Alinhamento Consolidado

### O que o `intelligence` **é** (papel canônico)

- **Relatório de sistema para LLMs.** Ele apresenta o Doxoade (e o projeto alvo) para um modelo de linguagem.
- **Análise técnica é secundária.** O valor está em: metadados, estrutura, glossário, visão geral, source quando pedido.
- **Heurística simples é aceitável.** O `god_assignment` é protocolo interno, não precisa ser "correto" semanticamente — precisa ser **consistente** e **explicado ao modelo**.
- **Não deve ignorar arquivos essenciais.** Binários (`.dll`, `.exe`) entram como metadados (existe/não existe, tamanho, hash). `.pyd`/`.so` são ignorados por ora. C/C++ fica como está (regex, sem AST). `tree-sitter` é futuro.

### O que **motivou** o aprimoramento (foco real)

1. **Explicar o Doxoade para o modelo.** O glossário de deuses existe, mas o modelo não sabe o que é o Doxoade, o ProDeNov, o Strap, o Typhon, o MPoT (defasado), o God protocol. Isso precisa ir no dossiê.
2. **Notificar funções sem `except` explicativo.** Detectar `try` sem `except` com mensagem útil, ou funções que fazem IO/parse sem tratamento. Isso é **débito técnico acionável** e pedagógico.
3. **Não ignorar arquivos essenciais.** Garantir que o pipeline não descarte arquivos que importam (build files, configs, etc.).
4. **Não ter dor de cabeça depois** quando for discutir o Tianzun (C++).

### O que **não** é escopo agora

- Parser C++ real / tree-sitter.
- Reuso de `check`/`security`/`deepcheck` (eles permanecem desacoplados).
- Grafo multi-linguagem.
- Paralelismo via multiprocessing — **mas** o Strap é a arquitetura canônica para streaming assíncrono, e o `intelligence` pode ser um **consumidor** dela no futuro. Por ora, sequencial e determinístico.
- Truncation verification mais robusta (a atual basta).
- Novos formatos de saída (XML é a escolha; markdown fica como possível futuro).

### MPoT

- **Defasado.** Não formalizar. O ProDeNov substitui.
- **Decisão:** manter o campo `mpot_violations` no XML por **compatibilidade** (não quebrar consumidores), mas **renomear semanticamente** no glossário para "débito legado (MPoT, substituído por ProDeNov)". Ou remover? — **pergunta abaixo**.

---

## ❓ Dúvidas remanescentes (curtas)

Antes de escrever o plano, preciso confirmar 4 pontos:

**D1. Remover ou manter `mpot_violations`?**
- (a) Manter o campo (compatibilidade), mas documentar no glossário como "legado MPoT".
- (b) Remover do XML.
- (c) Manter, mas **substituir a métrica** por uma aderente ao ProDeNov (ex: `prodenov_violations` contando: função >60 linhas, ausência de `except` explicativo, ausência de plano B em capítulo crítico).

**D2. "Função sem except explicativo" — qual o critério exato?**
Proponho 3 heurísticas combinadas (todas via AST, Python only por ora):
- **H1:** Função contém `try` cujo `except` tem corpo vazio, `pass`, ou só `raise` sem mensagem (`raise` nu, `raise e`, `raise Exception()`).
- **H2:** Função chama APIs de IO/parse reconhecidas (`open`, `json.load`, `ast.parse`, `subprocess.run`, `requests.*`, `os.*`, `sqlite3.*`) **fora** de qualquer `try`.
- **H3:** Função tem `except Exception` genérico **sem** `logger`/`print`/`raise` com contexto (ex: `except Exception: pass`).

Pergunta: **H1+H2+H3** é o critério? Ou só H1? Ou outro?

**D3. O glossário do Doxoade — o que incluir?**
Proponho uma seção `<doxoade_context>` no XML com:
- O que é o Doxoade (1 parágrafo).
- O que é o ProDeNov (1 parágrafo + link para o `.md`).
- Conceitos: Blitz, Strap, Typhon, God Protocol, Blacklist, DNA, Silo, Metalcraft, Vulcan.
- O que o `intelligence` **faz** e **não faz** (para o modelo não alucinar).

Pergunta: **isso é o suficiente?** Falta algum sistema que o modelo **precisa** saber para entender o dossiê?

**D4. "Não ignorar arquivos essenciais" — como garantir?**
Hoje o `intelligence` usa `get_ignore_spec` (respeita `.gitignore`, `intelligence.toml`, `pyproject.toml`). O risco é: um arquivo essencial (ex: `metalcraft.toml`, `Makefile`, `CMakeLists.txt`, `pyproject.toml`, `.env.example`) ser ignorado por regra genérica.
Proponho:
- **Whitelist de nomes essenciais** (nunca ignorar): `pyproject.toml`, `metalcraft.toml`, `intelligence.toml`, `Makefile`, `CMakeLists.txt`, `requirements*.txt`, `setup.py`, `Dockerfile`, `.env.example`, `README*`, `LICENSE*`, `*.dox`.
- **Auditoria de cobertura** já existe (`--analyze`), mas só reporta. Poderia **falhar** (exit≠0) se um arquivo essencial foi ignorado.

Pergunta: **whitelist fixa** é o caminho, ou você prefere que seja **configurável** em `intelligence.toml` (com um default sensato)?

---

## 🗺️ Plano de Aprimoramento (pré-aprovação, sujeito às respostas)

Seguindo ProDeNov (§1 planejamento, §2 placeholders, §5.6 roteiro):

### Capítulo 1 — Contexto Doxoade no XML (`<doxoade_context>`)
- **Objetivo:** o modelo entende o que é o Doxoade, o ProDeNov, o Strap, o God Protocol, e o papel do `intelligence`.
- **Arquivo:** `intelligence_utils.py` (nova função `get_doxoade_context()`), `intelligence.py` (`_save_llm_report` e `_save_qwen_report` incluem a seção).
- **Plano A:** seção fixa hardcoded (dict em `intelligence_utils.py`).
- **Plano B:** carregar de `doxoade/docs/Protocols/ProDeNov.md` (resumo + link) — se o arquivo existir no `CORE_ROOT`.
- **Validação:** XML gerado contém `<doxoade_context>` com ≥5 conceitos; modelo consegue responder "o que é o Strap?" lendo o dossiê.

### Capítulo 2 — Detecção de "except não explicativo" (Python)
- **Objetivo:** reportar funções com tratamento de exceção frágil (H1/H2/H3, conforme D2).
- **Arquivo:** `intelligence_utils.py` (`ChiefInsightVisitor` ganha `_analyze_except`), `intelligence_engine.py` (popula `data["error_handling_findings"]`), `intelligence.py` (serializa no XML).
- **Plano A:** AST-based (preciso, Python only).
- **Plano B:** regex fallback (se `ast.parse` falhar, não reporta — evita falso positivo).
- **Validação:** rodar no próprio Doxoade e no Tianzun; comparar contagem manual em 3 arquivos.

### Capítulo 3 — Garantia de cobertura (whitelist essencial)
- **Objetivo:** nenhum arquivo essencial é ignorado silenciosamente.
- **Arquivo:** `intelligence_utils.py` (`get_ignore_spec` ganha whitelist), `intelligence.py` (`_run_analyze_coverage` reporta "essenciais ignorados").
- **Plano A:** whitelist fixa + warn no `--analyze`.
- **Plano B:** whitelist configurável em `intelligence.toml` (`essential_files = [...]`).
- **Validação:** rodar `--analyze` no Tianzun; confirmar que `metalcraft.toml`, `pyproject.toml`, `requirements.txt` aparecem como "target" (não "ignored").

### Capítulo 4 — Correção do bug de CDATA
- **Objetivo:** corrigir `]]]]><![CDATA[></source_code>` → `]]></source_code>` (e o `safe_src.replace` correspondente).
- **Arquivo:** `intelligence.py` (`_save_llm_report`).
- **Plano A:** corrigir direto.
- **Plano B:** se houver motivo oculto (algum consumidor depende do formato atual), manter e documentar.
- **Validação:** `xmllint --noout` no XML gerado; parse com `xml.etree` sem erro.

### Capítulo 5 — `mpot_violations` (decisão D1)
- **Objetivo:** alinhar com ProDeNov.
- **Arquivo:** `intelligence.py` (serialização), `intelligence_utils.py` (glossário).
- **Plano A/B/C:** conforme D1.

---


## 📋 Alinhamento Consolidado (D1–D4)

| Item | Decisão |
|:---|:---|
| **D1** | Manter `mpot_violations` no XML (compatibilidade), mas **substituir a métrica** por `prodenov_violations` (opção **c**). O glossário documenta MPoT como "legado". |
| **D2** | Critério de "except não explicativo" = **H1** (função com `try` cujo `except` tem corpo vazio/`pass`/`raise` nu). H2 e H3 ficam para futuro. |
| **D3** | Sim, incluir `<doxoade_context>` com ProDeNov, Strap, Typhon, God Protocol, **Metalcraft** (relevante ao Tianzun), Vulcan, Silo, DNA. Fonte: `doxoade/docs/Protocols/ProDeNov.md` + `--help` do CLI. |
| **D4** | Whitelist fixa de arquivos essenciais (`pyproject.toml`, `metalcraft.toml`, `intelligence.toml`, `Makefile`, `CMakeLists.txt`, `requirements*.txt`, `setup.py`, `Dockerfile`, `.env.example`, `README*`, `LICENSE*`, `*.dox`). Configurável em `intelligence.toml` (opção `essential_files = [...]`). |

---

# 📜 BLITZPLAN — INTELIGÊNCIA v96 (Contexto Doxoade + Contratos)

**Documento:** `doxoade/docs/Blitzplans/blitzplan_intelligence_v96.md`  
**Protocolo:** ProDeNov v2.0 (§1.0–1.4, §2.1, §5.6)  
**Subsistemas:** Zeus (CLI) / Thoth (extração AST) / Atena (estratégia) / Hades (persistência de dossiê)  
**Foco:** Explicar o Doxoade ao LLM, notificar exceções frágeis (H1), garantir cobertura de arquivos essenciais.  
**Status:** Planejamento (nenhuma linha de código será escrita antes da aprovação).

---

## 1. Avaliação de Complexidade (ProDeNov §0)

* **0.0 Thirdparty:** Zero dependências novas. Tudo em stdlib (`ast`, `pathlib`, `json`, `tomllib`).
* **0.1 Devflow:** Baixo impacto. As mudanças são **aditivas** ao XML existente (novas tags), preservando compatibilidade com consumidores atuais.
* **0.2 Rabbit Hole:** Baixo. O parser Python já existe (`ast`); a extração de `--help` do CLI é via `subprocess` com timeout.
* **0.3 Sensibilidade:** Média. A geração de `<doxoade_context>` a partir do `--help` deve ser **cacheada** (o `--help` é estável, mas não deve rodar a cada arquivo).
* **0.4 Revisitar:** A estrutura `<doxoade_context>` deve ser extensível (novas chaves no TOML `doxoade_context`). A métrica `prodenov_violations` deve aceitar novos critérios no futuro (H2, H3) sem quebrar o schema.
* **0.5 Particularidade:** Nenhuma.

---

## 2. Matriz W5+2H (Diagnóstico)

| Eixo | Especificação |
|:---|:---|
| **O quê?** | Aprimorar o `intelligence` em 3 frentes: (1) `<doxoade_context>` no XML, (2) detecção H1 de `except` vazio (`prodenov_violations`), (3) whitelist de arquivos essenciais + auditoria em `--analyze`. |
| **Quem?** | Desenvolvedores e LLMs consumindo o dossiê. Zeus (CLI) orquestra, Thoth (AST) extrai, Atena (heurísticas) decide, Hades (XML) persiste. |
| **Onde?** | `doxoade/commands/intelligence_systems/intelligence.py` (CLI, XML), `intelligence_utils.py` (AST, glossário, whitelist), `intelligence_engine.py` (chamada), `intelligence.toml` (config). |
| **Quando?** | Em todo `doxoade intelligence .` e `doxoade intelligence --analyze`. |
| **Quanto?** | Impacto estimado: +5–10% no tempo de geração do XML (dado que o `<doxoade_context>` é gerado 1× e cacheado em memória). `--analyze` terá +3 verificações de cobertura. |
| **Por quê?** | O LLM não sabe o que é o Doxoade. O `except: pass` é um débito silencioso. Arquivos essenciais (ex.: `metalcraft.toml`) desaparecem do dossiê sem aviso. |
| **Origem** | Feedback do usuário após rodar `doxoade intelligence .` no projeto Tianzun e no Doxoade. |
| **Consequências** | Dossiê XML mais rico e autoexplicativo; XML ~5–15% maior; descoberta silenciosa de arquivos essenciais ignorados; melhor aderência ao ProDeNov. |

---

## 3. Planos de Contingência (ProDeNov §1.2.1)

### 🟢 Plano A (Principal — Aditivo + Cache + Config)
* `<doxoade_context>` montado a partir de um dict hardcoded (`get_doxoade_context()`) + override via `intelligence.toml` (seção `[doxoade_context]`).
* `prodenov_violations` = contagem H1 por arquivo, agregada no `<technical_debt>` (substituindo `mpot_violations`, mas mantendo `mpot_violations="0"` para compatibilidade).
* Whitelist de essenciais em `get_ignore_spec()` (nunca ignorados) + auditoria em `--analyze` (reporta "essenciais ignorados" e sai com código ≠ 0 se houver).

### 🟡 Plano B (Fallback — Config-Driven)
* Se `intelligence.toml` não existir ou estiver corrompido, o `<doxoade_context>` usa apenas o dict hardcoded.
* Se o `--help` do CLI falhar (timeout/erro), o `<doxoade_context>` omite a seção `<cli_commands>` e loga um `warning` no dossiê (sem quebrar a geração).
* Se a whitelist for removida do TOML, o default sensato (hardcoded) entra em vigor.

### 🔴 Plano C (Kill Switch)
* Variável de ambiente `DOXOADE_INTELLIGENCE_NO_CONTEXT=1` desativa a geração do `<doxoade_context>` (retorno ao comportamento v95.6).
* Variável `DOXOADE_INTELLIGENCE_NO_WHITELIST=1` desativa a whitelist (retorno ao comportamento estrito do `.gitignore`).

---

## 4. Estrutura de Arquivos (ProDeNov §2.1 — limite 50KB)

Nenhum arquivo novo. Apenas 4 arquivos existentes serão tocados:

| Arquivo | Tamanho est. após | Limite |
|:---|:---:|:---:|
| `intelligence_utils.py` | ~42 KB | < 50 KB ✅ |
| `intelligence.py` | ~38 KB | < 50 KB ✅ |
| `intelligence_engine.py` | ~18 KB | < 50 KB ✅ |
| `intelligence.toml` | ~3 KB | < 50 KB ✅ |

---

# 📖 CAPÍTULOS (Tasklist + Checklist + DoD)

## CAPÍTULO 1 — `<doxoade_context>` no XML

**Objetivo:** Explicar ao LLM o que é o Doxoade, o ProDeNov, o Strap, o Typhon, o Metalcraft, o Vulcan, o God Protocol, o Silo/DNA. Incluir o `--help` do CLI como `<cli_commands>`.

**Arquivos:** `intelligence_utils.py` (nova função `get_doxoade_context()`, `get_cli_help()`), `intelligence.py` (`_save_llm_report` insere a seção), `intelligence.toml` (seção `[doxoade_context]` opcional).

**Plano A:** dict hardcoded + override TOML + `--help` via `subprocess` cacheado.

**Plano B:** se o TOML existir mas estiver corrompido → dict hardcoded + warning no XML.

**Checklist:**
- [ ] `get_doxoade_context()` retorna dict com `what_is_doxoade`, `prodenov`, `strap`, `typhon`, `metalcraft`, `vulcan`, `god_protocol`, `silo_dna`, `cli_commands`.
- [ ] `--help` do CLI é extraído 1× e cacheado em memória (via `functools.lru_cache`).
- [ ] `<doxoade_context>` é emitido **antes** de `<god_glossary>` no XML (após `<focus_applied>`).
- [ ] Override via `intelligence.toml` (`[doxoade_context]`) funciona.
- [ ] `DOXOADE_INTELLIGENCE_NO_CONTEXT=1` desativa a seção.

**DoD:**
- Rodar `doxoade intelligence . --ai-export` e inspecionar `chief_dossier_llm.xml`.
- Verificar que `<doxoade_context>` contém as 9 chaves e que `<cli_commands>` lista ≥ 50 comandos do `--help`.
- Rodar com `intelligence.toml` modificado e confirmar override.
- Rodar com env var e confirmar ausência da seção.
- LLM (teste manual): "O que é o Metalcraft?" → resposta baseada no XML.

---

## CAPÍTULO 2 — Detecção de `except` Vazio (H1) → `prodenov_violations`

**Objetivo:** Detectar funções Python que têm `try/except` com `except` vazio (`pass`), `raise` nu, ou `raise Exception()` sem contexto. Reportar como `prodenov_violations`.

**Arquivos:** `intelligence_utils.py` (`ChiefInsightVisitor._analyze_except`), `intelligence_engine.py` (popula `data["prodenov_violations"]`), `intelligence.py` (XML).

**Plano A:** AST-based (preciso). Só Python.
**Plano B:** se `ast.parse` falhar (truncamento), não reportar (sem falso positivo).

**Checklist:**
- [ ] `_analyze_except(node)` em `ChiefInsightVisitor` detecta 3 padrões:
  - `except:` com `pass` (qualquer tipo).
  - `except Exception:` com `pass`.
  - `except Exception as e:` com `raise` nu (`raise`, `raise e`, `raise Exception()`).
- [ ] Cada ocorrência vira `{"line": N, "func": "<nome>", "pattern": "empty_pass|bare_raise|generic_raise"}`.
- [ ] `data["prodenov_violations"] = len(occurrences)`.
- [ ] XML: `<technical_debt tags="0" mpot_violations="0" prodenov_violations="N" />`.
- [ ] Glossário atualizado: MPoT = "legado (substituído por ProDeNov)".

**DoD:**
- Criar arquivo de teste `tests/fixtures/except_vazio.py` com 5 funções (2 vazias, 1 `raise` nu, 1 `raise Exception()`, 1 OK).
- Rodar `doxoade intelligence . --ai-export` e verificar `prodenov_violations="3"` para esse arquivo.
- Rodar no código do Doxoade e comparar contagem manual (esperado: dezenas de ocorrências, todas legítimas).
- Rodar no Tianzun (C++) e confirmar `prodenov_violations="0"` (não se aplica).

---

## CAPÍTULO 3 — Whitelist de Arquivos Essenciais + Auditoria `--analyze`

**Objetivo:** Nunca ignorar arquivos essenciais. Auditar via `--analyze` e reportar "essenciais ignorados".

**Arquivos:** `intelligence_utils.py` (`get_ignore_spec` ganha whitelist), `intelligence.py` (`_run_analyze_coverage` reporta).

**Plano A:** whitelist fixa hardcoded + configurável via `intelligence.toml` (`essential_files = [...]`).
**Plano B:** se TOML corrompido, usa whitelist hardcoded.

**Whitelist default:**
```
pyproject.toml, metalcraft.toml, intelligence.toml, Makefile, CMakeLists.txt,
requirements*.txt, setup.py, Dockerfile, .env.example, README*, LICENSE*, *.dox
```

**Checklist:**
- [ ] `get_ignore_spec(root, extra_patterns, essential_files)` retorna PathSpec **e** whitelist.
- [ ] Nenhum arquivo da whitelist é descartado por `ignore_spec.match_file()`.
- [ ] `_run_analyze_coverage` reporta "essenciais ignorados" (se algum foi ignorado por regra do `.gitignore`, warn; se foi ignorado por regra do próprio `intelligence.toml`, warn explícito).
- [ ] `--analyze` sai com código 1 se houver essencial ignorado.
- [ ] `DOXOADE_INTELLIGENCE_NO_WHITELIST=1` desativa a whitelist.

**DoD:**
- Rodar `doxoade intelligence . --analyze` no Tianzun e confirmar que `metalcraft.toml`, `pyproject.toml`, `requirements.txt` aparecem como "target" (não "ignored").
- Rodar no Doxoade e confirmar que `pyproject.toml`, `intelligence.toml`, `metalcraft.toml` não são ignorados.
- Adicionar `pyproject.toml` ao `intelligence.toml` (`ignore = ["pyproject.toml"]`) e confirmar que `--analyze` warn (essencial ignorado) e sai com código 1.
- Confirmar que `DOXOADE_INTELLIGENCE_NO_WHITELIST=1` restaura comportamento antigo.

---

## CAPÍTULO 4 — Correção do Bug de CDATA

**Objetivo:** Corrigir `]]]]><![CDATA[></source_code>` → `]]></source_code>` (bug visível no dossiê do Tianzun).

**Arquivos:** `intelligence.py` (`_save_llm_report`).

**Plano A:** corrigir direto.
**Plano B:** se algum consumidor depender do formato atual, manter e documentar (a confirmar).

**Checklist:**
- [ ] `safe_src.replace(']]]]><![CDATA[>', ']]]]]]><![CDATA[><![CDATA[>')` removido (era o bug).
- [ ] `lines.append('      ]]]]><![CDATA[></source_code>')` corrigido para `lines.append(']]></source_code>')` (com os espaços corretos).
- [ ] `xmllint --noout chief_dossier_llm.xml` roda sem erro.
- [ ] `python -c "import xml.etree.ElementTree as ET; ET.parse('chief_dossier_llm.xml')"` roda sem erro.

**DoD:**
- Rodar `doxoade intelligence . --ai-export`.
- Verificar com `xmllint` ou `ET.parse`.
- Comparar tamanho do XML antes/depois (esperado: ligeiramente menor, pois o bug adicionava bytes extras).

---

## CAPÍTULO 5 — `mpot_violations` → `prodenov_violations` (D1)

**Objetivo:** Substituir a métrica legada MPoT pela métrica ProDeNov. Manter `mpot_violations="0"` por compatibilidade.

**Arquivos:** `intelligence.py` (serialização), `intelligence_utils.py` (glossário).

**Checklist:**
- [ ] `<technical_debt tags="N" mpot_violations="0" prodenov_violations="M" />` (M = H1 do Capítulo 2).
- [ ] Glossário: adicionar nota "MPoT = legado (substituído por ProDeNov; mantido por compatibilidade)".
- [ ] `get_god_glossary()` ganha entrada `"prodenov"` com a descrição.

**DoD:**
- Confirmar que consumidores antigos (que leem `mpot_violations`) continuam funcionando (valor 0).
- Confirmar que `prodenov_violations` reflete a contagem real H1.

---

## 5. Roteiro de Implementação (RIT — ProDeNov §5.6)

**Ordem sugerida (do menor risco ao maior):**

```
Cap 4 (CDATA)  →  Cap 5 (mpot → prodenov)  →  Cap 3 (whitelist)  →  Cap 2 (H1)  →  Cap 1 (context)
```

**Por quê?**
- **Cap 4** é correção de bug isolada (5 min, baixo risco).
- **Cap 5** é mecânico (renomeação + glossário).
- **Cap 3** (whitelist) é independente e testável via `--analyze`.
- **Cap 2** (H1) depende de `ast` e alimenta o Cap 5.
- **Cap 1** (contexto) é o mais extenso (dict + TOML + CLI + cache) e beneficia-se dos outros prontos.

**Loop por capítulo (ProDeNov §5.6.2):**
1. Discussão (o que será feito, plano A/B).
2. Implementação (código + testes manuais).
3. Teste (rodar no Doxoade + Tianzun + fixtures).
4. Discussão/revisão (diff, regressões, manutenibilidade).

**Após Cap 1:** rodar `doxoade regret` (se existir) e `doxoade check .` no Doxoade para garantir que nada regrediu.

---

## 6. Checklist Final de Homologação (ProDeNov §5.6.4)

- [ ] `doxoade intelligence .` no **Doxoade** gera XML válido (xmllint) com `<doxoade_context>`, `prodenov_violations`, whitelist aplicada, CDATA correto.
- [ ] `doxoade intelligence .` no **Tianzun** gera XML válido com `<doxoade_context>` (incluindo Metalcraft) e `prodenov_violations="0"` (C++).
- [ ] `doxoade intelligence . --analyze` no **Tianzun** reporta que `metalcraft.toml`, `pyproject.toml`, `requirements.txt` são targets.
- [ ] `doxoade intelligence . --analyze` no **Doxoade** confirma que `pyproject.toml`, `intelligence.toml`, `metalcraft.toml` não são ignorados.
- [ ] `DOXOADE_INTELLIGENCE_NO_CONTEXT=1` restaura comportamento v95.6.
- [ ] `DOXOADE_INTELLIGENCE_NO_WHITELIST=1` restaura comportamento estrito.
- [ ] `doxoade check .` no Doxoade sem novas regressões.
- [ ] Diff revisado (ProDeNov §5.5).

---


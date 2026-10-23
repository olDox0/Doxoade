# 🏛️ BLITZPLAN — Vulcan Generalista

**Protocolo:** ProDeNov §5.6 (discussão → decisão → implementação → teste)
**Contexto:** Dados de 497 funções (Vulcan + ORN) mostram que o Cython direto **não compensa em 98,9% do código**. Mas 60% das calls são refatoráveis. Precisamos decidir: **o Vulcan generalista deve (a) compilar tudo e aceitar ganho marginal, ou (b) filtrar agressivamente e aceitar que só 2% compensa?**

---

## Parte 1 — O Paradoxo do Vulcan Generalista

Você tocou no ponto crucial: **"o Vulcan existe porque transforma Python em metal. 90% são elegíveis mesmo que não gere ganho."**

**Isso é a essência do problema.** Vamos formalizar o paradoxo:

### ✅ Caso a favor de compilar tudo (opção A)

1. **Simplicidade de UX** — usuário roda `vulcan ignite` e tudo compila. Zero decisão.
2. **Fallback silencioso** — se não compensou, o Tier 2 (Python otimizado) ainda roda.
3. **Consistência** — não precisa ensinar o usuário a "pensar como Cython".
4. **Defesa contra regressão** — se você decide não compilar e depois muda o código, precisa redecidir.

### ❌ Caso contra compilar tudo (opção B)

1. **Tempo de build** — 90 min de compile ORN (500s) para gerar 0 ADAMANTIUM.
2. **Risco de bug** — 522 arquivos quebrados no incidente do `--auto-main` são evidência empírica.
3. **Ilusão de performance** — usuário vê "13 compilado(s)" e pensa "13× mais rápido". Falso.
4. **Debt técnico** — cada função compilada que não vale é superfície de manutenção.
5. **Time wasted** — 90 min de build vs 0 ganho mensurável é ROI negativo.

### 🎯 A pergunta central

**"Quem é o cliente do Vulcan?"**

- **Se é o doxoade-internal**: compilar tudo é OK (build noturno, sem pressa).
- **Se é o usuário do ORN**: compilar tudo é hostil (cada build de 90 min é dor).
- **Se é biblioteca terceira**: compilar tudo é irresponsável (bugs em produção).

**A resposta honesta:** são **três clientes diferentes**. O Vulcan precisa **3 modos de operação**, não 1.

---

## Parte 2 — Três Modos de Operação Propostos

### Modo 1 — `SAFE` (padrão para usuário final)

**Filosofia:** só compila o que comprovadamente ganha.

**Critério:**
```
hoist + safe + batch + native >= 5
AND
(hoist + safe + batch + native) / (blocked + 1) >= 2.0
AND
score_calibrado >= 15 (BRONZE+)
```

**Efeito no corpus atual:**

- **Vulcan:** 2 funções elegíveis (`_build_fetch_ranges`, `_kill_registry`)
- **ORN:** 3 funções elegíveis (`build_index`, `_handle`, `get_runtime_status`)
- **Build time:** cai de 90 min para ~30 s
- **Ganho real:** concentrado nos 5 alvos de ROI

**Quando usar:** produção, usuário final, CI/CD.

**Trade-off:** compila quase nada. Mas **o que compila, funciona**.

### Modo 2 — `BALANCED` (padrão do doxoade-internal)

**Filosofia:** compila o que tem **potencial** de ganho se refatorado.

**Critério:**
```
score_calibrado >= 15 (BRONZE+)
AND
blocked / total_calls < 0.5
```

**Efeito no corpus atual:**

- **Vulcan:** ~15 funções elegíveis
- **ORN:** ~40 funções elegíveis
- **Build time:** cai para ~5 min
- **Ganho real:** ~2× em funções que vão virar template depois

**Quando usar:** desenvolvimento do doxoade, testes internos, código que você controla.

**Trade-off:** algumas compilam sem ganho imediato, mas ficam prontas para futura otimização.

### Modo 3 — `AGGRESSIVE` (opt-in, debug/perf research)

**Filosofia:** compila tudo, para análise.

**Critério:** o atual (compila tudo).

**Quando usar:** você quer medir headroom, coletar dados, investigar regressão.

**Trade-off:** lento, gera ruído, mas dá visibilidade total.

---

## Parte 3 — O Padrão "Quase 90% Elegível" — Vale Repensar

**Sua frase:** *"quase 90% dos python são elegíveis mesmo que não gere ganho."*

Isso é **tecnicamente verdadeiro, mas estrategicamente enganoso**. Deixe-me mostrar por quê:

### O que "elegível" significa no código atual

`assess_file_for_vulcan` retorna `True` se:
- Não é `__init__.py` ou `__main__.py`
- Não tem ≥2 de `[ctypes, socket, subprocess, threading, multiprocessing, asyncio, llama_cpp]`
- AST tem < 10000 nodes

**Isso filtra 0 funções no corpus.** Todos os 497 passam.

**"Elegível" ≠ "compensativo".** A palavra "elegível" carrega a **expectativa** de ganho. Mas os dados dizem: ganho é ~0.

**Proposta de vocabulário:**

| Termo | Significado | Quando usar |
|-------|-------------|-------------|
| **elegível** | Pode ser compilado (não quebra) | Atual — precisa corrigir |
| **compilável** | Cython transpila sem erro | Melhor termo |
| **produtivo** | Compilar reduz tempo de execução | Termo novo, honesto |
| **compensativo** | ROI positivo (build time + manutenção vs ganho) | Termo novo, definitivo |

**Com essa taxonomia:** dos 497, **todos** são compiláveis, mas só **5 são produtivos e compensativos**.

**E daí?** Não é problema. **É natureza do Python.** A maioria do código Python é I/O e orquestração — isso é Cython-resistant.

O que **é** problema: vender "Vulcan transforma tudo em metal" quando transforma **5 funções em metal com ganho, e 492 em metal sem ganho**.

---

## Parte 4 — Onde Está o Valor Real do Vulcan Generalista

Vamos repensar a partir dos dados. **Onde o Vulcan (atual) está agregando valor real?**

### Valor 1 — O Tier 2 (`opt_py`) é o verdadeiro herói

Olhe o `opt_benchmark.py`: 14 funções, 0 ADAMANTIUM, 0 STEEL. **O `opt_bench` compara Python puro vs Python otimizado (Tier 2)**, não Tier 2 vs Cython.

Os resultados de `opt_bench` que vimos antes mostram **-7% a +40% no tamanho de código, -5% a +50% no tempo de execução**. **Isso é o `LibOptimizer` (Tier 2), não o Cython (Tier 1).**

**Insight crítico:** o Tier 2 (Python otimizado via AST rewrite) **é mais efetivo** que o Tier 1 (Cython) para a maioria do código Python idiomático.

**Tier 1 (Cython)** ganha em: loops numéricos, simd, memória.
**Tier 2 (opt_py)** ganha em: código Python típico (string ops, I/O, orquestração).

**O Vulcan generalista deveria priorizar Tier 2 para 95% do código e Tier 1 só para os 5% identificados pelo headroom.**

### Valor 2 — Os kernels nativos (`nexus_*`) são o verdadeiro Tier 1

Os 5 kernels do `nexus_kernels.c` (`nexus_asm_cmov`, `nexus_asm_vec_search`, etc.) **são o valor real do Cython no doxoade**. São usados via Cython direto, sem precisar compilar o corpo da função.

**Uma função pode ser Tier 2 (opt_py) E chamar kernels nativos.** Isso é o **melhor dos dois mundos**:

```python
# Função Python (Tier 3)
def search_many(haystacks, needle):
    for h in haystacks:
        if h.find(needle) >= 0:  # ← Python find (lento)
            yield h

# Tier 2 (opt_py) — AST rewrite, sem Cython
def search_many(haystacks, needle):
    _h_lower = needle.lower()      # ← cache de atributo
    for h in haystacks:
        if h.find(_h_lower) >= 0:  # ← ainda Python, mas marginalmente mais rápido
            yield h

# Tier 2 + kernel nativo (mix)
def search_many(haystacks, needle):
    _ptr_needle = needle.encode()   # ← bytes
    for h in haystacks:
        if nexus_asm_vec_search(h, len(h), _ptr_needle[0]) >= 0:
            yield h
```

**A revolução não é "compilar tudo em Cython". É "identificar onde colocar kernel nativo dentro do código Python otimizado".**

### Valor 3 — O `--auto-main` foi um erro conceitual

O incidente dos 522 arquivos quebrados revelou: **injetar bootstrap em todo arquivo Python não funciona em escala.**

O correto é:

1. **Detectar entry points reais** (não por heurística `@click` ou `if __name__`, mas por análise de grafo de imports).
2. **Injetar só nesses.**
3. **Nunca tocar em código terceiro.**

**Isso já está no roadmap** (skip list expandida). Mas o **conceito** por trás é mais profundo: **`--auto-main` foi otimização de UX ao custo de robustez**. Isso é anti-ProDeNov.

---

## Parte 5 — Proposta: Vulcan Generalista V2

Consolidando tudo:

### 5.1 — Modo de operação explícito

```bash
doxoade vulcan ignite <target> --mode safe       # padrão para usuário
doxoade vulcan ignite <target> --mode balanced   # padrão doxoade
doxoade vulcan ignite <target> --mode aggressive # opt-in, debug
```

**Cada modo tem seu próprio `assess_file_for_vulcan`:**

```python
def assess_file_for_vulcan(file_path, mode="safe"):
    # ... checks atuais ...
    if mode == "aggressive":
        return (True, "Elegível", [])
    
    # Coleta dados de headroom
    report = analyze_file(file_path)
    if not report.functions:
        return (False, "Sem funções", [])
    
    best = max(report.functions, key=lambda f: f.score)
    
    if mode == "safe":
        # Exige ROI claro
        calls = classify_calls_in_file(file_path)
        by_cat = Counter(e.category for e in calls)
        refactorable = sum(by_cat.get(c, 0) for c in
                          ("HOIST", "SAFE", "BATCH", "NATIVE"))
        blocked = by_cat.get("BLOCKED", 0)
        if best.score >= 15 and refactorable >= 5 and refactorable / max(blocked, 1) >= 2.0:
            return (True, f"SAFE: score={best.score}, ref={refactorable}", [])
        return (False, f"SAFE: score={best.score} insuficiente", [])
    
    if mode == "balanced":
        if best.score >= 15:
            return (True, f"BALANCED: score={best.score}", [])
        return (False, f"BALANCED: score={best.score} insuficiente", [])
```

### 5.2 — Dois tracks de otimização: Tier 2 + Tier 1

**Fluxo padrão `vulcan ignite --mode safe`:**

```
1. Analyze -> headroom
2. If headroom >= threshold:
     -> FORGE (Tier 1, Cython)
     -> opt_py (Tier 2, AST rewrite)
3. Else:
     -> opt_py only (Tier 2)
     -> Skip FORGE (economiza tempo)
4. Build report
```

**Isso reduz build time drasticamente.** No ORN, sai de 90 min para ~10 min.

### 5.3 — Kernel nativo como "primeira classe"

Ao invés do usuário escrever `nexus_asm_vec_search(buf, len, target)`, o **Vulcan deveria substituir chamadas Python idiomáticas por kernels automaticamente**:

```python
# ANTES (Python puro)
if needle in haystack: ...

# DEPOIS (Tier 2 + Kernel)
if nexus_asm_vec_search(haystack, len(haystack), needle[0]) >= 0: ...
```

**Isso é o "pattern hoist" real** — substituir função Python por kernel nativo equivalente.

**Candidatos:**

| Python idiom | Kernel nativo | Pattern detectado |
|--------------|---------------|-------------------|
| `needle in haystack` | `nexus_asm_vec_search` | SAFE + HOIST |
| `haystack.find(needle)` | `nexus_raw_search` | SAFE + HOIST |
| `int(x > y)` | `nexus_asm_cmov(1, x, y)` | INLINE |
| `bin(x).count('1')` | `nexus_asm_popcount` | SAFE |

**O `forge.py` já tem `_transform_funcdef` para reconhecer `_search_loop` e gerar `nexus_asm_vec_search`. O que falta é generalizar para `if needle in haystack`.**

### 5.4 — Skip rule compilação definitiva

Vou juntar as decisões:

**Regra final `assess_file_for_vulcan`:**

```
if mode == "aggressive":
    return True  # compila tudo

if mode == "safe":
    if score >= 15 AND refactorable >= 5 AND refactorable/blocked >= 2:
        return True
    return False

if mode == "balanced":
    if score >= 15:
        return True
    return False
```

**Com o corpus atual:**
- SAFE compila 5 funções
- BALANCED compila 17
- AGGRESSIVE compila 497 (atual)

### 5.5 — Tratamento especial para bibliotecas

Bibliotecas externas (`numpy`, `torch`, `llama_cpp`) nunca devem passar por Tier 1. **O `_NATIVE_HEAVY_LIBS` no `LibForge` já faz isso.** O `assess_file_for_vulcan` precisa **herdar esse filtro**:

```python
RISKY_LIBS = {'numpy', 'torch', 'tensorflow', 'llama_cpp', ...}

def assess_file_for_vulcan(file_path, mode="safe"):
    # Checa imports do AST
    tree = ast.parse(source)
    imported = {a.name for n in ast.walk(tree)
                if isinstance(n, ast.Import) for a in n.names}
    if imported & RISKY_LIBS:
        return (False, "Importa lib C-extension — jamais", [])
    ...
```

---

## Parte 6 — Comparação: Ação vs Inação

### Se implementar tudo (modo seguro + kernels):

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Build time ORN | 90 min | 10 min |
| Funções compiladas | 497 | 5 |
| Ganho real | 0% | 30-40% (concentrado) |
| Risco de regressão | Alto | Baixo |
| Complexidade do código | Alta | Média |
| Confiança do usuário | Baixa ("por que 497?") | Alta ("5 funções, 30% faster") |

### Se **não** implementar:

| Aspecto | Realidade |
|---------|-----------|
| Build time ORN | 90 min para 0 ganho |
| Funções compiladas | 497 |
| Ganho real | 0% |
| Risco de regressão | Alto (5 bugs encontrados em 2 semanas) |
| Confiança do usuário | Baixa |
| Debt técnico | Crescente |

**ROI de implementar: 100× (build 90→10 min, ganho 0→30%).**

---

## Parte 7 — Recomendação Consolidada

Vulcan precisa de **3 decisões**:

### Decisão 1 — Modo de operação (default)

**Recomendação:** `safe` como default, `balanced` para doxoade-internal, `aggressive` opt-in.

**Impacto:** 90% dos usuários usam `safe`. Build time cai 90%.

### Decisão 2 — Track Tier 2 + Tier 1 sempre

**Recomendação:** sempre rodar `opt_py` (Tier 2), só rodar Tier 1 se `assess_file_for_vulcan` retorna `True`.

**Impacto:** todo arquivo ganha o ganho de Tier 2 (~-7% exec, -5% tamanho). Tier 1 é cirúrgico.

### Decisão 3 — Kernel substitution automática

**Recomendação:** Fase 3 do roadmap. Substituir `if x in y` por `nexus_asm_vec_search` no forge.

**Impacto:** +15-30% nas funções com HOIST dominante.

---

## Parte 8 — Tasklist (se aprovar)

### Fase 1 — Modos + Skip Rule (2-3 dias)

- [ ] Adicionar `--mode {safe,balanced,aggressive}` a `vulcan ignite`
- [ ] Reescrever `assess_file_for_vulcan` com os 3 modos
- [ ] Fazer `vulcan ignite` sempre rodar `opt_py` (Tier 2) em todo arquivo
- [ ] Só rodar `forge.py` se `assess_file_for_vulcan` retorna `True`
- [ ] Reduzir build time ORN de 90 min → ~10 min

### Fase 2 — Skip rule + Kernel substitution (1 semana)

- [ ] Detectar `needle in haystack` no forge → `nexus_asm_vec_search`
- [ ] Detectar `haystack.find(needle)` no forge → `nexus_raw_search`
- [ ] Detectar `bin(x).count('1')` no forge → `nexus_asm_popcount`
- [ ] **Não aplicar automaticamente** — só sugerir via `vulcan forge --template-kernel`

### Fase 3 — Tier 2 optimization (2 semanas)

- [ ] Expandir `LibOptimizer` para detectar padrões de kernel nativo
- [ ] Substituir no AST → Cython-friendly
- [ ] Reportar "ganho estimado" por função
- [ ] Benchmark Tier 2 vs Tier 3 vs mix

---

# 🔬 Detalhamento Completo — Fase 1: Modos + Skip Rule

Você está certo. A automatização da tomada de decisão **é exatamente o ponto**: humanos erram na escolha de "compilar ou não compilar". O sistema deve decidir **com base em evidência**, não em intuição do usuário.

Vou detalhar a Fase 1 em **7 subfases**, cada uma com:

- Objetivo
- Arquivos afetados
- Mudanças exatas
- Comportamento antes/depois
- Testes de validação
- Rollback (ProDeNov §4.1)

---

## 🎯 Objetivo da Fase 1 (uma frase)

> **"Fazer o Vulcan decidir automaticamente o que compilar, baseado em evidência de headroom, sem intervenção do usuário — mas mantendo a capacidade de override manual."**

---

## 📋 Subfase 1.1 — Introduzir o conceito de "mode" no sistema

### Objetivo

Adicionar o conceito de **modo de operação** sem ainda mudar comportamento. Só infraestrutura.

### Arquivos afetados

- `doxoade/commands/vulcan_cmd/vulcan_cmd_forge.py` (comando `ignite`)
- `doxoade/tools/vulcan/autopilot.py` (`scan_and_optimize`)

### Mudança exata

**Em `vulcan_cmd_forge.py::ignite`, adicionar a opção:**

```python
@click.option(
    "--mode", "-m",
    type=click.Choice(["safe", "balanced", "aggressive"]),
    default="safe",
    show_default=True,
    help=(
        "SAFE: compila apenas funções com ROI comprovado (padrão). "
        "BALANCED: compila se score de headroom >= 15. "
        "AGGRESSIVE: compila tudo (comportamento antigo)."
    ),
)
def ignite(ctx, path, soteria, force, jobs, no_pitstop, streaming, hybrid,
           scan_only, simd, simd_level, mode):
    ...
    # Propaga o mode para o autopilot
    autopilot.scan_and_optimize(
        candidates=candidates,
        force_recompile=force,
        max_workers=jobs,
        use_pitstop=not no_pitstop,
        streaming=streaming,
        use_soteria=soteria,
        mode=mode,  # ← NOVO
    )
```

**Em `autopilot.py::scan_and_optimize`, aceitar e propagar:**

```python
def scan_and_optimize(self, candidates=None, force_recompile=False, max_workers=None,
                      use_pitstop=True, streaming=True, use_soteria=False,
                      mode="safe"):  # ← NOVO parâmetro
    ...
    self._current_mode = mode  # armazena no estado
    ...
```

### Comportamento antes/depois

**Antes:**
```bash
doxoade vulcan ignite engine/  # compila tudo
```

**Depois:**
```bash
doxoade vulcan ignite engine/                      # compila só SAFE
doxoade vulcan ignite engine/ --mode aggressive    # compila tudo (compatível)
doxoade vulcan ignite engine/ --mode balanced      # compila médio
```

**Nada quebra.** Quem usar `--mode aggressive` tem comportamento **idêntico ao atual**. `--mode safe` é o novo default, mas pode ser desabilitado.

### Teste de validação

```bash
doxoade vulcan ignite --help | grep -A2 "mode"
# Esperado: mostra as 3 opções
```

### Rollback

Se `--mode safe` causar problema, o usuário adiciona `--mode aggressive` em todos os builds. **Zero mudança de código necessária.**

---

## 📋 Subfase 1.2 — Reescrever `assess_file_for_vulcan` com 3 estratégias

### Objetivo

Centralizar a decisão de elegibilidade em uma única função **que respeita o mode**.

### Arquivos afetados

- `doxoade/tools/vulcan/forge.py` (`assess_file_for_vulcan`)

### Mudança exata

**Substituir a função atual por:**

```python
def assess_file_for_vulcan(
    file_path: str,
    mode: str = "safe",
) -> tuple[bool, str, list[str]]:
    """
    Auditoria de elegibilidade para Vulcan Tier 1 (Cython).

    Modes:
      safe       — só compila se ROI comprovado (padrão)
      balanced   — compila se score >= 15, sem exigir ROI estrito
      aggressive — compila tudo (comportamento legado)

    Returns:
        (eligible: bool, reason: str, details: list[str])
    """
    p = Path(file_path)

    # === Checks estruturais (sempre aplicados) ===
    if p.name in _SKIP_FILENAMES:
        return (False, "Arquivo de entrada/namespace",
                [f"{p.name} é reservado para o interpretador."])

    try:
        source = p.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except Exception as e:
        return (False, "Falha de AST", [str(e)])

    node_count = sum(1 for _ in ast.walk(tree))

    # === Detecção de libs C-extension (jamais compilar) ===
    RISKY_LIBS = {
        "numpy", "torch", "tensorflow", "llama_cpp", "libzim",
        "safetensors", "tokenizers", "transformers", "faiss",
        "chromadb", "sentence_transformers",
    }
    imported_libs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mod = a.name.split(".")[0]
                if mod in RISKY_LIBS:
                    imported_libs.add(mod)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module.split(".")[0]
            if mod in RISKY_LIBS:
                imported_libs.add(mod)

    if imported_libs:
        return (False, "Importa C-extension",
                [f"Vetores de risco: {', '.join(sorted(imported_libs))}",
                 "Cython causaria conflito de ABI com a lib nativa."])

    # === Detecção de APIs sensíveis (threading, socket, etc) ===
    _RISKY_APIS = frozenset({
        "ctypes", "socket", "subprocess", "threading",
        "multiprocessing", "asyncio",
    })
    risky_apis = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mod = a.name.split(".")[0]
                if mod in _RISKY_APIS:
                    risky_apis.append(mod)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module.split(".")[0]
            if mod in _RISKY_APIS:
                risky_apis.append(mod)

    risky_apis = sorted(set(risky_apis))

    # Veto estrutural: APIs sensíveis + arquivo grande = perigo
    if len(risky_apis) >= 2 and node_count > 3000:
        return (False, "ALTO RISCO ESTRUTURAL", [
            f"Densidade: {node_count} nodes",
            f"Vetores: {', '.join(risky_apis)}",
            "Risco de deadlock nativo em arquivos grandes.",
        ])

    if node_count > 10000:
        return (False, "COMPLEXIDADE EXTREMA",
                [f"{node_count} nodes (máx 10000)"])

    # === Modo aggressive: compila tudo após checks estruturais ===
    if mode == "aggressive":
        return (True, "AGGRESSIVE: elegível", [])

    # === Modos safe/balanced: exigem análise de headroom ===
    from doxoade.tools.vulcan.purity_analyzer import (
        analyze_file, classify_calls_in_file, CallCategory,
    )

    report = analyze_file(str(p))
    if not report.functions:
        return (False, f"{mode.upper()}: sem funções", [])

    # Score máximo entre as funções do arquivo
    best_score = max(f.score for f in report.functions)

    # === Modo balanced: só exige score mínimo ===
    if mode == "balanced":
        if best_score >= 15:
            return (True, f"BALANCED: score={best_score}", [])
        return (False, f"BALANCED: score={best_score} < 15",
                [f"Melhor função tem score {best_score}, abaixo do threshold."])

    # === Modo safe: exige score + ROI de calls ===
    if mode == "safe":
        if best_score < 15:
            return (False, f"SAFE: score={best_score} < 15", [])

        # Análise de calls refatoráveis
        calls = classify_calls_in_file(str(p))
        if not calls:
            return (False, "SAFE: sem calls em loop", [])

        from collections import Counter
        by_cat = Counter(c.category for c in calls)
        refactorable = (
            by_cat.get(CallCategory.HOIST, 0) +
            by_cat.get(CallCategory.SAFE, 0) +
            by_cat.get(CallCategory.BATCH, 0) +
            by_cat.get(CallCategory.NATIVE, 0)
        )
        blocked = by_cat.get(CallCategory.BLOCKED, 0)

        # Regra SAFE: pelo menos 5 calls refatoráveis E razão >= 2
        if refactorable < 5:
            return (False, f"SAFE: {refactorable} calls refatoráveis < 5", [])

        ratio = refactorable / max(blocked, 1)
        if ratio < 2.0:
            return (False,
                    f"SAFE: ref/blocked = {ratio:.1f} < 2.0",
                    [f"{refactorable} refatoráveis, {blocked} bloqueadas"])

        return (True,
                f"SAFE: score={best_score}, ref={refactorable}, ratio={ratio:.1f}",
                [])

    # Fallback (não deveria acontecer)
    return (False, f"Modo desconhecido: {mode}", [])
```

### Comportamento antes/depois

| Arquivo | Antes (default implícito) | Depois SAFE | Depois BALANCED | Depois AGGRESSIVE |
|---------|---------------------------|-------------|-----------------|-------------------|
| `check_engine.py` | ✅ compila | ❌ skip (score 0) | ❌ skip | ✅ compila |
| `refactor_exec.py` | ✅ compila | ✅ compila (score 51, ref=10) | ✅ compila | ✅ compila |
| `autopilot.py` | ✅ compila | ✅ compila (ref=9 `_kill_registry`) | ✅ compila | ✅ compila |
| `opt_benchmark.py` | ✅ compila | ❌ skip (score 0) | ❌ skip | ✅ compila |

**Efeito no Vulcan corpus:** de 64 arquivos compilados para **~3** no modo SAFE, **~15** no BALANCED, **64** no AGGRESSIVE.

### Teste de validação

```bash
# Testar os 3 modos em arquivo conhecido
python -c "
from doxoade.tools.vulcan.forge import assess_file_for_vulcan
for mode in ['safe', 'balanced', 'aggressive']:
    ok, reason, details = assess_file_for_vulcan(
        'doxoade/tools/vulcan/refactor_exec.py', mode=mode
    )
    print(f'{mode:12}: {ok} | {reason}')
"
```

**Esperado:**
```
safe        : True | SAFE: score=51, ref=10, ratio=5.0
balanced    : True | BALANCED: score=51
aggressive  : True | AGGRESSIVE: elegível
```

### Rollback

Reverter função para versão anterior. Modo `aggressive` mantém comportamento original.

---

## 📋 Subfase 1.3 — Sempre rodar Tier 2, condicionalmente Tier 1

### Objetivo

Separar os dois tracks de otimização:

- **Tier 2 (opt_py)** — sempre, para todos os arquivos
- **Tier 1 (Cython)** — só se `assess_file_for_vulcan` retornar `True`

### Arquivos afetados

- `doxoade/tools/vulcan/pitstop.py::run` (ou `run_streaming`)
- `doxoade/tools/vulcan/pitstop.py::_filter_stale`

### Mudança exata

**Em `pitstop.py::run`, antes da filtragem de stale, adicionar:**

```python
def run(self, candidates, force_recompile=False, max_workers=None,
        streaming=False, use_soteria=False, on_result=None, mode="safe"):
    ensure_dirs(str(self.root))
    
    # === TIER 2: sempre rodar opt_py ===
    # Todo arquivo Python ganha otimização de AST, independente do mode
    if not force_recompile:
        click.echo(f"   {Fore.CYAN}▶ Tier 2 (opt_py): processando {len(candidates)} arquivo(s)...{Fore.RESET}")
    
    from doxoade.tools.vulcan.opt_cache import generate_opt_py
    from pathlib import Path
    
    tier2_count = 0
    for c in candidates:
        try:
            result = generate_opt_py(self.root, Path(c['file']))
            if result:
                tier2_count += 1
        except Exception as e:
            if on_result:
                on_result(c['file'], False, f"Tier 2: {e}")
    
    click.echo(f"   {Fore.GREEN}✔ Tier 2: {tier2_count}/{len(candidates)} arquivos otimizados{Fore.RESET}")
    
    # === TIER 1: só os aprovados pelo assess_file_for_vulcan ===
    from doxoade.tools.vulcan.forge import assess_file_for_vulcan
    
    tier1_candidates = []
    skipped = []
    for c in candidates:
        eligible, reason, _ = assess_file_for_vulcan(c['file'], mode=mode)
        if eligible:
            tier1_candidates.append(c)
        else:
            skipped.append((c['file'], reason))
    
    if skipped:
        click.echo(f"   {Fore.YELLOW}↷ Tier 1: {len(skipped)} arquivo(s) skipados pelo modo {mode}{Fore.RESET}")
        for path, reason in skipped[:3]:
            click.echo(f"     {Style.DIM}• {Path(path).name}: {reason}{Style.RESET_ALL}")
        if len(skipped) > 3:
            click.echo(f"     {Style.DIM}... e mais {len(skipped) - 3}{Style.RESET_ALL}")
    
    # Se nenhum candidato passou no Tier 1, retorna cedo
    if not tier1_candidates:
        click.echo(f"   {Fore.CYAN}✔ Modo {mode}: nada a compilar em Tier 1{Fore.RESET}")
        return {
            "total": len(candidates),
            "tier2_optimized": tier2_count,
            "tier1_attempted": 0,
            "tier1_success": 0,
            "skipped": len(skipped),
        }
    
    # Segue com o fluxo normal de Tier 1 usando tier1_candidates
    ...
```

### Comportamento antes/depois

**Antes (build ORN):**
```
[FORGE] 56 arquivos... 90 min
0 compilados  ✘ 56 falhas
```

**Depois (mode=safe):**
```
▶ Tier 2 (opt_py): processando 56 arquivo(s)...
✔ Tier 2: 56/56 arquivos otimizados  (~2 min)
↷ Tier 1: 51 arquivo(s) skipados pelo modo safe
  • check_engine.py: SAFE: score=0 < 15
  • opt_benchmark.py: SAFE: score=0 < 15
  • ...
✔ Tier 1: 5 arquivo(s) compilados (~5 min)
Total: ~7 min
```

**Ganho:**

- Build time: 90 min → 7 min
- Tier 2 sempre presente (todos ganham ~-7% exec, -5% size)
- Tier 1 só onde compensa
- Erros de Cython reduzidos de 56 para ~5

### Teste de validação

```bash
# Amaranth
doxoade vulcan purge
doxoade vulcan ignite doxoade/commands/check_systems/ --mode safe
# Esperado: Tier 2 em 13/13, Tier 1 em ~1-2

# ORN
doxoade vulcan purge
doxoade vulcan ignite engine/ --mode safe
# Esperado: Tier 2 em 55/55, Tier 1 em ~3
# Build time < 15 min (vs 90 min antes)
```

### Rollback

Adicionar `--mode aggressive` faz o comportamento voltar ao original. Ou reverter o patch de `pitstop.py::run`.

---

## 📋 Subfase 1.4 — Reportar "verdade" no final do build

### Objetivo

Mostrar ao usuário **o que realmente foi feito**, separando Tier 1 de Tier 2.

### Arquivos afetados

- `doxoade/tools/vulcan/pitstop.py` (final de `run`)
- `doxoade/commands/vulcan_cmd/vulcan_cmd_forge.py` (mensagem final)

### Mudança exata

**No final de `pitstop.py::run`, adicionar relatório:**

```python
    # === Relatório final honesto ===
    click.echo(f"\n{Fore.CYAN}{'─' * 60}{Fore.RESET}")
    click.echo(f"  {Fore.CYAN}{Style.BRIGHT}RELATÓRIO DE BUILD — Modo {mode.upper()}{Style.RESET_ALL}")
    click.echo(f"  {'─' * 60}")
    click.echo(f"  Arquivos analisados : {len(candidates)}")
    click.echo(f"  {Fore.GREEN}✔ Tier 2 (opt_py): {tier2_count} arquivos otimizados{Fore.RESET}")
    click.echo(f"  {Fore.GREEN}✔ Tier 1 (Cython) : {stats['success']} compilado(s){Fore.RESET}")
    click.echo(f"  {Fore.YELLOW}↷ Skipados         : {len(skipped)}{Fore.RESET}")
    click.echo(f"  {Fore.RED}✘ Falhas           : {stats['failed']}{Fore.RESET}")
    click.echo(f"  Tempo total        : {stats['total_time']:.1f}s")
    click.echo(f"  {'─' * 60}")
    
    # Recomendação contextual
    if mode == "safe" and stats['success'] == 0:
        click.echo(f"\n  {Fore.CYAN}ℹ Nenhuma função passou no critério SAFE.{Fore.RESET}")
        click.echo(f"  {Fore.CYAN}Isso é esperado se o código é I/O-bound.{Fore.RESET}")
        click.echo(f"  {Fore.CYAN}Tier 2 já está ativo (ganho marginal mas real).{Fore.RESET}")
    elif mode == "safe" and stats['success'] < 3:
        click.echo(f"\n  {Fore.CYAN}ℹ Modo SAFE é conservador (só compila ROI comprovado).{Fore.RESET}")
        click.echo(f"  {Fore.CYAN}Para explorar, tente: --mode balanced{Fore.RESET}")
    elif mode == "aggressive":
        click.echo(f"\n  {Fore.YELLOW}⚠ Modo AGGRESSIVE: compila tudo, sem garantia de ganho.{Fore.RESET}")
        click.echo(f"  {Fore.YELLOW}Use --mode safe para builds de produção.{Fore.RESET}")
    
    return stats
```

### Comportamento antes/depois

**Antes (confuso):**
```
✔ 13 compilado(s)  ✘ 0 falha(s)  ↷ 0 cache(s)
```
(O usuário pensa: "13× faster")

**Depois (honesto):**
```
RELATÓRIO DE BUILD — Modo SAFE
─────────────────────────────────────
Arquivos analisados : 13
✔ Tier 2 (opt_py): 13 arquivos otimizados
✔ Tier 1 (Cython) : 2 compilado(s)
↷ Skipados         : 11
✘ Falhas           : 0
Tempo total        : 8.3s
─────────────────────────────────────

ℹ Modo SAFE é conservador (só compila ROI comprovado).
Para explorar, tente: --mode balanced
```

**Efeito:** o usuário entende **exatamente** o que aconteceu.

### Teste de validação

Rodar em cada modo e verificar que o relatório reflete a realidade.

### Rollback

Reverter o bloco de relatório. Fluxo normal continua.

---

## 📋 Subfase 1.5 — Cuidado com meta-finder

### Objetivo

Garantir que o **meta-finder** (que redireciona imports para `.pyd`) saiba que só alguns módulos têm `.pyd` disponível.

### Arquivos afetados

- `doxoade/tools/vulcan/meta_finder.py::find_spec`

### Mudança exata

**O `find_spec` já faz `if not bin_path: return None`**, então funciona automaticamente. **MAS** há um caso de borda:

**Se um módulo foi compilado em modo `aggressive` em uma sessão anterior, e agora o usuário roda `safe`, o `.pyd` antigo ainda existe em `bin/` e o finder o carrega — mesmo que o modo atual seja `safe`.**

**Isso é OK.** O `.pyd` é válido. Só não foi recompilado nesta sessão. O comportamento correto.

**Mas precisa de logging claro:**

```python
def find_spec(self, fullname, path, target=None):
    ...
    if bin_path and self._is_binary_valid(bin_path, py_path):
        from doxoade.tools.vulcan.vulcan_safe_loader import SafeExtensionLoader
        loader = SafeExtensionLoader(fullname, str(bin_path), str(py_path))
        spec = importlib.util.spec_from_file_location(
            fullname, str(bin_path), loader=loader)
        if self._debug_enabled():
            self._dlog(f"[VULCAN HIT] {fullname} → {bin_path.name} (.pyd)")
        return spec
    return None
```

**Nada precisa mudar aqui** — o `_dlog` já existe. Só validar que o `.pyd` de `aggressive` não atrapalha `safe`. **Não atrapalha** — o `bin_path` é válido, então usa.

### Teste de validação

```bash
# 1. Compilar em aggressive
doxoade vulcan purge
doxoade vulcan ignite doxoade/tools/vulcan/ --mode aggressive -f
ls .doxoade/vulcan/bin/ | wc -l  # ~50 arquivos

# 2. Rodar em safe
doxoade vulcan ignite doxoade/tools/vulcan/ --mode safe -f
ls .doxoade/vulcan/bin/ | wc -l  # ainda ~50 (não apaga, correto)

# 3. Verificar que imports continuam funcionando
python -c "import doxoade.tools.vulcan.autopilot; print('OK')"
# Esperado: OK (usa .pyd do aggressive, que é válido)
```

### Rollback

Não aplicável — esta subfase é de **validação**, não de mudança.

---

## 📋 Subfase 1.6 — Cache do `assess_file_for_vulcan`

### Objetivo

Evitar que `assess_file_for_vulcan` re-analise o mesmo arquivo múltiplas vezes (chamado em `_filter_candidates` do `autopilot.py` **e** em `pitstop.py::run`).

### Arquivos afetados

- `doxoade/tools/vulcan/forge.py` (`assess_file_for_vulcan`)

### Mudança exata

**Adicionar cache em memória no topo do módulo:**

```python
# Cache: {(file_path, mode): (eligible, reason, details)}
_ASSESS_CACHE: dict[tuple[str, str], tuple[bool, str, list[str]]] = {}
_ASSESS_CACHE_MAX = 1000


def assess_file_for_vulcan(
    file_path: str,
    mode: str = "safe",
) -> tuple[bool, str, list[str]]:
    """... (docstring mantido) ..."""
    key = (str(Path(file_path).resolve()), mode)
    
    # Cache hit
    if key in _ASSESS_CACHE:
        return _ASSESS_CACHE[key]
    
    result = _assess_impl(file_path, mode)
    
    # Cache store (com LRU simples)
    if len(_ASSESS_CACHE) >= _ASSESS_CACHE_MAX:
        # Remove mais antigo
        _ASSESS_CACHE.pop(next(iter(_ASSESS_CACHE)))
    _ASSESS_CACHE[key] = result
    
    return result


def _assess_impl(file_path: str, mode: str) -> tuple[bool, str, list[str]]:
    """Implementação real, sem cache."""
    # ... todo o corpo que estava em assess_file_for_vulcan ...
    pass


def clear_assess_cache():
    """Limpa o cache (chamado no início de cada ignite)."""
    _ASSESS_CACHE.clear()
```

**Em `pitstop.py::run`, no início:**

```python
def run(self, candidates, force_recompile=False, ..., mode="safe"):
    from doxoade.tools.vulcan.forge import clear_assess_cache
    clear_assess_cache()  # invalida cache entre builds
    ...
```

### Comportamento antes/depois

**Antes:** cada arquivo analisado 2-3× por build (chamado em `autopilot._filter_candidates`, depois em `pitstop.run`).

**Depois:** 1× por build (cache hit).

**Ganho:** ~30-40% no tempo de `assess_file_for_vulcan` aggregate. Em ORN, ~5s economizados.

### Teste de validação

```bash
# Medir tempo sem cache vs com cache
python -c "
import time
from doxoade.tools.vulcan.forge import assess_file_for_vulcan, clear_assess_cache
files = ['doxoade/tools/vulcan/autopilot.py'] * 5
clear_assess_cache()
t0 = time.perf_counter()
for f in files:
    assess_file_for_vulcan(f, mode='safe')
print(f'Com cache: {(time.perf_counter()-t0)*1000:.1f}ms')
"
```

**Esperado:** ~10ms (só analisa 1×).

### Rollback

Desabilitar o cache removendo a chamada de `_ASSESS_CACHE.get`. Não quebra nada.

---

## 📋 Subfase 1.7 — Dashboard de escolha (transparência)

### Objetivo

Antes de rodar, mostrar **quantos arquivos** serão compilados em Tier 1 e **por quê**. Isso é transparência.

### Arquivos afetados

- `doxoade/commands/vulcan_cmd/vulcan_cmd_forge.py::ignite`

### Mudança exata

**Em `ignite`, logo após montar `candidates`, adicionar:**

```python
    # === Dry-run de elegibilidade (transparência) ===
    if candidates and not scan_only:
        from doxoade.tools.vulcan.forge import assess_file_for_vulcan
        
        eligible_count = 0
        skipped_count = 0
        reasons = {}
        for c in candidates:
            ok, reason, _ = assess_file_for_vulcan(c['file'], mode=mode)
            if ok:
                eligible_count += 1
            else:
                skipped_count += 1
                reasons[reason] = reasons.get(reason, 0) + 1
        
        click.echo(f"\n{Fore.CYAN}   ▶ Análise de elegibilidade (mode={mode}):{Style.RESET_ALL}")
        click.echo(f"     Tier 1 elegíveis : {Fore.GREEN}{eligible_count}{Style.RESET_ALL}")
        click.echo(f"     Skipados         : {Fore.YELLOW}{skipped_count}{Style.RESET_ALL}")
        
        if reasons and skipped_count > 0:
            click.echo(f"     {Style.DIM}Top motivos de skip:{Style.RESET_ALL}")
            for reason, count in sorted(reasons.items(),
                                         key=lambda x: -x[1])[:3]:
                click.echo(f"       {Style.DIM}• {reason}: {count}{Style.RESET_ALL}")
        
        if eligible_count == 0:
            click.echo(f"\n{Fore.YELLOW}   ⚠ Modo {mode} não encontrou nenhum arquivo elegível.{Style.RESET_ALL}")
            click.echo(f"   {Fore.CYAN}   Tente --mode balanced para explorar, ou --mode aggressive para debug.{Style.RESET_ALL}")
            if not click.confirm("Continuar mesmo assim?", default=False):
                return
```

### Comportamento antes/depois

**Antes:**
```
🔥 [VULCAN-IGNITION] ...
   > Modo  : MANUAL (diretório: engine)
   > Engine: PITSTOP
   [FORGE] 55 arquivos... (90 min)
```

**Depois:**
```
🔥 [VULCAN-IGNITION] ...
   > Modo  : MANUAL (diretório: engine)
   > Engine: PITSTOP
   > Mode  : SAFE

   ▶ Análise de elegibilidade (mode=safe):
     Tier 1 elegíveis : 3
     Skipados         : 52
     Top motivos de skip:
       • SAFE: score=0 < 15: 42
       • SAFE: sem calls em loop: 7
       • Importa C-extension: 3

   [FORGE] 3 arquivos... (~5 min)
```

**Efeito:** o usuário sabe **antes** que esperar.

### Teste de validação

```bash
doxoade vulcan ignite doxoade/tools/vulcan/ --mode safe
# Esperado: mostra "Tier 1 elegíveis: N" antes de compilar
```

### Rollback

Remover o bloco de dry-run. `ignite` funciona como antes.

---

## 🎯 Sumário Executivo da Fase 1

| Subfase | Mudança | Arquivo | Impacto |
|---------|---------|---------|---------|
| **1.1** | Opção `--mode` | `vulcan_cmd_forge.py` + `autopilot.py` | Infra |
| **1.2** | `assess_file_for_vulcan` com 3 modos | `forge.py` | **Core** |
| **1.3** | Tier 2 sempre, Tier 1 condicional | `pitstop.py` | **Maior ganho** |
| **1.4** | Relatório honesto | `pitstop.py` | UX |
| **1.5** | Validação meta-finder | (só testes) | Confiança |
| **1.6** | Cache do `assess_file_for_vulcan` | `forge.py` | Perf |
| **1.7** | Dry-run transparency | `vulcan_cmd_forge.py` | UX |

**Esforço total:** 2-3 dias de dev.

**Ganho esperado:**

| Métrica | Antes | Depois (SAFE) |
|---------|-------|---------------|
| Build ORN | 90 min | ~8 min |
| Compilados ORN | 56 | 3 |
| Falhas ORN | 56 | ~0 |
| Tier 2 cobertura | 100% | 100% |
| Confusão do usuário | Alta | Baixa |

**Risco:** **Baixo.** Cada subfase tem rollback isolado.

**Rollback global:** `--mode aggressive` restaura comportamento original em 1 segundo.

---

## 🛡️ ProDeNov §1.2.1 — Plano A / B / C

**Plano A (default):** implementar as 7 subfases em sequência. Testar em Amaranth, Bluebaby, ORN.

**Plano B:** se `assess_file_for_vulcan` SAFE filtrar **demais** (0 compilados em Amaranth, por exemplo), aumentar thresholds ou tornar `balanced` o default. **Critério:** se Amaranth ficar < 2 compilados, ajustar.

**Plano C (nuclear):** se tudo falhar, `--mode aggressive` é sempre o fallback. Usuário não fica bloqueado.

---

## 📋 Ordem de Implementação Recomendada

Não é 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7. **A ordem correta para reduzir risco é:**

1. **1.1** (infra — `--mode` sem efeito) → testa → commit
2. **1.6** (cache do assess — otimização passiva) → testa → commit
3. **1.2** (3 modos em `assess`) → testa em Amaranth → commit
4. **1.7** (dry-run) → testa → commit
5. **1.3** (Tier 2 + Tier 1 condicional) → **maior mudança** → testa em Amaranth, Bluebaby, ORN → commit
6. **1.4** (relatório final) → testa → commit
7. **1.5** (validação finder) → só teste, sem commit

**Por que essa ordem:** cada subfase isolada pode ser testada sem quebrar o build. **Se 1.3 falhar, os 4 primeiros commits continuam válidos.** Você pode reverter **apenas** o commit de 1.3.

---


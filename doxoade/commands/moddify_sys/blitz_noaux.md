
## 1. Diagnóstico — por que os 3 blocos falharam

| Bloco | Classificado como | Deveria ser | Causa |
|---|---|---|---|
| `dominators.c` | `fragment` | `function` | `_FUNC_HEAD` exige `(` na mesma linha do `{`. Sua função tem assinatura em **2 linhas** e `{` na terceira |
| `dominators.h` | `function` | `prototype` | `_PROTO_HEAD` exige `;` na mesma linha. Seu prototype tem `,` no fim + `);` na linha seguinte |
| `main.c` | `fragment` ✓ | `OP_MOD_BODY` | Correto na classificação, mas sem função-alvo |

**Causa raiz única**: `_classify` só olha as **primeiras 3 linhas** e não faz *continuation scanning*. Todos os 3 casos têm assinatura multilinha — o parser desiste antes de ver o `{` ou `;` terminador.

**Segunda causa**: mesmo classificando certo, `_find_insertion_point` **não consulta o conteúdo do arquivo-alvo** para decidir onde ir. Sempre vai para "append após última função" — o que é errado para `main.c`, onde o bloco deve ir **dentro de uma função existente**.

---

## 2. Taxonomia de operações

O `--noaux` não é 1 operação. É **7** (cada uma com pré-condição e pós-condição diferentes):

| Op | Trigger (assinatura) | Alvo natural | Ação | Idempotência |
|---|---|---|---|---|
| `OP_ADD_IMPL` | `ret name(args) { ... }` (function def completa) | `.c` | Inserir nova função | Nome já existe? |
| `OP_ADD_PROTO` | `ret name(args);` (function decl) | `.h` | Inserir prototype | Nome já existe? |
| `OP_ADD_TYPE` | `typedef` / `struct name { ... }` / `enum` | `.h` | Inserir tipo | Tag já existe? |
| `OP_ADD_INCLUDE` | `#include <...>` ou `#include "..."` | `.c`/`.h` | Inserir após último include | Path já está? |
| `OP_ADD_MACRO` | `#define X Y` | `.c`/`.h` | Inserir após último `#define` | `X` já definido? |
| `OP_MOD_BODY` | fragmento (`{ ... }` sem head) | `.c` | Inserir em função existente | Bloco verbatim já existe? |
| `OP_MOD_BRANCH` | fragmento + referência a `mode == N` ou similar | `.c` | Inserir em cadeia `if/else if` | `mode == N` já existe? |

**Regra geral**: a mesma string `int foo(...) { }` em `.h` vira `OP_ADD_TYPE` (erro, avisar) ou `OP_ADD_PROTO` (raro). Em `.c` vira `OP_ADD_IMPL`. **O target file decide a interpretação**, não a string.

---

## 3. Algoritmo de detecção (multilinha)

```
def classify_block(block_code, target_ext):
    lines = strip_blank_and_comments(block_code)
    
    # 1. Scan forward — junta linhas até encontrar ';' ou '{'
    signature = ""
    terminator = None
    for ln in lines[:10]:                  # limite: 10 linhas de assinatura
        signature += " " + ln.strip()
        if ';' in ln:
            terminator = ';'; break
        if '{' in ln:
            terminator = '{'; break
    
    # 2. Classificação primária
    if signature.startswith('#include'):
        return "OP_ADD_INCLUDE"
    if signature.startswith('#define'):
        return "OP_ADD_MACRO"
    if 'typedef' in signature or re.match(r'struct\s+\w+\s*\{', signature):
        return "OP_ADD_TYPE"
    
    # 3. Função vs prototype
    if terminator == ';':
        return "OP_ADD_PROTO"      # target .h idealmente
    if terminator == '{':
        return "OP_ADD_IMPL"       # target .c idealmente
    
    # 4. Fragmento (sem head identificável)
    if '{' in block_code and '}' in block_code:
        return "OP_MOD_BODY"       # precisa fuzzy match
    return "UNKNOWN"
```

**Nome extraído para idempotência** (via regex sobre `signature`):
- `OP_ADD_IMPL`/`OP_ADD_PROTO` → `ret (\w+)\s*\(` → `name`
- `OP_ADD_TYPE` → `struct (\w+)` ou `typedef ... (\w+);`
- `OP_ADD_MACRO` → `#define (\w+)`

---

## 4. Fuzzy matching para `OP_MOD_BODY` (o núcleo)

O `difflib.get_close_matches` que você testou **não serve** para código por 3 motivos:

1. Funciona em **linhas inteiras**, e o fragmento raramente tem linhas idênticas a uma função existente
2. `cutoff` baixo traz resultados aleatórios (seu teste `0.3` trouxe `out->rpo[count - 1 - i] = tmp;`)
3. Não entende estrutura (mesmo `CFG cfg = {0};` em 2 lugares é 100% similar)

### Algoritmo proposto: **token-Jaccard em função-alvo**

```
def find_target_function(fragment, target_file):
    # 1. Parse target em funções completas
    functions = parse_c_functions(target_file)
    # função = {name, start, end, body_lines}
    
    # 2. Extrair tokens do fragmento
    frag_tokens = extract_tokens(fragment)
    # tokens = identificadores >= 4 chars + chamadas + control keywords
    # ignorando: {, }, ;, (, ), tipos básicos (int, char, void, ...)
    # preservando: CFG, cfg_build, dom_compute, FunctionList, fl, insns
    
    # 3. Score cada função
    for fn in functions:
        fn_tokens = extract_tokens(fn.body_lines)
        score = jaccard(frag_tokens, fn_tokens)
        # jaccard = |A ∩ B| / |A ∪ B|
    
    # 4. Retorna top-3 com score > 0.15
    # Se nenhum > 0.15 → ANCHOR_REQUIRED (fragmento não localizável)
```

### Pontos de inserção dentro da função

Depois de achar a função-alvo (`test_dominators` no seu exemplo), achar onde **dentro** do corpo:

```
def find_insertion_point(fragment, function_body):
    # 1. Se o fragmento começa com declaração `Type var = ...;`
    #    → inserir após a última declaração desse tipo
    # 2. Se começa com `if (...)` ou `for (...)`
    #    → inserir após último bloco `if/for` de nível similar
    # 3. Se começa com chamada `func(...)`
    #    → inserir após chamada semelhante (mesmo prefixo)
    # 4. Fallback: após a última declaração de variável da função
```

Para o seu `main.c`:
- Fragmento começa com `CFG cfg = {0};`
- `test_dominators()` **já tem** `CFG cfg = {0};` — mas o fragmento é **sobre** `test_dominators`? Não, é sobre **extrair sub-CFG** e rodar dominators nele
- O fragmento compartilha `cfg_build`, `functions_build` — que aparecem em `test_dominators`
- **Decisão**: se `test_dominators` é o alvo, o fragmento adiciona análise sobre `fl.entries[0]` após `dom_compute(&cfg, &dt, ...)`. Isso faz sentido semântico: extrair sub-CFG da primeira função, rodar dominators **no sub-CFG**, comparar com o global.

Mas isso exige **raciocínio semântico**. O `--noaux` não vai fazer isso sozinho — vai **propor top-3** e o usuário escolhe. Ou, se houver `mode == 6` no target, **prioriza `OP_MOD_BRANCH`**.

### Estratégia para `OP_MOD_BRANCH`

Se o target tem padrão `if (mode == N) {` com N existente, **e** o fragmento não tem `mode ==` mas tem estrutura de "bloco de análise":
- Encontra a cadeia `if/else if (mode == ...)`
- Determina próximo N livre
- Propõe inserir como `else if (mode == N+1) { <fragment> }`
- **Mostra ao usuário antes de aplicar**

---

## 5. Matriz de teste — 3 amostras

| Amostra | Detectado | Op esperado | Insert esperado | O que testa |
|---|---|---|---|---|
| `dominators.c` | function | `OP_ADD_IMPL` | Após `dom_compute` (fuzzy nome) | Multiline sig + ID de duplicata |
| `dominators.h` | prototype | `OP_ADD_PROTO` | Após último prototype | Multiline prototype |
| `main.c` | fragment | `OP_MOD_BODY` ou `OP_MOD_BRANCH` | Dentro de `test_dominators` ou novo branch | Fuzzy semantic |

**Critérios de aceitação**:
- `dominators.c`: idempotente se `dom_extract_function` já existe no arquivo
- `dominators.h`: idempotente se `dom_extract_function` já declarado
- `main.c`: se fuzzy score < 0.15 → `ANCHOR_REQUIRED` com sugestão `# ANCHOR: <func_name>` ou `# ANCHOR_BRANCH: <N>`

---

## 6. Cadeia de fallback

Cada operação tenta em ordem; aborta com motivo explícito se todas falham:

```
OP_ADD_IMPL:
  1. Nome já existe no arquivo? → IDEMPOTENT
  2. Funções com prefixo igual (dom_*)? → inserir após a última
  3. Função chamadora no mesmo arquivo (`dom_compute` chamado em `dom_extract_function`)? → inserir após ela
  4. Fallback: append após última função
  5. Não é .c? → OP_ADD_PROTO (transição suave)

OP_ADD_PROTO:
  1. Nome já declarado? → IDEMPOTENT
  2. Seção `/* API */` ou `/* Public */` existe? → inserir nela
  3. Fallback: após último prototype (antes de 1ª função)
  4. Não é .h? → OP_ADD_IMPL

OP_ADD_TYPE:
  1. Tag já existe? → IDEMPOTENT
  2. Tipos relacionados por prefixo? → inserir após
  3. Fallback: antes do primeiro prototype (tipo antes de uso)

OP_MOD_BODY:
  1. Bloco verbatim existe? → IDEMPOTENT
  2. Fuzzy match função (score > 0.15)? → propor top-3
  3. Top-3 com # ANCHOR hint? → usar hint
  4. Nenhum? → ANCHOR_REQUIRED

OP_MOD_BRANCH:
  1. Padrão `mode == N` já existe? → IDEMPOTENT
  2. Cadeia `if/else if` encontrada? → propor N+1
  3. Sem cadeia? → degradar para OP_MOD_BODY
```

---

## 7. Rollout em 3 fases

### Fase 1 — `c_add_new` (revisão 1)
**Implementa**: `OP_ADD_IMPL` + `OP_ADD_TYPE` + `OP_ADD_INCLUDE` + `OP_ADD_MACRO`
- Multiline signature detection
- Idempotência por nome
- Prefix-based insertion
- Fallback: append

**Testa**: `dominators.c` (impl), 2-3 fixtures sintéticas para include/type/macro

**Fora de escopo**: `.h`, fragmentos

### Fase 2 — `c_declare` (revisão 2)
**Implementa**: `OP_ADD_PROTO`
- `.h` target detection
- Multiline prototype
- Seção `/* API */` awareness
- Fallback para `OP_ADD_IMPL` se target é `.c`

**Testa**: `dominators.h` (prototype), fixtures com/sem seção API

**Fora de escopo**: fragmentos

### Fase 3 — `c_mod_func` (revisão 3)
**Implementa**: `OP_MOD_BODY` + `OP_MOD_BRANCH`
- Fuzzy token-Jaccard matching
- Top-3 candidates + preview
- Insertion point dentro de função
- `# ANCHOR` e `# ANCHOR_BRANCH` hints
- `--dry-run` obrigatório antes de `--apply` para essa op

**Testa**: `main.c` (fragment + branch), fixtures adversariais (fragment ambíguo, fragment órfão)

**Cobertura final**: 3 amostras + ~10 fixtures

---

## 8. Flags do CLI

| Flag | Efeito |
|---|---|
| `--noaux` | Ativa parser raw-code |
| `--op=OP_ADD_IMPL` | Força uma operação (para casos onde detecção falha) |
| `--preview` | Mostra top-3 do fuzzy match (só OP_MOD_*) |
| `--shadow` | Já existe — escreve em `.doxoade/mody_patch/` |
| `--apply` | Efetiva |
| `--ANCHOR=hint` | Override do `# ANCHOR:` inline |

---

## 9. Não-objetivos (escopo negativo)

O `--noaux` **não vai**:
- Reordenar funções existentes
- Apagar código
- Modificar semântica (só inserir)
- Adivinhar `mode == 6` sem confirmação (OP_MOD_BRANCH pede aprovação)
- Substituir `mody replace` para edits pontuais

Para casos de "modificar código existente", use `mody replace` ou `mody patch` (diff). `--noaux` é **só inserção**.

---

## 10. Aprovação necessária

Antes de começar Fase 1, preciso confirmar:

1. **Taxonomia de 7 ops** está correta? Falta alguma (`static inline`, `extern`, `__attribute__`)?
2. **Fuzzy threshold 0.15** é razoável, ou prefere top-N sem threshold (sempre mostrar)?
3. **`OP_MOD_BRANCH`** deve sugerir `else if (mode == N+1) {` **automaticamente**, ou só inserir o bloco e deixar o usuário adicionar o wrapper?
4. **`--op=` override** deve ser global (substitui detecção) ou por-bloco (só se detecção falhar)?
5. **`OP_ADD_TYPE`** em `.c` — aceita (raro mas válido para tipos file-local) ou rejeita com aviso?

---


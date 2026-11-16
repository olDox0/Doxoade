# Experimento 06 — Fase 5b (pattern catalog)

## Hipótese
Consigo identificar padrões de arquitetura x86 (frame pointer, canary,
tail call, switch table, leaf) a partir da lista de instruções e do
CFG, em binários PE32 e PE32+, nativos e stripped.

## Método
1. `patterns_analyze` percorre cada função, olha o prólogo (detect_fp),
   todas as instruções (detect_canary, detect_switch) e todos os
   blocos (detect_tailcall).
2. Detecção via `op_str` (Capstone) ou `opcode` (native).
3. Resultado agregado no `[PATTERNS]` do doctor.

## Resultado por alvo

| Alvo | Compilador | fp | canary | tail | switch | leaf |
|---|---|---|---|---|---|---|
| degrau0_O0_g.exe | mingw -O0 | 4 | 0 | 0 | 0 | 72 |
| hostname.exe | MSVC -O2 | 0 | 0 | 0 | 0 | 5 |
| where32.exe | MSVC -O2 | 0 | 1 | 6 | 3 | 12 |

### Interpretação

**degrau0 (-O0):** fp=4 (as 4 funções do usuário), canary=0 (compilado
com `-fno-stack-protector`), tail=0 (-O0 não otimiza), switch=0 (-O0
compila switch como cadeia de cmp/jcc), leaf=72 (muitos thunks de IAT).

**hostname (MSVC -O2):** fp=0 (`/Oy` omit frame pointer), canary=0
(investigar — o binário deveria ter `/GS`), tail=0 (pode ser que o
MSVC use tail call indireto via IAT), switch=0 (binário pequeno, sem
switch), leaf=5.

**where32 (MSVC -O2):** fp=0, canary=1 (fs:[0x14] detectado), tail=6
(jmp direto para fora da função), switch=3 (jump tables em 32-bit),
leaf=12.

## Limites encontrados e corrigidos
1. **`canary_cb` com `gs:0x28`** — Capstone formata `gs:[0x28]`; o
   `strstr("gs:0x28")` quebrava com o `[`. Corrigido para `"gs:"` e
   adicionado `"fs:"` para 32-bit.
2. **`detect_tailcall` olhava só o último bloco** — o padding final
   (`nop`/`int3`) escondia o `jmp`. Corrigido para iterar todos os
   blocos da função.
3. **`imm` não preenchido pelo Capstone para CALLs** — o fallback
   estava dentro do `if (ci->detail)`, e `detail` é NULL. Movido para
   fora do bloco.
4. **`mody patch` corrompeu 2 arquivos** — removeu `if (cands == NULL)`
   em `functions.c` e `CFG cfg = {0}; if (cfg_build(...))` em
   `doctor.c`. Bug do patcher v6.4.2 (brace balance não valida contexto).

## Limites remanescentes
- `hostname.exe` com canary=0: investigar (o binário tem `/GS`?).
- Tail call indireto (via IAT) não detectado — só `jmp` direto.
- Switch table com índice escalado (`[eax + ebx*4]`) não detectado —
  o `switch_cb` procura `*4` ou `*8` literal.

## Próximo passo
Fase 5c — Xref database (quem referencia o quê). Preparação para o
Defaultier (pseudo-C pedagógico).

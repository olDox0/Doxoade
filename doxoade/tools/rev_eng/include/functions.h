/* functions.h — identificação de funções e call graph (Fase 5a)
 *
 * Uma função é identificada por:
 *   - símbolo COFF (storage class 2 = External, dentro do .text)
 *   - alvo de CALL direta dentro do .text
 *   - entrada do .text (primeiro byte)
 *
 * Funções são ordenadas por start_va. end_va = próxima função (ou fim
 * do .text). Blocos do CFG são atribuídos à função cujo [start, end)
 * contém o start do bloco.
 *
 * O call graph é construído a partir de CALLs diretas cujo alvo cai
 * em outra função. CALLs indiretas (FF /2) e ordinais contam como
 * "chamadas externas" (não têm alvo resolvível estaticamente).
 */
#ifndef FUNCTIONS_H
#define FUNCTIONS_H

#include "disasm.h"
#include "cfg.h"
#include "pre_ir.h"
#include <stdio.h>

/* Bitmask de padrões detectáveis. */
#define FUNC_FLAG_FP        (1u << 0)  /* push rbp; mov rbp, rsp */
#define FUNC_FLAG_CANARY    (1u << 1)  /* gs:0x28 no prólogo e epílogo */
#define FUNC_FLAG_TAILCALL  (1u << 2)  /* termina com jmp func (sem ret) */
#define FUNC_FLAG_SWITCH    (1u << 3)  /* jmp qword ptr [reg*8 + table] */
#define FUNC_FLAG_LEAF      (1u << 4)  /* nenhum call interno */

typedef struct {
    uint64_t    start_va;
    uint64_t    end_va;
    const char *name;
    char       *synth_name;
    uint32_t    block_first;
    uint32_t    block_count;
    uint32_t    call_count;
    uint32_t    callee_count;
    uint32_t   *callee_idx;
    uint32_t    flags;              /* NOVO: bitmask de padrões */
} FunctionEntry;

typedef struct {
    uint32_t       count;
    FunctionEntry *entries;
    uint32_t       external_calls;  /* CALLs indiretas ou fora do .text */
} FunctionList;

/* Constrói a lista de funções a partir de:
 *   - insns: lista linear do .text (disasm_collect)
 *   - cfg:   CFG do .text (cfg_build)
 *   - ir:    PreIR (para símbolos)
 * Os VAs inicial e final do .text são inferidos de insns[].
 * Retorna 0 em sucesso, -1 em erro. */
int functions_build(const InsnList *insns, const CFG *cfg, const PreIR *ir,
                    FunctionList *out, char *err_buf, size_t err_buf_size);

/* Libera a memória da FunctionList (não libera insns/cfg/ir). */
void functions_free(FunctionList *fl);

/* NOVO: formata flags como string curta ("fp canary leaf" ou "-"). */
void patterns_format_flags(uint32_t flags, char *out, size_t out_size);

/* Emite tabela legível: VA, nome, blocos, calls, callees. */
void functions_print_text(const FunctionList *fl, FILE *out);

/* Emite call graph em DOT (Graphviz). */
void functions_print_dot(const FunctionList *fl, FILE *out);

#endif /* FUNCTIONS_H */

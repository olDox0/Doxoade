/* cfg.h — construção de blocos básicos e grafo de fluxo (Fase 4)
 *
 * Recebe uma InsnList (saída de disasm_collect) e produz um CFG
 * com blocos básicos e arestas de sucessão.
 *
 * Modelo de bloco:
 *   - Começa em um "líder": primeira instrução da região, alvo de
 *     jcc/jmp, ou instrução imediatamente após jcc/jmp/ret.
 *   - Termina em: jcc, jmp, ret (fim de bloco), ou última instrução.
 *   - Blocos não se sobrepõem.
 *
 * Modelo de aresta:
 *   - CF_JCC: 2 sucessores — fallthrough e alvo.
 *   - CF_JMP: 1 sucessor — alvo (ou 0 se indireto).
 *   - CF_RET: 0 sucessores.
 *   - CF_CALL: 1 sucessor — fallthrough (call retorna).
 *   - CF_NONE (última instrução do bloco): 1 sucessor — fallthrough.
 */
#ifndef CFG_H
#define CFG_H

#include "disasm.h"
#include "file_reader.h"
#include <stdio.h>

typedef struct {
    uint64_t start_va;
    uint64_t end_va;         /* VA após a última instrução (exclusivo) */
    uint32_t insn_first;     /* índice em insn_list */
    uint32_t insn_count;
    uint32_t succ_count;
    uint32_t *succ_idx;      /* índices dos blocos sucessores em cfg->blocks */
} BasicBlock;

typedef struct {
    uint32_t    block_count;
    BasicBlock *blocks;
    const InsnList *insns;   /* referência (não possui) */
} CFG;

/* Constrói o CFG. Retorna 0 em sucesso, -1 em erro. */
int cfg_build(const InsnList *insns, CFG *out,
              char *err_buf, size_t err_buf_size);

/* Libera a memória do CFG (mas não `insns`). */
void cfg_free(CFG *cfg);

/* Imprime no formato texto: cada bloco com start/end, nº de instruções,
 * e lista de sucessores (com kind: fallthrough/jump/cond). */
void cfg_print_text(const CFG *cfg, const InsnList *insns, FILE *out);

/* Imprime no formato Graphviz DOT. */
void cfg_print_dot(const CFG *cfg, const InsnList *insns, FILE *out);

#endif /* CFG_H */

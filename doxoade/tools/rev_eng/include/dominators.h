/* dominators.h — árvore de dominadores e loops naturais (Fase 5d) */
#ifndef DOMINATORS_H
#define DOMINATORS_H

#include "cfg.h"
#include "disasm.h"
#include <stdio.h>

typedef struct {
    uint32_t  nblocks;
    uint32_t *rpo;
    uint32_t *rpo_num;
    uint32_t *idom;
    uint8_t  *reachable;
} DominatorTree;

int dom_compute(const CFG *cfg, DominatorTree *out,
                char *err_buf, size_t err_buf_size);
void dom_free(DominatorTree *dt);
int dom_dominates(const DominatorTree *dt, uint32_t a, uint32_t b);
void dom_print_text(const DominatorTree *dt, const CFG *cfg, FILE *out);
uint32_t dom_count_loops(const DominatorTree *dt, const CFG *cfg);

int dom_extract_function(const CFG *cfg, uint32_t first, uint32_t count,
                         CFG *out, char *err_buf, size_t err_buf_size);


#endif

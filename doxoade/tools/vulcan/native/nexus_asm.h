#ifndef NEXUS_ASM_H
#define NEXUS_ASM_H
#include <stdint.h>

// Protótipos das funções em Assembly (.s)
uint64_t nexus_asm_crc32(const uint8_t* buf, int64_t len);
int64_t nexus_asm_search_char(const uint8_t* buf, int64_t len, int64_t target);
int64_t nexus_asm_cmov(int64_t selector, int64_t val_true, int64_t val_false);
int64_t nexus_asm_vec_search(const uint8_t* buf, int64_t len, int64_t target);
long nexus_asm_popcount(long value);

#endif
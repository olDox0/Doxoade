# ---------------------------------------------------------------------------
# Nexus Warp Math - SSE4.2 Optimization for N2808
# Função: nexus_fast_hash (Calcula um checksum simples de 64 bits em ASM)
# ---------------------------------------------------------------------------
.text
.globl nexus_fast_hash
.type nexus_fast_hash, @function

nexus_fast_hash:
    # rcx = buffer, rdx = len
    xor %rax, %rax
    test %rdx, %rdx
    jz end_hash

loop_hash:
    # Usa a instrução CRC32 (disponível no SSE4.2 do seu Atom)
    crc32b (%rcx), %eax
    inc %rcx
    dec %rdx
    jnz loop_hash

end_hash:
    ret
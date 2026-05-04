# ---------------------------------------------------------------------------
# Nexus Assembly Kernel - SSE4.2 Optimization (Windows x64 Version)
# ---------------------------------------------------------------------------
.text
.globl nexus_asm_popcount

nexus_asm_popcount:
    # No Windows x64, o primeiro argumento inteiro chega via RCX.
    # O seu processador N2808 executará isso em um único ciclo de clock.
    popcnt %rcx, %rax   
    ret
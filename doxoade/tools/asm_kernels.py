#doxoade/tools/asm_kernels.py
# Intrinsics para aceleração X86_64
SIMD_KERNELS = {
    "tensor_sum": """
        movaps xmm0, [rsi]
        addps  xmm0, [rdi]
        movaps [rdx], xmm0
    """
}
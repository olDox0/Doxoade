# VULCAN IRON-HARD FORGE v6.1
# cython: language_level=3
# cython: cdivision=True
# cython: boundscheck=False


import time

def heavy_bitwise_process_vulcan_optimized(unsigned int n, unsigned int seed):
    cdef unsigned int result
    cdef long long ITERACOES
    cdef long long SEED_INICIAL
    cdef long long start
    cdef double res
    cdef long long end
    cdef unsigned int i
    # --- Zona de Metal Puro (No GIL) ---
    with nogil:
        result = seed
        for i in range(n):
            result = (result << 1 ^ i) & <unsigned int>4294967295
            result = result >> 1 | i << 16
            result = (result ^ <unsigned int>3735928559) & <unsigned int>4294967295
            if i % 3 == 0:
                result = result + i & <unsigned int>4294967295
            elif i % 2 == 0:
                result = result - 1 & <unsigned int>4294967295
    return result

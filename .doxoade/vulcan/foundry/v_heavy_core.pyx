# VULCAN IRON-HARD FORGE v6.1
# cython: language_level=3
# cython: cdivision=True
# cython: boundscheck=False

from libc.math cimport sqrt, sin, cos, atan
import math

def compute_chunk_vulcan_optimized(unsigned int iterations):
    cdef double res
    cdef unsigned int i
    # --- Zona de Metal Puro (No GIL) ---
    with nogil:
        res = 0.0
        for i in range(iterations):
            res += sqrt(i) * 1.5 / (sin(i) + 2.0)
    return res

//cpu_math.c
#include <stdio.h>

// Função de alta performance
float processar_sinal(float entrada, float ganho) {
    return entrada * ganho + 0.5f;
}

// Para Windows (DLL)
__declspec(dllexport) float c_processar_sinal(float entrada, float ganho) {
    return processar_sinal(entrada, ganho);
}
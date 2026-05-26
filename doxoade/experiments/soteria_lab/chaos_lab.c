#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "soteria.h"

void falha_logica_paradoxo() {
    SOTERIA_ENTER("falha_logica_paradoxo");
    SOTERIA_ALERT("PARADOX_DETECTED", "O sistema entrou em um loop de decisao impossivel (A == !A).");
}

void falha_hardware_incompativel() {
    SOTERIA_ENTER("falha_hardware_incompativel");
    SOTERIA_ALERT("INSTRUCTION_NOT_SUPPORTED", "Tentativa de usar kernel AVX-512 em hardware Celeron N2808.");
}

void corrupcao_de_protocolo() {
    SOTERIA_ENTER("corrupcao_de_protocolo");
    SOTERIA_ALERT("PROTOCOL_DESYNC", "Checksum do pacote recebido nao bate com o calculado (Bit-flip provavel).");
}

void falha_vazamento_refluxo() {
    SOTERIA_ENTER("falha_vazamento_refluxo");
    // Aloca memória repetidamente sem liberar para simular exaustão de RAM
    for (int i = 0; i < 50; i++) {
        void *lixo = malloc(1024 * 1024); // 1MB por iteração
        if (lixo == NULL) {
            SOTERIA_ALERT("OUT_OF_MEMORY", "Heap exaurido. Falha crítica na alocação de buffers.");
            return;
        }
    }
    SOTERIA_ALERT("RESOURCE_LEAK_WARNING", "Taxa de retenção de memória RAM acima do limite seguro.");
}

void falha_race_condition_telemetria() {
    SOTERIA_ENTER("falha_race_condition_telemetria");
    // Simula colisões e condições de corrida em sistemas concorrentes
    SOTERIA_ALERT("RACE_CONDITION_DETECTED", "Duas ou mais threads tentaram registrar o mesmo ID de evento simultaneamente.");
}

void falha_estouro_buffer_silencioso() {
    SOTERIA_ENTER("falha_estouro_buffer_silencioso");
    // Simula a invasão de dados em áreas de memória adjacentes (Data Corruption)
    SOTERIA_ALERT("MEMORY_CORRUPTION", "Sinalizador de segurança corrompido por escrita fora dos limites do buffer.");
}


int main() {
    soteria_init(0, NULL);
    srand(time(NULL));
    int sorteio = rand() % 6;

    printf("🎲 [NEXUS CHAOS] Sorteando desastre aleatorio...\n");

    if (sorteio == 0) falha_logica_paradoxo();
    if (sorteio == 1) falha_hardware_incompativel();
    if (sorteio == 2) corrupcao_de_protocolo();
    if (sorteio == 3) falha_vazamento_refluxo();
    if (sorteio == 4) falha_race_condition_telemetria();
    if (sorteio == 5) falha_estouro_buffer_silencioso();

    return 0;
}
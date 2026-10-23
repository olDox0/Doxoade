// ============================================================================
// TIANZUN ENGINE - MAIN (Fase 3: Panela de Pressao)
// Entry point e cenario de teste. Logica movida para src/core/ e src/include/
// ============================================================================
#include <iostream>
#include <iomanip>

#include "tianzun/engine.h"
#include "tianzun/constants.h"

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

int main() {
    std::cout << "=== TIANZUN ENGINE - FASE 3: PRESSURE SOLVER ===\n";

    using namespace Tianzun;

    SimulationEngine engine;
    const int GRID_SIZE = 10;
    const int center    = GRID_SIZE / 2;

    engine.initialize(GRID_SIZE, GRID_SIZE, MAT_WATER);
    engine.set_log_interval(6);  // 10 Hz de amostragem (antes 1 Hz = 3 pontos)

    std::cout << "[ACAO] Aquecedor continuo ligado no centro ("
              << center << "," << center << ")\n";

    const float dt = 1.0f / 60.0f;
    const int total_frames = 3 * 60;   // 3 segundos
    const float heater_power = 1.5f;   // graus por frame
    const int render_interval = 6;     // 10 Hz
    const int render_delay_ms = 80;

    std::cout << "[START] Simulando " << total_frames << " frames...\n";
    #ifdef _WIN32
    Sleep(500);
    #else
    usleep(500000);
    #endif

    for (int i = 0; i < total_frames; ++i) {
        engine.apply_heater(center, center, heater_power);
        engine.tick(dt);
        if (i % render_interval == 0) {
            engine.render_terminal();
            #ifdef _WIN32
            Sleep(render_delay_ms);
            #else
            usleep(render_delay_ms * 1000);
            #endif
        }
    }

    // ------------------------------------------------------------------------
    // VALIDACAO MATEMATICA
    // ------------------------------------------------------------------------
    std::cout << "\033[2J\033[H";
    std::cout << "=== VALIDACAO MATEMATICA ===\n";

    int failures = 0;
    auto check = [&failures](const char* name, bool ok) {
        std::cout << (ok ? "[PASS] " : "[FAIL] ") << name << "\n";
        if (!ok) ++failures;
    };

    float center_temp     = engine.get_temperature(center, center);
    float center_pressure = engine.get_pressure(center, center);
    int   center_mat      = engine.get_material(center, center);

    check("Evaporacao ocorreu (WATER -> STEAM)",
          engine.get_evaporation_count() >= 1);
    check("Pressao do centro subiu acima da ambiente (>1 atm)",
          center_pressure > Physics::AMBIENT_PRESSURE);
    check("Pressao critica foi atingida (evento disparado)",
          engine.get_pressure_critical_count() >= 1);
    check("Centro virou VAPOR com aquecimento continuo",
          center_mat == MAT_STEAM);
    check("Sem NaN na temperatura", center_temp == center_temp);
    check("Sem NaN na pressao",     center_pressure == center_pressure);
    // ANTI-REGRESSAO (Fase 1): difusao termica DEVE aquecer vizinhos.
    // Esta assertiva teria capturado a regressao do refactor automaticamente.
    check("REGRESSAO F1: vizinho recebeu calor (difusao ativa)",
          engine.get_temperature(center, center - 1) > Physics::AMBIENT_TEMP + 1.0f);

    std::cout << "\nResumo: T_centro=" << std::fixed << std::setprecision(1)
              << center_temp << " C | P_centro=" << std::setprecision(2)
              << center_pressure << " atm"
              << " | evaporacoes=" << engine.get_evaporation_count()
              << " | eventos_criticos=" << engine.get_pressure_critical_count() << "\n";

    engine.export_data("simulation_data.csv");

    if (failures == 0) {
        std::cout << "\n*** FASE 3 VALIDADA: Pressao sobe com vapor confinado. ***\n";
        std::cout.flush();
        return 0;
    } else {
        std::cout << "\n*** FASE 3 FALHOU: " << failures << " assertiva(s) reprovada(s). ***\n";
        std::cout.flush();
        return 1;
    }
}



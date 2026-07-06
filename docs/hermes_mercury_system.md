# 🔱 Mercury Systems v2 — Compressed Data Processing Runtime

## 📜 Visão Geral
O Mercury Systems é o motor de carregamento nativo do Doxoade, projetado para quebrar o *Memory Wall* em CPUs de baixo consumo (Celeron N2808 / DDR3). Ele substitui o pipeline tradicional `read → compile → exec` por um fluxo binário zero-copy com dicionários dual-layer e decodificação branchless via SSE 4.2.

## 🏆 Resultados de Benchmark (v2.0)

### Performance Geral
| Cenário | Python Puro | Mercury v2 | Speedup |
|---------|-------------|------------|---------|
| **Cold Start** | 1121.54 ms | 419.65 ms | **2.67×** |
| **Warm Start** | 1121.54 ms | 429.64 ms | **2.61×** |

### Breakdown por Módulo
| Módulo | Python (ms) | Mercury (ms) | Speedup |
|--------|-------------|--------------|---------|
| `doxoade.cli` | 361.54 | 137.88 | **2.62×** |
| `doxoade.tools.vulcan.forge` | 203.14 | 16.36 | **12.42×** |
| `doxoade.tools.hermes_systems.hermes_loader` | 117.50 | 17.92 | **6.56×** |
| `doxoade.core_database` | 371.34 | 214.09 | **1.73×** |
| `doxoade.tools.filesystem` | 68.02 | 33.40 | **2.04×** |

### Padrões Observados
1. **Módulos Puros:** Speedup massivo (6-12×) porque o Mercury elimina quase todo o overhead de parsing.
2. **Módulos com Cascade:** Speedup menor (1.7-2.6×) porque o custo de carregar dependências domina.
3. **Cold vs Warm:** Diferença de ~2%, provando que o Marshal Cache funciona perfeitamente.

## 🧠 Arquitetura

### Formato HBC5 (Zero-Compression)
```
[ Magic "HBC5" (4B) | Version 0x05 (1B) | Flags (1B) | TokenCount (2B) | Bitmap (32B) | Tokens... | PayloadSize (4B) | marshal(PyCodeObject) ]
```

### Dual-Dictionary Architecture
- **Global Dict (`master.bin`):** Mapeado via `mmap` (L3 Cache). Tokens transversais.
- **Local Dict:** Embutido no header HBC5 (L1 Cache). Padrões por módulo.

### Motor C-Native (`hermes_bridge.pyd`)
- **Parser HBC5:** Leitura branchless via `READ_U16/READ_U32` (shifts).
- **Walker In-Place:** Modifica `co_consts` diretamente no `PyCodeObject` deserializado.
- **Marshal Cache:** 
  - **Cold Start:** Parse HBC5 → Expansão Branchless → Grava `.cache` via `mmap`.
  - **Warm Start:** `mmap` leitura → `marshal.loads()` → Execução direta.

## 🛠️ Uso

### Compressão
```bash
# Comprimir todos os módulos para HBC5
doxoade hermes build --hbc5 --all

# Comprimir módulo específico
doxoade hermes build doxoade/cli.py --hbc5
```

### Benchmark
```bash
# Benchmark comparativo (Python Puro vs Mercury)
doxoade hermes benchmark

# Benchmark de módulo específico
doxoade hermes benchmark --module doxoade.tools.vulcan.forge
```

### Telemetria
```bash
# Telemetria RAW (análise profunda)
python hermes_raw_telemetry.py

# Ver gargalos em JSON
cat .doxoade/hermes/raw_telemetry.json
```

## 📈 Roadmap v3
- [ ] **Import Cascade Optimization:** Pré-carregar dependências em paralelo.
- [ ] **Dicionário Global Imutável:** Kernel Shared Memory via `CreateFileMapping`.
- [ ] **SIMD AVX2:** Processamento de 32 tokens/ciclo no `walk_inplace`.
- [ ] **Telemetria em Tempo Real:** Windows Event Tracing (ETW).

## 🔧 Estrutura de Arquivos
```
doxoade/tools/hermes_systems/
├── native/
│   ├── hermes_py_bridge.c      # Motor C (Parser + Walker + Cache)
│   ├── hermes_hbc5_parser.c    # Parser de Header HBC5
│   ├── hermes_gd_format.h      # Formato do Dicionário Global
│   ├── hermes_mmap.h           # Wrapper Windows mmap
│   └── hermes_bridge_builder.py# Integrador Metalcraft
├── hermes_hook_v2.py           # MetaPathFinder + Loader
├── hermes_compress_hbc5.py     # Compressor HBC5
└── hermes_benchmark_compare.py # Sistema de Benchmark
```
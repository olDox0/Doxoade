
---

# 1. Mapeamento Forense: Onde o `w64devkit` Está Acoplado Hoje

Varremos o projeto e localizamos **11 arquivos** que contêm caminhos fixos ou lógicas legadas do `w64devkit` para substituição pelo `janus_systems`:

| Arquivo | Acoplamento Atual com `w64devkit` | Ação de Substituição |
| :--- | :--- | :--- |
| **`doxoade/tools/metalcraft/metal_toolchain.py`** | Procura fixa em `thirdparty/w64devkit/bin/gcc.exe` | Delegar para `Janus.get_compiler()` |
| **`doxoade/tools/metalcraft/provisioner.py`** | Função `download_w64devkit` (zip de 85MB do GitHub) | Substituir por `JanusProvisioner` sob demanda |
| **`doxoade/commands/metalcraft.py`** | Comando `setup-tools` baixa `w64devkit` fixo | Atualizar para `doxoade janus setup` |
| **`doxoade/tools/vulcan/compiler.py`** | `_prepare_pitstop_env` busca `w64devkit/bin/gcc.exe` | Delegar injeção de PATH ao `Janus` |
| **`doxoade/commands/vulcan_cmd_forge.py`** | `_ensure_gcc_in_path` com lista estática de pastas | Usar `Janus.ensure_toolchain_in_path()` |
| **`doxoade/tools/hermes_systems/native/build_auto.py`** | `_detect_gcc` com caminhos de fallback | Delegar ao `Janus` |
| **`doxoade/tools/hermes_systems/native/build_logger.py`** | `find_gcc` busca no `thirdparty/w64devkit` | Delegar ao `Janus` |
| **`doxoade/tools/hermes_systems/native/build_decoder_simd.py`**| Procura `gcc.exe` na pasta `thirdparty/w64devkit` | Delegar ao `Janus` |
| **`doxoade/tools/hermes_systems/native/build_decoder.py`** | Lista caminhos `C:/w64devkit/lib` | Delegar ao `Janus` |
| **`doxoade/tools/hermes_systems/native/hermes_bridge_builder.py`**| Chama `NexusToolchain` | Delegar ao `Janus` |
| **`doxoade/commands/search_systems/search_engine.py`** | Lista `w64devkit` no `SKIP_DIRS` | Manter apenas no filtro de ignorados |

---

# 2. O Pipeline do `Janus_systems`: Descoberta ➔ Registro ➔ Sistema

O subsistema residirá em **`doxoade/tools/janus_systems/`** operando em três estágios transparentes:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        JANUS ENGINE PIPELINE                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌──────────────────┐      ┌──────────────────┐       ┌──────────────────┐
│  1. DESCOBERTA   │      │   2. REGISTRO    │       │   3. SISTEMA     │
│ (JanusScanner)   │      │ (JanusManifest)  │       │  (JanusBridge)   │
├──────────────────┤      ├──────────────────┤       ├──────────────────┤
│ Varre:           │      │ Persiste em:     │       │ Fornece à VM:    │
│ • PATH           │      │ .doxoade/janus/  │       │ • Injeção no PATH│
│ • MinGW (Amaranth)      │ toolchain.json   │       │ • Flags de C/C++ │
│ • WinLibs (Blueb)│      │                  │       │ • Detecção SIMD  │
│ • Clang (Termux) │      │ Guarda: versão,  │       │ • Suporte a DLLs │
│ • GCC (Linux)    │      │ tipo, arch, mtime│       │   e binários .so │
└──────────────────┘      └──────────────────┘       └──────────────────┘
```

### 1. Descoberta (`janus_detector.py`):
Varre os locais canônicos de cada ecossistema sem travar se não encontrar:
* **No Android / Termux:** Verifica `$PREFIX/bin/clang`, `$PREFIX/bin/gcc`.
* **No Windows (Amaranth / Bluebaby):**
  * MinGW padrão: `C:\MinGW\bin\gcc.exe`, `C:\mingw64\bin\gcc.exe`.
  * WinLibs: pastas de `winlibs-x86_64-*`, `C:\winlibs\bin`.
  * MSYS2 / UCRT: `C:\msys64\ucrt64\bin\gcc.exe`, `C:\msys64\mingw64\bin\gcc.exe`.
  * PATH do sistema: `shutil.which("clang")` ou `shutil.which("gcc")`.
* **No Linux / WSL:** `/usr/bin/gcc`, `/usr/bin/clang`.

### 2. Registro (`janus_manifest.py`):
Executa um probe rápido (10ms) de `--version` e `-dumpmachine`, salvando em `.doxoade/janus/toolchain.json`:
```json
{
  "station": "bluebaby",
  "compiler_type": "clang", 
  "compiler_path": "C:\\winlibs\\bin\\gcc.exe",
  "version": "14.2.0",
  "arch": "x86_64",
  "supports_simd": true,
  "last_verified": "2026-09-26T02:30:00"
}
```

### 3. Sistema (`janus_bridge.py`):
Fornece uma interface unificada para Metalcraft, Vulcan e Hermes:
```python
from doxoade.tools.janus_systems import Janus

# Injeta gcc/clang no PATH do processo em 1 linha
Janus.ensure_active()

# Retorna comando pronto para subprocess
cmd = Janus.build_compile_command(sources, output, flags=["-O2"])
```

---

# 3. Plano de Ação em 3 Etapas (ProDeNov §1.2)

```
[Etapa 1] Criação do Pacote doxoade/tools/janus_systems/
   ├── __init__.py          # API unificada: get_compiler(), ensure_active()
   ├── janus_detector.py    # Scanner multi-plataforma (Clang/MinGW/WinLibs)
   ├── janus_manifest.py    # Cache e persistência do manifesto
   └── janus_bridge.py      # Construtor de comandos e injeção de ambiente

[Etapa 2] Migração de Metalcraft, Vulcan e Hermes
   ↳ Substituir as 11 checagens fixas de 'w64devkit' pelo Janus.

[Etapa 3] Interface CLI de Diagnóstico
   ↳ doxoade janus status   (Exibe compilador ativo, versão e estação).
   ↳ doxoade janus scan     (Força re-detecção se você instalar outro compilador).
```

---


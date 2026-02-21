### CORE INTRODUCTION
# Núcleo da Arquitetura (Doxoade Core)

**Status:** Estável (Platinum/Gold)
**Conformidade:** PASC-8.4 (Planejamento), PASC-8.5 (Divisão de Responsabilidades)

O núcleo do Doxoade é desenhado sob o arquétipo de **Ártemis** (precisão CLI autônoma) e orquestrado por **Zeus** (roteamento central). A arquitetura segue rigorosamente a separação modular (Expert-Split) para garantir que nenhum arquivo exceda o limite de peso (OSL-16 / PASC-1.3).

## 1. Roteamento e Inicialização (O Olimpo)
A entrada do sistema ocorre de forma blindada:
* `__main__.py`: O guardião da entrada. Captura falhas fatais de importação e aciona o **Protocolo Lázaro** (`rescue.py`) em um subprocesso limpo caso o núcleo falhe.
* `cli.py` (Zeus): Utiliza a classe `DoxoadeLazyGroup` para carregar comandos sob demanda (PASC-6.7 - Lazyload). Isso reduz drasticamente a pegada de RAM no boot.

## 2. Padrão "Expert-Split" (Sistemas)
Comandos complexos não são monolíticos. Eles são divididos em "Sistemas" (`_systems/`) baseados em responsabilidade única:
* **Interface:** `comando.py` (Recebe o input do usuário via Click).
* **Motor Lógico:** `_engine.py` / `_logic.py` (Atena - Executa o trabalho pesado).
* **Estado:** `_state.py` (Hera - Armazena as variáveis e findings da execução).
* **I/O e Cache:** `_io.py` / `_utils.py` (Poseidon - Lida com leitura, escrita e cache).

*Exemplos notáveis:* `check_systems/`, `audit_systems/`, `search_systems/`, `impact_systems/`.

## 3. Topologia dos Deuses (Mapeamento de Pastas)
O código está organizado segundo os arquétipos funcionais:
* ⚡ **Zeus / Orquestração:** `commands/` (Despachantes de comandos).
* ⚖️ **Ma'at & Anúbis / Validação:** `audit_systems/`, `check_systems/`, `security_utils.py`, `guards.py`.
* 📜 **Thoth & Atena / Lógica e Inteligência:** `impact_systems/`, `intelligence_systems/`, `deepcheck.py`.
* 💾 **Osíris & Hades / Persistência:** `database.py` (Sapiens), `history.py`, `indexer/cache.py`.
* 🌊 **Poseidon / I/O Seguro:** `tools/streamer.py` (Unified File Streamer - UFS), `tools/filesystem.py`.
* 🔨 **Hefesto / Performance:** `tools/vulcan/` (Transpilador Cython/C e motor JIT).
* 👁️ **Hórus / Telemetria:** `chronos.py`, `telemetry.py`, `tools/governor.py` (ALB).

## 4. Gerenciamento de Recursos (ALB - Resource Governor)
Para respeitar o ambiente do usuário (PASC-6.4 - Well-Processing), o Doxoade utiliza:
* **Memory Pool:** `tools/memory_pool.py` (Evita fragmentação instanciando dicts vazios via `FindingArena`).
* **UFS (Unified File Streamer):** `tools/streamer.py` (Garante que um arquivo seja lido do disco apenas uma vez por ciclo).
* **Governor:** `tools/governor.py` (Monitora uso de CPU/RAM em tempo real e insere delays táticos se o sistema do usuário estiver sobrecarregado).
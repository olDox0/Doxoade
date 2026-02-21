# Doxoade: Visão Geral da Arquitetura (Overview)

**Data de Atualização:** 2026.02.20
**Versão:** 1.0 (Chief Gold Standard)

## 1. O que é o Doxoade?
O **Doxoade** é uma CLI autônoma de próxima geração, um acelerador de desenvolvimento e um sentinela de projetos. Projetado sob o arquétipo de **Ártemis** (precisão, autonomia e caça a gargalos), ele atua em múltiplas frentes de engenharia de software: qualidade de código (linting profundo), segurança (SAST/SCA), otimização de performance (transpilação JIT para C/Cython), análise de impacto via AST e recuperação forense de desastres.

## 2. Filosofia Base e Protocolos
A arquitetura do Doxoade não é definida apenas por pastas, mas por leis rígidas de sobrevivência e escalabilidade. Todo o desenvolvimento deve obedecer a dois grandes manifestos:

* **OSL (olDox222 Software Law / Modern Power of Ten):** 
  Foco em fluxos observáveis, funções curtas, alocação controlada de memória, proibição de arquivos monolíticos (limite estrito de 500 linhas / ~20KB) e tolerância a falhas (Fail-Safe).
* **PASC (Políticas de Atualização Segura de Códigos):** 
  Foco em Refatoração Conservadora, Anti-Regressividade, divisão cirúrgica de responsabilidades (Expert-Split) e I/O unificado (UTF-8 puro).

## 3. O Panteão Arquitetural (Mapeamento de Domínios)
Para manter o sistema coeso e com responsabilidades únicas (PASC 8.5), os subsistemas são divididos e conceituados usando uma taxonomia baseada em divindades (Programming Gods):

| Sistema / Domínio | Divindade | Descrição e Responsabilidade |
| :--- | :--- | :--- |
| **Core & Orquestração** | **Zeus / Rá** | Ponto de entrada (`cli.py`), roteamento de comandos com *Lazy Loading* (para poupar RAM) e loop global de execução. |
| **Auditoria & Check** | **Ma'at / Anúbis** | O Tribunal. Analisa complexidade, estilo, regressões e aplica *Auto-fixes* (Gênese). Garante que nenhuma regra PASC/OSL seja violada. |
| **Vulcan Forge** | **Hefesto / Ptah** | Motor de performance. Transpila *Hot-paths* de Python para Cython/C nativo de forma dinâmica e os injeta em tempo de execução. |
| **Chronos & Telemetry** | **Hades / Hórus** | Observabilidade de baixo custo. Rastreia picos de CPU, RAM e I/O, guardando o histórico em um banco SQLite (`doxoade.db`). |
| **Rescue & Forensics** | **Osíris / Poseidon** | Protocolo Lázaro. Realiza autópsia de *crashes*, escaneia *reflogs* do Git e recupera sessões perdidas do Notepad++. |
| **Segurança (Aegis)** | **Bastet / Sekhmet** | Escudo ativo. Varreduras de *Taint Analysis*, controle de quarentena de testes e análise de dependências vulneráveis. |
| **Inteligência (AST)** | **Atena / Thoth** | Motores `Deepcheck` e `Impact Analysis`. Lê o código semanticamente (Árvores de Sintaxe) para desenhar grafos de chamada e linhagem de dados. |

## 4. Topologia Física do Código
O código-fonte segue a diretriz **PASC 8.6 (Direcionalidade de Dependências)**, apontando sempre das camadas externas para o núcleo central.

```text
doxoade/
├── __main__.py          # Entrypoint de emergência (captura crash fatal antes da CLI)
├── cli.py               # Roteador LazyGroup (Zeus) - Carrega comandos sob demanda
├── commands/            # Comandos da CLI (Frontend das ações)
│   ├── check.py         # Orquestrador do Linter
│   ├── vulcan_cmd.py    # Orquestrador da Forja
│   ├── rescue_cmd.py    # Orquestrador de Resgate
│   └── *_systems/       # Subpastas de domínio fechado (ex: check_systems/)
├── tools/               # Utilitários Compartilhados (Tools Centralizadas - PASC 8.3)
│   ├── vulcan/          # Lógica pesada do compilador C
│   ├── security_utils.py# Funções de isolamento e hash
│   ├── db_utils.py      # Persistência assíncrona (Sapiens DB)
│   └── streamer.py      # FileStreamer (UFS) - RAM-First para evitar I/O repetitivo
├── probes/              # Sondas (Execução Isolada / Sandbox)
│   ├── syntax_probe.py  # Executado em subprocesso para não derrubar a CLI
│   └── style_probe.py   # Análise MPoT isolada
├── indexer/             # Motor de mapeamento AST puro
└── docs/                # Documentação e Protocolos
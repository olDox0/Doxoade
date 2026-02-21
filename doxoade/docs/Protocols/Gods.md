# Programming Gods (Arquétipos de Engenharia)

Os sistemas do Doxoade são desenhados e classificados com base nestes arquétipos para definir claramente suas responsabilidades lógicas.

## Panteão Grego (Foco em Estrutura e Ação)
* ⚡ **Zeus:** Kernel / Orquestrador / Root. Controla permissões e roteamento (`cli.py`, `__main__.py`).
* 🦚 **Hera:** Consistência / Contratos / Estado. Mantém a integridade de dados inter-sistemas (`_state.py`).
* 🌊 **Poseidon:** Streams / I/O / Caos controlável. Lida com I/O de arquivos e redes (`streamer.py`, `rescue.py`).
* 💀 **Hades:** Persistência / Arquivamento. Armazena o histórico e logs profundos (`database.py`, `indexer/cache.py`).
* 🦉 **Atena:** Estratégia / Arquitetura. Define os design patterns e lógica de análise profunda (`impact_systems/`, `deepcheck.py`).
* ⚔️ **Ares:** Força Bruta / Hack. Ofensiva, scripts rígidos e de execução agressiva (`security.py`, `check.py`).
* ☀️ **Apolo:** Ordem / Código Limpo. Responsável por UI/UX clara no terminal (`display.py`, `telemetry_io.py`).
* 🏹 **Ártemis:** Ferramentas Autônomas. O espírito original do Doxoade, independência e precisão.
* 🔨 **Hefesto:** Construção / Engenharia. Build systems, compilação C/Cython (`tools/vulcan/`).
* 🪽 **Hermes:** Comunicação. APIs, bridges inter-sistemas (`npp_integration.py`).
* 🍷 **Dionísio:** Caos Criativo. Prototipagem, laboratórios de experimentação (`experiments/`, `lab.py`).

## Panteão Egípcio (Foco em Sobrevivência e Dados)
* ☀️ **Rá:** Loop Principal. Fonte de energia, clock do sistema.
* 🌱 **Osíris:** Persistência e Renascimento. Snapshots e recovery.
* ✨ **Ísis:** Integração. Magia de juntar partes quebradas (Middlewares).
* 🦅 **Hórus:** Observabilidade. O olho que tudo vê (Telemetria, Chronos).
* ⚖️ **Ma'at:** Ordem e Invariantes. O que nunca pode quebrar (Asserções, `audit_systems/`).
* 🐺 **Anúbis:** Validação e Auditoria. O juiz que decide o que passa ou morre (`check_filters.py`, `security_utils.py`).
* 📖 **Thoth:** Linguagem e Lógica. AST Parsers, Inteligência Simbólica (`genesis.py`, `learning.py`).
* 🏜️ **Set:** Entropia. Falhas esperadas, inputs maliciosos. O sistema maduro espera por Set.
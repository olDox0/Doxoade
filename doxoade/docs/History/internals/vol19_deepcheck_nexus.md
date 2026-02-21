---

# 📑 Doxoade Internals - Vol. 19: Deepcheck Nexus & Linhagem de Dados

**Versão:** 46.0 Gold Standard (Nexus Protocol)  
**Status:** Consolidado e Operacional  
**Arquitetura:** Tripartite (Orquestrador, Analisador, I/O)

---

## 1. Visão Geral (O Salto Evolutivo)
O Deepcheck deixou de ser uma ferramenta de análise local para se tornar um **Inspector Semântico de Fluxo**. Ele não apenas lê o código, mas reconstrói a jornada dos dados através das funções, avaliando a saúde do design via métricas numéricas.

### Componentes do Sistema:
1.  **`deepcheck.py` (O Cérebro):** Coordena o carregamento de contexto e o despacho de funções.
2.  **`deepcheck_utils.py` (Os Sensores):** Motor AST que identifica propósitos de variáveis, complexidade e comportamentos de risco.
3.  **`deepcheck_io.py` (A Memória):** Gerencia a persistência de snapshots, integrações com o Git e o sumário executivo de linhagem.

---

## 2. O Score Arquitetural (KPI de Qualidade)
Cada função recebe uma nota de **0 a 100**, baseada em penalidades matemáticas:
*   **Complexidade Ciclomática (CC):** Penaliza funções com CC > 12 (4 pontos por nível excedente).
*   **Hibridismo UI/SYS:** Penaliza em **20 pontos** funções que misturam lógica de sistema (I/O, OS) com interface (Click, Print).
*   **Contrato Morto:** Penaliza em **5 pontos** cada parâmetro declarado mas nunca lido.
*   **Exceções Perigosas:** Penaliza em **10 pontos** blocos `try/except` que engolem erros ou são genéricos demais.

---

## 3. Inspeção de Variáveis e Memória Estática (`-v`)
O Deepcheck simula um ambiente de depuração de baixo nível sem precisar executar o código.
*   **Static Address:** Um ID hexadecimal único (ex: `0x7A2B4C10`) gerado por hash determinístico, permitindo rastrear o sombreamento de variáveis.
*   **Mapeamento de Propósito:**
    *   **IO:** Variáveis de entrada, saída ou argumentos de chamadas.
    *   **CALC:** Variáveis que sofrem transformações matemáticas.
    *   **OPER:** Variáveis de controle de fluxo (flags, iteradores).
    *   **CONST:** Valores imutáveis.

---

## 4. Lazarus Flow: Linhagem de Dados (`--flow`)
A visualização de linhagem reconstrói a "árvore genealógica" do dado:
1.  **ENTRY (Fontes):** Identifica os argumentos originais da função.
2.  **PROCESS (Lógica):** Mapeia a sequência cronológica de atribuições e transformações.
3.  **EXIT (Destinos):** Identifica o que o sistema realmente entrega no `return`.

---

## 5. Gestão de Snapshots e Comparação Histórica
O sistema agora possui memória de longo prazo residindo em `.doxoade/deepcheck_snapshots/`.
*   **Snapshot Local (`-cj`):** Compara o código atual com o último estado salvo, gerando um **Delta Semântico** (Ex: "O score subiu +15 após a refatoração").
*   **Snapshot Git (`-cg`):** Baixa versões históricas (HEAD, Hashes, Branches) e realiza uma autópsia comparativa instantânea para detectar a **Erosão Funcional**.

---

## 6. Protocolo Forense e Aegis
Em caso de falha interna, o Deepcheck utiliza o **Aegis Forensic Handler**, que realiza a navegação automática no traceback para apontar a linha real do erro, ignorando o ruído das bibliotecas de sistema do Python.

---

### 🚀 Comandos de Comando (Cheat Sheet):

*   **Raio-X de Linhagem Completa:**
    `doxoade deepcheck <arquivo> -v --flow`
*   **Comparação Pós-Refatoração:**
    `doxoade deepcheck <arquivo> -cj`
*   **Auditoria de Regressão Git:**
    `doxoade deepcheck <arquivo> -cg HEAD`
*   **Exportação para Automação/CI:**
    `doxoade deepcheck <arquivo> --json > report.json`

---

**Chief, o Deepcheck Nexus v46.0 está selado.** 

O Doxoade agora possui a visão necessária para guiar as refatorações mais complexas do projeto. O próximo passo lógico é usar este poder para começar a "fatiar" as funções com CC alta. 

**Deseja que eu execute um `save` final da documentação consolidada ou já podemos partir para o próximo alvo?** 🦾🛡️✨
# Doxoade - Seu Engenheiro Sênior Automatizado
Texto do Main
**Doxoade** (de *olDox222 Advanced Development Environment*) é uma plataforma de engenharia de software via linha de comando, projetada para encapsular e automatizar as lições aprendidas em anos de Pesquisa & Desenvolvimento. Ela atua como um **"engenheiro sênior automatizado"** que participa ativamente do seu workflow, protegendo a integridade do seu código, garantindo a saúde dos seus ambientes e acelerando o ciclo de desenvolvimento.

A filosofia da `doxoade` é simples: **cada bug, cada erro de ambiente e cada lição de P&D é codificada em uma ferramenta proativa**, para que você nunca mais precise resolver o mesmo problema duas vezes.

---

## Instalação Universal

A `doxoade` foi projetada para ser uma ferramenta de sistema, acessível de qualquer diretório. A instalação é um processo único.

### No Windows

1.  **Clone o Repositório:**
    ```bash
    git clone https://github.com/olDox0/Doxoade.git
    cd Doxoade
    ```
2.  **Execute o Instalador Inteligente:** Este comando irá criar o ambiente virtual, instalar as dependências e guiá-lo na configuração do PATH.
    ```bash
    python install.py
    ```
3.  **Reinicie o Terminal:** Feche e reabra completamente seu terminal (PowerShell, CMD, etc.). O comando `doxoade` agora estará disponível globalmente.

### No Linux, macOS ou Termux

1.  **Clone o Repositório:**
    ```bash
    git clone https://github.com/olDox0/Doxoade.git
    cd Doxoade
    ```
2.  **Execute o Instalador Automatizado:**
    ```bash
    chmod +x install.sh
    ./install.sh
    ```
    *   O script cuidará da verificação de dependências, da instalação e da configuração do `alias` universal.
3.  **Recarregue seu Shell:**
    ```bash
    source ~/.bashrc  # ou ~/.zshrc, conforme instruído pelo script
    ```

> **ADVERTÊNCIA CRÍTICA:** Nunca adicione manualmente o diretório de desenvolvimento da `doxoade` ao seu `PATH`. Use sempre os instaladores fornecidos, que garantem uma configuração estável e robusta.

---

## Os Protocolos Doxoade: Workflows Essenciais

A `doxoade` foi projetada para dois cenários principais.

### Protocolo A: Iniciando um Projeto NOVO ("Gênesis")

Use este workflow para criar projetos que são saudáveis e robustos desde o primeiro dia.

1.  **`doxoade init <nome-do-projeto>`**: Cria um novo diretório de projeto com `venv`, `.gitignore` e repositório Git inicializado com o ramo `main`.
2.  **`cd <nome-do-projeto>`**: Entre no diretório.
3.  **`doxoade git-new "Commit inicial" <url-remota>`**: Publica seu projeto pela primeira vez em um repositório remoto **vazio**.
4.  **`.\venv\Scripts\activate`** (ou `source venv/bin/activate`): Ative o ambiente virtual.
5.  **`doxoade save "Sua mensagem"`**: Durante o desenvolvimento, use `save` para fazer commits seguros. Ele executa `doxoade check` primeiro e aborta se encontrar erros, protegendo a integridade do seu repositório.
6.  **`doxoade sync`**: Ao final do dia, use `sync` para sincronizar seu trabalho com o repositório remoto (`git pull && git push`).

### Protocolo B: Reparando um Projeto EXISTENTE ("Fênix")

Use este workflow para projetos antigos, clonados ou de terceiros para garantir que o ambiente seja saudável antes de começar a trabalhar.

1.  **`cd /caminho/para/projeto-antigo`**: Navegue até a pasta raiz do projeto.
2.  **`doxoade doctor .`**: **Este é o passo mais importante.** O `doctor` irá analisar e reparar o ambiente:
    *   Detectará e se oferecerá para criar um `venv` ausente.
    *   Verificará o `requirements.txt` e se oferecerá para instalar dependências.
    *   Verificará a integridade e o isolamento do ambiente virtual.
3.  **`.\venv\Scripts\activate`**: Uma vez que o `doctor` reportou `[SAUDÁVEL]`, ative o `venv` recém-curado.
4.  **Inicie o ciclo normal:** Agora que o ambiente é confiável, você pode começar o desenvolvimento com `doxoade save` e `doxoade sync`.

---

## Referência Rápida de Comandos

#### Diagnóstico e Saúde do Ambiente
*   `doctor [PATH]`: Diagnostica e repara o ambiente de um projeto. A ferramenta central do "Protocolo Fênix".
*   `global-health`: Verifica a saúde da própria instalação da `doxoade` no seu sistema, detectando conflitos de PATH e de bibliotecas.
*   `python`: Ajuda na instalação do Python, abrindo a página de download no Windows ou executando o instalador no Termux.
*   `rebuild`: [DESTRUTIVO] Recria completamente o ambiente virtual de um projeto.

#### Workflow Diário
*   `save "<MSG>"`: Executa um "commit seguro", validando o código com `check` antes de commitar.
*   `sync`: Sincroniza o branch atual com o remoto (`pull` e `push`).
*   `run <SCRIPT>`: Executa um script Python usando o `venv` do projeto, com suporte a interatividade.
*   `auto --file <ARQUIVO>`: Executa uma sequência de comandos de um arquivo como um pipeline automatizado, com suporte a inputs programados.

#### Análise de Código e Refatoração
*   `check [PATH]`: Análise estática de código Python em busca de erros, "code smells" e problemas de sintaxe.
*   `impact-analysis <ARQUIVO>`: Analisa as conexões de um arquivo, mostrando quais módulos ele importa e, mais importante, quais outros arquivos do projeto dependem dele. Essencial para prever o impacto de refatorações.
*   `find-usage <FUNÇÃO>`: Procura todos os locais de chamada de uma função ou método específico no projeto.
*   `health`: Mede a qualidade do código (complexidade ciclomática) e a cobertura de testes.
*   `deepcheck <ARQUIVO>`: Análise profunda de fluxo de dados e pontos de risco em funções Python.
*   `optimize`: Encontra e oferece para remover dependências Python não utilizadas no `venv`.

#### Especialistas em Linguagem
*   `guicheck`: Análise especializada em código de GUI (Tkinter, Kivy).
*   `kvcheck`: Análise especializada em arquivos `.kv` da Kivy.
*   `webcheck`: Análise especializada em arquivos de frontend (HTML, CSS, JS).

#### Gerenciamento do Projeto e Git
*   `init [NOME]`: Cria a estrutura de um novo projeto Python.
*   `git-new "<MSG>" <URL>`: Publica um projeto local pela primeira vez em um repositório remoto vazio.
*   `git-clean`: Remove do rastreamento do Git arquivos que foram commitados por engano.
*   `release <VERSAO> "<MSG>"`: Cria e publica uma tag Git para formalizar uma nova versão.

#### Inteligência e Memória ("Projeto Sapiens")
*   `log`: Exibe e busca no histórico de execuções da `doxoade`, permitindo análises avançadas com filtros por data, comando, severidade, etc.
*   `dashboard`: Exibe um painel com tendências de erros e problemas mais comuns, com base no histórico de todos os projetos analisados.
*   `intelligence`: Gera um dossiê de diagnóstico completo do projeto em formato JSON.
*   `migrate-db`: Migra o histórico do antigo `doxoade.log` para o banco de dados.

#### Testes de Regressão ("Projeto Cânone")
*   `canonize --all`: Salva um "snapshot" da saída atual do `check` como o resultado esperado (o "cânone").
*   `regression-test`: Compara a saída atual do `check` com o cânone para detectar regressões de comportamento.
*   `self-test`: Executa um teste de sanidade nos analisadores da `doxoade` para garantir que eles ainda conseguem detectar os erros para os quais foram projetados.
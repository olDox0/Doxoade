# Doxoade - Seu Engenheiro Sênior Automatizado

**Doxoade** (de *olDox222 Advanced Development Environment*) é uma plataforma de engenharia de software via linha de comando, projetada para encapsular e automatizar as lições aprendidas em anos de Pesquisa & Desenvolvimento. Ela atua como um **"engenheiro sênior automatizado"** que participa ativamente do seu workflow, protegendo a integridade do seu código, garantindo a saúde dos seus ambientes e acelerando o ciclo de desenvolvimento.

A filosofia da `doxoade` é simples: **cada bug, cada erro de ambiente e cada lição de P&D é codificada em uma ferramenta proativa**, para que você nunca mais precise resolver o mesmo problema duas vezes.

---

## Instalação Universal

A `doxoade` foi projetada para ser uma ferramenta de sistema, acessível de qualquer diretório. A instalação é um processo de duas etapas: preparar o ambiente e depois configurar o acesso universal.

### No Windows

1.  **Clone o Repositório:**
    ```bash
    git clone https://github.com/olDox0/Doxoade.git
    cd Doxoade
    ```
2.  **Execute o Instalador/Reparador Universal:** O comando `doctor` irá preparar todo o ambiente da `doxoade` pela primeira vez.
    ```bash
    # Cria o venv, instala dependências e prepara a ferramenta
    doxoade.bat doctor .
    ```
3.  **Configure o Acesso Universal (Apenas uma vez):** O `doctor`, ao final, fornecerá um **"Guia de Instalação Universal"**. Siga as instruções para adicionar a pasta do projeto `Doxoade` ao seu `PATH` de sistema.
4.  **Reinicie o Terminal:** Feche e reabra completamente seu terminal. O comando `doxoade` agora estará disponível em qualquer lugar.

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
    *   O script cuidará da verificação de dependências de sistema, da instalação das bibliotecas Python e da configuração do `alias` universal.
3.  **Ative o `alias`:**
    ```bash
    source ~/.bashrc  # ou ~/.zshrc, conforme instruído pelo script
    ```
    *   O comando `doxoade` agora estará disponível em qualquer lugar.

> **ADVERTÊNCIA CRÍTICA:** Siga sempre as instruções fornecidas pelo `doctor` ou pelo `install.sh`. Nunca adicione manualmente um caminho que não seja a raiz do projeto `Doxoade` ao seu `PATH`, pois configurações instáveis podem causar falhas imprevisíveis.

---

## O Protocolo Doxoade: Workflows Essenciais

A `doxoade` foi projetada para dois cenários principais.

### Workflow A: Iniciando um Projeto NOVO

Use este workflow para criar projetos que são saudáveis e robustos desde o primeiro dia.

1.  **`doxoade init <nome-do-projeto>`**: Cria um novo diretório de projeto com `venv`, `.gitignore` e repositório Git.
2.  **`cd <nome-do-projeto>`**: Entre no diretório.
3.  **`doxoade git-new "Commit inicial" <url-remota>`**: Publica seu projeto em um repositório remoto **vazio**.
4.  **`.\venv\Scripts\activate`** (ou `source venv/bin/activate`): Ative o ambiente virtual.
5.  **`doxoade save "Sua mensagem"`**: Durante o desenvolvimento, use `save` para fazer commits seguros. Ele executa `doxoade check` primeiro e aborta se encontrar erros.
6.  **`doxoade sync`**: Ao final do dia, use `sync` para sincronizar seu trabalho com o repositório remoto.

### Workflow B: Reparando um Projeto EXISTENTE (O "Protocolo Fênix")

Use este workflow para projetos antigos, clonados ou de terceiros para garantir que o ambiente seja saudável antes de começar a trabalhar.

1.  **`cd /caminho/para/projeto-antigo`**: Navegue até a pasta raiz do projeto.
2.  **`doxoade doctor .`**: **Este é o passo mais importante.** Chame o `doctor` para analisar e reparar o ambiente. Ele irá:
    *   Detectar e se oferecer para criar um `venv` ausente.
    *   Verificar o `requirements.txt`, se oferecer para instalar dependências ausentes e provar que a instalação foi bem-sucedida.
    *   Verificar se o `venv` está isolado e não contaminado.
3.  **`.\venv\Scripts\activate`**: Uma vez que o `doctor` reportou `[SAUDÁVEL]`, ative o `venv` recém-curado.
4.  **Inicie o Workflow A:** Agora que o ambiente é confiável, você pode começar o ciclo de desenvolvimento normal com `doxoade save` e `doxoade sync`.

---

## Referência Rápida de Comandos

#### Diagnóstico e Reparo
*   `doctor [PATH]`: Diagnostica e repara o ambiente de um projeto. A ferramenta central do "Protocolo Fênix".

#### Ciclo de Vida do Projeto
*   `init [NOME]`: Cria a estrutura de um novo projeto Python.
*   `git-new "<MSG>" <URL>`: Publica um projeto local pela primeira vez em um repositório remoto vazio.
*   `release <VERSAO> "<MSG>"`: Cria e publica uma tag Git para formalizar uma nova versão.

#### Workflow Diário
*   `save "<MSG>"`: Executa um "commit seguro", validando o código com `check` antes de commitar.
*   `sync`: Sincroniza o branch atual com o remoto (`pull` e `push`).
*   `run <SCRIPT>`: Executa um script Python usando o `venv` do projeto.
*   `auto "<CMD1>" "<CMD2>"`: Executa uma sequência de comandos como um pipeline.

#### Análise de Qualidade
*   `check`: Análise estática de código Python em busca de erros e "code smells".
*   `health`: Mede a qualidade do código (complexidade e cobertura de testes).
*   `deepcheck <ARQUIVO>`: Análise profunda de fluxo de dados e pontos de risco em funções Python.
*   `guicheck`: Análise especializada em código de GUI (Tkinter, Kivy).
*   `kvcheck`: Análise especializada em arquivos `.kv` da Kivy.
*   `webcheck`: Análise especializada em arquivos de frontend (HTML, CSS, JS).
*   `optimize`: Encontra e oferece para remover dependências Python não utilizadas.

#### Utilitários
*   `log`: Exibe o histórico de execuções da `doxoade`.
*   `dashboard`: Exibe um painel com tendências de erros e saúde dos projetos.
*   `clean`: Deleta arquivos de cache e build do seu diretório local.
*   `git-clean`: Remove do *rastreamento do Git* arquivos que foram commitados por engano.
*   `mk <ARQUIVO/PASTA>`: Cria arquivos e pastas rapidamente.
*   `encoding <ALVO> <CODIFICACAO>`: Converte a codificação de arquivos.
*   `show-trace`: Analisa e exibe um arquivo de trace de sessão.
*   `create-pipeline`: Cria um arquivo de automação para ser usado com `doxoade auto`.

#### Aprendizado
*   `tutorial main`: Exibe um guia completo dos workflows.
*   `tutorial simulation`: Executa uma simulação guiada do workflow.
*   `tutorial interactive`: Um laboratório prático para aprender usando os comandos.
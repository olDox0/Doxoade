# doxoade - olDox222 Advanced Development Environment (v3.0)

`doxoade` é uma ferramenta de linha de comando para **iniciar, analisar e gerenciar o workflow completo** de projetos Python. Ela foi criada para ser um **"engenheiro sênior automatizado"**, encapsulando lições aprendidas de projetos anteriores para prevenir erros comuns, reforçar boas práticas e acelerar o ciclo de desenvolvimento de forma segura e consistente.

A filosofia da ferramenta é fornecer diagnósticos e automações que não apenas resolvem um problema, mas também **ensinam e impõem um processo de engenharia robusto**, desde a criação do projeto até o seu versionamento.

## Funcionalidades Principais

A suíte OADE v3.0 cobre todo o ciclo de vida de um projeto, integrando análise de código, execução segura, automação e versionamento com Git.

### Ciclo de Vida do Projeto
*   `doxoade init [NOME_PROJETO]`: Cria a estrutura inicial de um projeto Python, incluindo `venv`, um `.gitignore` robusto e a inicialização de um repositório Git (`git init -b main`).
*   `doxoade clean`: Limpa o projeto de artefatos de build e cache (`__pycache__`, `build/`, `dist/`, etc.) de forma segura.

### Análise e Qualidade de Código
*   `doxoade check`: Executa um diagnóstico completo do código-fonte Python, verificando ambiente, dependências e procurando por bugs e "code smells" com Pyflakes.
*   `doxoade webcheck`: Analisa arquivos de frontend (`.html`, `.css`, `.js`) em busca de problemas como links quebrados e erros de sintaxe.
*   `doxoade guicheck`: Analisa arquivos de GUI (Tkinter) em busca de problemas comuns usando análise de árvore de sintaxe abstrata (AST).

### Workflow, Git e Automação
*   `doxoade run <script>`: Executa scripts Python de forma segura e **não-bloqueante**, garantindo o uso do `venv` correto e oferecendo diagnóstico pós-execução.
*   `doxoade save "MENSAGEM"`: Um **"commit seguro"**. Ele primeiro executa `doxoade check`. Se houver erros, o commit é **abortado**, protegendo seu repositório de código quebrado.
*   `doxoade git-clean`: Uma ferramenta de "higienização" que lê seu `.gitignore` e remove do rastreamento do Git quaisquer arquivos que foram commitados por engano.
*   `doxoade git-new "MENSAGEM" <URL>`: Automação completa para **publicar um projeto local pela primeira vez**, executando todo o boilerplate do Git por você.
*   `doxoade auto "CMD1" "CMD2"...`: Um executor de tarefas que roda uma sequência de comandos e apresenta um sumário final de sucessos e falhas.

### Telemetria e Aprendizado
*   `doxoade log`: Exibe as últimas entradas do log de execuções do `doxoade`. A flag `--snippets` mostra o contexto de código exato para cada problema.
*   `doxoade tutorial`: Exibe um guia passo a passo completo do workflow recomendado do `doxoade`, ideal para novos usuários.

## Instalação

O `doxoade` é projetado para ser instalado como uma ferramenta global.

**1. Clone o Repositório:**
```bash
git clone <URL_DO_REPOSITORIO>
cd doxoade
```

**2. Instale em Modo Editável:**
Recomenda-se instalar em "modo editável" (`-e`). Isso cria o comando `doxoade` no seu sistema, mas o vincula diretamente ao código-fonte.
```bash
# Navegue até a pasta raiz do projeto 'doxoade'
pip install -e .
```
Após a instalação, o comando `doxoade` estará disponível em qualquer novo terminal.

## Aprendendo a Usar o doxoade

A ferramenta foi projetada para se auto-documentar e ensinar o usuário.

*   **Para um guia completo**, execute o tutorial interativo:
    ```bash
    doxoade tutorial
    ```
*   **Para ver todos os comandos disponíveis**, use a ajuda principal:
    ```bash
    doxoade --help
    ```
*   **Para ver as opções e exemplos de um comando específico**, use a ajuda desse comando:
    ```bash
    doxoade save --help
    doxoade log --help
    ```

## Workflow Recomendado

O `doxoade` simplifica drasticamente o ciclo de desenvolvimento.

### Iniciando um Novo Projeto (O Método Doxoade)

```bash
# 1. Crie a estrutura local com 'init'
doxoade init meu-novo-projeto

# 2. Crie um repositório VAZIO no GitHub e copie a URL.

# 3. Entre no diretório e use 'git-new' para publicar
cd meu-novo-projeto
doxoade git-new "Commit inicial: Estrutura do projeto" <URL_DO_SEU_REPOSITORIO.git>
```

### O Ciclo de Desenvolvimento Diário

```bash
# Entre no seu projeto e ative o ambiente virtual
cd meu-novo-projeto
.\venv\Scripts\activate

# 1. Programe e faça suas alterações...

# 2. Quando estiver pronto para salvar, use o 'doxoade save'.
(venv) > doxoade save "Adicionada nova funcionalidade X"

# 3. Envie suas alterações para o repositório remoto.
(venv) > git push
```

---
*Este projeto é uma ferramenta de P&D para encapsular e automatizar o conhecimento adquirido em engenharia de software.*
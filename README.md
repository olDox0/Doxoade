# doxoade - olDox222 Advanced Development Environment (v2.0)

`doxoade` é uma ferramenta de linha de comando para **iniciar, analisar e gerenciar o workflow** de projetos Python. Ela foi criada para ser um **"engenheiro sênior automatizado"**, encapsulando lições aprendidas de projetos anteriores para prevenir erros comuns, reforçar boas práticas e acelerar o ciclo de desenvolvimento de forma segura e consistente.

A filosofia da ferramenta é fornecer diagnósticos e automações que não apenas resolvem um problema, mas também **ensinam e impõem um processo de engenharia robusto**, desde a criação do projeto até o seu versionamento.

## Funcionalidades Principais

A suíte OADE v2.0 cobre todo o ciclo de vida de um projeto, integrando análise de código, execução segura e versionamento com Git.

### Ciclo de Vida do Projeto
*   `doxoade init [NOME_PROJETO]`: Cria a estrutura inicial de um projeto Python, incluindo `venv`, um `.gitignore` robusto e a inicialização de um repositório Git (`git init -b main`).
*   `doxoade clean`: Limpa o projeto de artefatos de build e cache (`__pycache__`, `build/`, `dist/`, `*.egg-info`, `*.spec`) de forma segura.

### Análise e Qualidade de Código
*   `doxoade check`: Executa um diagnóstico completo do código-fonte Python, verificando ambiente, dependências e procurando por bugs e "code smells" com Pyflakes.
*   `doxoade webcheck`: Analisa arquivos de frontend (`.html`, `.css`, `.js`) em busca de problemas como links quebrados, erros de sintaxe e más práticas.
*   `doxoade guicheck`: Analisa arquivos de GUI (Tkinter) em busca de problemas comuns, como widgets sem ação, usando análise de árvore de sintaxe abstrata (AST).

### Workflow e Automação
*   `doxoade run <script>`: Executa scripts Python de forma segura e **não-bloqueante**, garantindo o uso do `venv` correto e oferecendo diagnóstico pós-execução. O `CTRL+C` é tratado de forma graciosa.
*   `doxoade save "MENSAGEM"`: Um **"commit seguro"**. Ele primeiro executa `doxoade check`. Se houver erros, o commit é **abortado**, protegendo seu repositório. Se tudo estiver correto, ele prossegue com o `commit`.
*   `doxoade git-clean`: Uma ferramenta de "higienização" que lê seu `.gitignore` e remove do rastreamento do Git quaisquer arquivos que foram commitados por engano.
*   `doxoade git-new "MENSAGEM" <URL>`: Automação completa para **publicar um projeto local pela primeira vez**, executando `git init`, criando um `.gitignore`, fazendo o `save` inicial e enviando para a URL remota.
*   `doxoade auto "CMD1" "CMD2"...`: Um executor de tarefas que roda uma sequência de comandos, executa todos os passos (mesmo que um falhe) e apresenta um sumário final de sucessos e falhas.

### Telemetria e Análise
*   `doxoade log`: Exibe as últimas entradas do log de execuções do `doxoade`, permitindo uma consulta rápida. A flag `--snippets` mostra o contexto de código exato para cada problema encontrado.

## Instalação

O `doxoade` é projetado para ser instalado como uma ferramenta global.

**1. Clone o Repositório:**```bash
git clone <URL_DO_REPOSITORIO>
cd doxoade
```

**2. Instale em Modo Editável:**
Recomenda-se instalar em "modo editável" (`-e`). Isso cria o comando `doxoade` no seu sistema, mas o vincula diretamente ao código-fonte, permitindo que futuras melhorias sejam refletidas instantaneamente.
```bash
# Navegue até a pasta raiz do projeto 'doxoade'
pip install -e .
```
Após a instalação, o comando `doxoade` estará disponível em qualquer novo terminal.

## Configuração (Opcional)

Para centralizar configurações como pastas a serem ignoradas, crie um arquivo `.doxoaderc` na raiz do seu projeto.

**Exemplo de `.doxoaderc`:**
```ini
[doxoade]
# Adicione nomes de pastas a serem ignoradas, um por linha.
ignore = 
    node_modules
    backups
    documentacao_antiga
```

## Guia de Uso e Workflow Recomendado

O `doxoade` foi projetado para se integrar perfeitamente ao seu fluxo de trabalho diário.

### Iniciando um Novo Projeto do Zero

Este é o fluxo completo, da criação local à publicação no GitHub, usando o `doxoade` para automatizar quase tudo.

```bash
# 1. Navegue para sua pasta de trabalho
cd C:\Caminho\Para\MeusProjetos

# 2. Use 'init' para criar a estrutura local do projeto
doxoade init meu-novo-projeto

# 3. Vá para o GitHub e crie um novo repositório VAZIO chamado "meu-novo-projeto". Copie a URL.

# 4. Entre no diretório do projeto e use 'git-new' para fazer todo o resto
cd meu-novo-projeto
doxoade git-new "Commit inicial: Estrutura do projeto criada pelo doxoade" <URL_DO_SEU_REPOSITORIO.git>
```

### O Ciclo de Desenvolvimento Diário

Para cada nova funcionalidade ou correção de bug.

```bash
# Entre no seu projeto e ative o ambiente virtual
cd meu-novo-projeto
.\venv\Scripts\activate

# 1. Escreva seu código, modifique arquivos...

# 2. Quando estiver pronto para salvar, use o 'doxoade save'.
# Ele irá proteger seu repositório de código com erros.
(venv) > doxoade save "Adicionada funcionalidade de login de usuário"

# 3. Se o 'save' foi bem-sucedido, envie suas alterações para o repositório remoto.
(venv) > git push
```

### Executando uma Suíte de Diagnóstico Completa

Use o `doxoade auto` para rodar uma bateria de testes e ver um sumário no final.

```bash
# Executa todas as principais verificações e depois tenta rodar a GUI
doxoade auto "doxoade check ." "doxoade guicheck ." "doxoade webcheck ." "doxoade run main_gui.py"
```

---
*Este projeto é uma ferramenta de P&D para encapsular e automatizar o conhecimento adquirido em engenharia de software.*
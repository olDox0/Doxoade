# doxoade - Your Automated Senior Engineer

> `doxoade` (olDox222 Advanced Development Environment) é uma ferramenta de linha de comando para **iniciar, analisar e gerenciar o workflow completo** de projetos Python. Ela foi criada para ser um **"engenheiro sênior automatizado"**, encapsulando lições de engenharia para prevenir erros comuns, reforçar boas práticas e acelerar o ciclo de desenvolvimento de forma segura e consistente.

A filosofia da ferramenta é fornecer diagnósticos e automações que não apenas resolvem um problema, mas também **ensinam e impõem um processo de engenharia robusto**, desde a criação do projeto até o seu versionamento e manutenção.

---

## Funcionalidades Principais

A `doxoade` cobre todo o ciclo de vida de um projeto, integrando análise de código, execução segura, automação, versionamento com Git e até mesmo auto-diagnóstico.

#### Ciclo de Vida do Projeto
*   `doxoade init [NOME]`: Cria a estrutura inicial de um projeto Python, incluindo `venv`, um `.gitignore` robusto e a inicialização de um repositório Git.
*   `doxoade git-new "<MSG>" <URL>`: Automação completa para **publicar um projeto local pela primeira vez**, executando todo o boilerplate do Git por você.

#### Workflow Diário
*   `doxoade save "<MSG>"`: Um **"commit seguro"**. Ele primeiro executa `doxoade check`. Se houver erros, o commit é **abortado**, protegendo seu repositório de código quebrado.
*   `doxoade run <script>`: Executa scripts Python de forma segura e interativa, garantindo o uso do `venv` correto.
*   `doxoade sync`: Sincroniza o branch local com o remoto, executando `git pull` e `git push` para manter tudo atualizado.
*   `doxoade release <VERSAO> "<MSG>"`: Cria e publica uma tag Git para formalizar uma nova versão do seu projeto.

#### Análise de Qualidade e Saúde
*   `doxoade check`: Executa um diagnóstico de bugs e "code smells" com Pyflakes.
*   `doxoade webcheck`: Analisa arquivos de frontend (`.html`, `.css`, `.js`).
*   `doxoade guicheck`: Analisa arquivos de GUI (Tkinter) em busca de problemas de design e arquitetura de layout.
*   `doxoade health`: Vai além dos bugs e **mede a qualidade do código**, analisando a complexidade ciclomática (`radon`) e a cobertura de testes (`coverage.py`).

#### Ferramentas e Manutenção
*   `doxoade setup-health`: **Prepara um projeto para análise de saúde**, atualizando `requirements.txt`, criando o `.doxoaderc` e instalando as dependências necessárias.
*   `doxoade clean`: Limpa o projeto de artefatos de build e cache (`__pycache__`, `build/`, etc.).
*   `doxoade git-clean`: "Higieniza" seu repositório, removendo do rastreamento do Git quaisquer arquivos que foram commitados por engano.
*   `doxoade doctor`: Um **meta-diagnóstico** que verifica a saúde da própria instalação do `doxoade`, procurando por conflitos de `PATH` e problemas de dependência interna.
*   `doxoade auto "<CMD1>" "<CMD2>"`: Um executor de tarefas que roda uma sequência de comandos e apresenta um sumário final.

#### Aprendizado e Insights
*   `doxoade tutorial`: Exibe um guia de referência completo do workflow.
*   `doxoade tutorial-simulation`: Executa uma simulação guiada do workflow em um ambiente seguro.
*   `doxoade tutorial-interactive`: Um **laboratório prático** onde você digita os comandos para aprender fazendo.
*   `doxoade log`: Exibe as últimas entradas do log de execuções. A flag `--snippets` mostra o contexto de código exato para cada problema.
*   `doxoade dashboard`: Lê o histórico de logs e exibe um **painel de inteligência de engenharia** com tendências de erros, projetos mais problemáticos e os tipos de bug mais comuns.

---

## Instalação

O `doxoade` é projetado para ser instalado como uma ferramenta de desenvolvimento a partir do código-fonte.

**1. Clone o Repositório:**
]bash
git clone <URL_DO_REPOSITORIO>
cd doxoade
]

**2. Crie e Ative um Ambiente Virtual:**
]bash
python -m venv venv
.\venv\Scripts\activate
]

**3. Instale em Modo Editável:**
Isso cria o comando `doxoade` no seu sistema, mas o vincula diretamente ao código-fonte, permitindo que você o modifique e veja as mudanças instantaneamente.
]bash
pip install -e .
]
Após a instalação, o comando `doxoade` estará disponível em qualquer novo terminal.

---

## Modo de Uso Avançado e Advertências

### Acesso Universal (Adicionando ao PATH)

A `doxoade` foi projetada para ser uma ferramenta de sistema, como o `git`. Para torná-la acessível de qualquer diretório, o `doxoade doctor` irá guiá-lo no processo de configuração para sua plataforma (Windows, Linux, Termux).

**ADVERTÊNCIA CRÍTICA:** **Nunca** adicione o diretório de código-fonte da `doxoade` diretamente à sua variável `PATH` do sistema. Esta é uma prática de configuração instável que pode causar falhas imprevisíveis, especialmente em caminhos que contêm espaços. Siga sempre as instruções fornecidas pelo `doxoade doctor` para uma instalação robusta.


## Workflow Recomendado

### Iniciando um Novo Projeto
]bash
# 1. Crie a estrutura local com 'init'
doxoade init meu-novo-projeto

# 2. Crie um repositório VAZIO no GitHub e copie a URL.

# 3. Entre no diretório e use 'git-new' para publicar
cd meu-novo-projeto
doxoade git-new "Commit inicial: Estrutura do projeto" <URL_DO_SEU_REPOSITORIO.git>
]

### O Ciclo de Desenvolvimento Diário
]bash
# Entre no seu projeto e ative o ambiente virtual
cd meu-novo-projeto
.\venv\Scripts\activate

# 1. Programe suas alterações...

# 2. Quando estiver pronto, faça um commit seguro
(venv) > doxoade save "Adicionada nova funcionalidade X"

# 3. Sincronize suas alterações com o repositório remoto
(venv) > doxoade sync
]

### Analisando a Saúde de um Projeto Existente
]bash
# 1. Navegue até o projeto e prepare-o para a análise
doxoade setup-health

# 2. Siga as instruções para configurar o source_dir

# 3. Agora, rode a análise de saúde
doxoade health
]

---
*Este projeto é uma ferramenta de P&D para encapsular e automatizar o conhecimento adquirido em engenharia de software.*
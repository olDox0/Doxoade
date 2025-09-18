doxoade - olDox222 Advanced Development Environment (v2.0)
doxoade é uma ferramenta de linha de comando para iniciar, analisar e gerenciar o workflow de projetos Python. Ela foi criada para ser um "engenheiro sênior automatizado", encapsulando lições aprendidas de projetos anteriores para prevenir erros comuns, reforçar boas práticas e acelerar o ciclo de desenvolvimento de forma segura e consistente.
A filosofia da ferramenta é fornecer diagnósticos e automações que não apenas resolvem um problema, mas também ensinam e impõem um processo de engenharia robusto, desde a criação do projeto até o seu versionamento.
Funcionalidades Principais
A suíte OADE v2.0 cobre todo o ciclo de vida de um projeto, integrando análise de código, execução segura e versionamento com Git.
Ciclo de Vida do Projeto
doxoade init [NOME_PROJETO]: Um assistente para criar a estrutura inicial de um novo projeto Python, incluindo venv, um .gitignore robusto e a inicialização de um repositório Git (git init -b main).
doxoade clean: Limpa o projeto de artefatos de build e cache (__pycache__, build/, dist/, *.egg-info, *.spec) de forma segura.
Análise e Qualidade de Código
doxoade check: Executa um diagnóstico completo do código-fonte Python, verificando o ambiente, as dependências e procurando por bugs e "code smells" com Pyflakes.
doxoade webcheck: Analisa arquivos de frontend (.html, .css, .js) em busca de problemas como links quebrados, erros de sintaxe e más práticas.
doxoade guicheck: Analisa arquivos de GUI (Tkinter) em busca de problemas comuns, como widgets sem ação, usando análise de árvore de sintaxe abstrata (AST).
Workflow e Automação
doxoade run <script>: Executa scripts Python de forma segura e não-bloqueante, garantindo o uso do venv correto e oferecendo um diagnóstico pós-execução em caso de falha. O CTRL+C é tratado de forma graciosa.
doxoade save "MENSAGEM": Um "commit seguro". Ele primeiro executa doxoade check. Se houver erros, o commit é abortado, protegendo seu repositório. Se tudo estiver certo, ele executa git add . e git commit.
doxoade git-clean: Uma ferramenta de "higienização" que lê seu .gitignore e remove do rastreamento do Git quaisquer arquivos que foram commitados por engano (como a pasta venv).
doxoade auto "CMD1" "CMD2"...: Um executor de tarefas que roda uma sequência de comandos. Ele executa todos os passos, mesmo que um falhe, e apresenta um sumário final de sucessos e falhas.
Telemetria e Análise
doxoade log: Exibe as últimas entradas do log de execuções do doxoade, permitindo uma consulta rápida dos resultados de análises anteriores. A flag --snippets mostra o contexto de código exato para cada problema encontrado.
Instalação
O doxoade é projetado para ser instalado como uma ferramenta global.
1. Clone o Repositório (se aplicável):
code
Bash
git clone <URL_DO_REPOSITORIO>
cd doxoade
2. Instale em Modo Editável:
Recomenda-se instalar em "modo editável" (-e). Isso cria o comando doxoade no seu sistema, mas o vincula diretamente ao código-fonte.
code
Bash
# Navegue até a pasta raiz do projeto 'doxoade'
pip install -e .
Após a instalação, o comando doxoade estará disponível em qualquer novo terminal.
Configuração (Opcional)
Para evitar repetir opções como --ignore em múltiplos comandos, você pode criar um arquivo .doxoaderc na raiz do projeto que deseja analisar.
Exemplo de .doxoaderc:
code
Ini
[doxoade]
# Adicione nomes de pastas a serem ignoradas, um por linha.
ignore = 
    node_modules
    backups
    documentacao_antiga
Guia de Uso e Workflow Recomendado
O doxoade foi projetado para se integrar perfeitamente ao seu fluxo de trabalho diário.
Iniciando um Novo Projeto do Zero
Este é o fluxo completo, da criação local à publicação no GitHub.
code
Bash
# 1. Navegue para sua pasta de trabalho
cd C:\Caminho\Para\MeusProjetos

# 2. Crie o projeto. O doxoade vai criar a pasta, o venv, o .gitignore e inicializar o Git.
doxoade init meu-novo-projeto

# 3. Vá para o GitHub e crie um novo repositório VAZIO chamado "meu-novo-projeto". Copie a URL.

# 4. Entre no diretório do projeto e conecte-o ao GitHub
cd meu-novo-projeto
git remote add origin <URL_DO_SEU_REPOSITORIO_NO_GITHUB.git>

# 5. Ative o ambiente virtual
.\venv\Scripts\activate

# 6. Faça o primeiro commit usando o "commit seguro" do doxoade
(venv) > doxoade save "Commit inicial: Estrutura do projeto criada pelo doxoade"

# 7. Envie seu projeto para o GitHub pela primeira vez
(venv) > git push -u origin main
O Ciclo de Desenvolvimento Diário
Para cada nova funcionalidade ou correção de bug.
code
Bash
# (venv) > Ative o ambiente virtual, se ainda não estiver ativo.

# 1. Escreva seu código, modifique arquivos...

# 2. Quando estiver pronto para salvar, use o 'doxoade save'.
# Ele irá verificar seu código por erros antes de permitir o commit.
(venv) > doxoade save "Adicionada funcionalidade de login de usuário"

# 3. Se o 'save' foi bem-sucedido, envie suas alterações para o repositório remoto.
(venv) > git push```

### Executando uma Suíte de Diagnóstico Completa

Use o `doxoade auto` para rodar uma bateria de testes e ver um sumário no final.

```bash
# Executa todas as principais verificações e depois tenta rodar a GUI.
doxoade auto "doxoade check ." "doxoade guicheck ." "doxoade webcheck ." "doxoade run main_gui.py"
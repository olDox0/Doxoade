# doxoade - olDox222 Advanced Development Environment (v1.0)

`doxoade` é uma ferramenta de linha de comando para analisar e auxiliar no desenvolvimento de projetos Python. Ela foi criada para ser um "engenheiro sênior automatizado", encapsulando lições aprendidas de projetos anteriores para prevenir erros comuns, reforçar boas práticas e acelerar o ciclo de desenvolvimento.

A filosofia da ferramenta é fornecer diagnósticos rápidos e precisos que não apenas identificam um problema, mas também oferecem contexto e soluções baseadas em uma base de conhecimento interna de P&D.

## Funcionalidades Principais

A suíte OADE-LITE v1.0 cobre todo o ciclo de vida básico de um projeto:

-   **`doxoade init`**: Um assistente interativo para criar a estrutura inicial de um novo projeto Python, incluindo `venv`, `.gitignore` e arquivos iniciais.
-   **`doxoade run`**: Executa scripts Python garantindo o uso do ambiente virtual (`venv`) correto, prevenindo a classe de erros mais comum de "discrepância de ambiente" e oferecendo diagnóstico em caso de falha.
-   **`doxoade check`**: Executa um diagnóstico completo do código-fonte Python, verificando o ambiente, as dependências e procurando por bugs comuns e "code smells".
-   **`doxoade webcheck`**: Analisa arquivos de frontend (`.html`, `.css`, `.js`) em busca de problemas como links quebrados, erros de sintaxe e más práticas de acessibilidade/manutenção.
-   **`doxoade guicheck`**: Analisa arquivos de GUI (Tkinter) em busca de problemas comuns, como widgets sem ação.
-   **`doxoade clean`**: Limpa o projeto de artefatos de build e cache (`__pycache__`, `build/`, `dist/`, `*.spec`) de forma segura.

## Instalação

O `doxoade` é projetado para ser instalado como uma ferramenta global no seu sistema, permitindo que seja usado para analisar qualquer projeto, em qualquer diretório.

**1. Clone o Repositório (se aplicável):**
```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd doxoade
2. Instale em Modo Editável:
Recomenda-se instalar em "modo editável" (-e). Isso cria o comando doxoade no seu sistema, mas o vincula diretamente ao código-fonte, permitindo que futuras melhorias na ferramenta sejam refletidas instantaneamente.
Abra um terminal como Administrador e execute:
code
Bash
# Navegue até a pasta raiz do projeto 'doxoade'
pip install -e .
Após a instalação, o comando doxoade estará disponível em qualquer novo terminal.
Guia de Uso
Uma vez instalado, você pode usar o doxoade de qualquer diretório para iniciar ou analisar seus projetos.
Iniciando um Novo Projeto
Use o assistente init para criar um novo projeto com a estrutura correta.
code
Bash
# Navegue para sua pasta de projetos
cd C:\Caminho\Para\MeusProjetos

# Inicie o assistente
doxoade init
Siga as instruções, fornecendo um nome para o seu projeto. O doxoade criará a pasta do projeto, o venv e os arquivos iniciais para você.
Analisando um Projeto Existente
O fluxo de trabalho mais comum é usar check, webcheck e guicheck.
code
Bash
# Navegue até a pasta do projeto que você quer analisar
cd C:\Caminho\Para\MeuProjeto

# Execute a análise de backend (Python)
doxoade check

# Execute a análise de frontend, ignorando pastas de backup
doxoade webcheck . --ignore backups --ignore old_versions
Omitir o caminho (ou usar .) analisa o diretório atual.
A opção --ignore pode ser usada várias vezes. venv, build, e dist são ignorados por padrão.
Executando Scripts com Segurança
Para executar um script garantindo que ele use o venv do seu projeto, use o comando run.
code
Bash
# Navegue até a pasta do projeto
cd C:\Caminho\Para\MeuProjeto

# Execute o script principal
doxoade run main.py

# Execute um script com argumentos
doxoade run process_data.py --input dados.csv --force```
O `doxoade run` detecta automaticamente o `venv` do projeto e o utiliza, prevenindo erros de `ModuleNotFoundError`. Se o script falhar, ele apresentará um diagnóstico com possíveis causas baseadas em problemas conhecidos.

---
*Este projeto é uma ferramenta interna de P&D para encapsular e automatizar o conhecimento adquirido.*
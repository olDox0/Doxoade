# Doxoade Internals - Vol. 13: Estratégias de Teste e Mocks de Sonda


## 1. O Desafio de Testar Orquestradores
Comandos como `check.py` e `save.py` são orquestradores que invocam processos externos. Testar esses comandos sem Mocks resultaria em testes lentos e dependentes da instalação do Git/Python no ambiente.


## 2. Padrão de Mocking de Sondas
Utilizamos o `unittest.mock.patch` para interceptar a função `_run_probe`. Isso nos permite:
- Simular saídas de texto (Pyflakes) para validar o Regex de captura.
- Simular saídas JSON (Hunter/Style) para validar o parsing.
- Simular códigos de erro (Return Code != 0) para testar o Fail-Fast de sintaxe.


## 3. Validação de Cache Stateless
Os testes de cache utilizam a fixture `tmp_path` do Pytest, garantindo que o `check_cache.json` de teste nunca sobrescreva o cache real do desenvolvedor durante a execução da suíte.


## 4. Entendendo Alertas de Exceção no Deepcheck
O Deepcheck atua sob a ótica de **Análise Estática de Fluxo**. 

Quando o sistema aponta `[!] Levanta Exceção`, ele está alertando o engenheiro de que o "Caminho Feliz" (Happy Path) da função pode ser interrompido. 
- **Em utilitários:** Muitas vezes é desejado (fail-fast).
- **Em lógica de negócio:** Deve ser verificado se o chamador está preparado para tratar esse erro.
Este alerta não deve ser visto como um "erro a ser removido", mas como um "comportamento a ser documentado/validado".


## 5. Calibração de Falsos Positivos Analíticos
Na transição para o v69, percebeu-se que a análise de fluxo (Deepcheck) era excessivamente pessimista em relação a exceções.

**Mudança de Paradigma:** O sistema agora reconhece que um `raise` disparado nos primeiros 15% do corpo de uma função é um **mecanismo de defesa** e não uma falha de design. Isso alinha a ferramenta com o padrão de "Fail-Fast" exigido em sistemas de missão crítica.


## 8. Arquitetura de Filtros sem Contexto
O Doxoade v69 utiliza o padrão **Lazy File Inspection** para filtros. Em vez de manter o conteúdo de todos os arquivos em memória durante o `check`, o `check_filters` só abre o arquivo no momento final do relatório.

**Benefícios:**
- **Economia de RAM:** Em projetos de 1000+ arquivos, a economia é de aproximadamente 40MB.
- **Priorização de Fachada:** Arquivos como `shared_tools.py` são tratados como agregadores de API, onde avisos de "imported but unused" são silenciados por design para facilitar o desenvolvimento modular.
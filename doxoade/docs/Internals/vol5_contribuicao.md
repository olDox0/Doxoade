# Doxoade Internals - Vol. 5: Guia de Contribuição e Manutenção

**Versão do Documento:** 1.0 (Gênese V14)
**Data:** 01/12/2025
**Público Alvo:** Engenheiros mantenedores do Doxoade.

## 1. Configurando o Ambiente de Desenvolvimento

O Doxoade deve ser desenvolvido dentro de si mesmo (Bootstrapping).

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/olDox0/Doxoade.git
    cd doxoade
    ```
2.  **Instalação em Modo Editável:**
    Isso é crucial. Permite que alterações no código reflitam imediatamente no comando `doxoade` sem reinstalar.
    ```bash
    # Windows
    python install.py
    # Linux/Termux
    bash install.sh
    ```
3.  **Validação Inicial:**
    Execute `doxoade self-test` para garantir que o núcleo está operante.

---

## 2. Anatomia de um Novo Comando

Para adicionar uma nova funcionalidade (ex: `doxoade novocomando`), siga o padrão de Plugin.

### Passo 1: Criar o arquivo do comando
Crie `doxoade/commands/novocomando.py`:

```python
import click
from colorama import Fore
from ..shared_tools import ExecutionLogger

@click.command('novocomando')
@click.pass_context
@click.argument('alvo', default='.')
def novocomando(ctx, alvo):
    """Descrição que aparecerá no --help."""
    
    # Sempre use o ExecutionLogger para telemetria e consistência
    with ExecutionLogger('novocomando', alvo, ctx.params) as logger:
        click.echo(Fore.CYAN + f"Executando novocomando em {alvo}...")
        
        try:
            # Lógica aqui
            click.echo(Fore.GREEN + "[OK] Sucesso.")
        except Exception as e:
            logger.add_finding('CRITICAL', f"Falha: {e}")
            # Não use exit() direto se puder evitar, deixe o logger finalizar
```

### Passo 2: Registrar no Núcleo (`cli.py`)
O `doxoade` não descobre comandos magicamente (por design, para evitar importação circular e lentidão). Você deve registrá-lo explicitamente.

Edite `doxoade/cli.py`:

```python
# 1. Importe o módulo
from doxoade.commands.novocomando import novocomando

# ... (no final do arquivo, bloco de registro) ...

# 2. Adicione ao grupo CLI
cli.add_command(novocomando)
```

---

## 3. O Ciclo de Desenvolvimento Seguro

Nunca faça commits manuais (`git commit`). O Doxoade possui um workflow assistido que garante a qualidade e o aprendizado do sistema.

### Workflow Diário:
1.  **Codificar:** Faça suas alterações.
2.  **Verificar:** Rode `doxoade check .` (ou `doxoade check . --clones` se adicionou muita lógica).
3.  **Salvar:** Use o comando `save`.
    ```bash
    doxoade save "Categoria : Versão : Descrição do que mudou"
    ```
    *   O `save` roda o `check` automaticamente.
    *   Se você corrigiu bugs, o `save` detectará a diferença e alimentará o Motor Gênese (`learning.py`).
4.  **Sincronizar:** Envie para o GitHub.
    ```bash
    doxoade sync
    ```

---

## 4. Estratégia de Testes

Como o Doxoade é uma ferramenta de infraestrutura, testes unitários são importantes, mas **testes de comportamento** são vitais.

### A. Testes de Regressão (Cânone)
Localizados em `regression_tests/`.
Eles garantem que a saída JSON do `check` não mudou para projetos conhecidos.
*   **Rodar:** `doxoade regression-test`

### B. Testes de Integração via Maestro
Crie scripts `.dox` na pasta `tests/` para simular o uso real.
*   Exemplo: Criar um arquivo Python quebrado, rodar o `check`, verificar se o erro aparece, rodar o `--fix` e verificar se o erro sumiu.

---

## 5. Gerenciamento de Versão (Release)

Quando o software atinge um marco estável (como a Gênese V14):

1.  **Atualize a Versão:** Edite `doxoade/_version.py`.
2.  **Migração de DB:** Se mudou a estrutura do banco, adicione a lógica em `doxoade/database.py` (função `init_db`).
3.  **Release:**
    ```bash
    doxoade release "v60.50" "Lançamento da Gênese V14 com DRY Check"
    ```
    Isso cria uma tag Git e sobe para o repositório remoto.

---

## 6. Diretrizes de Código (Style Guide)

*   **Imports:** Sempre use caminhos relativos para módulos internos (`from ..shared_tools import ...`) para manter a portabilidade.
*   **IO Seguro:** Nunca assuma UTF-8 no Windows. Use `encoding='utf-8', errors='ignore'` ao abrir arquivos de usuários desconhecidos.
*   **Fail Fast, Fail Loud:** Se um comando depende de uma ferramenta externa (ex: `git`), verifique a existência dela no início e falhe com uma mensagem clara se não estiver presente.
*   **Inteligência:** Se encontrar um padrão de erro novo, considere se ele pode ser generalizado em um template para o `learning.py`.

---
---

# 📜 Protocolo Modern Power of Ten (MPoT) - Doxoade
**Versão:** v71.0 (Consolidação Final)  
**Data da última atualização:** 31/12/2025  
**Status:** Obrigatório para todo o Core e Ferramentas.

---

## 🏗️ As 10 Regras Clássicas (Adaptadas)

### 1. Fluxo de Controle Simples
*   **Regra:** Proibido `goto` ou recursão não controlada. Exceções (`try/except`) devem seguir políticas estritas.
*   **Porquê:** Facilita a análise de cobertura e o raciocínio lógico.
*   **Controle:** Revisão de complexidade ciclomática no `doxoade check`.

### 2. Loops com Limites Prováveis
*   **Regra:** Todo loop deve ter um limite superior (`loop bound`) ou um timeout/watchdog em runtime.
*   **Porquê:** Evita travamentos e garante o *liveness* do sistema.
*   **Controle:** Uso de sensores de tempo em testes de stress.

### 3. Alocação Controlada (Memory Pools)
*   **Regra:** Proibida alocação dinâmica incontrolada após a inicialização. Use *arenas* ou limites rígidos.
*   **Porquê:** Previne fragmentação e falhas de memória (OOM).

### 4. Funções Curtas e Coesas
*   **Regra:** Limite de **60 linhas** por função. Se exceder, modularize em subfunções descritivas.
*   **Porquê:** Melhora a manutenibilidade e facilita testes unitários.
*   **Controle:** Bloqueio no CI para funções "monstruosas".

### 5. Asserções e Contratos
*   **Regra:** Média de 2 asserções por função. Devem validar invariantes e pré/pós-condições.
*   **Porquê:** Detecta falhas de lógica no momento exato em que ocorrem.

### 6. Escopo Mínimo e Imutabilidade
*   **Regra:** Declare variáveis no menor escopo possível. Prefira objetos imutáveis.
*   **Porquê:** Reduz efeitos colaterais e bugs de estado global.

### 7. Tratamento de Erros Obrigatório
*   **Regra:** Todo retorno de API/Função que possa falhar **deve** ser verificado. Proibido ignorar resultados.
*   **Porquê:** Impede comportamentos indefinidos e erros silenciosos.

### 8. Metaprogramação Restrita
*   **Regra:** Limite macros e metaprogramação ao estritamente necessário. Prefira constructs seguros da linguagem.
*   **Porquê:** Facilita a análise estática e evita código "mágico" difícil de depurar.

### 9. Ponteiros e Referências Seguros
*   **Regra:** Use *smart pointers* ou modelos de *ownership* (propriedade). No Python, evite manipulação direta de referências complexas sem justificativa.

### 10. Compilação e Análise Contínua
*   **Regra:** Build limpo sem warnings. Uso obrigatório de múltiplos analisadores estáticos e sanitizers no CI.

---

## 🚀 Extensões Modernas (Doxoade Specials)

### 11. Concorrência Explicitamente Segura
*   Uso de tipos thread-safe e locks de escopo mínimo. Priorize o modelo de atores ou canais.

### 12. Telemetria de Baixo Custo (Chronos)
*   Instrumentação obrigatória em código crítico, garantindo que o monitoramento não altere o comportamento do sistema.

### 13. Segurança da Supply Chain
*   Fixação de versões (*pinning*), verificação de assinaturas e uso de SBOM para todas as dependências externas.

### 14. Testes de Propriedade e Fuzzing
*   Uso de `property-based tests` para interfaces externas e parsers de arquivos.

### 15. Modos Degradados de Falha
*   O sistema deve saber como falhar com segurança (*fail-safe*), retornando a um estado estável conhecido.

### 16. Política Anti-Monólito
*   **Python:** Proibido arquivos únicos com mais de **500 linhas**. Funções complexas devem ser distribuídas.

### 17. Princípio de Responsabilidade Independente
*   Os módulos devem ser o mais independentes possível. Se um componente quebrar, o sistema de diagnóstico deve permanecer funcional.

### 18. Soberania da Biblioteca Padrão
*   Priorize a `stdlib`. Use bibliotecas externas apenas se a padrão for comprovadamente insuficiente. Isso garante leveza e portabilidade (especialmente no Termux).

---

## 🐍 Padrões Específicos para Python (PEP8+)

1.  **POO:** Use classes para agrupar estados e comportamentos relacionados.
2.  **Naming:** `snake_case` para funções/variáveis, `CamelCase` para classes, `CAPS_LOCK` para constantes.
3.  **Docstrings:** Obrigatório em todas as funções públicas explicando parâmetros e retornos.
4.  **Type Hinting:** Uso rigoroso de dicas de tipo para aumentar a previsibilidade do código.
5.  **Tratamento de Exceções:** Especifique sempre a exceção (ex: `except ValueError:`). **Nunca use `except:` puro.**

---

## 🏆 Exemplo de Ouro (Módulo Cânone)

```python
# -*- coding: utf-8 -*-
"""
Exemplo de conformidade MPoT: Gerenciamento de Usuários.
"""

# Constante Global (Imutável)
PADRAO_DATA = "%Y-%d-%m"

class Usuario:
    """Representa um usuário com validação rigorosa."""
    
    def __init__(self, nome: str, email: str, idade: int):
        # Regra 5: Asserções de Contrato
        if not nome or idade < 0:
            raise ValueError("Dados de entrada inválidos para Usuario.")
            
        self.nome = nome.strip().title()
        self.email = email.lower()
        self.idade = idade

    def saudacao(self) -> str:
        """Retorna saudação seguindo Regra 4 (Curta/Coesa)."""
        return f"Olá, {self.nome}! Acesso autorizado."

def criar_usuario_do_terminal() -> Usuario:
    """Fábrica de usuários com tratamento de erro (Regra 7)."""
    try:
        nome = input("Nome: ")
        idade = int(input("Idade: "))
        return Usuario(nome, "default@mail.com", idade)
    except (ValueError, EOFError) as e:
        # Regra 15: Modo Degradado / Fallback
        print(f"[ERRO] Falha na criação: {e}")
        return None

if __name__ == "__main__":
    # Ponto de entrada seguindo Regra 10
    user = criar_usuario_do_terminal()
    if user:
        print(user.saudacao())
```

---
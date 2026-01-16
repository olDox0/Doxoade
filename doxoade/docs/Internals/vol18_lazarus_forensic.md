# Doxoade Internals - Vol. 18: Protocolo Lázaro e Interface Forense

**Status:** v41.7 Gold Edition
**Foco:** Recuperação Pós-Crash Fatal

## 1. Dual Forensic Report
Se o Doxoade crashar, o Lázaro ativa uma visualização de alto contraste:
- **BROKEN (Red):** Exibe a linha do crash no arquivo local.
- **STABLE (Green):** Exibe a mesma posição no último commit funcional (HEAD).

## 2. Orquestração de Resgate
O sistema detecta e prioriza o melhor editor disponível:
- **Windows:** Busca exaustiva de Notepad++ (Caminhos fixos + PATH).
- **Termux/Linux:** Invocação direta de micro, nano ou vim com retorno de controle ao terminal.

## 3. Autópsia Digital
Antes da reversão, o sistema grava o crash na tabela `solutions` como um "Incidente Negativo", permitindo que a Gênese aprenda quais padrões de alteração causaram falhas fatais.
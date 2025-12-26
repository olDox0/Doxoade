# Guia de Onboarding - Doxoade Developer

Bem-vindo à equipe de engenharia do Doxoade. Este projeto não é apenas uma CLI, é um "Engenheiro Sênior Automatizado".

## 🚀 Primeiros Passos

1.  **Instalação do Ambiente:**
    Não use o Python global. O Doxoade possui um sistema de auto-bootstrapping.
    Execute: `python install.py` (Isso cria o venv e instala dependências).

2.  **Verifique a Saúde:**
    Execute: `doxoade diagnose`
    *   Certifique-se de que o VENV está **ATIVO**.
    *   Certifique-se de que a Integridade do Núcleo está **OK**.

3.  **Fluxo de Trabalho Diário (The Loop):**
    *   **Codar:** Faça suas alterações.
    *   **Verificar:** `doxoade check` (Sintaxe, Estilo, Segurança).
    *   **Testar:** `doxoade regression-test` (Garante que você não quebrou nada que funcionava).
    *   **Salvar:** `doxoade save "Mensagem"` (Nunca use `git commit` direto).

## ⚠️ Regras de Ouro
1.  **Nunca use `shell=True`** em subprocessos (Protocolo Aegis).
2.  **Nunca use `pickle`** para persistência de dados (Use JSON).
3.  **Não comite código com `except:` genérico** (Use `except Exception:`).
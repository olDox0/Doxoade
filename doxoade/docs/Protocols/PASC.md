# Políticas de Atualização Segura de Códigos (PASC)
**Atualização:** 2026.01.25

## 1. Refatoração Conservadora (ConRef)
Planejamento prévio é obrigatório. Refatore apenas a funcionalidade complexa avaliando o ecossistema com `deepcheck` e `impact-analysis`.
* **1.1. Resgate (Recov):** Investigue e recupere rapidamente em caso de regressões.
* **1.2. Support_Utils (SuUt):** Use arquivos de suporte (`_utils.py`, `_io.py`) para desafogar arquivos principais.
* **1.3. Safe_Weighting (SafeW):** Limite de 500 linhas, 140 caracteres por linha, máximo de 20KB por arquivo.
* **1.4. Planejamento (P&M):** Use marcadores `TODO` visíveis na IDE/Linter para não esquecer tarefas.

## 2. Anti-Regressividade (ARegre)
Nenhuma funcionalidade deve ser removida sob justificativa de "simplicidade" ou capricho.

## 3. Progressividade (Prgr)
Soluções complexas não devem quebrar o fluxo. Se falhar, deve ser um *safe-fail* elegante.
* **3.1. DevOpsPol:** Desenvolver ferramentas de aceleração.
* **3.2. ContPol:** Manter a documentação (`docs/`) sincronizada e obrigatória.

## 4. Comunicação (Comm)
Instruções de código devem ser claras, breves e com apontamentos exatos do que modificar e onde.

## 5. Parceiros e Contribuidores (P&C)
Tolere falhas humanas (cansaço, falta de tempo). Use a brevidade para instruções gerais e detalhamento apenas para zonas de risco.

## 6. Codificação (CodS)
Siga o MPoT e protocolos internos (`docs/library/patterns.json`).
* **6.1. Verbose-import:** Em imports lentos (>100ms), importe explicitamente para poupar RAM.
* **6.3. UTF8:** Padrão universal. Evite emojis no core para prevenir *unicode-plague*.
* **6.4. Well-Processing:** Respeite a CPU do usuário (Evite picos em 100% sem justificativa).
* **6.5. Anti-Kin:** Centralize funções semelhantes na pasta `tools/`.
* **6.6. Import-localized:** Importe dentro da função se o recurso for de uso exclusivo dela.
* **6.7. Lazyload:** CLIs devem carregar módulos apenas sob demanda.
* **6.8. Exibição:** Prefira recursos nativos do Python ou centralize num `tools/display.py` para evitar peso.

## 8. Políticas Sistemáticas Padronizadas (SSP)
* **8.1. DiagPol:** Código deve conter mecanismos de autodiagnóstico.
* **8.2. SysPol:** Módulos com mais de 3 arquivos (`_utils`, `_io`) formam um "sistema" padronizado.
* **8.4. ArchPlan:** Arquitetura deve ser definida (em Docs) *antes* do código.
* **8.5. RepDiv:** Cada módulo deve ter apenas uma responsabilidade (Single Responsibility).
* **8.6. DiDe (Dependência):** Camadas externas não devem ditar regras para o núcleo.
* **8.9. FCP (Fail-Control):** O núcleo falha rápido; as bordas tratam a falha e sobrevivem.
* **8.17. PArch (Arquitetura Protegida):** Bloqueie usos incorretos ou acoplamentos ilegais.
# olDox222 Software Law (OSL)
*ex MODERN POWER OF TEN*
**Atualizado:** 2026.02.06

## Regras Atualizadas — OSL Powers

**1. Fluxo de controle simples e observável**
* **Regra:** Evite `goto`, `setjmp/longjmp` e recursão não controlada. Permita exceções estruturadas apenas com políticas bem definidas. Prefira fluxos controlados por estados.
* **Porquê:** Simplifica raciocínio e análise de cobertura.

**2. Loops com limites prováveis ou timeouts verificáveis**
* **Regra:** Todos os loops devem ter um limite superior comprovável (prova estática, contrato ou watchdog).
* **Porquê:** Evita travamentos silenciosos.

**3. Alocação controlada e segura**
* **Regra:** Proíba alocação dinâmica incontrolada em código crítico. Use `memory pools`, arenas ou limite alocações ao startup.

**4. Funções curtas e coesas; modularize legibilidade**
* **Regra:** Mantenha funções pequenas (~60 linhas). Divida em subfunções com nomes descritivos.

**5. Asserções e contratos formais**
* **5.1.** Use asserções com densidade mínima (ex: 2 por função), focando em invariantes.
* **5.2.** Funções internas de I/O devem validar a integridade da entrada para evitar efeito cascata (Protocolo Lázaro).
* **5.3.** Exceções devem ser informativas e centralizadas.

**6. Escopo mínimo e imutabilidade**
* **Regra:** Declare dados no menor escopo prático. Prefira imutabilidade.

**7. Tratamento de erros obrigatório**
* **Regra:** Todo retorno que possa falhar deve ser verificado.

**8. Macros e metaprogramação restrita**
* **Regra:** Limite macros a trivialidades. Prefira constructs seguros (inline, generics).

**9. Ponteiros e referências seguros**
* **Regra:** Restrinja ponteiros brutos a um nível de indireção.

**10. Compilação rigorosa e CI**
* **Regra:** Warnings máximos ativados. O pipeline deve falhar no menor aviso.

**11. Concorrência explicitamente segura**
* **Regra:** Declare invariantes de thread-safety. Use locks de escopo mínimo.

**12. Observabilidade e telemetria**
* **Regra:** Instrumente o código crítico (logs, métricas) sem causar efeitos colaterais.

**13. Segurança da Cadeia de Fornecimento**
* **Regra:** Pin de versões e uso de SBOM.

**14. Testes de propriedade e fuzzing**
* **Regra:** Inclua testes além de testes unitários para interfaces externas.

**15. Política de tolerância a falhas**
* **Regra:** Defina modos degradados seguros (fail-stop mensurável).

**16. Política Anti-Monolito**
* **Regra:** É proibido scripts com mais de 500 linhas (Python) ou excesso de responsabilidade.

**17. Princípio de Responsabilidade**
* **Regra:** O projeto não pode quebrar por inteiro se uma parte falhar. Recomenda-se sistemas de diagnóstico independentes.

**18. Bibliotecas Padrão**
* **Regra:** Priorize a biblioteca padrão da linguagem para garantir portabilidade.

**19. Quarentena de Testes (Test-Lock)**
* **19.1. Isolamento:** O diretório `tests/` é zona de quarentena. Não deve ser importado por produção.
* **19.2. Bloqueio (Run-Block):** `doxoade run` deve recusar scripts de teste sem a flag `--test-mode`.
* **19.3. Assinatura:** Testes sensíveis devem exigir `DOXOADE_AUTHORIZED_RUN`.

**20. Anti-Apocalypse**
* **20.1. Continuity:** SALVAR sempre após atualizações estáveis.
* **20.2. Damage Control:** Em caso de perda, listar material e recuperar via backup IDE/Git.
* **20.3. Recovery:** Recuperação cautelosa, priorizando sistemas centrais.
* **20.4. Backup:** Contínuo e terceirizado.
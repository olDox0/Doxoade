# Doxoade Internals - Vol. 11: Otimização Mobile e Robustez Nátiva

**Versão do Documento:** 1.0 (v69 Alfa)
**Status:** Vigente
**Foco:** Eficiência de Recursos e Segurança de Bytecode

## 1. Filosofia "No-Giant-Libs"
A partir da versão v69, o Doxoade adota a postura de evitar bibliotecas de infraestrutura pesada (`pandas`, `scikit-learn`, `lxml`) em comandos de rotina. 

### Benefícios:
1. **Startup Instantâneo:** Redução do tempo de importação de 1.2s para 0.3s.
2. **Portabilidade Android:** Facilita a instalação no Termux sem necessidade de compiladores Fortran/C++ pesados.
3. **Auditabilidade:** Menos código de terceiros significa menor superfície de ataque (SCA).

## 2. Implementação de Contratos Seguros
O uso de `assert` é desencorajado em favor de exceções explícitas. Embora o MPoT (Modern Power of Ten) defenda asserções, a natureza do interpretador Python exige `if/raise` para que a checagem seja persistente em bytecode otimizado.

### Exemplo de Ouro (Cânone):
```python
# Ruim (Pode ser removido pelo Python -O)
assert cursor is not None

# Bom (Permanente e Seguro)
if cursor is None:
    raise ValueError("Mensagem descritiva")```


# Auditoria Web e Compatibilidade Termux

## 1. O Fim da Dependência LXML
Historicamente, o `webcheck` utilizava o parser `lxml` por sua performance. No entanto, o `lxml` exige compilação nativa de bibliotecas C, o que é um ponto frequente de falha no Termux/Android. 

**Decisão de Engenharia:** Migramos para o `html.parser` nativo do Python dentro do BeautifulSoup. Embora ligeiramente mais lento em arquivos massivos, ele é 100% portátil e resiliente.

## 2. Capacidades NiceGUI (Web-in-Python)
O `webcheck` agora identifica riscos de segurança em NiceGUI:
- **Sanitize Check:** Alerta se `ui.html()` for chamado sem o parâmetro `sanitize`, prevenindo injeções de script acidentais.
- **Style Mocking:** Strings de CSS fragmentadas (ex: `.style('color: red')`) são encapsuladas em seletores falsos (`.mock_selector { ... }`) para que o parser CSS consiga validar a sintaxe sem erros de estrutura.

## 3. Interceptação de Logs de Terceiros
Bibliotecas de parsing (como `cssutils`) frequentemente utilizam o módulo `logging` em vez de levantar exceções para erros de sintaxe (abordagem *graceful degradation*). 

Para garantir a precisão do `doxoade check`, implementamos o padrão **Log Interceptor**:
1. Criamos um `logging.Handler` efêmero.
2. Anexamos ao logger da biblioteca alvo.
3. Convertemos registros de nível `ERROR` em objetos `finding` do Doxoade.
4. Removemos o handler no bloco `finally` para manter a neutralidade do ambiente.

## 4. Estudo de Caso: Auditoria de CSS Silencioso
Durante a refatoração do `webcheck`, identificamos que parsers externos (como `cssutils`) falham silenciosamente em prol da continuidade da renderização.

**Solução Implementada:** O padrão **Log Interceptor** foi adotado como requisito para qualquer integração de biblioteca de terceiros que não utilize exceções estruturadas. Isso garante que o Doxoade mantenha sua promessa de "Falha Ruidosa" (Fail Loudly), nunca ignorando um erro de sintaxe do usuário.

## 5. Refatoração Modular: O Padrão Expert-Split
Durante a otimização do comando `style`, implementamos o padrão **Expert-Split** para cumprir a regra MPoT-4 (Funções < 60 linhas).

**Mudança:** O comando único foi decomposto em:
1. `style`: Coordenador de interface.
2. `_execute_probe`: Especialista em execução isolada.
3. `_render_findings`: Especialista em UI (Rich).

**Resultado:** Redução de complexidade cognitiva e facilidade de manutenção de contratos individuais.

## 6. Heurística de Leitura vs Detecção Estatística
Para ferramentas CLI de alta performance, a detecção estatística de encoding (Chardet) deve ser evitada. O Doxoade utiliza agora a **Heurística de Fallback Segura**:
1. Tenta-se UTF-8 (Padrão Global).
2. Tenta-se Latin-1 (Fallback para sistemas legados que permite leitura sem erro de byte).
3. Arquivos > 1MB sem match são ignorados para preservar a integridade da memória.

## 7. Eliminação de Parâmetros Inertes (Dead Params)
Através do uso do `doxoade deepcheck`, identificamos que o comando `save` passava o objeto `logger` para funções de aprendizado que já possuíam sua própria lógica de persistência via SQLite.

**Ação:** A assinatura de `_learn_solutions_from_commit` foi simplificada. Isso reduz a sobrecarga de memória (overhead) e evita o acoplamento desnecessário entre o Logger de execução e o Motor Gênese.

## 8. Arquitetura de Filtros sem Contexto
O Doxoade v69 utiliza o padrão **Lazy File Inspection** para filtros. Em vez de manter o conteúdo de todos os arquivos em memória durante o `check`, o `check_filters` só abre o arquivo no momento final do relatório.

**Benefícios:**
- **Economia de RAM:** Em projetos de 1000+ arquivos, a economia é de aproximadamente 40MB.
- **Priorização de Fachada:** Arquivos como `shared_tools.py` são tratados como agregadores de API, onde avisos de "imported but unused" são silenciados por design para facilitar o desenvolvimento modular.
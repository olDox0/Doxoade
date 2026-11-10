
# Experimento 02 — Degrau 3 (fuzz por truncamento)

## Hipótese
O parser não crasha em binários truncados. Retorna erro estruturado
(exit 1) ou JSON válido (exit 0) em qualquer truncamento.

## Método
- Script: `fuzz_truncate.py` (Python 3.12)
- Pontos: 19 estratégicos (lidos do PE) + 50 aleatórios = 69 por binário
- Classificação: OK (exit 0 + JSON válido), ERR (exit 1 + stderr), CRASH (resto)

## Resultado

| Binário | Tamanho | OK | ERR | CRASH |
|---|---|---|---|---|
| degrau0_O0_g.exe | 74.526 | 54 | 15 | 0 |
| hostname.exe | 14.848 | 50 | 19 | 0 |
| where32.exe | 33.280 | 54 | 15 | 0 |

## Análise
- ERR: truncamentos antes/no meio da Section Table → erro estruturado.
- OK: truncamentos após a Section Table → JSON válido (imports podem vir vazios).
- CRASH: zero em todos os binários.

## Limite conhecido (não é bug)
Quando a Import Directory está truncada, o parser retorna
`"imports": []` silenciosamente. O JSON é válido, mas o usuário
pode confundir "sem imports" com "imports truncados".
Melhoria futura: campo `"imports_complete": bool` ou erro
explícito se `.idata` existir mas estiver truncada.

## Próximo passo
Fase 3 — desmontador (subconjunto de x86-64) OU fuzz por corrupção
(flip de bytes em campos estratégicos).

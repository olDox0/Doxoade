# Experimento 05 — Fase 5a (functions + call graph)

## Hipótese
Consigo identificar funções e construir call graph em binários
stripped (sem símbolos), usando apenas call targets e entry point.

## Alvos testados
- degrau0_O0_g.exe (PE32+, com símbolos, próprio)
- hostname.exe (PE32+, stripped, Win10)
- where32.exe (PE32, stripped, Win10)

## Resultado
| Alvo | Funções | Blocos | Externas | Observação |
|---|---|---|---|---|
| degrau0 (native) | 150 | 1648 | 32 | com símbolos |
| degrau0 (capstone) | 150 | ~1648 | 32 | equivalente |
| hostname.exe | ? | ? | ? | stripped |
| where32.exe | ? | ? | ? | stripped, PE32 |

## Limites encontrados
- Nomes `.text` (filtrados por section_name match)
- Chamadas via IAT contam como externas
- Diferenças de 1 bloco entre native e capstone (prefixos)

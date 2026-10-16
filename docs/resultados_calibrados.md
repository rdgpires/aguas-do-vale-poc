# Resultados calibrados

Gerado por `python -m scripts.registrar_resultados` em 15/10/2026. Base: 499.753 ligações, semente 42, referência 2026-08, 1008 visitas por grupo (21 dias × 6 equipes × 8).

## Taxa de acerto das visitas

| Estratégia | Visitas | Irregularidades | Acerto | Volume recuperado por visita (m³/mês) |
|---|---|---|---|---|
| Regra antiga | 1008 | 195 | **19.3%** | 3.83 |
| PoC v1 (queda de consumo) | 1008 | 125 | **12.4%** | 16.38 |
| PoC v2 (queda inexplicada) | 1008 | 228 | **22.6%** | 22.29 |

Linha de base do discovery: 20.0% (1 em 5).
v2 contra a regra: +3.3 pp; v1 contra a regra: -6.9 pp.

## Para onde o modelo mandou as equipes (visitas sem irregularidade, por causa)

| Estratégia | Imóvel vazio | Troca de hidrômetro | Sazonalidade | Mudança de uso | Sem causa identificada | Sem acesso |
|---|---|---|---|---|---|---|
| Regra antiga | 577 | 14 | 0 | 103 | 0 | 119 |
| PoC v1 | 243 | 112 | 57 | 67 | 284 | 120 |
| PoC v2 | 232 | 89 | 9 | 50 | 292 | 108 |

## Valor (conversão do ganho da v2 contra a regra antiga)

- Diferença de volume por visita: +18.46 m³/mês.
- Visitas da empresa por mês: 2016.
- **Uma fila mensal** da v2: 0.344 pp de perda aparente ≈ R$ 1.031.602/ano.
- **Doze filas mensais** (efeito acumulado ao fim do ano): 4.126 pp ≈ R$ 12.379.224/ano.
- Premissa do caso: 1 pp de perda aparente ≈ R$ 3.000.000/ano.

> Estimativa, não promessa: assume que a perda recuperada persiste, que não há reincidência e que o volume por visita se mantém ao repetir a fila todo mês.

## Concordância dos rótulos

Rotulador: **offline** (regras-v1), amostra revisada de 500 anotações.

| Campo | Concordância |
|---|---|
| irregularidade | 96.4% |
| tipo | 96.2% |
| motivo_nao_acesso | 96.8% |
| tipo (apenas entre as irregulares) | 74.0% |

O modo offline é um rotulador por regras: o LLM real deve cobrir melhor a gíria de campo (`hd morto`, `puxadinho no ramal`).

## Maiores quedas de consumo

Entre as 4383 maiores quedas (1% do total com leitura real), **100.0%** não são irregularidade (imóvel vazio, troca, sazonalidade, uso). Só 67.5% delas têm a explicação registrada nos sistemas, e é essa lacuna que a v2 explora até onde o dado permite.

## Condições de calibração

- [x] regra antiga ≈ 20% (entre 17% e 23%)
- [x] PoC v1 abaixo da regra antiga
- [x] PoC v2 acima da regra, ganho modesto (1 a 10 pp)
- [x] maiores quedas concentradas em casos explicados (>= 90% das 1% maiores)

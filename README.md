# Águas do Vale · PoC de priorização de visitas

Prova de conceito do curso *Forward Deployed Engineer: da descoberta à entrega de valor*. Prioriza a fila mensal de visitas de campo de uma companhia de saneamento fictícia para recuperar **perda aparente** de água (hidrômetro parado, ligação clandestina, cadastro errado).

**Prioridade de cada ligação = chance de irregularidade × volume recuperável.**
A virada do curso: a formulação **v1** ("queda de consumo") perde para a regra antiga; a **v2** ("queda de consumo *inexplicada*", feature `queda_explicada`) ganha. Escolhe-se em `config.yaml` (`formulacao: v1 | v2`), sem mudar código.

## Rodar com um comando

```bash
python -m venv .venv && .venv\Scripts\activate && pip install -e .
python -m scripts.gerar_base --escala 50000 --semente 42 && python -m src.pipeline --mes 2026-08
```

```text
[extração]  49.974 ligações lidas
[rotulagem] 6.311 anotações rotuladas
[modelo]    49.974 ligações pontuadas
[fila]      192 visitas no mês (12 equipes × 8 × 2 dias)
```

Com `--escala 500000` (padrão) o resumo é o do caso: 2.016 visitas (12 × 8 × 21). Em base reduzida a capacidade cai na mesma proporção, para manter a seletividade. Roda em ~40 s para 500 mil ligações; sem chave de API (modo offline).

Outros comandos:

```bash
python -m src.pipeline --mes 2026-08 --formulacao v1 --etapa modelo   # uma etapa
python -m src.evaluate                                                # concordância dos rótulos
python -m src.experiment --mes 2026-08 --formulacao v1                # A/B simulado
python -m scripts.registrar_resultados                                # A/B v1 e v2 + docs/resultados_calibrados.md
streamlit run app/painel.py                                           # painel de apresentação
```

> Rode sempre da raiz do repositório: `src/queue.py` é `src.queue` e não colide com a `queue` da stdlib.

## De onde vêm os dados

Três sistemas que não conversam, lidos **somente leitura** por adapters (hoje, arquivos Parquet gerados por `scripts/gerar_base.py`, com os problemas reais: setor ausente, OS duplicada, matrícula sem padrão, texto livre, leitura estimada, dados pessoais):

1. **Sistema comercial:** cadastro, consumo mensal, trocas de hidrômetro, mudança de categoria.
2. **Telemetria:** vazão por setor (contexto, nunca dado da ligação).
3. **App de campo:** ordens de serviço com matrícula digitada à mão e resultado em texto livre.

A "verdade oculta" (`data/oculto/`) só é lida pelo simulador do A/B.

## O que cada etapa entrega

| Etapa | Arquivo | Entrega |
|---|---|---|
| Extração | `src/extract.py` | Dados validados por contrato; matrícula canônica de 7 dígitos; duplicidade removida; PII mascarada; pendências |
| Rotulagem | `src/label_llm.py` | `rotulo_visita` (irregularidade, tipo, motivo de não acesso), com cache, retentativa e custo |
| Features | `src/features.py` | `features_ligacao` e as quatro flags de explicação (`queda_explicada`) |
| Modelo | `src/model.py` | Regressão logística, coeficientes em relatório, `score_ligacao` |
| Fila | `src/queue.py` | CSV por equipe por dia + consolidado, respeitando as restrições |
| A/B | `src/experiment.py` | 6 equipes × 6 por simulação; acerto, volume, pontos e reais |

## Avaliar

`python -m src.evaluate` compara o rotulador com 500 anotações revisadas e reporta concordância por campo. `python -m scripts.registrar_resultados` roda o A/B e escreve `docs/resultados_calibrados.md`.

## Onde mudar capacidade e regras

Tudo em `config.yaml`:

```yaml
visitas_por_equipe: 8
limite_condominios_por_equipe: 2
regioes_com_dupla:
  - norte        # acrescente jardim_alto e veja a fila mudar
```

Equipes, fontes, provedor de LLM, janelas de explicação e valor do ponto percentual também estão lá.

## Estrutura

```text
aguas-do-vale-poc/
├── config.yaml            capacidade, regras, fontes, LLM, formulação
├── data/                  base sintética (bruta), lake Parquet e saídas   (gerado)
├── eval/                  amostra revisada à mão (gabarito dos rótulos)
├── prompts/               prompt de rotulagem versionado
├── docs/                  arquitetura, contratos, decisões, riscos, handoff, resultados
├── scripts/               gerar_base, gerar_docs_contratos, registrar_resultados
├── app/                   painel Streamlit (camada fina): painel.py + paginas/
└── src/
    ├── contracts/         contratos de dados (base, domínios, registros)
    ├── sources/           interfaces + adapters de fonte + registro
    ├── storage/           camada de armazenamento (Parquet local)
    ├── llm/               ClienteLLM, modo offline, mascaramento
    ├── comum.py           contexto de execução, pendências, run_id
    ├── extract.py         extração, normalização e validação
    ├── label_llm.py       rotulagem
    ├── features.py        features e flags de explicação
    ├── model.py           treino e score
    ├── queue.py           fila com restrições
    ├── regra_antiga.py    a linha de base
    ├── experiment.py      simulação do A/B
    ├── evaluate.py        concordância dos rótulos
    └── pipeline.py        orquestração e CLI
```

Desvios em relação aos nomes sugeridos: `regra_antiga.py` e `comum.py` foram acrescentados (a regra é a linha de base e merece arquivo próprio; `comum.py` guarda o contexto de execução). Documentação: `docs/handoff.md` (ponto de partida), `docs/arquitetura.md`, `docs/decisoes.md`, `docs/riscos.md`.

## Provedor real de LLM

`cp .env.example .env`, defina `LLM_PROVEDOR=anthropic` e `ANTHROPIC_API_KEY`. O modo usado fica registrado em `fonte_rotulo`. O adapter real **não foi exercitado** nesta PoC (sem chave): o modo offline é o caminho testado.

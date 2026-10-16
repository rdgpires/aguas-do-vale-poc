# Handoff: PoC Águas do Vale

## 1. Formulação

- **Decisão:** quais ligações visitar no mês (~2.000 entre ~500 mil).
- **Restrição:** 12 equipes, 8 visitas por equipe por dia, condomínios com acesso incerto, regiões que exigem dupla.
- **Sinal:** taxa de acerto das visitas contra a linha de base de 1 em 5; volume recuperado por visita.
- **Dado:** consumo e cadastro (sistema comercial), resultado das visitas (app de campo, texto livre), vazão por setor (telemetria).
- **Prioridade** = chance de irregularidade × volume recuperável.
- **v1** "queda de consumo" perde para a regra antiga; **v2** "queda de consumo inexplicada" ganha (`formulacao` em `config.yaml`).

## 2. Como rodar

```bash
python -m venv .venv && .venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -e .
python -m scripts.gerar_base --escala 500000 --semente 42   # ou --escala 50000 para aula
python -m src.pipeline --mes 2026-08                         # pipeline completo
python -m src.pipeline --mes 2026-08 --etapa rotulagem       # uma etapa
python -m src.evaluate                                       # concordância dos rótulos
python -m src.experiment --mes 2026-08 --formulacao v1       # A/B simulado
python -m scripts.registrar_resultados                       # A/B v1 e v2 + docs/resultados_calibrados.md
streamlit run app/painel.py                                  # painel
```

Saída: `data/saida/<mes>/<formulacao>/equipes/<data>_<equipe>.csv` e `fila_<mes>.csv`.

## 3. Arquitetura e contratos

Ver `docs/arquitetura.md` (componentes, fluxo, extensões) e `docs/contratos.md` (gerado do código). Fontes por adapters configurados em `config.yaml`; armazenamento atrás de `Armazenamento`; cada etapa é `executar(ctx) -> dict`.

## 4. Decisões

Ver `docs/decisoes.md`. As que mais pesam: LLM para texto livre, integração somente leitura, modelo explicável, formulação como configuração.

## 5. Avaliação

- **Rótulos:** `python -m src.evaluate` compara com `eval/amostra_revisada.csv` (500 anotações). *Futuro:* esse conjunto vira teste de regressão no CI, falhando abaixo de um piso de concordância ao trocar prompt ou modelo (não implementado).
- **Fila:** `python -m src.experiment` simula 6 equipes contra 6 com a verdade oculta da base sintética.
- **Números calibrados:** `docs/resultados_calibrados.md`.
- **Não há testes unitários**, por decisão: a qualidade vem dos contratos validados em execução e da avaliação dos rótulos.

## 6. Riscos

Ver `docs/riscos.md`.

## 7. Contatos

| Papel | Nome | Contato |
|---|---|---|
| Patrocinador (Águas do Vale) | _a preencher_ | _a preencher_ |
| Responsável de dados do sistema comercial | _a preencher_ | _a preencher_ |
| Coordenação das equipes de campo | _a preencher_ | _a preencher_ |
| Time de sistemas (mantenedor da PoC) | _a preencher_ | _a preencher_ |
| FDE | _a preencher_ | _a preencher_ |

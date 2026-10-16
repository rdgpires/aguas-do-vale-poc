# Riscos

| Risco | Sinal de alerta | O que fazer |
|---|---|---|
| **O texto livre muda** (nova gíria, novo app, novo modelo de formulário) | Concordância na amostra revisada cai; cresce a fração de rótulos `null`; sobem pendências de rotulagem | Rodar `python -m src.evaluate` a cada mudança de prompt ou modelo; renovar a amostra revisada trimestralmente; subir `versao_prompt` (o cache se invalida sozinho) |
| **Outro sistema escreve no mesmo banco** (ou o esquema de origem muda) | `ContratoQuebrado` na extração; salto de registros inválidos; colunas novas ou tipos trocados | A etapa para e avisa por desenho. Tratar na origem, atualizar o contrato em `src/contracts/` e regenerar `docs/contratos.md`. Nunca relaxar o contrato para "passar" |
| **As equipes mudam** (mais equipes, duplas novas, regiões novas) | Fila com muitas `nao_alocadas`; equipes de dupla saturadas | Editar `equipes`, `regioes_com_dupla` e `visitas_por_equipe` no `config.yaml`; testar antes no simulador do painel |
| **Cadastro desatualizado** (imóvel vazio ou troca de hidrômetro sem registro) | Visitas sem irregularidade por causa conhecida continuam altas na v2 | Devolver ao comercial a lista de ligações com queda explicada pelo campo; medir a lacuna entre explicação real e registrada |
| **Viés de seleção do treino** (só aprende com o que já foi visitado) | AUC alta no treino e acerto baixo em produção | Reservar uma fração pequena da fila para visitas fora do ranking (exploração) e treinar com ela |
| **Condomínios e acesso incerto** | `tentativas_sem_acesso` alto; condomínios dominam as `nao_alocadas` | Ajustar `limite_condominios_por_equipe`; combinar agendamento com síndicos fora da PoC |
| **Dado pessoal vaza** (texto fora do padrão do mascaramento) | Amostra de `anotacao_mascarada` com nome ou número inteiro | Revisar amostra periodicamente; ampliar padrões em `src/llm/mascaramento.py`; sem log do texto cru |
| **Valor superestimado** | Ganho medido em campo bem abaixo do simulado | O A/B simulado usa verdade oculta sintética: confirmar com o experimento real de 6 equipes contra 6 antes de escalar |
| **Dependência do fornecedor de LLM** | Custo por lote sobe; latência; mudança de modelo | A interface `ClienteLLM` isola o fornecedor; o modo offline mantém a PoC rodando sem chave |

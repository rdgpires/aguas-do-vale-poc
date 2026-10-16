# Contratos de dados

> Gerado por `python -m scripts.gerar_docs_contratos` a partir de `src/contracts/`. Não edite à mão.

## `cadastro_ligacao`

- **Origem:** Sistema comercial
- **Granularidade:** 1 linha por ligação
- **Chave:** matricula

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| matricula | str | sim | `\d{7}` |  | 7 dígitos, zeros à esquerda |
| categoria | str | sim | residencial, comercial, industrial, publica |  |  |
| setor_id | str | não |  |  | ausente em parte das ligações |
| bairro | str | sim |  |  |  |
| regiao | str | sim |  |  |  |
| condominio | bool | sim |  |  |  |
| situacao_imovel | str | sim | ocupado, desocupado, desconhecido |  |  |
| nome_titular | str | não |  | **PII** |  |
| cpf_titular | str | não |  | **PII** |  |

**Regras de qualidade:**
- matricula única
- PII sai do fluxo na extração: nenhuma etapa seguinte recebe nome ou CPF

## `consumo_mensal`

- **Origem:** Sistema comercial
- **Granularidade:** 1 linha por ligação e mês
- **Chave:** matricula, referencia

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| matricula | str | sim | `\d{7}` |  | 7 dígitos, zeros à esquerda |
| referencia | str | sim | `\d{4}-(0[1-9]|1[0-2])` |  | YYYY-MM |
| consumo_m3 | float | sim |  ≥ 0 |  |  |
| tipo_leitura | str | sim | real, estimada |  |  |
| hidrometro_id | str | sim |  |  |  |

**Regras de qualidade:**
- consumo_m3 >= 0
- leitura estimada nunca entra no cálculo de queda

## `troca_hidrometro`

- **Origem:** Sistema comercial
- **Granularidade:** 1 linha por troca
- **Chave:** matricula, data_troca

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| matricula | str | sim | `\d{7}` |  | 7 dígitos, zeros à esquerda |
| data_troca | date | sim |  |  |  |
| hidrometro_antigo | str | sim |  |  |  |
| hidrometro_novo | str | sim |  |  |  |

## `historico_categoria`

- **Origem:** Sistema comercial
- **Granularidade:** 1 linha por mudança
- **Chave:** matricula, data_mudanca

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| matricula | str | sim | `\d{7}` |  | 7 dígitos, zeros à esquerda |
| categoria_anterior | str | sim | residencial, comercial, industrial, publica |  |  |
| categoria_nova | str | sim | residencial, comercial, industrial, publica |  |  |
| data_mudanca | date | sim |  |  |  |

## `vazao_setor`

- **Origem:** Telemetria de setor
- **Granularidade:** 1 linha por setor e mês
- **Chave:** setor_id, referencia

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| setor_id | str | sim |  |  |  |
| referencia | str | sim | `\d{4}-(0[1-9]|1[0-2])` |  | YYYY-MM |
| vazao_media_m3h | float | sim |  ≥ 0 |  |  |

**Regras de qualidade:**
- chave é o SETOR, não a ligação: entra como contexto, nunca como dado da ligação

## `ordem_servico`

- **Origem:** App de campo
- **Granularidade:** 1 linha por OS
- **Chave:** os_id

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| os_id | str | sim |  |  |  |
| matricula_digitada | str | sim |  |  | bruta, digitada à mão, sem garantia de formato |
| data_visita | date | sim |  |  |  |
| equipe_id | str | sim |  |  |  |
| tipo_os | str | sim | inspecao, troca_hidrometro, religacao, outro |  |  |
| anotacao | str | não |  | **PII** | texto livre; pode conter PII |

**Regras de qualidade:**
- duplicidades possíveis
- matrícula precisa ser normalizada antes do join

## `ordem_servico_normalizada`

- **Origem:** Saída da extração
- **Granularidade:** 1 linha por OS única
- **Chave:** os_id

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| os_id | str | sim |  |  |  |
| matricula | str | sim | `\d{7}` |  | 7 dígitos, zeros à esquerda |
| data_visita | date | sim |  |  |  |
| equipe_id | str | sim |  |  |  |
| tipo_os | str | sim | inspecao, troca_hidrometro, religacao, outro |  |  |
| anotacao_mascarada | str | não |  |  | PII mascarada (LGPD) |
| como_matricula | str | sim |  |  | exata | normalizada | corrigida_dist1 |

**Regras de qualidade:**
- matrícula existe no cadastro
- sem duplicidade por (matricula, data, anotação)

## `equipe`

- **Origem:** config.yaml
- **Granularidade:** 1 linha por equipe
- **Chave:** equipe_id

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| equipe_id | str | sim |  |  |  |
| tipo | str | sim | individual, dupla |  |  |
| regiao_base | str | sim |  |  |  |

## `rotulo_visita`

- **Origem:** Rotulagem (LLM ou offline)
- **Granularidade:** 1 linha por OS
- **Chave:** os_id

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| irregularidade | bool | sim |  |  |  |
| tipo | str | não | hidrometro_parado, ligacao_clandestina, cadastro_errado, outro |  |  |
| motivo_nao_acesso | str | não | condominio, ausente, recusa, outro |  |  |
| os_id | str | sim |  |  |  |
| matricula | str | sim |  |  |  |
| fonte_rotulo | str | sim | llm, offline, revisao_manual |  |  |
| modelo_llm | str | não |  |  |  |
| versao_prompt | str | não |  |  |  |

**Regras de qualidade:**
- saída do LLM validada contra RotuloVisita
- irregularidade=true implica motivo_nao_acesso nulo

## `features_ligacao`

- **Origem:** Features
- **Granularidade:** 1 linha por matrícula e referência
- **Chave:** matricula, referencia

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| matricula | str | sim | `\d{7}` |  | 7 dígitos, zeros à esquerda |
| referencia | str | sim | `\d{4}-(0[1-9]|1[0-2])` |  | YYYY-MM |
| categoria | str | sim | residencial, comercial, industrial, publica |  |  |
| queda_pct | float | não |  |  | queda da última leitura REAL contra a média das 6 leituras reais anteriores |
| consumo_base_m3 | float | não |  |  |  |
| leitura_real | bool | sim |  |  | última leitura do mês anterior é real |
| proporcao_estimadas | float | sim |  ≥ 0 |  |  |
| irregularidades_anteriores | int | sim |  ≥ 0 |  |  |
| tentativas_sem_acesso | int | sim |  ≥ 0 |  |  |
| meses_desde_ultima_visita | float | não |  |  |  |
| setor_ausente | bool | sim |  |  |  |
| indice_vazao_setor | float | não |  |  | contexto; nulo sem setor |
| imovel_vazio | bool | sim |  |  |  |
| troca_hidrometro_recente | bool | sim |  |  |  |
| queda_sazonal | bool | sim |  |  |  |
| mudanca_de_uso | bool | sim |  |  |  |
| queda_explicada | bool | sim |  |  | OU das quatro flags; só entra no modelo na v2 |

**Regras de qualidade:**
- uma linha por (matricula, referencia)

## `score_ligacao`

- **Origem:** Modelo
- **Granularidade:** 1 linha por matrícula e referência
- **Chave:** matricula, referencia

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| matricula | str | sim | `\d{7}` |  | 7 dígitos, zeros à esquerda |
| referencia | str | sim | `\d{4}-(0[1-9]|1[0-2])` |  | YYYY-MM |
| p_irregularidade | float | sim |  ≥ 0 |  |  |
| volume_recuperavel_m3 | float | sim |  ≥ 0 |  |  |
| prioridade | float | sim |  ≥ 0 |  |  |
| formulacao | str | sim | v1, v2 |  |  |
| versao_modelo | str | sim |  |  |  |

**Regras de qualidade:**
- prioridade = p_irregularidade x volume_recuperavel_m3
- p_irregularidade entre 0 e 1

## `fila_visita`

- **Origem:** Fila
- **Granularidade:** 1 linha por visita planejada
- **Chave:** data, equipe_id, ordem

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| data | date | sim |  |  |  |
| equipe_id | str | sim |  |  |  |
| ordem | int | sim |  ≥ 1 |  |  |
| matricula | str | sim | `\d{7}` |  | 7 dígitos, zeros à esquerda |
| categoria | str | sim | residencial, comercial, industrial, publica |  |  |
| bairro | str | sim |  |  |  |
| regiao | str | sim |  |  |  |
| motivo | str | sim |  |  | texto curto legível pela equipe |

**Regras de qualidade:**
- <= visitas_por_equipe por equipe e dia
- <= limite_condominios_por_equipe
- regiões com dupla só para equipes tipo dupla

## `pendencia`

- **Origem:** Todas as etapas
- **Granularidade:** 1 linha por item fora do fluxo
- **Chave:** etapa, chave, motivo

| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |
|---|---|---|---|---|---|
| etapa | str | sim |  |  |  |
| chave | str | sim |  |  |  |
| motivo | str | sim |  |  |  |
| run_id | str | sim |  |  |  |

**Regras de qualidade:**
- nada é descartado em silêncio

"""Módulo único de contratos de dados. `REGISTRO` lista todos; `docs/contratos.md` sai daqui."""
from __future__ import annotations

import typing

from .base import Campo, Contrato, ContratoQuebrado
from .dominios import (CATEGORIAS, FONTES_ROTULO, FORMULACOES, LEITURAS, MOTIVOS_NAO_ACESSO,  # noqa: F401
                       REGEX_MATRICULA, REGEX_REFERENCIA, SITUACOES, TIPOS_IRREG, TIPOS_OS)
from .registros import Equipe, Pendencia, RotuloVisita, RotuloVisitaRegistro

SIST = "Sistema comercial"
MAT = Campo("matricula", "str", padrao=REGEX_MATRICULA, descricao="7 dígitos, zeros à esquerda")
REF = Campo("referencia", "str", padrao=REGEX_REFERENCIA, descricao="YYYY-MM")

cadastro_ligacao = Contrato(
    "cadastro_ligacao", SIST, "1 linha por ligação", ("matricula",),
    (MAT,
     Campo("categoria", "str", dominio=CATEGORIAS),
     Campo("setor_id", "str", obrigatorio=False, descricao="ausente em parte das ligações"),
     Campo("bairro", "str"), Campo("regiao", "str"),
     Campo("condominio", "bool"),
     Campo("situacao_imovel", "str", dominio=SITUACOES),
     Campo("nome_titular", "str", obrigatorio=False, pii=True),
     Campo("cpf_titular", "str", obrigatorio=False, pii=True)),
    ("matricula única", "PII sai do fluxo na extração: nenhuma etapa seguinte recebe nome ou CPF"))

consumo_mensal = Contrato(
    "consumo_mensal", SIST, "1 linha por ligação e mês", ("matricula", "referencia"),
    (MAT, REF,
     Campo("consumo_m3", "float", minimo=0),
     Campo("tipo_leitura", "str", dominio=LEITURAS),
     Campo("hidrometro_id", "str")),
    ("consumo_m3 >= 0", "leitura estimada nunca entra no cálculo de queda"))

troca_hidrometro = Contrato(
    "troca_hidrometro", SIST, "1 linha por troca", ("matricula", "data_troca"),
    (MAT, Campo("data_troca", "date"), Campo("hidrometro_antigo", "str"),
     Campo("hidrometro_novo", "str")), ())

historico_categoria = Contrato(
    "historico_categoria", SIST, "1 linha por mudança", ("matricula", "data_mudanca"),
    (MAT, Campo("categoria_anterior", "str", dominio=CATEGORIAS),
     Campo("categoria_nova", "str", dominio=CATEGORIAS), Campo("data_mudanca", "date")), ())

vazao_setor = Contrato(
    "vazao_setor", "Telemetria de setor", "1 linha por setor e mês", ("setor_id", "referencia"),
    (Campo("setor_id", "str"), REF, Campo("vazao_media_m3h", "float", minimo=0)),
    ("chave é o SETOR, não a ligação: entra como contexto, nunca como dado da ligação",))

ordem_servico = Contrato(
    "ordem_servico", "App de campo", "1 linha por OS", ("os_id",),
    (Campo("os_id", "str"),
     Campo("matricula_digitada", "str", descricao="bruta, digitada à mão, sem garantia de formato"),
     Campo("data_visita", "date"), Campo("equipe_id", "str"),
     Campo("tipo_os", "str", dominio=TIPOS_OS),
     Campo("anotacao", "str", obrigatorio=False, pii=True, descricao="texto livre; pode conter PII")),
    ("duplicidades possíveis", "matrícula precisa ser normalizada antes do join"))

ordem_servico_normalizada = Contrato(
    "ordem_servico_normalizada", "Saída da extração", "1 linha por OS única", ("os_id",),
    (Campo("os_id", "str"), MAT, Campo("data_visita", "date"), Campo("equipe_id", "str"),
     Campo("tipo_os", "str", dominio=TIPOS_OS),
     Campo("anotacao_mascarada", "str", obrigatorio=False, descricao="PII mascarada (LGPD)"),
     Campo("como_matricula", "str", descricao="exata | normalizada | corrigida_dist1")),
    ("matrícula existe no cadastro", "sem duplicidade por (matricula, data, anotação)"))


def _de_modelo(m: type, nome: str, origem: str, gran: str, chave: tuple, regras=()) -> Contrato:
    """Deriva um Contrato descritivo de um modelo Pydantic (um só lugar para documentar)."""
    campos = []
    for n, f in m.model_fields.items():
        ann = f.annotation
        args = typing.get_args(ann)
        nulo = type(None) in args
        lits = [typing.get_args(a) for a in args if typing.get_origin(a) is typing.Literal]
        if typing.get_origin(ann) is typing.Literal:
            lits = [args]
        campos.append(Campo(n, "bool" if ann is bool else "str", obrigatorio=not nulo,
                            dominio=lits[0] if lits else None))
    return Contrato(nome, origem, gran, chave, tuple(campos), tuple(regras))


rotulo_visita = _de_modelo(
    RotuloVisitaRegistro, "rotulo_visita", "Rotulagem (LLM ou offline)", "1 linha por OS", ("os_id",),
    ("saída do LLM validada contra RotuloVisita", "irregularidade=true implica motivo_nao_acesso nulo"))
equipe = _de_modelo(Equipe, "equipe", "config.yaml", "1 linha por equipe", ("equipe_id",))
pendencia = _de_modelo(Pendencia, "pendencia", "Todas as etapas", "1 linha por item fora do fluxo",
                       ("etapa", "chave", "motivo"), ("nada é descartado em silêncio",))

features_ligacao = Contrato(
    "features_ligacao", "Features", "1 linha por matrícula e referência", ("matricula", "referencia"),
    (MAT, REF, Campo("categoria", "str", dominio=CATEGORIAS),
     Campo("queda_pct", "float", obrigatorio=False,
           descricao="queda da última leitura REAL contra a média das 6 leituras reais anteriores"),
     Campo("consumo_base_m3", "float", obrigatorio=False),
     Campo("leitura_real", "bool", descricao="última leitura do mês anterior é real"),
     Campo("proporcao_estimadas", "float", minimo=0),
     Campo("irregularidades_anteriores", "int", minimo=0),
     Campo("tentativas_sem_acesso", "int", minimo=0),
     Campo("meses_desde_ultima_visita", "float", obrigatorio=False),
     Campo("setor_ausente", "bool"),
     Campo("indice_vazao_setor", "float", obrigatorio=False, descricao="contexto; nulo sem setor"),
     Campo("imovel_vazio", "bool"), Campo("troca_hidrometro_recente", "bool"),
     Campo("queda_sazonal", "bool"), Campo("mudanca_de_uso", "bool"),
     Campo("queda_explicada", "bool", descricao="OU das quatro flags; só entra no modelo na v2")),
    ("uma linha por (matricula, referencia)",))

score_ligacao = Contrato(
    "score_ligacao", "Modelo", "1 linha por matrícula e referência", ("matricula", "referencia"),
    (MAT, REF, Campo("p_irregularidade", "float", minimo=0),
     Campo("volume_recuperavel_m3", "float", minimo=0),
     Campo("prioridade", "float", minimo=0), Campo("formulacao", "str", dominio=FORMULACOES),
     Campo("versao_modelo", "str")),
    ("prioridade = p_irregularidade x volume_recuperavel_m3", "p_irregularidade entre 0 e 1"))

fila_visita = Contrato(
    "fila_visita", "Fila", "1 linha por visita planejada", ("data", "equipe_id", "ordem"),
    (Campo("data", "date"), Campo("equipe_id", "str"), Campo("ordem", "int", minimo=1), MAT,
     Campo("categoria", "str", dominio=CATEGORIAS), Campo("bairro", "str"), Campo("regiao", "str"),
     Campo("motivo", "str", descricao="texto curto legível pela equipe")),
    ("<= visitas_por_equipe por equipe e dia", "<= limite_condominios_por_equipe",
     "regiões com dupla só para equipes tipo dupla"))

REGISTRO: dict[str, Contrato] = {c.nome: c for c in (
    cadastro_ligacao, consumo_mensal, troca_hidrometro, historico_categoria, vazao_setor,
    ordem_servico, ordem_servico_normalizada, equipe, rotulo_visita, features_ligacao,
    score_ligacao, fila_visita, pendencia)}

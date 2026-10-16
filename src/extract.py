"""Extração, normalização e validação.

É a ÚNICA etapa que lê dados pessoais (nome, CPF, texto cru). Ela os usa para mascarar e
não os repassa: o que sai daqui para o armazenamento não tem PII.

Fluxo: fontes (somente leitura) -> contrato de entrada -> normalização -> contrato de saída.
Registro ruim vira pendência; estrutura quebrada interrompe (ver contracts/base.py).
"""
from __future__ import annotations

import pandas as pd

from .comum import Contexto
from .llm.mascaramento import mascarar
from .sources import criar_fontes

_DIGITOS = "0123456789"


def normalizar_matriculas(digitadas: pd.Series, existentes: set[str]) -> pd.DataFrame:
    """Chave canônica: 7 dígitos com zeros à esquerda.

    1) tira o que não é dígito e completa zeros (cobre "12345", "0012-345", " 0012345 ");
    2) se ainda não existe no cadastro, tenta UM dígito trocado, mas só aceita se houver
       exatamente um candidato. Com 500 mil matrículas em 10 milhões de números, corrigir
       "no chute" ligaria a visita à ligação errada: na dúvida, pendência.
    """
    dig = digitadas.fillna("").astype(str).str.replace(r"\D", "", regex=True)
    pad = dig.where(dig.str.len().between(1, 7), "").str.zfill(7).where(dig.str.len().between(1, 7), "")
    como = pd.Series("normalizada", index=digitadas.index, dtype=object)
    como[digitadas.astype(str) == pad] = "exata"
    achou = pad.isin(existentes)
    motivo = pd.Series(None, index=digitadas.index, dtype=object)
    final = pad.where(achou, None)
    for valor in pad[~achou].unique():
        mask = (pad == valor) & ~achou
        if valor == "":
            motivo[mask] = "matricula_vazia_ou_longa_demais"
            continue
        vizinhos = {valor[:i] + d + valor[i + 1:] for i in range(7) for d in _DIGITOS if d != valor[i]}
        cand = [v for v in vizinhos if v in existentes]
        if len(cand) == 1:
            final[mask] = cand[0]
            como[mask] = "corrigida_dist1"
        else:
            motivo[mask] = "matricula_inexistente" if not cand else f"matricula_ambigua({len(cand)} candidatos)"
    return pd.DataFrame({"matricula": final, "como_matricula": como, "motivo": motivo})


def executar(ctx: Contexto) -> dict:
    fontes = criar_fontes(ctx.cfg)
    ref, arm = ctx.referencia, ctx.arm

    cad = ctx.validar("cadastro_ligacao", fontes.cadastro.ler_cadastro(), "extracao", "entrada")
    dup = cad["matricula"].duplicated()
    ctx.pendencia("extracao", cad.loc[dup, "matricula"], "cadastro_ligacao.matricula: duplicada")
    cad = cad[~dup].reset_index(drop=True)
    existentes = set(cad["matricula"])

    # PII: usada só aqui, para mascarar. Sai do cadastro antes de gravar.
    nomes = cad.set_index("matricula")["nome_titular"]
    cad_sem_pii = cad.drop(columns=["nome_titular", "cpf_titular"])
    arm.gravar("cadastro", ref, cad_sem_pii)

    consumo = ctx.validar("consumo_mensal", fontes.consumo.ler_consumo(ref), "extracao", "entrada")
    arm.gravar("consumo", ref, consumo)
    arm.gravar("trocas", ref, ctx.validar("troca_hidrometro", fontes.cadastro.ler_trocas(), "extracao", "entrada"))
    arm.gravar("historico_categoria", ref,
               ctx.validar("historico_categoria", fontes.cadastro.ler_historico_categoria(), "extracao", "entrada"))
    arm.gravar("vazao_setor", ref, ctx.validar("vazao_setor", fontes.telemetria.ler_vazao(ref), "extracao", "entrada"))

    # --- ordens de serviço: o ponto mais sujo do discovery ---
    os_ = ctx.validar("ordem_servico", fontes.ordens.ler_ordens(ref), "extracao", "entrada")
    n_os = len(os_)
    norm = normalizar_matriculas(os_["matricula_digitada"], existentes)
    sem = norm["matricula"].isna()
    ctx.pendencia("extracao", os_.loc[sem, "os_id"], norm.loc[sem, "motivo"])
    os_ = pd.concat([os_.drop(columns="matricula_digitada"), norm[["matricula", "como_matricula"]]],
                    axis=1)[~sem]
    # duplicidade: mesma visita registrada duas vezes (chave = matrícula normalizada + data + texto)
    dup = os_.duplicated(["matricula", "data_visita", "anotacao"], keep="first")
    ctx.pendencia("extracao", os_.loc[dup, "os_id"], "os_duplicada_removida")
    os_ = os_[~dup].copy()
    # LGPD: mascara antes de qualquer envio ao LLM; o texto cru é descartado aqui
    os_["anotacao_mascarada"] = [mascarar(a, [nomes.get(m)]) for a, m in zip(os_["anotacao"], os_["matricula"])]
    os_ = os_.drop(columns="anotacao")
    os_ = ctx.validar("ordem_servico_normalizada", os_, "extracao", "saida")
    arm.gravar("ordem_servico", ref, os_.reset_index(drop=True))

    corrigidas = int((os_["como_matricula"] == "corrigida_dist1").sum())
    c = {"ligacoes_lidas": int(len(cad)), "consumo_linhas": int(len(consumo)), "os_lidas": int(n_os),
         "os_matricula_corrigida": corrigidas, "os_matricula_nao_resolvida": int(sem.sum()),
         "os_duplicadas_removidas": int(dup.sum()), "os_validas": int(len(os_)),
         "ligacoes_sem_setor": int(cad["setor_id"].isna().sum())}
    ctx.log("extracao", "concluida", **c)
    return c

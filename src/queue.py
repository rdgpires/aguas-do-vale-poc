"""Fila com restrições.

Percorre o ranking (já ordenado por prioridade) e, para cada ligação, procura o primeiro
dia/equipe compatível. As três restrições do slide vêm do `config.yaml`:

    visitas_por_equipe: 8
    limite_condominios_por_equipe: 2
    regioes_com_dupla: [norte]

Nota: o módulo se chama `queue` (nome do slide). Rode sempre pela raiz do repositório
(`python -m src.pipeline`), onde ele é `src.queue` e não colide com a `queue` da stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Restricoes:
    visitas_por_equipe: int = 8
    limite_condominios_por_equipe: int = 2
    regioes_com_dupla: tuple[str, ...] = ("norte",)

    @classmethod
    def do_config(cls, cfg: dict) -> "Restricoes":
        return cls(cfg["visitas_por_equipe"], cfg["limite_condominios_por_equipe"],
                   tuple(cfg["regioes_com_dupla"]))


def compativel(regiao: str, equipe_tipo: str, r: Restricoes) -> bool:
    """Região com dupla só aceita equipe do tipo dupla."""
    return equipe_tipo == "dupla" or regiao not in r.regioes_com_dupla


def motivo_legivel(queda: float, explicada: bool, condominio: bool, dupla: bool, formulacao: str) -> str:
    base = f"Queda de {queda:.0%} no consumo"
    if formulacao == "v2":
        base += " sem causa registrada" if not explicada else " (causa registrada: conferir)"
    extra = []
    if condominio:
        extra.append("condomínio: confirmar acesso")
    if dupla:
        extra.append("ir em dupla")
    return base + ("; " + "; ".join(extra) if extra else "")


def montar_fila(ranking: pd.DataFrame, equipes: list[dict], dias: list[pd.Timestamp], r: Restricoes,
                olhar_ate: int = 200_000) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`ranking`: colunas matricula, categoria, bairro, regiao, condominio, motivo (já em ordem).

    Devolve (fila, nao_alocadas). Uma ligação sem equipe compatível passa para o próximo dia;
    se nenhum dia serve, vai para `nao_alocadas` com o motivo (nunca some)."""
    # preferir equipe individual nas regiões comuns preserva as duplas para as regiões que exigem
    individuais = [e for e in equipes if e["tipo"] != "dupla"]
    duplas = [e for e in equipes if e["tipo"] == "dupla"]
    carga = {(d, e["equipe_id"]): [0, 0] for d in dias for e in equipes}   # [visitas, condomínios]
    total = len(dias) * len(equipes) * r.visitas_por_equipe
    saida, fora = [], []
    ordem = {k: 0 for k in carga}
    cols = ranking[["matricula", "categoria", "bairro", "regiao", "condominio", "motivo"]].head(olhar_ate)
    for lig in cols.itertuples(index=False):
        if len(saida) >= total:
            break
        candidatas = (duplas if lig.regiao in r.regioes_com_dupla else individuais + duplas)
        alocada = False
        for d in dias:
            for e in candidatas:
                c = carga[(d, e["equipe_id"])]
                if c[0] >= r.visitas_por_equipe or (lig.condominio and c[1] >= r.limite_condominios_por_equipe):
                    continue
                c[0] += 1
                c[1] += int(lig.condominio)
                ordem[(d, e["equipe_id"])] += 1
                saida.append((d, e["equipe_id"], ordem[(d, e["equipe_id"])], lig.matricula, lig.categoria,
                              lig.bairro, lig.regiao, lig.motivo))
                alocada = True
                break
            if alocada:
                break
        if not alocada:
            fora.append((lig.matricula, lig.regiao, "sem_equipe_compativel_no_mes"))
    fila = pd.DataFrame(saida, columns=["data", "equipe_id", "ordem", "matricula", "categoria", "bairro",
                                        "regiao", "motivo"])
    fila["data"] = pd.to_datetime(fila["data"])
    nao = pd.DataFrame(fora, columns=["matricula", "regiao", "motivo"])
    return fila.sort_values(["data", "equipe_id", "ordem"]).reset_index(drop=True), nao


def preparar_ranking(score: pd.DataFrame, cad: pd.DataFrame, feats: pd.DataFrame, formulacao: str,
                     meses_sem_visita: int) -> pd.DataFrame:
    """Une score + cadastro, tira quem foi visitado há pouco e escreve o motivo em texto."""
    df = score.merge(cad[["matricula", "categoria", "bairro", "regiao", "condominio"]], on="matricula") \
              .merge(feats[["matricula", "queda_pct", "queda_explicada", "meses_desde_ultima_visita"]],
                     on="matricula")
    recente = df["meses_desde_ultima_visita"] < meses_sem_visita
    df = df[~recente & (df["prioridade"] > 0)].sort_values("prioridade", ascending=False)
    q = df["queda_pct"].fillna(0).to_numpy()
    df["motivo"] = [motivo_legivel(a, b, c, False, formulacao) for a, b, c in
                    zip(q, df["queda_explicada"], df["condominio"])]
    return df.reset_index(drop=True)


def exportar_csv(fila: pd.DataFrame, pasta, referencia: str) -> int:
    """Um arquivo por equipe por dia, no formato que as equipes já usam, mais o consolidado."""
    from pathlib import Path
    pasta = Path(pasta)
    (pasta / "equipes").mkdir(parents=True, exist_ok=True)
    for (d, e), g in fila.groupby(["data", "equipe_id"]):
        g.drop(columns=["data", "equipe_id"]).to_csv(pasta / "equipes" / f"{d:%Y-%m-%d}_{e}.csv", index=False,
                                                       sep=";", encoding="utf-8-sig")
    fila.to_csv(pasta / f"fila_{referencia}.csv", index=False, sep=";", encoding="utf-8-sig")
    return fila.groupby(["data", "equipe_id"]).ngroups


def executar(ctx) -> dict:
    from .comum import dias_efetivos, dias_uteis
    f, ref, cfg = ctx.formulacao, ctx.referencia, ctx.cfg
    cad = ctx.arm.ler("cadastro", ref)
    feats = ctx.arm.ler("features_ligacao", ref)
    score = ctx.arm.ler("score_ligacao", ref, variante=f)
    rank = preparar_ranking(score, cad, feats, f, cfg["meses_sem_visita"])
    dias = dias_uteis(ref)[:dias_efetivos(cfg, len(cad))]
    fila, nao = montar_fila(rank, cfg["equipes"], dias, Restricoes.do_config(cfg))
    # marca no motivo quando a ligação foi para equipe em dupla
    dupla = {e["equipe_id"] for e in cfg["equipes"] if e["tipo"] == "dupla"}
    fila.loc[fila["equipe_id"].isin(dupla), "motivo"] += "; ir em dupla"
    fila = ctx.validar("fila_visita", fila, "fila", "saida")
    ctx.arm.gravar("fila_visita", ref, fila, variante=f)
    ctx.arm.gravar("fila_nao_alocada", ref, nao, variante=f)
    arquivos = exportar_csv(fila, f"{cfg['saidas']['raiz']}/{ref}/{f}", ref)
    c = {"visitas_no_mes": int(len(fila)), "equipes": len(cfg["equipes"]), "dias": len(dias),
         "visitas_por_equipe": cfg["visitas_por_equipe"], "nao_alocadas": int(len(nao)),
         "arquivos_csv": arquivos}
    ctx.log("fila", "concluida", **c)
    return c

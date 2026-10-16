"""Treino e score.

Regressão logística, de propósito: o time de sistemas do cliente precisa manter isso, e
cada coeficiente se explica numa frase. O relatório de coeficientes faz parte da entrega.

A formulação é um contrato configurável:
    v1: queda de consumo                         -> flags de explicação NÃO entram
    v2: queda de consumo INEXPLICADA             -> entra `queda_explicada`
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .comum import Contexto

VERSAO_MODELO = "logreg-1"

FEATURES = ["queda_pct", "sem_queda_calculavel", "log_consumo_base", "cat_comercial", "cat_industrial",
            "cat_publica", "proporcao_estimadas", "irregularidades_anteriores", "tentativas_sem_acesso",
            "meses_desde_ultima_visita", "indice_vazao_setor", "setor_ausente"]


def features_da_formulacao(formulacao: str) -> list[str]:
    cols = list(FEATURES)
    if formulacao == "v2":
        cols.append("queda_explicada")   # <- o slide: FEATURES.append("queda_explicada")
    return cols


def matriz(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Transforma features_ligacao na matriz do modelo. Nulos têm tratamento explícito:
    setor ausente e queda não calculável viram indicadores, não valores inventados."""
    x = pd.DataFrame(index=df.index)
    x["queda_pct"] = df["queda_pct"].fillna(0).clip(-1, 1)
    x["sem_queda_calculavel"] = df["queda_pct"].isna().astype(float)
    x["log_consumo_base"] = np.log1p(df["consumo_base_m3"].fillna(0))
    for c in ("comercial", "industrial", "publica"):
        x[f"cat_{c}"] = (df["categoria"] == c).astype(float)
    x["proporcao_estimadas"] = df["proporcao_estimadas"]
    x["irregularidades_anteriores"] = df["irregularidades_anteriores"].clip(0, 3)
    x["tentativas_sem_acesso"] = df["tentativas_sem_acesso"].clip(0, 3)
    x["meses_desde_ultima_visita"] = df["meses_desde_ultima_visita"].fillna(24).clip(0, 24)
    x["indice_vazao_setor"] = df["indice_vazao_setor"].fillna(1.0).clip(0, 3)
    x["setor_ausente"] = df["setor_ausente"].astype(float)
    x["queda_explicada"] = df["queda_explicada"].astype(float)
    return x[cols]


def volume_recuperavel(df: pd.DataFrame, fator_categoria: dict[str, float]) -> pd.Series:
    """m3/mês que a ligação deixaria de perder: queda sobre o histórico x consumo-base,
    ponderada por categoria (comércio rende mais que residência)."""
    queda = df["queda_pct"].fillna(0).clip(0, 1)
    return (df["consumo_base_m3"].fillna(0) * queda * df["categoria"].map(fator_categoria).fillna(1.0))


def treinar(treino: pd.DataFrame, formulacao: str) -> tuple[object, dict]:
    cols = features_da_formulacao(formulacao)
    X, y = matriz(treino, cols), treino["irregularidade"].astype(int)
    Xa, Xb, ya, yb = train_test_split(X, y, test_size=0.25, random_state=7, stratify=y)
    pipe = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))
    pipe.fit(Xa, ya)
    auc = float(roc_auc_score(yb, pipe.predict_proba(Xb)[:, 1]))
    pipe.fit(X, y)                       # modelo final usa todas as visitas rotuladas
    coef = pipe[-1].coef_[0]
    rel = {"formulacao": formulacao, "versao_modelo": VERSAO_MODELO, "n_treino": int(len(y)),
           "taxa_irregularidade_treino": round(float(y.mean()), 4), "auc_holdout": round(auc, 3),
           "coeficientes_padronizados": {c: round(float(b), 3) for c, b in
                                         sorted(zip(cols, coef), key=lambda t: -abs(t[1]))},
           "intercepto": round(float(pipe[-1].intercept_[0]), 3)}
    return pipe, rel


def pontuar(pipe, feats: pd.DataFrame, formulacao: str, fator_categoria: dict[str, float]) -> pd.DataFrame:
    cols = features_da_formulacao(formulacao)
    p = pipe.predict_proba(matriz(feats, cols))[:, 1]
    vol = volume_recuperavel(feats, fator_categoria).to_numpy()
    return pd.DataFrame({"matricula": feats["matricula"].to_numpy(), "referencia": feats["referencia"].to_numpy(),
                         "p_irregularidade": p, "volume_recuperavel_m3": vol,
                         "prioridade": p * vol,           # prioridade = chance x volume recuperável
                         "formulacao": formulacao, "versao_modelo": VERSAO_MODELO})


def executar(ctx: Contexto, formulacao: str | None = None) -> dict:
    f = formulacao or ctx.formulacao
    feats = ctx.arm.ler("features_ligacao", ctx.referencia)
    treino = ctx.arm.ler("features_treino", ctx.referencia)
    if len(treino) < 50 or treino["irregularidade"].nunique() < 2:
        raise RuntimeError(f"[modelo] treino insuficiente ({len(treino)} visitas rotuladas): rode a rotulagem")
    pipe, rel = treinar(treino, f)
    sc = pontuar(pipe, feats, f, ctx.cfg["modelo"]["fator_categoria"])
    sc = ctx.validar("score_ligacao", sc, "modelo", "saida")
    ctx.arm.gravar("score_ligacao", ctx.referencia, sc, variante=f)
    ctx.arm.gravar_json("relatorio_modelo", f"{ctx.referencia}_{f}", rel)
    c = {"ligacoes_pontuadas": int(len(sc)), "formulacao": f, "n_treino": rel["n_treino"], "auc_holdout": rel["auc_holdout"]}
    ctx.log("modelo", "concluida", **c)
    return c

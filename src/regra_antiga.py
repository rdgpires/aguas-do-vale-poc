"""A regra atual, a linha de base: "uma regra escrita há dez anos".

Selecionar ligações com queda de consumo entre 30% e 90% em relação à média dos 6 meses
anteriores, com leitura real, sem visita nos últimos 6 meses, ordenadas pela queda percentual.

O teto de 90% é conhecimento tácito antigo: "queda para quase zero costuma ser imóvel vazio".
É por isso que uma regra tão simples ganha da PoC v1.
"""
import pandas as pd


def regra_antiga(feats: pd.DataFrame, meses_sem_visita: int = 6) -> pd.DataFrame:
    ok = (
        feats["leitura_real"]
        & feats["queda_pct"].between(0.30, 0.90)
        & (feats["meses_desde_ultima_visita"].isna() | (feats["meses_desde_ultima_visita"] >= meses_sem_visita))
    )
    return feats[ok].sort_values("queda_pct", ascending=False)

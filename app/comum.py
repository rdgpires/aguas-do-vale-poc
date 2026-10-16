"""Contexto do painel: config, armazenamento, execução e mês escolhidos."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from src.comum import carregar_config
from src.storage import criar_armazenamento


@dataclass
class PainelCtx:
    cfg: dict
    arm: object
    referencia: str
    run_id: str
    manifesto: dict

    @property
    def formulacao(self) -> str:
        return self.manifesto.get("formulacao", self.cfg["formulacao"])


@st.cache_resource
def _base():
    cfg = carregar_config()
    return cfg, criar_armazenamento(cfg)


def barra_lateral() -> PainelCtx | None:
    cfg, arm = _base()
    runs = arm.listar_json("execucoes")
    if not runs:
        return None
    runs = sorted(runs, reverse=True)               # run_id começa com timestamp: o mais novo vem primeiro
    refs = sorted(arm.referencias("fila_visita"), reverse=True) or [cfg["referencia_padrao"]]
    ref = st.sidebar.selectbox("Mês de referência", refs)
    run = st.sidebar.selectbox("Execução", runs)
    return PainelCtx(cfg, arm, ref, run, arm.ler_json("execucoes", run))


@st.cache_data(show_spinner=False)
def ler(_arm, etapa: str, referencia: str, variante: str | None = None) -> pd.DataFrame:
    return _arm.ler(etapa, referencia, variante)


def milhar(n: int | float) -> str:
    return f"{int(n):,}".replace(",", ".")

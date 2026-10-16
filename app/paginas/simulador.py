"""Simulador de restrições: recalcula a fila chamando o componente `queue`.
As alterações NÃO sobrescrevem o config.yaml; servem para demonstrar o efeito."""
import pandas as pd
import streamlit as st

from app import comum
from src import queue as fila
from src.comum import dias_efetivos, dias_uteis

REGIOES = ["norte", "sul", "leste", "oeste", "centro", "jardim_alto"]


@st.cache_data(show_spinner="Montando a fila...")
def _fila(_arm, ref, formulacao, visitas, cond, regioes, equipes, dias_n, meses_sem_visita):
    cad = _arm.ler("cadastro", ref)
    feats = _arm.ler("features_ligacao", ref)
    score = _arm.ler("score_ligacao", ref, formulacao)
    rank = fila.preparar_ranking(score, cad, feats, formulacao, meses_sem_visita)
    dias = dias_uteis(ref)[:dias_n]
    return fila.montar_fila(rank, [dict(e) for e in equipes], dias, fila.Restricoes(visitas, cond, tuple(regioes)))


def _resumo(f: pd.DataFrame, nao: pd.DataFrame) -> pd.Series:
    return pd.Series({"visitas no mês": len(f), "ligações sem equipe compatível": len(nao),
                      "visitas em jardim_alto": int((f["regiao"] == "jardim_alto").sum()),
                      "visitas em norte": int((f["regiao"] == "norte").sum())})


def render(c) -> None:
    st.title("Simulador de restrições")
    cfg = c.cfg
    a, b, d = st.columns(3)
    visitas = a.number_input("visitas_por_equipe", 1, 20, cfg["visitas_por_equipe"])
    cond = b.number_input("limite_condominios_por_equipe", 0, 8, cfg["limite_condominios_por_equipe"])
    regioes = d.multiselect("regioes_com_dupla", REGIOES, default=cfg["regioes_com_dupla"])
    n_lig = len(comum.ler(c.arm, "cadastro", c.referencia))
    dias_n = dias_efetivos(cfg, n_lig)
    eq = tuple(tuple(sorted(e.items())) for e in cfg["equipes"])
    antes = _fila(c.arm, c.referencia, c.formulacao, cfg["visitas_por_equipe"],
                  cfg["limite_condominios_por_equipe"], tuple(cfg["regioes_com_dupla"]), eq, dias_n,
                  cfg["meses_sem_visita"])
    depois = _fila(c.arm, c.referencia, c.formulacao, int(visitas), int(cond), tuple(regioes), eq, dias_n,
                   cfg["meses_sem_visita"])
    tab = pd.DataFrame({"antes (config.yaml)": _resumo(*antes), "depois (esta tela)": _resumo(*depois)})
    tab["diferença"] = tab["depois (esta tela)"] - tab["antes (config.yaml)"]
    st.dataframe(tab, width="stretch")
    mud = len(set(depois[0]["matricula"]) ^ set(antes[0]["matricula"]))
    st.caption(f"{mud} ligações entram ou saem da fila com a mudança. O `config.yaml` não foi alterado.")

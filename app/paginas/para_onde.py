import altair as alt
import pandas as pd
import streamlit as st

NOMES = {"imovel_vazio": "Imóvel vazio", "troca_hidrometro": "Troca de hidrômetro", "sazonalidade": "Sazonalidade",
         "mudanca_de_uso": "Mudança de uso", "sem_causa_identificada": "Sem causa identificada"}


def render(c) -> None:
    st.title("Para onde o modelo mandou as equipes")
    try:
        r1 = c.arm.ler_json("experimento", f"{c.referencia}_v1")
        r2 = c.arm.ler_json("experimento", f"{c.referencia}_v2")
    except FileNotFoundError:
        st.info("Rode o experimento para v1 e v2.")
        return
    linhas = []
    for nome, g in [("Regra antiga", r2["regra_antiga"]), ("PoC v1", r1["poc"]), ("PoC v2", r2["poc"])]:
        for k, n in g["sem_irregularidade_por_causa"].items():
            linhas.append({"estratégia": nome, "causa": NOMES.get(k, k), "visitas": n})
    d = pd.DataFrame(linhas)
    st.altair_chart(alt.Chart(d).mark_bar().encode(
        x=alt.X("estratégia", sort=["Regra antiga", "PoC v1", "PoC v2"], axis=alt.Axis(labelAngle=0, title=None)),
        y=alt.Y("visitas", title="Visitas sem irregularidade"), color="causa",
        tooltip=["estratégia", "causa", "visitas"]), width="stretch")
    st.caption("Cada visita sem irregularidade tem uma causa conhecida na base sintética. "
               "A v2 troca visitas em imóvel vazio e troca de hidrômetro por visitas com chance real.")

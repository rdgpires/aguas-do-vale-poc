import altair as alt
import pandas as pd
import streamlit as st

from app.comum import milhar


def _carregar(c, f):
    try:
        return c.arm.ler_json("experimento", f"{c.referencia}_{f}")
    except FileNotFoundError:
        return None


def render(c) -> None:
    st.title("Experimento A/B (simulação)")
    r1, r2 = _carregar(c, "v1"), _carregar(c, "v2")
    if not (r1 and r2):
        st.info("Rode `python -m src.experiment --formulacao v1` e `--formulacao v2`.")
        return
    base = r2["linha_de_base_taxa"]
    d = pd.DataFrame({"estratégia": ["Regra antiga", "PoC v1", "PoC v2"],
                      "taxa": [r2["regra_antiga"]["taxa_acerto"], r1["poc"]["taxa_acerto"], r2["poc"]["taxa_acerto"]],
                      "m3": [r2["regra_antiga"]["volume_por_visita_m3"], r1["poc"]["volume_por_visita_m3"],
                             r2["poc"]["volume_por_visita_m3"]]})
    barras = alt.Chart(d).mark_bar().encode(
        x=alt.X("estratégia", sort=None, axis=alt.Axis(labelAngle=0, title=None)),
        y=alt.Y("taxa", axis=alt.Axis(format="%", title="Taxa de acerto das visitas")),
        color=alt.Color("estratégia", legend=None, scale=alt.Scale(range=["#8a8f98", "#d1603d", "#2b7a78"])))
    linha = alt.Chart(pd.DataFrame({"y": [base]})).mark_rule(strokeDash=[6, 4], color="black").encode(y="y")
    rotulo = barras.mark_text(dy=-8).encode(text=alt.Text("taxa", format=".1%"))
    st.altair_chart(barras + linha + rotulo, width="stretch")
    st.caption(f"Linha tracejada: linha de base de 1 em 5 ({base:.0%}). "
               f"{r2['regra_antiga']['visitas']} visitas por grupo, 6 equipes contra 6.")
    a, b = st.columns(2)
    a.subheader("Volume recuperado por visita")
    a.dataframe(d[["estratégia", "m3"]].rename(columns={"m3": "m³/mês por visita"}), hide_index=True)
    b.subheader("Ganho da v2 contra a regra")
    b.metric("Pontos de perda aparente (1 fila mensal)", f"{r2['ganho_pontos_perda_aparente_1_fila']:.3f} pp")
    b.metric("Reais por ano (1 fila mensal)", f"R$ {milhar(r2['ganho_reais_ano_1_fila'])}")
    b.caption(f"Doze filas mensais: {r2['ganho_pontos_perda_aparente_12_filas']:.2f} pp ≈ "
              f"R$ {milhar(r2['ganho_reais_ano_12_filas'])}/ano. Estimativa, não promessa.")

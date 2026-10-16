import streamlit as st

from app.comum import ler


def render(c) -> None:
    st.title("Fila do dia")
    f = ler(c.arm, "fila_visita", c.referencia, c.formulacao)
    dupla = {e["equipe_id"] for e in c.cfg["equipes"] if e["tipo"] == "dupla"}
    a, b = st.columns(2)
    dia = a.selectbox("Data", sorted(f["data"].dt.date.unique()))
    sub = f[f["data"].dt.date == dia]
    eq = b.selectbox("Equipe", sorted(sub["equipe_id"].unique()),
                     format_func=lambda e: f"{e} (dupla)" if e in dupla else e)
    tipo = "Equipe em DUPLA: entra em regiões que exigem dupla." if eq in dupla else "Equipe individual."
    st.caption(f"{tipo} Formulação {c.formulacao}.")
    t = sub[sub["equipe_id"] == eq][["ordem", "matricula", "categoria", "bairro", "regiao", "motivo"]]
    st.dataframe(t, hide_index=True, width="stretch")
    st.download_button("Baixar CSV", t.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name=f"{dia}_{eq}.csv", mime="text/csv")

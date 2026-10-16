import pandas as pd
import streamlit as st

from app.comum import ler
from src.contracts import REGISTRO


def render(c) -> None:
    st.title("Contratos e pendências")
    val = pd.DataFrame(c.manifesto.get("validacoes", []))
    linhas = []
    for nome, k in REGISTRO.items():
        v = val[val["contrato"] == nome] if len(val) else val
        if len(v):
            onde = ", ".join(sorted(set(v["etapa"] + "/" + v["direcao"])))
            inval = int(v["invalidos"].sum())
            status = "ok" if inval == 0 else "com pendências"
        else:
            onde, inval, status = "-", 0, "não validado nesta execução"
        linhas.append({"contrato": nome, "origem": k.origem, "chave": ", ".join(k.chave), "validado em": onde,
                       "registros": int(v["registros"].sum()) if len(v) else 0, "inválidos": inval,
                       "status": status})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    st.subheader("Pendências por etapa e motivo")
    partes = []
    for etapa in c.manifesto.get("etapas", []):
        try:
            partes.append(ler(c.arm, "pendencia", c.referencia, etapa))
        except FileNotFoundError:
            pass
    partes = [p for p in partes if len(p)]
    if not partes:
        st.write("Sem pendências.")
        return
    p = pd.concat(partes)
    p["motivo"] = p["motivo"].str.replace(r"\(.*\)|:.*", "", regex=True)
    st.dataframe(p.groupby(["etapa", "motivo"]).size().reset_index(name="itens"), hide_index=True,
                 width="stretch")

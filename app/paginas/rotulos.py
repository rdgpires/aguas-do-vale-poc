import pandas as pd
import streamlit as st

from app.comum import ler


def render(c) -> None:
    st.title("Rótulos do texto livre")
    os_ = ler(c.arm, "ordem_servico", c.referencia)
    rot = ler(c.arm, "rotulo_visita", c.referencia)
    j = os_.merge(rot, on="os_id")
    j = j[j["anotacao_mascarada"].notna()]
    pii = j[j["anotacao_mascarada"].str.contains(r"\[(?:NOME|CPF|TELEFONE|ENDERECO)\]")]
    amostra = pd.concat([pii.head(6), j.sample(6, random_state=1)])
    for _, r in amostra.iterrows():
        a, b = st.columns([3, 2])
        a.code(r["anotacao_mascarada"], language=None)
        b.json({"irregularidade": bool(r["irregularidade"]), "tipo": r["tipo"],
                "motivo_nao_acesso": r["motivo_nao_acesso"]})
    st.caption(f"Fonte do rótulo: {j['fonte_rotulo'].iloc[0]} · modelo: {j['modelo_llm'].iloc[0]} · "
               f"prompt: {j['versao_prompt'].iloc[0]}")
    st.subheader("Concordância com a amostra revisada")
    try:
        av = c.arm.ler_json("avaliacao_rotulos", c.referencia)
    except FileNotFoundError:
        st.info("Rode `python -m src.evaluate`.")
        return
    d = pd.DataFrame({"campo": list(av["concordancia"]),
                      "concordância": [f"{v:.1%}" for v in av["concordancia"].values()]})
    st.dataframe(d, hide_index=True)
    st.caption(f"Amostra: {av['n_amostra']} anotações · rotulador {av['fonte']}.")

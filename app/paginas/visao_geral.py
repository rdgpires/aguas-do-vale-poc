import pandas as pd
import streamlit as st

from app.comum import milhar


def render(c) -> None:
    st.title("Águas do Vale · priorização da fila de visitas")
    m, cfg = c.manifesto, c.cfg
    cont = m["contagens"]
    cols = st.columns(4)
    cols[0].metric("Ligações", milhar(cont.get("extracao", {}).get("ligacoes_lidas", 0)))
    cols[1].metric("Equipes", len(cfg["equipes"]))
    cols[2].metric("Visitas no mês", milhar(cont.get("fila", {}).get("visitas_no_mes", 0)))
    cols[3].metric("Formulação ativa", c.formulacao)
    st.caption("v1 = queda de consumo · v2 = queda de consumo inexplicada. Muda em `config.yaml`, sem mexer no código.")
    st.subheader(f"Última execução · {c.run_id}")
    linhas = []
    for etapa, d in cont.items():
        simples = {k: v for k, v in d.items() if isinstance(v, (int, float, str)) and k != "segundos"}
        linhas.append({"etapa": etapa, "segundos": d.get("segundos"),
                       "contagens": ", ".join(f"{k}={v}" for k, v in list(simples.items())[:5])})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    a, b = st.columns(2)
    a.metric("Pendências", milhar(m.get("pendencias_total", 0)))
    llm = m.get("llm", {})
    b.metric("Custo estimado do LLM (US$)", f"{llm.get('custo_estimado_usd', 0):.2f}",
             help=f"fonte={llm.get('fonte')} · modelo={llm.get('modelo')} · cache={llm.get('acertos_cache')}")

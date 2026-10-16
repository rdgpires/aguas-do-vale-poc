"""Features por ligação e as flags que EXPLICAM uma queda de consumo.

Tudo é calculado "como de" um mês de referência: só entra o que existia antes dele. Isso
permite construir o conjunto de treino com as visitas passadas sem vazar o futuro.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .comum import inicio_do_mes

JANELA = 24                 # meses de histórico carregados
MIN_LEITURAS_BASE = 3       # menos que isso: não há média confiável de leituras reais

# As quatro explicações possíveis (aparecem na aula)
FLAGS_EXPLICACAO = ["imovel_vazio", "troca_hidrometro_recente", "queda_sazonal", "mudanca_de_uso"]


def _ord_ref(r: str) -> int:
    p = pd.Period(r, "M")
    return p.year * 12 + p.month


def matriz_consumo(consumo: pd.DataFrame, matriculas: pd.Index, referencia: str):
    """Pivota o consumo longo em (ligações x 24 meses) de valor e de 'estimada'.
    Coluna 23 = mês imediatamente anterior à referência."""
    cats = consumo["matricula"].cat.categories
    linha_da_cat = matriculas.get_indexer(cats)
    lin = linha_da_cat[consumo["matricula"].cat.codes.to_numpy()]
    ords = np.array([_ord_ref(str(r)) for r in consumo["referencia"].cat.categories])
    col = ords[consumo["referencia"].cat.codes.to_numpy()] - (_ord_ref(referencia) - JANELA)
    bom = (lin >= 0) & (col >= 0) & (col < JANELA)
    val = np.full((len(matriculas), JANELA), np.nan, dtype=np.float32)
    est = np.zeros((len(matriculas), JANELA), dtype=bool)
    val[lin[bom], col[bom]] = consumo["consumo_m3"].to_numpy()[bom]
    est[lin[bom], col[bom]] = (consumo["tipo_leitura"].astype(str).to_numpy() == "estimada")[bom]
    return val, est


def _queda(real: np.ndarray, ult: int) -> tuple[np.ndarray, np.ndarray]:
    """queda = 1 - leitura real do mês `ult` / média das 6 leituras reais anteriores."""
    base_win = real[:, ult - 6:ult]
    n = np.sum(~np.isnan(base_win), axis=1)
    with np.errstate(all="ignore"):
        base = np.where(n >= MIN_LEITURAS_BASE, np.nanmean(base_win, axis=1), np.nan)
        q = 1 - real[:, ult] / base
    q[~(base > 0)] = np.nan
    return q, base


def calcular(val: np.ndarray, est: np.ndarray, ult: int, cad: pd.DataFrame, trocas: pd.DataFrame,
             hist: pd.DataFrame, vazao: pd.DataFrame, os_rot: pd.DataFrame, referencia_modelo: str,
             inicio: pd.Timestamp, cfg_modelo: dict, linhas: np.ndarray | None = None) -> pd.DataFrame:
    """Features como de `inicio` (primeiro dia do mês de referência da linha).

    `ult` = coluna do último mês fechado (23 na referência corrente; menor no treino).
    `linhas` restringe o cálculo (treino usa só as ligações visitadas)."""
    linhas = np.arange(len(cad)) if linhas is None else linhas
    c = cad.iloc[linhas].reset_index(drop=True)
    v, e = val[linhas], est[linhas]
    real = np.where(e, np.nan, v)

    # --- queda de consumo (só leituras REAIS) ---
    queda, base = _queda(real, ult)
    leitura_real = ~np.isnan(real[:, ult])
    # --- sazonal: queda parecida no mesmo mês do ano anterior ---
    q_prev, _ = _queda(real, ult - 12)
    with np.errstate(invalid="ignore"):
        sazonal = (q_prev >= 0.25) & (np.abs(queda - q_prev) <= 0.25)
    # --- histórico de visitas (rótulos), só antes de `inicio` ---
    ant = os_rot[os_rot["data_visita"] < inicio]
    g = ant.groupby("matricula")
    irreg = g["irregularidade"].sum()
    sem_acesso = ant[ant["motivo_nao_acesso"].notna()].groupby("matricula").size()
    ultima = ant[ant["tipo_os"] == "inspecao"].groupby("matricula")["data_visita"].max()
    m = c["matricula"]
    meses_visita = ((inicio - m.map(ultima)).dt.days / 30.4).astype(float)

    recente_t = trocas[(trocas["data_troca"] < inicio) &
                       (trocas["data_troca"] >= inicio - pd.Timedelta(days=cfg_modelo["janela_troca_dias"]))]
    recente_h = hist[(hist["data_mudanca"] < inicio) &
                     (hist["data_mudanca"] >= inicio - pd.Timedelta(days=cfg_modelo["janela_mudanca_uso_dias"]))]

    # --- contexto de setor: vazão medida contra o que as ligações do setor faturaram ---
    mes_ult = str(pd.Period(referencia_modelo, "M") - 1)
    vz = vazao[vazao["referencia"].astype(str) == mes_ult].set_index("setor_id")["vazao_media_m3h"]
    soma_setor = pd.Series(val[:, ult].astype(float)).groupby(cad["setor_id"].to_numpy()).sum()
    idx_setor = (c["setor_id"].map(vz) * 730 / c["setor_id"].map(soma_setor)).astype(float)

    f = pd.DataFrame({
        "matricula": m, "referencia": referencia_modelo, "categoria": c["categoria"],
        "queda_pct": queda, "consumo_base_m3": base, "leitura_real": leitura_real,
        "proporcao_estimadas": e[:, ult - 5:ult + 1].mean(axis=1),
        "irregularidades_anteriores": m.map(irreg).fillna(0).astype(int),
        "tentativas_sem_acesso": m.map(sem_acesso).fillna(0).astype(int),
        "meses_desde_ultima_visita": meses_visita,
        "setor_ausente": c["setor_id"].isna(), "indice_vazao_setor": idx_setor,
        "imovel_vazio": c["situacao_imovel"] == "desocupado",
        "troca_hidrometro_recente": m.isin(set(recente_t["matricula"])),
        "queda_sazonal": sazonal,
        "mudanca_de_uso": m.isin(set(recente_h["matricula"])),
    })
    # A virada do curso, no mesmo formato do slide:
    f["queda_explicada"] = (f["imovel_vazio"] | f["troca_hidrometro_recente"]
                            | f["queda_sazonal"] | f["mudanca_de_uso"])
    return f


def construir_referencia(val, est, cad, trocas, hist, vazao, os_rot, referencia, cfg_modelo) -> pd.DataFrame:
    """Features de TODAS as ligações na referência corrente."""
    return calcular(val, est, JANELA - 1, cad, trocas, hist, vazao, os_rot, referencia,
                    inicio_do_mes(referencia), cfg_modelo)


def construir_treino(val, est, cad, trocas, hist, vazao, os_rot, referencia, cfg_modelo,
                     meses_atras: range = range(1, 6)) -> pd.DataFrame:
    """Uma linha por visita passada rotulada, com features como de um mês antes da visita."""
    partes = []
    pos = pd.Series(np.arange(len(cad)), index=cad["matricula"])
    ins = os_rot[(os_rot["tipo_os"] == "inspecao") & os_rot["rotulado"]]
    for k in meses_atras:
        ref_k = str(pd.Period(referencia, "M") - k)
        ini = inicio_do_mes(ref_k)
        visitas = ins[(ins["data_visita"] >= ini) & (ins["data_visita"] < ini + pd.offsets.MonthBegin(1))]
        visitas = visitas[visitas["motivo_nao_acesso"].isna()]       # sem acesso = sem rótulo de verdade
        linhas = pos.reindex(visitas["matricula"].unique()).dropna().astype(int).to_numpy()
        if len(linhas) == 0:
            continue
        f = calcular(val, est, JANELA - 1 - k, cad, trocas, hist, vazao, os_rot, ref_k, ini, cfg_modelo, linhas)
        f = f.merge(visitas.drop_duplicates("matricula")[["matricula", "irregularidade"]], on="matricula")
        partes.append(f)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def executar(ctx) -> dict:
    ref, arm = ctx.referencia, ctx.arm
    cad = arm.ler("cadastro", ref)
    cons = arm.ler("consumo", ref)
    trocas = arm.ler("trocas", ref)
    hist = arm.ler("historico_categoria", ref)
    vazao = arm.ler("vazao_setor", ref)
    os_ = arm.ler("ordem_servico", ref)
    rot = arm.ler("rotulo_visita", ref)
    os_rot = os_.merge(rot[["os_id", "irregularidade", "tipo", "motivo_nao_acesso"]], on="os_id", how="left")
    os_rot["rotulado"] = os_rot["irregularidade"].notna()
    os_rot["irregularidade"] = os_rot["irregularidade"].fillna(False).astype(bool)

    # só leitura REAL entra no cálculo de queda; a proporção de estimadas vira feature
    val, est = matriz_consumo(cons, pd.Index(cad["matricula"]), ref)
    mm = ctx.cfg["modelo"]
    atual = construir_referencia(val, est, cad, trocas, hist, vazao, os_rot, ref, mm)
    atual = ctx.validar("features_ligacao", atual, "features", "saida")
    treino = construir_treino(val, est, cad, trocas, hist, vazao, os_rot, ref, mm)
    arm.gravar("features_ligacao", ref, atual)
    arm.gravar("features_treino", ref, treino)
    c = {"ligacoes_com_features": int(len(atual)), "linhas_de_treino": int(len(treino)),
         "ligacoes_queda_explicada": int(atual["queda_explicada"].sum())}
    ctx.log("features", "concluida", **c)
    return c

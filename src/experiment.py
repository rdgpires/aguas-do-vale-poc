"""Experimento A/B por simulação.

6 equipes seguem a regra antiga, 6 seguem a fila da PoC. As ligações são repartidas entre os
grupos por paridade da matrícula (duas metades equivalentes), e cada grupo monta a fila com
as MESMAS restrições (mesmo componente `queue`). O resultado de cada visita vem da verdade
oculta da base sintética: nada aqui é medido sobre o que o modelo já viu.

    python -m src.experiment --mes 2026-08 --formulacao v1
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import typer

from . import queue as fila
from .comum import Contexto, carregar_config, dias_efetivos, dias_uteis
from .regra_antiga import regra_antiga

CAUSAS = {"vazio": "imovel_vazio", "troca": "troca_hidrometro", "sazonal": "sazonalidade",
          "mudanca": "mudanca_de_uso", "oscilacao": "sem_causa_identificada", "nenhuma": "sem_causa_identificada",
          "irregular": "irregular"}


def _u(matricula: pd.Series) -> np.ndarray:
    """Número em [0,1) determinístico por matrícula: o mesmo imóvel dá o mesmo acesso nas duas
    formulações e nos dois grupos (comparação pareada, sem ruído de sorteio)."""
    return ((matricula.astype("int64") * 2654435761) % 2**32 / 2**32).to_numpy()


def _simular_visitas(visitas: pd.DataFrame, verdade: pd.DataFrame, cond: pd.Series, p_na: tuple[float, float]) -> dict:
    v = visitas[["matricula"]].merge(verdade, on="matricula", how="left")
    v["condominio"] = v["matricula"].map(cond).fillna(False).to_numpy()
    corte = np.where(v["condominio"], p_na[0], p_na[1])
    sem_acesso = _u(v["matricula"]) < corte
    acerto = v["irregular"].fillna(False).to_numpy() & ~sem_acesso
    causa = v["causa"].map(CAUSAS).fillna("sem_causa_identificada")
    sem_irreg = causa[~acerto & ~sem_acesso].value_counts().to_dict()
    n = len(v)
    vol = float(v.loc[acerto, "perda_m3_mes"].sum())
    return {"visitas": n, "acertos": int(acerto.sum()), "taxa_acerto": float(acerto.mean()) if n else 0.0,
            "volume_recuperado_m3_mes": round(vol, 1), "volume_por_visita_m3": round(vol / n, 3) if n else 0.0,
            "sem_acesso": int(sem_acesso.sum()),
            "sem_irregularidade_por_causa": {k: int(x) for k, x in sem_irreg.items()}}


def simular(ctx: Contexto, formulacao: str) -> dict:
    cfg, ref, arm = ctx.cfg, ctx.referencia, ctx.arm
    ex = cfg["experimento"]
    # sempre repontua: score guardado de uma base anterior daria um A/B de dados diferentes
    ctx.formulacao = formulacao
    from .pipeline import ETAPAS
    ETAPAS["modelo"](ctx)
    cad = arm.ler("cadastro", ref)
    feats = arm.ler("features_ligacao", ref)
    score = arm.ler("score_ligacao", ref, formulacao)
    verdade = pd.read_parquet(ex["verdade_oculta"])[["matricula", "irregular", "causa", "perda_m3_mes"]]
    cons = arm.ler("consumo", ref)

    grupo = (feats["matricula"].astype("int64") % 2).to_numpy()     # 0 = regra antiga, 1 = PoC
    eq = {e["equipe_id"]: e for e in cfg["equipes"]}
    dias = dias_uteis(ref)[:dias_efetivos(cfg, len(cad))]
    restr = fila.Restricoes.do_config(cfg)
    base = cad[["matricula", "categoria", "bairro", "regiao", "condominio"]]

    # grupo A: regra antiga
    r = regra_antiga(feats[grupo == 0], cfg["meses_sem_visita"]).merge(base, on="matricula", suffixes=("_f", ""))
    r["motivo"] = "Queda de " + (r["queda_pct"] * 100).round().astype(int).astype(str) + "% no consumo"
    f_regra, _ = fila.montar_fila(r, [eq[i] for i in ex["grupo_regra"]], dias, restr)
    # grupo B: PoC
    rk = fila.preparar_ranking(score[grupo == 1], cad, feats[grupo == 1], formulacao, cfg["meses_sem_visita"])
    f_poc, _ = fila.montar_fila(rk, [eq[i] for i in ex["grupo_poc"]], dias, restr)

    cond = cad.set_index("matricula")["condominio"]
    p_na = (0.35, 0.08)          # mesmas probabilidades do gerador: acesso incerto em condomínio
    rg = _simular_visitas(f_regra, verdade, cond, p_na)
    pc = _simular_visitas(f_poc, verdade, cond, p_na)

    # --- conversão em valor ---
    ult12 = str(pd.Period(ref, "M") - 12)
    cats = cons["referencia"].cat.categories
    ok = np.array([str(c) >= ult12 for c in cats])[cons["referencia"].cat.codes.to_numpy()]
    vol_ano = float(cons.loc[ok, "consumo_m3"].sum())
    visitas_empresa = len(dias) * len(cfg["equipes"]) * cfg["visitas_por_equipe"]
    d_vol = pc["volume_por_visita_m3"] - rg["volume_por_visita_m3"]
    extra_mes = d_vol * visitas_empresa
    pp_1fila = (extra_mes * 12) / (vol_ano / 100) if vol_ano else 0.0
    valor = ex["valor_ponto_pp_ano_reais"]
    rel = {
        "referencia": ref, "formulacao": formulacao, "escala_ligacoes": int(len(cad)), "dias": len(dias),
        "regra_antiga": rg, "poc": pc,
        "linha_de_base_taxa": ex["taxa_acerto_base"],
        "poc_menos_regra_pp": round((pc["taxa_acerto"] - rg["taxa_acerto"]) * 100, 2),
        "poc_menos_base_pp": round((pc["taxa_acerto"] - ex["taxa_acerto_base"]) * 100, 2),
        "delta_volume_por_visita_m3": round(d_vol, 3),
        "visitas_empresa_mes": visitas_empresa,
        "volume_anual_faturado_m3": round(vol_ano),
        "ganho_pontos_perda_aparente_1_fila": round(pp_1fila, 4),
        "ganho_reais_ano_1_fila": round(pp_1fila * valor),
        "ganho_pontos_perda_aparente_12_filas": round(pp_1fila * 12, 4),
        "ganho_reais_ano_12_filas": round(pp_1fila * 12 * valor),
        "poc_vence_regra": bool(pc["taxa_acerto"] > rg["taxa_acerto"]),
    }
    arm.gravar_json("experimento", f"{ref}_{formulacao}", rel)
    return rel


def imprimir(rel: dict) -> None:
    r, p = rel["regra_antiga"], rel["poc"]
    print(f"A/B {rel['referencia']} formulação {rel['formulacao']}  ({r['visitas']} + {p['visitas']} visitas)")
    print(f"  regra antiga : {r['taxa_acerto']:.1%} de acerto, {r['volume_por_visita_m3']:.2f} m3/visita")
    print(f"  PoC          : {p['taxa_acerto']:.1%} de acerto, {p['volume_por_visita_m3']:.2f} m3/visita")
    print(f"  PoC - regra  : {rel['poc_menos_regra_pp']:+.1f} pp  |  PoC - 1 em 5: {rel['poc_menos_base_pp']:+.1f} pp")
    print(f"  ganho (1 fila mensal): {rel['ganho_pontos_perda_aparente_1_fila']:.3f} pp de perda aparente "
          f"~ R$ {rel['ganho_reais_ano_1_fila']:,}/ano".replace(",", "."))
    print("  visitas sem irregularidade (PoC):", p["sem_irregularidade_por_causa"], "sem acesso:", p["sem_acesso"])
    print("  visitas sem irregularidade (regra):", r["sem_irregularidade_por_causa"], "sem acesso:", r["sem_acesso"])


app = typer.Typer(add_completion=False)


@app.command()
def main(mes: str = typer.Option(None), formulacao: str = typer.Option(None)) -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = carregar_config()
    ctx = Contexto.criar(cfg, mes, formulacao)
    imprimir(simular(ctx, ctx.formulacao))


if __name__ == "__main__":
    app()

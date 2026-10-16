"""Orquestração e CLI.

    python -m src.pipeline --mes 2026-08 [--formulacao v2] [--etapa rotulagem]

Cada etapa é uma função `executar(ctx) -> dict` que lê e grava só pela camada de
armazenamento, é idempotente por partição (mês) e pode rodar isolada. Trocar este arquivo
por um DAG do Airflow/Prefect é mapear uma task por entrada de ETAPAS.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime

import typer

from . import extract, features, label_llm, model
from . import queue as fila
from .comum import Contexto, carregar_config

ETAPAS = {
    "extracao": extract.executar,
    "rotulagem": label_llm.executar,
    "features": features.executar,
    "modelo": model.executar,
    "fila": fila.executar,
}


def _n(x: int) -> str:
    return f"{x:,}".replace(",", ".")


def resumo(c: dict[str, dict]) -> str:
    L = []
    if "extracao" in c:
        L.append(f"[extração]  {_n(c['extracao']['ligacoes_lidas'])} ligações lidas")
    if "rotulagem" in c:
        L.append(f"[rotulagem] {_n(c['rotulagem']['anotacoes_rotuladas'])} anotações rotuladas")
    if "modelo" in c:
        L.append(f"[modelo]    {_n(c['modelo']['ligacoes_pontuadas'])} ligações pontuadas")
    if "fila" in c:
        f = c["fila"]
        L.append(f"[fila]      {_n(f['visitas_no_mes'])} visitas no mês "
                 f"({f['equipes']} equipes × {f['visitas_por_equipe']} × {f['dias']} dias)")
    return "\n".join(L)


def rodar(ctx: Contexto, etapas: list[str]) -> dict:
    inicio = datetime.now()
    for nome in etapas:
        t0 = time.time()
        ctx.log(nome, "inicio")
        ctx.contagens[nome] = ETAPAS[nome](ctx)
        ctx.contagens[nome]["segundos"] = round(time.time() - t0, 1)
        pend = ctx.pendencias_df()
        ctx.arm.gravar("pendencia", ctx.referencia, pend[pend["etapa"] == _etapa_pend(nome)].reset_index(drop=True),
                       variante=nome)
    pend = ctx.pendencias_df()
    por_motivo = (pend.assign(motivo=pend["motivo"].str.replace(r"\(.*\)|:.*", "", regex=True))
                  .groupby(["etapa", "motivo"]).size().reset_index(name="n").to_dict("records")) if len(pend) else []
    manifesto = {"run_id": ctx.run_id, "referencia": ctx.referencia, "formulacao": ctx.formulacao,
                 "inicio": inicio.isoformat(timespec="seconds"), "fim": datetime.now().isoformat(timespec="seconds"),
                 "etapas": etapas, "contagens": ctx.contagens, "pendencias": por_motivo,
                 "pendencias_total": int(len(pend)), "llm": ctx.llm_uso, "validacoes": ctx.validacoes,
                 "config": ctx.cfg}
    ctx.arm.gravar_json("execucoes", ctx.run_id, manifesto)
    return manifesto


def _etapa_pend(nome: str) -> str:
    return {"extracao": "extracao", "rotulagem": "rotulagem", "features": "features", "modelo": "modelo",
            "fila": "fila"}[nome]


app = typer.Typer(add_completion=False, help="Pipeline da PoC Águas do Vale")


@app.command()
def main(mes: str = typer.Option(None, help="Mês de referência YYYY-MM"),
         formulacao: str = typer.Option(None, help="v1 | v2 (sobrescreve o config.yaml)"),
         etapa: str = typer.Option(None, help=f"Uma etapa: {', '.join(ETAPAS)}"),
         config: str = typer.Option("config.yaml", help="Caminho do config")) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ctx = Contexto.criar(carregar_config(config), mes, formulacao)
    if etapa and etapa not in ETAPAS:
        raise typer.BadParameter(f"etapa desconhecida: {etapa}")
    rodar(ctx, [etapa] if etapa else list(ETAPAS))
    print(resumo(ctx.contagens))
    print(f"run_id={ctx.run_id}  formulação={ctx.formulacao}  pendências={len(ctx.pendencias_df())}")


if __name__ == "__main__":
    app()

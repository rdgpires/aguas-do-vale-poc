"""Avaliação dos rótulos (não é teste unitário).

Compara o rotulador com a amostra revisada à mão (`eval/amostra_revisada.csv`) e reporta a
concordância por campo e o tamanho da amostra.

Futuro: este mesmo conjunto vira teste de regressão no CI (falha se a concordância cair
abaixo de um piso ao trocar prompt ou modelo). Documentado em docs/handoff.md; sem CI aqui.

    python -m src.evaluate
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import typer

from .comum import Contexto, carregar_config
from .label_llm import rotular_texto
from .llm.cliente import criar_cliente
from .llm.mascaramento import mascarar

CAMPOS = ["irregularidade", "tipo", "motivo_nao_acesso"]


def _nulo(x):
    return None if pd.isna(x) else x


def avaliar(cfg: dict, caminho: str = "eval/amostra_revisada.csv") -> dict:
    gab = pd.read_csv(caminho)
    cl = criar_cliente(cfg["llm"])
    base = Path(cfg["llm"]["prompt"]).read_text(encoding="utf-8")
    pred = []
    for texto in gab["anotacao"]:
        r = rotular_texto(cl, base, mascarar(texto), cfg["llm"]["tentativas"], cfg["llm"]["espera_inicial_s"])
        pred.append(r.model_dump() if not isinstance(r, str) else {c: "ERRO" for c in CAMPOS})
    p = pd.DataFrame(pred)
    rel = {"n_amostra": int(len(gab)), "fonte": cl.fonte, "modelo": cl.modelo, "concordancia": {}}
    erros = []
    for c in CAMPOS:
        a = gab[c].map(_nulo).astype(object).reset_index(drop=True)
        b = p[c].map(_nulo).astype(object).reset_index(drop=True)
        ok = (a == b) | (a.isna() & b.isna())
        rel["concordancia"][c] = round(float(ok.mean()), 4)
        for i in ok[~ok].index[:5]:
            erros.append({"campo": c, "anotacao": gab["anotacao"][i], "revisado": a[i], "rotulador": b[i]})
    irr = gab["irregularidade"].astype(bool).reset_index(drop=True)
    rel["concordancia_tipo_entre_irregulares"] = round(float(
        (gab["tipo"].reset_index(drop=True)[irr] == p["tipo"][irr]).mean()), 4)
    rel["exemplos_de_divergencia"] = erros
    return rel


app = typer.Typer(add_completion=False)


@app.command()
def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = carregar_config()
    rel = avaliar(cfg)
    ctx = Contexto.criar(cfg)
    ctx.arm.gravar_json("avaliacao_rotulos", ctx.referencia, rel)
    print(f"Amostra revisada: {rel['n_amostra']} anotações | rotulador: {rel['fonte']} ({rel['modelo']})")
    for c, v in rel["concordancia"].items():
        print(f"  {c:<20} {v:.1%}")
    print(f"  tipo (só entre irregulares) {rel['concordancia_tipo_entre_irregulares']:.1%}")
    for e in rel["exemplos_de_divergencia"][:6]:
        print(f"  [{e['campo']}] {e['anotacao'][:60]!r}: revisado={e['revisado']} rotulador={e['rotulador']}")


if __name__ == "__main__":
    app()

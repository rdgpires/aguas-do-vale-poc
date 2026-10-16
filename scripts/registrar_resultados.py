"""Roda A/B (v1 e v2), avalia os rótulos e grava docs/resultados_calibrados.md.

    python -m scripts.registrar_resultados

Os números abaixo vão para os slides. A condição de calibração é verificada aqui:
regra antiga ~ 1 em 5; v1 abaixo da regra; v2 acima, com ganho modesto; maiores quedas
concentradas em casos explicados.
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from src.comum import Contexto, carregar_config
from src.evaluate import avaliar
from src.experiment import simular


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = carregar_config()
    ctx = Contexto.criar(cfg)
    r1, r2 = simular(ctx, "v1"), simular(ctx, "v2")
    rot = avaliar(cfg)
    ctx.arm.gravar_json("avaliacao_rotulos", ctx.referencia, rot)

    f = ctx.arm.ler("features_ligacao", ctx.referencia)
    v = pd.read_parquet(cfg["experimento"]["verdade_oculta"])
    d = f.merge(v, on="matricula")
    d = d[d["leitura_real"] & d["queda_pct"].notna()]
    top = d.nlargest(max(1, int(len(d) * 0.01)), "queda_pct")
    inocente = float((~top["irregular"]).mean())
    sinalizada = float(top["queda_explicada"].mean())

    regra, v1, v2 = r1["regra_antiga"], r1["poc"], r2["poc"]
    cond = [
        ("regra antiga ≈ 20% (entre 17% e 23%)", 0.17 <= regra["taxa_acerto"] <= 0.23),
        ("PoC v1 abaixo da regra antiga", v1["taxa_acerto"] < regra["taxa_acerto"]),
        ("PoC v2 acima da regra, ganho modesto (1 a 10 pp)", 0.01 <= v2["taxa_acerto"] - regra["taxa_acerto"] <= 0.10),
        ("maiores quedas concentradas em casos explicados (>= 90% das 1% maiores)", inocente >= 0.90),
    ]
    causas = ["imovel_vazio", "troca_hidrometro", "sazonalidade", "mudanca_de_uso", "sem_causa_identificada"]

    def linha(nome, g):
        c = g["sem_irregularidade_por_causa"]
        return f"| {nome} | " + " | ".join(str(c.get(k, 0)) for k in causas) + f" | {g['sem_acesso']} |"

    L = [
        "# Resultados calibrados", "",
        f"Gerado por `python -m scripts.registrar_resultados` em {date.today():%d/%m/%Y}. "
        f"Base: {r2['escala_ligacoes']:,} ligações".replace(",", ".")
        + f", semente 42, referência {r2['referencia']}, "
        f"{regra['visitas']} visitas por grupo ({r2['dias']} dias × 6 equipes × 8).", "",
        "## Taxa de acerto das visitas", "",
        "| Estratégia | Visitas | Irregularidades | Acerto | Volume recuperado por visita (m³/mês) |",
        "|---|---|---|---|---|",
        f"| Regra antiga | {regra['visitas']} | {regra['acertos']} | **{pct(regra['taxa_acerto'])}** | {regra['volume_por_visita_m3']:.2f} |",
        f"| PoC v1 (queda de consumo) | {v1['visitas']} | {v1['acertos']} | **{pct(v1['taxa_acerto'])}** | {v1['volume_por_visita_m3']:.2f} |",
        f"| PoC v2 (queda inexplicada) | {v2['visitas']} | {v2['acertos']} | **{pct(v2['taxa_acerto'])}** | {v2['volume_por_visita_m3']:.2f} |",
        "", f"Linha de base do discovery: {pct(cfg['experimento']['taxa_acerto_base'])} (1 em 5).",
        f"v2 contra a regra: {r2['poc_menos_regra_pp']:+.1f} pp; v1 contra a regra: {r1['poc_menos_regra_pp']:+.1f} pp.", "",
        "## Para onde o modelo mandou as equipes (visitas sem irregularidade, por causa)", "",
        "| Estratégia | Imóvel vazio | Troca de hidrômetro | Sazonalidade | Mudança de uso | Sem causa identificada | Sem acesso |",
        "|---|---|---|---|---|---|---|",
        linha("Regra antiga", regra), linha("PoC v1", v1), linha("PoC v2", v2), "",
        "## Valor (conversão do ganho da v2 contra a regra antiga)", "",
        f"- Diferença de volume por visita: {r2['delta_volume_por_visita_m3']:+.2f} m³/mês.",
        f"- Visitas da empresa por mês: {r2['visitas_empresa_mes']}.",
        f"- **Uma fila mensal** da v2: {r2['ganho_pontos_perda_aparente_1_fila']:.3f} pp de perda aparente "
        f"≈ R$ {r2['ganho_reais_ano_1_fila']:,}/ano.".replace(",", "."),
        f"- **Doze filas mensais** (efeito acumulado ao fim do ano): {r2['ganho_pontos_perda_aparente_12_filas']:.3f} pp "
        f"≈ R$ {r2['ganho_reais_ano_12_filas']:,}/ano.".replace(",", "."),
        f"- Premissa do caso: 1 pp de perda aparente ≈ R$ {cfg['experimento']['valor_ponto_pp_ano_reais']:,}/ano.".replace(",", "."),
        "", "> Estimativa, não promessa: assume que a perda recuperada persiste, que não há reincidência "
        "e que o volume por visita se mantém ao repetir a fila todo mês.",
        "", "## Concordância dos rótulos", "",
        f"Rotulador: **{rot['fonte']}** ({rot['modelo']}), amostra revisada de {rot['n_amostra']} anotações.", "",
        "| Campo | Concordância |", "|---|---|",
        *[f"| {c} | {pct(x)} |" for c, x in rot["concordancia"].items()],
        f"| tipo (apenas entre as irregulares) | {pct(rot['concordancia_tipo_entre_irregulares'])} |", "",
        "O modo offline é um rotulador por regras: o LLM real deve cobrir melhor a gíria de campo "
        "(`hd morto`, `puxadinho no ramal`).", "",
        "## Maiores quedas de consumo", "",
        f"Entre as {len(top)} maiores quedas (1% do total com leitura real), **{pct(inocente)}** não são "
        f"irregularidade (imóvel vazio, troca, sazonalidade, uso). Só {pct(sinalizada)} delas têm a explicação "
        "registrada nos sistemas, e é essa lacuna que a v2 explora até onde o dado permite.", "",
        "## Condições de calibração", "",
        *[f"- [{'x' if ok else ' '}] {t}" for t, ok in cond], "",
    ]
    Path("docs").mkdir(exist_ok=True)
    Path("docs/resultados_calibrados.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    if not all(ok for _, ok in cond):
        sys.exit("calibração fora das condições: ajuste PARAMS em scripts/gerar_base.py")


if __name__ == "__main__":
    main()

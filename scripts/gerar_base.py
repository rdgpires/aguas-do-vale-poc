"""Gerador da base sintética (formato BRUTO, com os problemas de qualidade do discovery).

    python -m scripts.gerar_base --escala 50000 --semente 42

Modelo do mundo (é isto que torna a virada v1 -> v2 reproduzível):

* ~30% das ligações têm UM evento de queda de consumo, com início nos 6 últimos meses.
* Cada evento tem uma causa OCULTA: irregularidade real (perda aparente) ou uma causa
  inocente (imóvel vazio, troca de hidrômetro, sazonalidade, mudança de uso, oscilação).
* As quedas inocentes são, em geral, as maiores. Imóvel vazio chega perto de 100%.
* Parte das explicações NÃO está registrada nos sistemas (cadastro desatualizado):
  é o que impede a v2 de ser perfeita, e é por isso que o ganho dela é modesto.
* A "verdade oculta" é gravada à parte e só o simulador do A/B e o gabarito a usam.

Os parâmetros calibrados estão em PARAMS, no topo, para serem ajustados em um lugar só.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

T = 24  # meses de histórico: 24 permite comparar com o mesmo mês do ano anterior

PARAMS = {
    "p_evento": 0.30,
    # mistura de causas entre os eventos
    "mix": {"irregular": 0.17, "vazio": 0.26, "troca": 0.17, "sazonal": 0.12, "mudanca": 0.10,
            "oscilacao": 0.18},
    "tipos_irregular": {"hidrometro_parado": 0.50, "ligacao_clandestina": 0.30,
                        "cadastro_errado": 0.15, "outro": 0.05},
    # faixa da queda real (min, max) por subtipo
    "queda": {"hidrometro_parado": (0.60, 0.95), "ligacao_clandestina": (0.40, 0.80),
              "cadastro_errado": (0.20, 0.50), "outro": (0.30, 0.60),
              "vazio": (0.50, 0.90),   # vazio parcial; ver vazio_quase_zero
              "troca": (0.40, 0.85), "sazonal": (0.35, 0.75),
              "mudanca": (0.40, 0.90), "oscilacao": (0.30, 0.60)},
    # fração das explicações que está de fato registrada nos sistemas
    "registrado": {"vazio": 0.67, "troca": 0.72, "mudanca": 0.72, "sazonal": 1.0},
    # imóvel vazio costuma ir para quase zero (>90%): é o "conhecimento tácito" da regra antiga
    "vazio_quase_zero": 0.70, "queda_quase_zero": (0.93, 1.00),
    "p_visita_historica": 0.35,     # fração dos eventos já visitada em meses passados
    "p_visita_antiga": 0.04,        # visitas anteriores ao último semestre (reincidência)
    "p_sem_acesso_cond": 0.35,
    "p_sem_acesso": 0.08,
    "p_estimada": 0.12,
    "p_nota_vaga": 0.05,            # técnico escreve algo que não permite decidir
    "p_duplicada": 0.04,
}

CATEGORIAS = ["residencial", "comercial", "industrial", "publica"]
P_CAT = [0.82, 0.13, 0.02, 0.03]
BASE_M3 = {"residencial": (14, 0.45), "comercial": (45, 0.55), "industrial": (180, 0.55), "publica": (60, 0.5)}
REGIOES = ["norte", "sul", "leste", "oeste", "centro", "jardim_alto"]
P_REG = [0.18, 0.20, 0.20, 0.17, 0.15, 0.10]
P_COND = {"norte": 0.15, "sul": 0.08, "leste": 0.08, "oeste": 0.08, "centro": 0.10, "jardim_alto": 0.60}
PRIMEIROS = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fabio", "Gisele", "Hugo", "Iara", "Joao",
             "Karen", "Lucas", "Marta", "Nelson", "Olivia", "Paulo", "Rita", "Sergio", "Tania", "Vitor"]
SOBRENOMES = ["Silva", "Souza", "Oliveira", "Santos", "Lima", "Pereira", "Costa", "Ribeiro", "Alves",
              "Carvalho", "Gomes", "Martins", "Rocha", "Barbosa", "Dias", "Nunes", "Teixeira", "Moraes"]

TEXTOS = {
    ("irregular", "hidrometro_parado"): [
        "hd parado, ponteiro nao gira", "hidrometro parado - necessario troca", "hidr. travado n registra consumo",
        "hd parado/travado, notificado", "constatado hd parado. notif. emitida", "medidor parado, lacre ok",
        "hd morto, nao anda", "medidor nao marca nada, trocar"],
    ("irregular", "ligacao_clandestina"): [
        "ligacao clandestina antes do hd", "gato no ramal, notificado", "desvio no cavalete (gato)",
        "lig. clandest. detectada, corte efetuado", "by-pass no hidrometro, irregular", "ligacao direta s/ hd",
        "agua puxada direto da rede, sem passar no hd", "puxadinho no ramal, notif."],
    ("irregular", "cadastro_errado"): [
        "cadastro errado, consta resid. mas funciona comercio", "categ. incorreta, imovel comercial lancado como resid.",
        "end. nao confere c/ cadastro", "cadastro desatualizado, atualizar categ.", "virou loja, ainda lancado como casa"],
    ("irregular", "outro"): [
        "lacre rompido, violacao do hd", "violacao de lacre, irregular", "irregularidade: hd invertido"],
    ("regular", None): [
        "tudo ok, sem irregularidade", "ligacao regular, hd girando normal", "nada constatado",
        "hd ok, consumo compativel", "imovel vazio, sem consumo, regular", "visita realizada, s/ alteracao", "regular"],
    ("acesso", "condominio"): [
        "cond. fechado, portaria nao autorizou", "n teve acesso, condominio", "condominio s/ acesso, sindico n autorizou",
        "cond fechado, nao entrou", "porteiro barrou a entrada"],
    ("acesso", "ausente"): [
        "morador ausente, n atendeu", "ausente. retornar", "ninguem em casa", "n tinha ninguem, deixado aviso", "ninguem abriu, voltar outro dia", "casa fechada, sem resposta"],
    ("acesso", "recusa"): [
        "morador recusou acesso", "recusa de entrada, n permitiu", "cliente n permitiu inspecao", "nao quis deixar entrar"],
    ("acesso", "outro"): [
        "cachorro bravo, n entrei", "chuva forte, n foi possivel", "acesso bloqueado por obra"],
    ("vaga", None): ["verificar", "ver obs. anterior", "hd com leitura estranha, voltar", "possivel desvio, confirmar"],
}
RUAS = ["Rua das Flores", "Av. Brasil", "Rua Sao Jose", "Travessa do Comercio", "Rua XV de Novembro"]


def _typo(txt: str, py: random.Random) -> str:
    if len(txt) < 6 or py.random() > 0.18:
        return txt
    i = py.randrange(1, len(txt) - 1)
    op = py.choice(["del", "dup", "swap"])
    if op == "del":
        return txt[:i] + txt[i + 1:]
    if op == "dup":
        return txt[:i] + txt[i] + txt[i:]
    return txt[:i - 1] + txt[i] + txt[i - 1] + txt[i + 1:]


def _pii(txt: str, nome: str, py: random.Random) -> str:
    if py.random() < 0.25:
        quem = nome if py.random() < 0.6 else f"{py.choice(PRIMEIROS)} {py.choice(SOBRENOMES)}"
        cpf = f"{py.randrange(10**11):011d}"
        cpf = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if py.random() < 0.6 else cpf
        tel = f"({py.randrange(11, 99)}) 9{py.randrange(10**4):04d}-{py.randrange(10**4):04d}"
        txt += py.choice([f". Falei c/ Sr(a). {quem}, CPF {cpf}", f" - resp. {quem} tel {tel}",
                          f". Titular {quem} cpf {cpf} tel {tel}"])
    if py.random() < 0.12:
        txt += f". {py.choice(RUAS)}, {py.randrange(1, 2000)}, apto {py.randrange(1, 300)}"
    return txt


def _resultado(irregular: bool, tipo: str | None, condominio: bool, py: random.Random, forcar_acesso=None):
    """(irregularidade, tipo, motivo, texto, esperado_do_texto)."""
    p_na = PARAMS["p_sem_acesso_cond"] if condominio else PARAMS["p_sem_acesso"]
    if py.random() < p_na:
        if condominio and py.random() < 0.75:
            mot = "condominio"
        else:
            mot = py.choice(["ausente", "ausente", "recusa", "outro"])
        return False, None, mot, py.choice(TEXTOS[("acesso", mot)])
    if py.random() < PARAMS["p_nota_vaga"]:
        return False, None, None, py.choice(TEXTOS[("vaga", None)])
    if irregular:
        return True, tipo, None, py.choice(TEXTOS[("irregular", tipo)])
    return False, None, None, py.choice(TEXTOS[("regular", None)])


def _variar_matricula(m: str, existentes: set[str], py: random.Random) -> str:
    r = py.random()
    if r < 0.45:
        return m.lstrip("0") or "0"
    if r < 0.55:
        return f"{m[:4]}-{m[4:]}" if py.random() < 0.5 else f" {m} "
    if r < 0.58:
        i = py.randrange(7)
        d = py.choice([c for c in "0123456789" if c != m[i]])
        return m[:i] + d + m[i + 1:]
    if r < 0.59:
        while True:
            g = f"{py.randrange(10**7):07d}"
            if g not in existentes:
                return g
    return m


def gerar(escala: int, semente: int, referencia: str = "2026-08", raiz: Path = Path("data")) -> dict:
    rng = np.random.default_rng(semente)
    py = random.Random(semente)
    N = escala
    ref = pd.Period(referencia, "M")
    meses = [ref - T + i for i in range(T)]
    mes_str = np.array([str(m) for m in meses])
    mes_ini = [m.to_timestamp() for m in meses]
    onda = 1 + 0.07 * np.cos(2 * np.pi * (np.array([m.month for m in meses]) - 1) / 12)

    # ---- cadastro -------------------------------------------------------------------
    nums = rng.choice(10_000_000, size=N, replace=False)
    matr = np.char.zfill(nums.astype(str), 7)
    existentes = set(matr.tolist())
    cat = rng.choice(CATEGORIAS, N, p=P_CAT)
    reg = rng.choice(REGIOES, N, p=P_REG)
    cond = rng.random(N) < np.vectorize(P_COND.get)(reg)
    nset = max(N // 250, 1)
    setor = np.char.add("S", np.char.zfill(rng.integers(0, nset, N).astype(str), 4)).astype(object)
    setor[rng.random(N) < 0.03] = None
    bairro = np.char.add(np.char.add(reg, "_b"), rng.integers(1, 7, N).astype(str))
    nome = np.char.add(np.char.add(rng.choice(PRIMEIROS, N), " "), rng.choice(SOBRENOMES, N))

    # ---- eventos --------------------------------------------------------------------
    mix = PARAMS["mix"]
    evento = rng.random(N) < PARAMS["p_evento"]
    onset = rng.integers(18, 24, N)
    causa = np.where(evento, rng.choice(list(mix), N, p=list(mix.values())), "nenhuma").astype(object)
    ti = PARAMS["tipos_irregular"]
    tipo = np.where(causa == "irregular", rng.choice(list(ti), N, p=list(ti.values())), None).astype(object)
    sub = np.where(causa == "irregular", tipo, causa).astype(object)
    lo = np.zeros(N)
    hi = np.zeros(N)
    for k, (a, b) in PARAMS["queda"].items():
        lo[sub == k], hi[sub == k] = a, b
    queda = np.where(evento, lo + (hi - lo) * rng.random(N), 0.0)
    zero = (causa == "vazio") & (rng.random(N) < PARAMS["vazio_quase_zero"])
    a, b = PARAMS["queda_quase_zero"]
    queda[zero] = a + (b - a) * rng.random(zero.sum())
    dur = np.full(N, 99)
    dur[causa == "sazonal"] = 3
    osc = causa == "oscilacao"
    dur[osc] = rng.integers(1, 4, osc.sum())

    # situação do imóvel (flag imovel_vazio sai daqui)
    sit = rng.choice(["ocupado", "desconhecido"], N, p=[0.90, 0.10]).astype(object)
    vz = causa == "vazio"
    sit[vz] = np.where(rng.random(vz.sum()) < PARAMS["registrado"]["vazio"], "desocupado", "desconhecido")
    irr = causa == "irregular"
    sit[irr & (rng.random(N) < 0.04)] = "desocupado"

    # ---- consumo --------------------------------------------------------------------
    mu = np.array([BASE_M3[c][0] for c in cat])
    sg = np.array([BASE_M3[c][1] for c in cat])
    base = np.exp(np.log(mu) + sg * rng.standard_normal(N) - sg ** 2 / 2)
    t = np.arange(T)[None, :]
    ativo = (t >= onset[:, None]) & (t < (onset + dur)[:, None])
    saz = causa == "sazonal"
    ativo |= saz[:, None] & (t >= (onset - 12)[:, None]) & (t < (onset - 12 + 3)[:, None])
    normal = base[:, None] * onda[None, :]
    real = normal * np.exp(0.07 * rng.standard_normal((N, T))) * (1 - queda[:, None] * ativo)
    estim = rng.random((N, T)) < PARAMS["p_estimada"]
    cons = np.where(estim, normal, real).clip(min=0).round(1)

    # trocas e mudanças de uso (registradas só em parte)
    troca_rec = (causa == "troca") & (rng.random(N) < PARAMS["registrado"]["troca"])
    mud_rec = (causa == "mudanca") & (rng.random(N) < PARAMS["registrado"]["mudanca"])
    hid_orig = np.arange(N)
    hid_novo = N + np.arange(N)
    hid = np.where(troca_rec[:, None] & (t >= onset[:, None]), hid_novo[:, None], hid_orig[:, None])
    hid_dic = np.char.add("H", np.char.zfill(np.arange(2 * N).astype(str), 8))

    def dia(idx_mes: np.ndarray) -> pd.DatetimeIndex:
        base_d = pd.DatetimeIndex([mes_ini[i] for i in idx_mes])
        return base_d + pd.to_timedelta(rng.integers(0, 27, len(idx_mes)), unit="D")

    i_tr = np.flatnonzero(troca_rec)
    trocas = pd.DataFrame({"matricula": matr[i_tr], "data_troca": dia(onset[i_tr]),
                           "hidrometro_antigo": hid_dic[hid_orig[i_tr]], "hidrometro_novo": hid_dic[hid_novo[i_tr]]})
    ruido = np.flatnonzero(rng.random(N) < 0.03)               # trocas antigas: distratores
    trocas = pd.concat([trocas, pd.DataFrame({
        "matricula": matr[ruido], "data_troca": dia(rng.integers(0, 10, len(ruido))),
        "hidrometro_antigo": "H9" + np.char.zfill(rng.integers(0, 10**6, len(ruido)).astype(str), 6),
        "hidrometro_novo": "H8" + np.char.zfill(rng.integers(0, 10**6, len(ruido)).astype(str), 6)})])

    def outra(c: str) -> str:
        return py.choice([x for x in CATEGORIAS if x != c])

    i_mu = np.flatnonzero(mud_rec)
    i_mu_old = np.flatnonzero(rng.random(N) < 0.015)
    hist = pd.DataFrame({
        "matricula": np.concatenate([matr[i_mu], matr[i_mu_old]]),
        "categoria_anterior": [outra(cat[i]) for i in np.concatenate([i_mu, i_mu_old])],
        "categoria_nova": np.concatenate([cat[i_mu], cat[i_mu_old]]),
        "data_mudanca": dia(np.concatenate([onset[i_mu], rng.integers(0, 10, len(i_mu_old))]))})

    # ---- verdade oculta ---------------------------------------------------------------
    perda = np.where(irr, base * queda, 0.0)
    verdade = pd.DataFrame({"matricula": matr, "irregular": irr, "tipo": tipo, "causa": causa,
                            "queda_real": queda.round(3), "perda_m3_mes": perda.round(2),
                            "onset_idx": np.where(evento, onset, -1), "base_m3": base.round(2)})

    # ---- cadastro (com defeitos pequenos e proposital) -----------------------------------
    cat_cad = cat.astype(object)
    cat_cad[rng.random(N) < 0.0005] = "RESID"
    cadastro = pd.DataFrame({
        "matricula": matr, "categoria": cat_cad, "setor_id": setor, "bairro": bairro, "regiao": reg,
        "condominio": cond, "situacao_imovel": sit, "nome_titular": nome,
        "cpf_titular": [f"{c:011d}" for c in rng.integers(0, 10**11, N)]})
    cadastro["cpf_titular"] = cadastro["cpf_titular"].str.replace(r"(\d{3})(\d{3})(\d{3})(\d{2})", r"\1.\2.\3-\4", regex=True)

    # ---- ordens de serviço --------------------------------------------------------------
    linhas: list[tuple] = []   # (idx_ligacao, data, tipo_os, texto, irreg, tipo, motivo)
    vis = np.flatnonzero(evento & (onset <= 22) & (rng.random(N) < PARAMS["p_visita_historica"]))
    for i in vis:
        irg, tp, mot, txt = _resultado(bool(irr[i]), tipo[i], bool(cond[i]), py)
        linhas.append((i, dia(np.array([onset[i] + 1]))[0], "inspecao", txt, irg, tp, mot))
    antigas = np.flatnonzero(rng.random(N) < PARAMS["p_visita_antiga"])
    for i in antigas:
        irg0 = py.random() < (0.30 if irr[i] else 0.05)
        irg, tp, mot, txt = _resultado(irg0, py.choice(list(ti)), bool(cond[i]), py)
        linhas.append((i, dia(np.array([py.randrange(0, 18)]))[0], "inspecao", txt, irg, tp, mot))
    for i in i_tr:
        linhas.append((i, dia(np.array([onset[i]]))[0], "troca_hidrometro",
                       "troca de hd realizada, novo medidor instalado", False, None, None))
    for i in np.flatnonzero(rng.random(N) < 0.005):
        linhas.append((i, dia(np.array([py.randrange(0, 24)]))[0], "religacao", "religacao efetuada",
                       False, None, None))

    reg_os, gab = [], []
    for k, (i, d, tipo_os, txt, irg, tp, mot) in enumerate(linhas):
        texto = _pii(_typo(txt, py), nome[i], py)
        osid = f"OS{k:07d}"
        reg_os.append((osid, _variar_matricula(matr[i], existentes, py), d, f"E{py.randrange(1, 13):02d}",
                       tipo_os, texto))
        if tipo_os == "inspecao":
            gab.append((osid, texto, irg, tp, mot))
        if py.random() < PARAMS["p_duplicada"]:
            reg_os.append((f"OS{len(linhas) + k:07d}", _variar_matricula(matr[i], existentes, py), d,
                           reg_os[-1][3], tipo_os, texto))
    os_df = pd.DataFrame(reg_os, columns=["os_id", "matricula_digitada", "data_visita", "equipe_id",
                                          "tipo_os", "anotacao"])
    os_df["data_visita"] = pd.to_datetime(os_df["data_visita"])
    os_df = os_df.sample(frac=1, random_state=semente).reset_index(drop=True)

    gab_df = pd.DataFrame(gab, columns=["os_id", "anotacao", "irregularidade", "tipo", "motivo_nao_acesso"])
    gab_df = gab_df.sample(n=min(500, len(gab_df)), random_state=semente)

    # ---- telemetria por setor -----------------------------------------------------------
    cod_set = pd.Series(setor).astype("category")
    sc = cod_set.cat.codes.to_numpy()
    ok = sc >= 0
    vol_set = np.zeros((len(cod_set.cat.categories), T))
    vaz_leak = np.zeros_like(vol_set)
    np.add.at(vol_set, sc[ok], cons[ok])
    leak = (base * queda * irr)[:, None] * (t >= onset[:, None])
    np.add.at(vaz_leak, sc[ok], leak[ok])
    vazao = ((vol_set + vaz_leak) / 730 * 1.12 * np.exp(0.03 * rng.standard_normal(vol_set.shape))).round(3)
    telem = pd.DataFrame({
        "setor_id": np.repeat(cod_set.cat.categories.to_numpy(), T),
        "referencia": np.tile(mes_str, len(cod_set.cat.categories)),
        "vazao_media_m3h": vazao.ravel()})

    # ---- grava --------------------------------------------------------------------------
    bruto, oculto = raiz / "bruto", raiz / "oculto"
    bruto.mkdir(parents=True, exist_ok=True)
    oculto.mkdir(parents=True, exist_ok=True)
    cons_neg = cons.copy()
    flat = cons_neg.ravel()
    flat[rng.random(flat.size) < 0.0002] = -1.0                # leituras inválidas: vão para pendência
    tabela = pa.table({
        "matricula": pa.DictionaryArray.from_arrays(pa.array(np.repeat(np.arange(N), T), pa.int32()),
                                                    pa.array(matr)),
        "referencia": pa.DictionaryArray.from_arrays(pa.array(np.tile(np.arange(T), N), pa.int8()),
                                                     pa.array(mes_str)),
        "consumo_m3": pa.array(flat.astype(np.float32)),
        "tipo_leitura": pa.DictionaryArray.from_arrays(pa.array(estim.ravel().astype(np.int8)),
                                                       pa.array(["real", "estimada"])),
        "hidrometro_id": pa.DictionaryArray.from_arrays(pa.array(hid.ravel(), pa.int32()), pa.array(hid_dic)),
    })
    pq.write_table(tabela, bruto / "consumo_mensal.parquet", compression="zstd")
    cadastro.to_parquet(bruto / "cadastro_ligacao.parquet", index=False)
    trocas.to_parquet(bruto / "troca_hidrometro.parquet", index=False)
    hist.to_parquet(bruto / "historico_categoria.parquet", index=False)
    telem.to_parquet(bruto / "vazao_setor.parquet", index=False)
    os_df.to_parquet(bruto / "ordem_servico.parquet", index=False)
    verdade.to_parquet(oculto / "verdade_oculta.parquet", index=False)
    Path("eval").mkdir(exist_ok=True)
    gab_df.to_csv("eval/amostra_revisada.csv", index=False)
    meta = {"escala": N, "semente": semente, "referencia": referencia, "meses": mes_str.tolist(),
            "ordens_servico": len(os_df), "gabarito": len(gab_df)}
    (bruto / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--escala", type=int, default=500_000, help="número de ligações (ex.: 50000 para aula)")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--mes-referencia", default="2026-08")
    a = ap.parse_args()
    print(json.dumps(gerar(a.escala, a.semente, a.mes_referencia), indent=2))


if __name__ == "__main__":
    main()

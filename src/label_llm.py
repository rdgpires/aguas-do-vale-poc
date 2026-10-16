"""Rotulagem do texto livre das visitas: anotação mascarada -> RotuloVisita validado.

Decisões:
* o LLM só vê texto JÁ mascarado (feito na extração);
* só textos ÚNICOS são rotulados, e o resultado é guardado em cache por
  hash(anotação mascarada + versão do prompt + modelo): reexecutar custa zero;
* JSON inválido -> nova tentativa (limite configurável) -> pendência; timeout -> espera
  exponencial; nada é descartado em silêncio.
"""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from .comum import Contexto
from .contracts import RotuloVisita
from .llm.cliente import ClienteLLM, RespostaInvalida, TimeoutLLM, criar_cliente, montar_prompt


def chave_cache(texto: str, versao_prompt: str, modelo: str | None) -> str:
    return hashlib.sha256(f"{texto}|{versao_prompt}|{modelo}".encode()).hexdigest()


class CacheRotulos:
    """jsonl append-only: simples de inspecionar e de versionar."""
    def __init__(self, caminho: Path):
        self.caminho, self.mem = caminho, {}
        if caminho.exists():
            for linha in caminho.read_text(encoding="utf-8").splitlines():
                k, v = json.loads(linha)
                self.mem[k] = v

    def novos(self, itens: dict[str, dict]) -> None:
        self.mem.update(itens)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.caminho.open("a", encoding="utf-8") as f:
            for k, v in itens.items():
                f.write(json.dumps([k, v]) + "\n")


def rotular_texto(cliente: ClienteLLM, prompt_base: str, texto: str, tentativas: int,
                  espera_s: float) -> RotuloVisita | str:
    """Uma anotação, com repetição. Devolve o rótulo ou o motivo da falha (str)."""
    prompt = montar_prompt(prompt_base, texto)
    erro = "sem_tentativa"
    for k in range(tentativas):
        try:
            return cliente.rotular(prompt)
        except RespostaInvalida as e:
            erro = f"json_invalido: {e}"
        except TimeoutLLM as e:
            erro = f"timeout: {e}"
            time.sleep(espera_s * 2 ** k)          # espera exponencial
    return f"falhou_apos_{tentativas}_tentativas: {erro}"


def executar(ctx: Contexto, cliente: ClienteLLM | None = None) -> dict:
    cfg = ctx.cfg["llm"]
    cliente = cliente or criar_cliente(cfg)
    prompt_base = Path(cfg["prompt"]).read_text(encoding="utf-8")
    versao = cfg["versao_prompt"]
    os_ = ctx.arm.ler("ordem_servico", ctx.referencia)
    alvo = os_[(os_["tipo_os"] == "inspecao") & os_["anotacao_mascarada"].notna()].copy()

    cache = CacheRotulos(Path(ctx.cfg["armazenamento"]["raiz"]).parent / "cache" / "rotulos.jsonl")
    alvo["_k"] = [chave_cache(t, versao, cliente.modelo) for t in alvo["anotacao_mascarada"]]
    unicos = alvo.drop_duplicates("_k")[["_k", "anotacao_mascarada"]]
    faltam = unicos[~unicos["_k"].isin(cache.mem)]
    hits = len(unicos) - len(faltam)

    falhas: dict[str, str] = {}
    lote = cfg["tamanho_lote"]
    for i in range(0, len(faltam), lote):
        parte = faltam.iloc[i:i + lote]
        with ThreadPoolExecutor(max_workers=cfg["concorrencia"]) as ex:
            res = list(ex.map(lambda t: rotular_texto(cliente, prompt_base, t, cfg["tentativas"],
                                                      cfg["espera_inicial_s"]), parte["anotacao_mascarada"]))
        novos = {}
        for k, r in zip(parte["_k"], res):
            if isinstance(r, str):
                falhas[k] = r
            else:
                novos[k] = r.model_dump()
        cache.novos(novos)
        ctx.log("rotulagem", "lote", inicio=i, tamanho=len(parte), falhas=len(falhas))

    rot = pd.DataFrame([cache.mem.get(k) or {"irregularidade": False, "tipo": None, "motivo_nao_acesso": None}
                        for k in alvo["_k"]], index=alvo.index)
    ok = alvo["_k"].isin(cache.mem)
    ctx.pendencia("rotulagem", alvo.loc[~ok, "os_id"], [falhas.get(k, "sem_rotulo") for k in alvo.loc[~ok, "_k"]])
    out = pd.DataFrame({"os_id": alvo["os_id"], "matricula": alvo["matricula"],
                        "irregularidade": rot["irregularidade"].astype(bool),
                        "tipo": rot["tipo"], "motivo_nao_acesso": rot["motivo_nao_acesso"],
                        "fonte_rotulo": cliente.fonte, "modelo_llm": cliente.modelo,
                        "versao_prompt": versao})[ok]
    out = ctx.validar("rotulo_visita", out, "rotulagem", "saida")
    ctx.arm.gravar("rotulo_visita", ctx.referencia, out.reset_index(drop=True))

    preco = cfg["preco_por_milhao_tokens"]
    u = cliente.uso
    custo = (u.tokens_entrada * preco["entrada"] + u.tokens_saida * preco["saida"]) / 1e6
    ctx.llm_uso = {"fonte": cliente.fonte, "modelo": cliente.modelo, "versao_prompt": versao,
                   "chamadas": u.chamadas, "acertos_cache": hits, "tokens_entrada": u.tokens_entrada,
                   "tokens_saida": u.tokens_saida, "custo_estimado_usd": round(custo, 4)}
    c = {"anotacoes_rotuladas": int(len(out)), "textos_unicos": int(len(unicos)), "falhas": int((~ok).sum()),
         **ctx.llm_uso}
    ctx.log("rotulagem", "concluida", **c)
    return c

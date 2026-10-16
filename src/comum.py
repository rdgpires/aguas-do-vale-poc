"""Contexto de execução compartilhado: config, armazenamento, run_id, pendências, logs.

Cada etapa recebe um `Contexto` e devolve um dict de contagens. É esse contrato mínimo que
permite, no futuro, transformar cada etapa em uma task de orquestrador sem reescrever nada.
"""
from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .contracts import REGISTRO
from .storage import Armazenamento, criar_armazenamento


def carregar_config(caminho: str | Path = "config.yaml") -> dict:
    return yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))


def novo_run_id() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:4]


def inicio_do_mes(referencia: str) -> pd.Timestamp:
    return pd.Period(referencia, "M").to_timestamp()


def dias_uteis(referencia: str) -> list[pd.Timestamp]:
    p = pd.Period(referencia, "M")
    return list(pd.bdate_range(p.start_time, p.end_time.normalize()))


def dias_efetivos(cfg: dict, n_ligacoes: int) -> int:
    """Dias úteis usados na fila. Em base reduzida a capacidade cai na mesma proporção."""
    dias = cfg["dias_uteis_mes"]
    if cfg.get("escalar_capacidade_pela_base"):
        dias = max(1, round(dias * n_ligacoes / cfg["ligacoes_base_referencia"]))
    return dias


@dataclass
class Contexto:
    cfg: dict
    arm: Armazenamento
    referencia: str
    formulacao: str
    run_id: str
    _pend: list[pd.DataFrame] = field(default_factory=list)
    validacoes: list[dict] = field(default_factory=list)
    contagens: dict[str, dict] = field(default_factory=dict)
    llm_uso: dict = field(default_factory=dict)

    @classmethod
    def criar(cls, cfg: dict, referencia: str | None = None, formulacao: str | None = None) -> "Contexto":
        return cls(cfg, criar_armazenamento(cfg), referencia or cfg["referencia_padrao"],
                   formulacao or cfg["formulacao"], novo_run_id())

    # --- observabilidade ---------------------------------------------------------------
    def log(self, etapa: str, evento: str, **kv: Any) -> None:
        print(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "run_id": self.run_id,
                          "etapa": etapa, "evento": evento, **kv}, ensure_ascii=False, default=str),
              file=sys.stderr)

    # --- pendências: nada some em silêncio -----------------------------------------------
    def pendencia(self, etapa: str, chaves: pd.Series | list, motivos: pd.Series | list | str) -> None:
        chaves = pd.Series(list(chaves), dtype=object)
        if len(chaves) == 0:
            return
        self._pend.append(pd.DataFrame({"etapa": etapa, "chave": chaves.astype(str).to_numpy(),
                                        "motivo": motivos if isinstance(motivos, str) else list(motivos),
                                        "run_id": self.run_id}))

    def pendencias_df(self) -> pd.DataFrame:
        if not self._pend:
            return pd.DataFrame(columns=list(REGISTRO["pendencia"].colunas()))
        return pd.concat(self._pend, ignore_index=True)

    # --- contratos ---------------------------------------------------------------------
    def validar(self, contrato: str, df: pd.DataFrame, etapa: str, direcao: str) -> pd.DataFrame:
        """Valida `df` contra o contrato. Inválidos viram pendência; quebra estrutural levanta."""
        c = REGISTRO[contrato]
        validos, invalidos = c.validar(df, etapa)
        if len(invalidos):
            chave = invalidos[[k for k in c.chave if k in invalidos.columns]].astype(str).agg("|".join, axis=1)
            self.pendencia(etapa, chave, invalidos["motivo"])
        self.validacoes.append({"contrato": contrato, "etapa": etapa, "direcao": direcao,
                                "registros": int(len(df)), "invalidos": int(len(invalidos)),
                                "status": "ok" if len(invalidos) == 0 else "com_pendencias"})
        return validos

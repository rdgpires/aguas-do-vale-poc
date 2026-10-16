"""Camada de armazenamento.

Nenhuma etapa conhece caminho ou formato: todas pedem `(etapa, referencia, variante)`.
A partição é o mês de referência (YYYY-MM), então reexecutar um mês SUBSTITUI a partição
em vez de duplicá-la (idempotência). `variante` guarda coisas que coexistem no mesmo mês,
como a formulação (v1/v2) ou a etapa dona de uma pendência.

Ponto de extensão: object storage (S3/GCS) ou data warehouse = nova classe com os mesmos
quatro métodos de `Armazenamento` e uma linha em `criar_armazenamento`. Exemplo:

    class ArmazenamentoS3:                       # NÃO implementado nesta PoC
        def gravar(self, etapa, referencia, df, variante=None):
            df.to_parquet(f"s3://{bucket}/{etapa}/ref={referencia}/dados.parquet")
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Protocol

import pandas as pd


class Armazenamento(Protocol):
    def gravar(self, etapa: str, referencia: str, df: pd.DataFrame, variante: str | None = None) -> None: ...
    def ler(self, etapa: str, referencia: str, variante: str | None = None) -> pd.DataFrame: ...
    def existe(self, etapa: str, referencia: str, variante: str | None = None) -> bool: ...
    def gravar_json(self, colecao: str, nome: str, obj: Any) -> None: ...
    def ler_json(self, colecao: str, nome: str) -> Any: ...
    def listar_json(self, colecao: str) -> list[str]: ...
    def referencias(self, etapa: str) -> list[str]: ...


class ArmazenamentoLocalParquet:
    def __init__(self, raiz: str | Path):
        self.raiz = Path(raiz)

    def _dir(self, etapa: str, referencia: str, variante: str | None) -> Path:
        p = self.raiz / etapa / f"ref={referencia}"
        return p / f"variante={variante}" if variante else p

    def gravar(self, etapa, referencia, df, variante=None) -> None:
        d = self._dir(etapa, referencia, variante)
        if d.exists():
            shutil.rmtree(d)           # substitui a partição inteira: reexecução não duplica
        d.mkdir(parents=True)
        df.to_parquet(d / "dados.parquet", index=False)

    def ler(self, etapa, referencia, variante=None) -> pd.DataFrame:
        arq = self._dir(etapa, referencia, variante) / "dados.parquet"
        if not arq.exists():
            raise FileNotFoundError(f"partição inexistente: {etapa} ref={referencia} variante={variante}")
        return pd.read_parquet(arq)

    def existe(self, etapa, referencia, variante=None) -> bool:
        return (self._dir(etapa, referencia, variante) / "dados.parquet").exists()

    def gravar_json(self, colecao: str, nome: str, obj: Any) -> None:
        d = self.raiz / "_docs" / colecao
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{nome}.json").write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str),
                                        encoding="utf-8")

    def ler_json(self, colecao: str, nome: str) -> Any:
        return json.loads((self.raiz / "_docs" / colecao / f"{nome}.json").read_text(encoding="utf-8"))

    def listar_json(self, colecao: str) -> list[str]:
        d = self.raiz / "_docs" / colecao
        return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []

    def referencias(self, etapa: str) -> list[str]:
        d = self.raiz / etapa
        return sorted(p.name.split("=")[1] for p in d.glob("ref=*")) if d.exists() else []


def criar_armazenamento(cfg: dict) -> Armazenamento:
    a = cfg["armazenamento"]
    if a["tipo"] == "local_parquet":
        return ArmazenamentoLocalParquet(a["raiz"])
    raise ValueError(f"armazenamento '{a['tipo']}' não implementado (ver docstring do módulo)")

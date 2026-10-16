"""Adapters de ARQUIVO (Parquet) para a PoC. Somente leitura."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


def _ler(caminho: str | Path) -> pd.DataFrame:
    return pd.read_parquet(caminho)


class CadastroArquivo:
    def __init__(self, caminho: str, trocas: str, historico: str):
        self.caminho, self.trocas, self.historico = caminho, trocas, historico

    def ler_cadastro(self) -> pd.DataFrame:
        return _ler(self.caminho)

    def ler_trocas(self) -> pd.DataFrame:
        return _ler(self.trocas)

    def ler_historico_categoria(self) -> pd.DataFrame:
        return _ler(self.historico)


class ConsumoArquivo:
    def __init__(self, caminho: str):
        self.caminho = caminho

    def ler_consumo(self, referencia: str) -> pd.DataFrame:
        # matrícula e referência chegam como dicionário (categórico): 12 milhões de linhas
        # com string repetida estourariam a memória sem necessidade.
        t = pq.read_table(self.caminho, read_dictionary=["matricula", "referencia", "tipo_leitura",
                                                         "hidrometro_id"])
        df = t.to_pandas()
        return df[df["referencia"].astype(str) < referencia].reset_index(drop=True)


class OrdensArquivo:
    def __init__(self, caminho: str):
        self.caminho = caminho

    def ler_ordens(self, referencia: str) -> pd.DataFrame:
        df = _ler(self.caminho)
        inicio = pd.Period(referencia, "M").to_timestamp()
        return df[df["data_visita"] < inicio].reset_index(drop=True)


class TelemetriaArquivo:
    def __init__(self, caminho: str):
        self.caminho = caminho

    def ler_vazao(self, referencia: str) -> pd.DataFrame:
        df = _ler(self.caminho)
        return df[df["referencia"] < referencia].reset_index(drop=True)

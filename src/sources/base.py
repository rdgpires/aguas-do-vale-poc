"""Interfaces de fonte, uma por domínio/sistema de origem."""
from __future__ import annotations

from typing import Protocol

import pandas as pd


class FonteCadastro(Protocol):
    """Sistema comercial: cadastro, trocas de hidrômetro, histórico de categoria."""
    def ler_cadastro(self) -> pd.DataFrame: ...
    def ler_trocas(self) -> pd.DataFrame: ...
    def ler_historico_categoria(self) -> pd.DataFrame: ...


class FonteConsumo(Protocol):
    """Consumo mensal. Devolve só meses ANTERIORES à referência (o mês corrente não fechou)."""
    def ler_consumo(self, referencia: str) -> pd.DataFrame: ...


class FonteOrdensServico(Protocol):
    """App de campo. Devolve OS com data anterior ao início do mês de referência."""
    def ler_ordens(self, referencia: str) -> pd.DataFrame: ...


class FonteTelemetria(Protocol):
    """Telemetria: vazão por SETOR (contexto, nunca dado da ligação)."""
    def ler_vazao(self, referencia: str) -> pd.DataFrame: ...

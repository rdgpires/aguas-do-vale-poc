"""Mecanismo de contratos de dados.

Um contrato é um objeto de dados (não uma classe com lógica espalhada): lista de campos
com tipo, obrigatoriedade, domínio e regra de formato. Dele saem duas coisas:
a validação em tempo de execução e o documento `docs/contratos.md`.

Duas severidades, de propósito:
- registro inválido  -> vai para `pendencia`, o fluxo segue;
- quebra estrutural  -> `ContratoQuebrado`, a etapa PARA (coluna faltando, tipo errado,
  ou fração de inválidos acima do limite).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd


class ContratoQuebrado(Exception):
    """Quebra estrutural: não adianta passar o dado adiante."""


@dataclass(frozen=True)
class Campo:
    nome: str
    tipo: str                      # str | int | float | bool | date
    obrigatorio: bool = True
    dominio: tuple | None = None
    padrao: str | None = None      # regex completa
    minimo: float | None = None
    pii: bool = False
    descricao: str = ""


@dataclass(frozen=True)
class Contrato:
    nome: str
    origem: str
    granularidade: str
    chave: tuple[str, ...]
    campos: tuple[Campo, ...]
    regras: tuple[str, ...] = ()
    limite_invalidos: float = 0.2  # acima disso deixa de ser "registro ruim" e vira quebra estrutural

    def colunas(self) -> list[str]:
        return [c.nome for c in self.campos]

    def validar(self, df: pd.DataFrame, etapa: str = "") -> tuple[pd.DataFrame, pd.DataFrame]:
        """Devolve (validos, invalidos). `invalidos` ganha a coluna `motivo`."""
        faltando = [c.nome for c in self.campos if c.obrigatorio and c.nome not in df.columns]
        if faltando:
            raise ContratoQuebrado(f"[{etapa}] contrato '{self.nome}': colunas ausentes {faltando}")
        motivo = np.full(len(df), None, dtype=object)
        marcado = np.zeros(len(df), dtype=bool)
        for c in self.campos:
            if c.nome not in df.columns:
                continue
            serie = df[c.nome]
            self._checar_tipo(c, serie, etapa)
            ruim = _mascara_invalida(c, serie)
            livre = ruim & ~marcado
            motivo[livre] = f"{self.nome}.{c.nome}: invalido"
            marcado |= ruim
        invalido = marcado
        if len(df) and invalido.mean() > self.limite_invalidos:
            raise ContratoQuebrado(
                f"[{etapa}] contrato '{self.nome}': {invalido.mean():.0%} dos registros inválidos "
                f"(limite {self.limite_invalidos:.0%}) — provável quebra estrutural na origem")
        bad = df[invalido].copy()
        bad["motivo"] = motivo[invalido]
        return df[~invalido], bad

    def _checar_tipo(self, c: Campo, s: pd.Series, etapa: str) -> None:
        k = s.dtype.kind
        ok = {
            "str": isinstance(s.dtype, pd.CategoricalDtype) or k in "OUS" or pd.api.types.is_string_dtype(s),
            "int": k in "iu" or str(s.dtype).startswith("Int"),
            "float": k in "iuf" or str(s.dtype).startswith(("Float", "Int")),
            "bool": k == "b" or str(s.dtype) == "boolean",
            "date": k == "M",
        }[c.tipo]
        if not ok:
            raise ContratoQuebrado(
                f"[{etapa}] contrato '{self.nome}': campo '{c.nome}' esperado {c.tipo}, veio {s.dtype}")


def _mascara_invalida(c: Campo, s: pd.Series) -> np.ndarray:
    nulo = s.isna().to_numpy()
    ruim = nulo.copy() if c.obrigatorio else np.zeros(len(s), bool)
    if c.minimo is not None:
        ruim |= (pd.to_numeric(s, errors="coerce") < c.minimo).fillna(False).to_numpy()
    if c.dominio is not None or c.padrao is not None:
        if isinstance(s.dtype, pd.CategoricalDtype):   # avalia só as categorias, não 12 milhões de linhas
            ok_cat = _ok_texto(pd.Series(s.cat.categories.astype(str)), c)
            cod = s.cat.codes.to_numpy()
            ok = np.where(cod >= 0, ok_cat[np.clip(cod, 0, None)], True)
        else:
            ok = _ok_texto(s.astype(object), c)
        ruim |= ~ok & ~nulo
    return ruim


def _ok_texto(s: pd.Series, c: Campo) -> np.ndarray:
    ok = np.ones(len(s), bool)
    if c.dominio is not None:
        ok &= s.isin(c.dominio).to_numpy()
    if c.padrao is not None:
        rx = re.compile(c.padrao)
        ok &= s.astype(str).map(lambda x: rx.fullmatch(x) is not None).to_numpy()
    return ok

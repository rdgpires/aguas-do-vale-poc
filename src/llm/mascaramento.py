"""Mascaramento de dados pessoais (LGPD) antes de qualquer envio ao LLM.

Componente separado e reutilizável: a extração o aplica (a extração é a única etapa que vê
nome e CPF), o avaliador também. Nenhuma etapa posterior recebe o texto cru.

Decisão: mascarar por padrões + nomes conhecidos do cadastro, em vez de pedir ao LLM que
ignore. O dado pessoal nunca sai do ambiente do cliente.
"""
from __future__ import annotations

import re
from typing import Iterable

_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_TEL = re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-\d{4}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_END = re.compile(r"\b(?:Rua|R\.|Av\.?|Avenida|Travessa|Tv\.|Alameda)\s[^,.]{2,40},\s?\d+(?:,\s?(?:apto|ap\.?|bloco)\s?\w+)?",
                  re.IGNORECASE)
_NOME_APOS_TRATAMENTO = re.compile(
    r"(\b(?:Sr\(a\)\.|Sr\.|Sra\.|Dona|Seu|resp\.|Titular|titular)\s+)"
    r"([A-ZÀ-Ú][\wà-ú]+(?:\s[A-ZÀ-Ú][\wà-ú]+){0,3})")


def mascarar(texto: str | None, nomes_conhecidos: Iterable[str] = ()) -> str | None:
    if texto is None or texto != texto:
        return None
    t = texto
    for nome in nomes_conhecidos:
        if nome:
            t = re.sub(re.escape(nome), "[NOME]", t, flags=re.IGNORECASE)
    t = _EMAIL.sub("[EMAIL]", t)
    t = _END.sub("[ENDERECO]", t)
    t = _CPF.sub("[CPF]", t)
    t = _TEL.sub("[TELEFONE]", t)
    t = _NOME_APOS_TRATAMENTO.sub(r"\1[NOME]", t)
    return t

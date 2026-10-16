"""Cliente de LLM agnóstico de fornecedor + modo offline.

A rotulagem só conhece `ClienteLLM`: recebe o prompt, devolve um `RotuloVisita` já validado.
Trocar de fornecedor = escrever outra classe com `rotular`. O modo usado fica registrado
em `fonte_rotulo` (llm | offline) em cada rótulo.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from ..contracts import RotuloVisita


class RespostaInvalida(Exception):
    """O modelo respondeu algo que não valida contra RotuloVisita."""


class TimeoutLLM(Exception):
    """Timeout ou erro transitório do fornecedor: vale tentar de novo com espera."""


@dataclass
class Uso:
    chamadas: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0


class ClienteLLM(Protocol):
    fonte: str                 # "llm" | "offline"
    modelo: str | None
    uso: Uso

    def rotular(self, prompt: str) -> RotuloVisita: ...


MARCADOR = "Anotação:"


def montar_prompt(base: str, anotacao_mascarada: str) -> str:
    return f"{base.strip()}\n\n{MARCADOR} {anotacao_mascarada}\n"


def validar_resposta(texto: str) -> RotuloVisita:
    """Extrai o JSON da resposta e valida contra o schema. Incoerência também é inválida."""
    ini, fim = texto.find("{"), texto.rfind("}")
    if ini < 0 or fim < ini:
        raise RespostaInvalida(f"sem JSON: {texto[:80]!r}")
    try:
        r = RotuloVisita.model_validate(json.loads(texto[ini:fim + 1]))
    except (json.JSONDecodeError, ValidationError) as e:
        raise RespostaInvalida(str(e)[:120]) from e
    if r.irregularidade and r.motivo_nao_acesso is not None:
        raise RespostaInvalida("irregularidade=true com motivo_nao_acesso preenchido")
    if not r.irregularidade and r.tipo is not None:
        raise RespostaInvalida("tipo preenchido sem irregularidade")
    return r


# --- modo offline: regras simples sobre o texto -------------------------------------------
def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t)


_MOTIVOS = [
    ("condominio", re.compile(r"\bcond")),
    ("ausente", re.compile(r"ausente|ninguem|n atendeu")),
    ("recusa", re.compile(r"recus|n permitiu|nao permitiu")),
    ("outro", re.compile(r"cachorro|chuva|bloquead")),
]
_ACESSO_COND = re.compile(r"acesso|autoriz|fechado|entrou|portaria")
_TIPOS = [
    ("hidrometro_parado", re.compile(r"parad|travad|n(ao)? (gira|registra)")),
    ("ligacao_clandestina", re.compile(r"clandest|gato|desvio|by-?pass|ligacao direta")),
    ("cadastro_errado", re.compile(r"cadastro|categ|end\. n")),
    ("outro", re.compile(r"lacre|violac|invertido")),
]


def classificar_offline(texto: str) -> RotuloVisita:
    t = _norm(texto)
    for motivo, rx in _MOTIVOS:
        if rx.search(t) and (motivo != "condominio" or _ACESSO_COND.search(t)):
            return RotuloVisita(irregularidade=False, tipo=None, motivo_nao_acesso=motivo)
    for tipo, rx in _TIPOS:
        if rx.search(t):
            return RotuloVisita(irregularidade=True, tipo=tipo, motivo_nao_acesso=None)
    return RotuloVisita(irregularidade=False, tipo=None, motivo_nao_acesso=None)


class ClienteOffline:
    """Rotulador por regras: roda a PoC sem chave de API. Mais frágil que o LLM, e é por isso
    que a avaliação contra a amostra revisada existe."""
    fonte = "offline"
    modelo = "regras-v1"

    def __init__(self) -> None:
        self.uso = Uso()

    def rotular(self, prompt: str) -> RotuloVisita:
        self.uso.chamadas += 1
        return classificar_offline(prompt.rsplit(MARCADOR, 1)[-1])


class ClienteAnthropic:
    """Provedor real (Anthropic). Chave por variável de ambiente; nada no código."""
    fonte = "llm"

    def __init__(self, modelo: str, timeout_s: float = 30.0) -> None:
        import anthropic  # importado aqui: o modo offline não exige o pacote
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY ausente (use LLM_PROVEDOR=offline para rodar sem chave)")
        self._anthropic = anthropic
        self._cli = anthropic.Anthropic(timeout=timeout_s, max_retries=0)  # o retry é nosso, com contagem
        self.modelo = modelo
        self.uso = Uso()

    def rotular(self, prompt: str) -> RotuloVisita:
        try:
            r = self._cli.messages.create(model=self.modelo, max_tokens=120,
                                          messages=[{"role": "user", "content": prompt}])
        except (self._anthropic.APITimeoutError, self._anthropic.APIConnectionError,
                self._anthropic.RateLimitError, self._anthropic.InternalServerError) as e:
            raise TimeoutLLM(str(e)) from e
        self.uso.chamadas += 1
        self.uso.tokens_entrada += r.usage.input_tokens
        self.uso.tokens_saida += r.usage.output_tokens
        return validar_resposta("".join(b.text for b in r.content if getattr(b, "type", "") == "text"))


def criar_cliente(cfg_llm: dict) -> ClienteLLM:
    provedor = os.environ.get("LLM_PROVEDOR", cfg_llm.get("provedor", "offline"))
    if provedor == "offline":
        return ClienteOffline()
    if provedor == "anthropic":
        return ClienteAnthropic(os.environ.get("LLM_MODELO", cfg_llm["modelo"]))
    raise ValueError(f"provedor de LLM desconhecido: {provedor}")

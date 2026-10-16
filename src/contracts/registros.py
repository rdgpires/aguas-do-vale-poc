"""Contratos de registro (Pydantic v2): o que é um item individual.

`RotuloVisita` é exatamente o schema do slide: é ele que o LLM precisa devolver.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RotuloVisita(BaseModel):
    irregularidade: bool
    tipo: Literal["hidrometro_parado", "ligacao_clandestina",
                  "cadastro_errado", "outro"] | None
    motivo_nao_acesso: Literal["condominio", "ausente",
                               "recusa", "outro"] | None


class RotuloVisitaRegistro(RotuloVisita):
    """Rótulo + rastreabilidade (de onde veio, com qual prompt e modelo)."""
    os_id: str
    matricula: str
    fonte_rotulo: Literal["llm", "offline", "revisao_manual"]
    modelo_llm: str | None
    versao_prompt: str | None


class Equipe(BaseModel):
    equipe_id: str
    tipo: Literal["individual", "dupla"]
    regiao_base: str


class Pendencia(BaseModel):
    """Tudo que não entra no fluxo vira pendência — nunca é descartado em silêncio."""
    etapa: str
    chave: str
    motivo: str
    run_id: str

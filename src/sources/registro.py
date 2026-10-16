"""Registro de adapters: o `config.yaml` escolhe o adapter por `tipo`.

Para adicionar uma origem nova: escrever o adapter, registrá-lo aqui, mudar `tipo` no config.
Nada acima desta camada muda.
"""
from __future__ import annotations

from dataclasses import dataclass

from .arquivo import CadastroArquivo, ConsumoArquivo, OrdensArquivo, TelemetriaArquivo
from .base import FonteCadastro, FonteConsumo, FonteOrdensServico, FonteTelemetria

# domínio -> {tipo -> construtor(config_da_fonte, config_completa)}
ADAPTERS = {
    "cadastro": {"arquivo": lambda c, cfg: CadastroArquivo(
        c["caminho"], cfg["fontes"]["trocas"]["caminho"], cfg["fontes"]["historico"]["caminho"])},
    "consumo": {"arquivo": lambda c, cfg: ConsumoArquivo(c["caminho"])},
    "ordens": {"arquivo": lambda c, cfg: OrdensArquivo(c["caminho"])},
    "telemetria": {"arquivo": lambda c, cfg: TelemetriaArquivo(c["caminho"])},
    # "cadastro": {"sql": ...}, "ordens": {"api": ...}, "consumo": {"datalake": ...}  -> futuros
}


@dataclass
class Fontes:
    cadastro: FonteCadastro
    consumo: FonteConsumo
    ordens: FonteOrdensServico
    telemetria: FonteTelemetria


def criar_fontes(cfg: dict) -> Fontes:
    def uma(dominio: str):
        c = cfg["fontes"][dominio]
        try:
            return ADAPTERS[dominio][c["tipo"]](c, cfg)
        except KeyError:
            raise ValueError(f"fonte '{dominio}': tipo '{c['tipo']}' sem adapter registrado") from None
    return Fontes(uma("cadastro"), uma("consumo"), uma("ordens"), uma("telemetria"))

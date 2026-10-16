"""Fontes de dados: interfaces (ports) e adapters.

Nenhum componente acima desta camada conhece formato de arquivo, caminho ou sistema de origem.
Cada interface devolve DataFrames JÁ no formato do contrato de entrada; a validação do contrato
acontece na extração.

Como um adapter novo entra (NÃO implementado nesta PoC):

    class CadastroSQL:                                   # implementa FonteCadastro
        def __init__(self, dsn_env: str, consulta: str): ...
        def ler_cadastro(self) -> pd.DataFrame:
            return pd.read_sql(self.consulta, engine_somente_leitura(self.dsn))

    # config.yaml:  cadastro: {tipo: sql, dsn_env: COMERCIAL_DSN, consulta: sql/cadastro.sql}
    # registro.py:  ADAPTERS["cadastro"]["sql"] = CadastroSQL

Qualquer adapter deve usar credencial SOMENTE LEITURA: a PoC nunca escreve em sistema do cliente.
"""
from .base import FonteCadastro, FonteConsumo, FonteOrdensServico, FonteTelemetria
from .registro import criar_fontes

__all__ = ["FonteCadastro", "FonteConsumo", "FonteOrdensServico", "FonteTelemetria", "criar_fontes"]

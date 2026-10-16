"""Domínios permitidos, compartilhados pelos contratos e pelo código."""
CATEGORIAS = ("residencial", "comercial", "industrial", "publica")
SITUACOES = ("ocupado", "desocupado", "desconhecido")
LEITURAS = ("real", "estimada")
TIPOS_OS = ("inspecao", "troca_hidrometro", "religacao", "outro")
TIPOS_IRREG = ("hidrometro_parado", "ligacao_clandestina", "cadastro_errado", "outro")
MOTIVOS_NAO_ACESSO = ("condominio", "ausente", "recusa", "outro")
FONTES_ROTULO = ("llm", "offline", "revisao_manual")
FORMULACOES = ("v1", "v2")
REGEX_MATRICULA = r"\d{7}"
REGEX_REFERENCIA = r"\d{4}-(0[1-9]|1[0-2])"

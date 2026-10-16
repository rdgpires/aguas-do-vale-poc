"""Gera docs/contratos.md a partir do código dos contratos (fonte única de verdade)."""
from pathlib import Path

from src.contracts import REGISTRO


def main() -> None:
    L = ["# Contratos de dados", "",
         "> Gerado por `python -m scripts.gerar_docs_contratos` a partir de `src/contracts/`. "
         "Não edite à mão.", ""]
    for c in REGISTRO.values():
        L += [f"## `{c.nome}`", "", f"- **Origem:** {c.origem}", f"- **Granularidade:** {c.granularidade}",
              f"- **Chave:** {', '.join(c.chave)}", "",
              "| Campo | Tipo | Obrigatório | Domínio / formato | PII | Descrição |", "|---|---|---|---|---|---|"]
        for f in c.campos:
            dom = ", ".join(map(str, f.dominio)) if f.dominio else (f"`{f.padrao}`" if f.padrao else "")
            if f.minimo is not None:
                dom = (dom + " ").strip() + f" ≥ {f.minimo:g}"
            L.append(f"| {f.nome} | {f.tipo} | {'sim' if f.obrigatorio else 'não'} | {dom} | "
                     f"{'**PII**' if f.pii else ''} | {f.descricao} |")
        if c.regras:
            L += ["", "**Regras de qualidade:**", *[f"- {r}" for r in c.regras]]
        L.append("")
    Path("docs").mkdir(exist_ok=True)
    Path("docs/contratos.md").write_text("\n".join(L), encoding="utf-8")
    print(f"docs/contratos.md: {len(REGISTRO)} contratos")


if __name__ == "__main__":
    main()

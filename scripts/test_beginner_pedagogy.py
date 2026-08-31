#!/usr/bin/env python3
"""Behavioral regressions for beginner-first lesson pedagogy."""

from __future__ import annotations

from beginner_pedagogy import title_acronyms, validate_module_pedagogy


def valid_beginner_body(*, analogy: bool = True) -> str:
    intuition = """
**Analogia:** um teclado sugere a próxima palavra com base em padrões.

**Onde a analogia ajuda:** mostra a ideia de continuação provável.

**Onde a analogia deixa de funcionar:** um LLM usa uma escala e um treinamento muito maiores.
""" if analogy else """
**Exemplo concreto:** ao escrever uma mensagem, o teclado oferece continuações prováveis sem consultar uma base de fatos.
"""
    return f"""# Como os LLMs geram texto

## Começando do zero

Um modelo é um sistema ajustado a partir de exemplos. Um modelo de linguagem trabalha com padrões em sequências de texto e pode estimar continuações prováveis. Um Large Language Model, ou modelo de linguagem de grande porte, amplia essa capacidade com muitos parâmetros e grande volume de treinamento. Treinamento é a etapa de ajuste; inferência é o uso do modelo já treinado.

### Vocabulário desta aula

- **LLM — Large Language Model:** modelo de linguagem de grande porte.
- **Modelo:** representação aprendida a partir de dados.
- **Inferência:** uso do modelo já treinado para produzir uma saída.

## Intuição antes dos detalhes
{intuition}
## Conteúdo essencial

Agora entram tokens, contexto e previsão do próximo token.
"""


def test_plural_title_acronyms_are_normalized() -> None:
    assert title_acronyms("Contratos para APIs com LLMs") == ["API", "LLM"]


def test_beginner_requires_first_principles() -> None:
    errors = validate_module_pedagogy(
        "Como os LLMs geram texto",
        "## Conteúdo essencial\nTokens e probabilidades.",
        "beginner",
    )
    assert any("Começando do zero" in error for error in errors)
    assert any("LLM" in error for error in errors)


def test_beginner_accepts_bounded_analogy() -> None:
    assert validate_module_pedagogy(
        "Como os LLMs geram texto",
        valid_beginner_body(),
        "beginner",
    ) == []


def test_concrete_example_can_replace_analogy() -> None:
    assert validate_module_pedagogy(
        "Como os LLMs geram texto",
        valid_beginner_body(analogy=False),
        "beginner",
    ) == []


def test_analogy_requires_explicit_limit() -> None:
    body = valid_beginner_body().replace(
        "**Onde a analogia deixa de funcionar:** um LLM usa uma escala e um treinamento muito maiores.\n",
        "",
    )
    errors = validate_module_pedagogy("Como os LLMs geram texto", body, "beginner")
    assert "analogy must explain where it stops working" in errors


def main() -> None:
    test_plural_title_acronyms_are_normalized()
    test_beginner_requires_first_principles()
    test_beginner_accepts_bounded_analogy()
    test_concrete_example_can_replace_analogy()
    test_analogy_requires_explicit_limit()
    print("Beginner-first pedagogy behavioral regressions passed.")


if __name__ == "__main__":
    main()

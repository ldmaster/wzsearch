import pytest

from wzsearch.search import build_terms


def test_literal_term_matches_exactly() -> None:
    terms = build_terms(["pix"], [])
    matches = [m.group(0) for m in terms[0].pattern.finditer("pix e pixels e PIX")]
    assert matches == ["pix", "pix"]


def test_case_insensitive() -> None:
    terms = build_terms(["pix"], [], ignore_case=True)
    matches = [m.group(0) for m in terms[0].pattern.finditer("PIX Pix")]
    assert matches == ["PIX", "Pix"]


def test_regex_term_labelled() -> None:
    terms = build_terms([], [r"\d{3}\.\d{3}\.\d{3}-\d{2}"])
    assert terms[0].label.startswith("re:")
    matches = [m.group(0) for m in terms[0].pattern.finditer("cpf 123.456.789-00")]
    assert matches == ["123.456.789-00"]


def test_invalid_regex_raises() -> None:
    with pytest.raises(ValueError):
        build_terms([], ["("])

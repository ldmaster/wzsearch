from typing import Any

from wzsearch.score import (
    ORIGEM_AUTO,
    ORIGEM_VAZIA,
    PONTOS_EXERCICIO,
    PONTOS_MIN,
    fold,
    is_exercise,
    match_reason,
    matched_terms,
    score_for,
    suggestions,
    terms_for,
)


def test_fold_ignores_case_and_accents() -> None:
    assert fold("TREINO Ação") == "treino acao"
    assert fold("Musculação") == "musculacao"


def test_is_exercise_matches_common_captions() -> None:
    assert is_exercise("treino de hoje", "")
    assert is_exercise("Bom dia! Academia 💪", "")
    assert is_exercise("", "corrida de rua amanhã")
    assert is_exercise("fui de BIKE", "")
    assert is_exercise("aula de musculação", "")


def test_is_exercise_needs_a_whole_word() -> None:
    assert not is_exercise("treinamento interno da empresa", "")
    assert not is_exercise("minha corridinha de leve", "")


def test_is_exercise_ignores_ambiguous_words() -> None:
    assert not is_exercise("comprei um bolo de chocolate", "")
    assert not is_exercise("tênis novo chegou", "")
    assert not is_exercise("que luta pra conseguir isso", "")
    assert not is_exercise("", "")


def test_score_for_defaults_to_one_point() -> None:
    assert score_for({"legenda": "olha o bolo", "contexto_provavel": "dia 02"}) == (
        PONTOS_MIN,
        ORIGEM_VAZIA,
    )
    assert score_for({}) == (PONTOS_MIN, ORIGEM_VAZIA)


def test_score_for_flags_exercise_as_suggestion() -> None:
    assert score_for({"legenda": "treino concluído"}) == (PONTOS_EXERCICIO, ORIGEM_AUTO)
    assert score_for({"contexto_provavel": "academia às 7h"}) == (PONTOS_EXERCICIO, ORIGEM_AUTO)


def test_suggestions_map_every_record_with_an_id() -> None:
    rows: list[dict[str, Any]] = [
        {"id": 1, "legenda": "treino"},
        {"id": 2, "legenda": "bolo"},
        {"legenda": "sem id"},
    ]
    assert suggestions(rows) == {1: PONTOS_EXERCICIO, 2: PONTOS_MIN}


def test_matched_terms_lists_the_words_without_repeating() -> None:
    assert matched_terms("treino de hoje, treino pesado", "") == ("treino",)
    assert matched_terms("academia", "corrida amanhã") == ("academia", "corrida")
    assert matched_terms("olha o bolo", "") == ()


def test_match_reason_says_where_the_word_came_from() -> None:
    na_legenda = {"legenda": "Treino de hoje", "contexto_provavel": ""}
    assert "treino" in match_reason(na_legenda)
    assert "na legenda" in match_reason(na_legenda)

    no_contexto = {"legenda": "olha o bolo", "contexto_provavel": "academia às 7h"}
    assert "academia" in match_reason(no_contexto)
    assert "na mensagem seguinte" in match_reason(no_contexto)

    assert match_reason({"legenda": "bolo"}) == ""
    assert terms_for({"legenda": "treino"}) == ("treino",)

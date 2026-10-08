from wzsearch.numbers import extract_numbers, format_numbers, sender_phone


def test_extracts_cpf_and_cnpj() -> None:
    found = extract_numbers("CPF 123.456.789-00 e CNPJ 12.345.678/0001-90")
    assert ("cpf", "123.456.789-00") in found
    assert ("cnpj", "12.345.678/0001-90") in found


def test_numbers_follow_text_order() -> None:
    found = extract_numbers("CPF 123.456.789-00 e CNPJ 12.345.678/0001-90")
    assert [label for label, _ in found] == ["cpf", "cnpj"]


def test_extracts_valor() -> None:
    assert extract_numbers("valor R$ 1.234,56") == [("valor", "R$ 1.234,56")]


def test_extracts_phone() -> None:
    assert extract_numbers("(11) 91234-5678") == [("telefone", "(11) 91234-5678")]


def test_extracts_order_code() -> None:
    assert extract_numbers("Pedido #A1234 pago") == [("pedido", "A1234")]


def test_ordinal_keyword_does_not_match_plain_no() -> None:
    assert extract_numbers("no valor de 10 reais") == []
    assert extract_numbers("nº 123") == [("pedido", "123")]


def test_no_duplicate_span() -> None:
    found = extract_numbers("+55 11 91234-5678")
    assert [label for label, _ in found] == ["telefone"]


def test_ignores_plain_dates() -> None:
    assert extract_numbers("em 12/03/2024 tudo certo") == []


def test_sender_phone() -> None:
    assert sender_phone("+55 11 91234-5678") == "+55 11 91234-5678"
    assert sender_phone("Fulano") == ""


def test_format_numbers() -> None:
    assert format_numbers([("cpf", "1"), ("valor", "2")]) == "cpf:1; valor:2"

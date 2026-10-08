from pathlib import Path

from wzsearch.parser import parse_chat

FIXTURES = Path(__file__).parent / "fixtures"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parses_android_fixture() -> None:
    messages = parse_chat(_text("chat_android_pt.txt"), chat_name="Amigos", eu="Eu")
    assert len(messages) == 10
    assert [m.message_id for m in messages] == list(range(1, 11))


def test_system_messages_flagged() -> None:
    messages = parse_chat(_text("chat_android_pt.txt"), chat_name="Amigos", eu="Eu")
    assert messages[0].is_system is True
    assert messages[1].is_system is True
    assert messages[2].is_system is False


def test_multiline_message_joined() -> None:
    messages = parse_chat(_text("chat_android_pt.txt"), chat_name="Amigos", eu="Eu")
    multiline = messages[4]
    assert "\n" in multiline.text
    assert multiline.text.startswith("Preciso do pix hoje")
    assert multiline.sender == "Fulano"


def test_senders_resolved_with_eu() -> None:
    messages = parse_chat(_text("chat_android_pt.txt"), chat_name="Amigos", eu="Lucas")
    senders = {m.sender for m in messages if not m.is_system}
    assert "Lucas" in senders
    assert "Fulano" in senders
    assert "Beltrano" in senders


def test_media_placeholder_detected() -> None:
    messages = parse_chat(_text("chat_android_pt.txt"), chat_name="Amigos", eu="Eu")
    media = messages[6].media
    assert media.present is True
    assert media.filename == "00000042-FOTO-2024-03-12-14-22-31.jpg"


def test_ios_you_normalised() -> None:
    messages = parse_chat(_text("chat_ios_en.txt"), chat_name="John", eu="Lucas")
    senders = [m.sender for m in messages]
    assert "Lucas" in senders
    assert "John" in senders
    assert messages[1].is_system is True


def test_unmarked_1to1_attributed_to_contact() -> None:
    messages = parse_chat(_text("chat_unmarked_1to1.txt"), chat_name="Fulano", eu="Lucas")
    assert messages[0].sender == "Fulano"
    assert messages[1].sender == "Lucas"
    assert messages[2].sender == "Fulano"


def test_time_like_prefix_is_not_a_sender() -> None:
    messages = parse_chat(_text("chat_unmarked_1to1.txt"), chat_name="Fulano", eu="Lucas")
    assert messages[0].text == "Bom dia! 10:30 vamos? Beleza: combinado"


def test_trailing_newline_does_not_change_last_message() -> None:
    base = "12/03/2024 14:22 - Ana: oi"
    assert parse_chat(base + "\n", chat_name="X")[-1].text == "oi"
    assert parse_chat(base, chat_name="X")[-1].text == "oi"

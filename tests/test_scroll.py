from wzsearch.scroll import (
    LINES_PER_NOTCH,
    MAX_ROWS_PER_EVENT,
    PIXELS_PER_ROW,
    rows_for_delta,
    touchpad_rows,
    unpack_touchpad_delta,
)


def test_direction_follows_the_delta() -> None:
    assert rows_for_delta(1) < 0  # wheel up scrolls back
    assert rows_for_delta(-1) > 0


def test_macos_events_move_exactly_one_row() -> None:
    # trackpad and mouse notches both report small deltas on macOS
    assert rows_for_delta(1) == -1
    assert rows_for_delta(-1) == 1
    assert rows_for_delta(3) == -1
    assert rows_for_delta(-8) == 1


def test_windows_notches_move_a_few_lines() -> None:
    assert rows_for_delta(120) == -LINES_PER_NOTCH
    assert rows_for_delta(-240) == 2 * LINES_PER_NOTCH


def test_large_deltas_are_capped() -> None:
    assert rows_for_delta(-1200) == MAX_ROWS_PER_EVENT
    assert rows_for_delta(99999) == -MAX_ROWS_PER_EVENT


def test_zero_delta_does_nothing() -> None:
    assert rows_for_delta(0) == 0
    assert rows_for_delta(None) == 0


def test_macos_fractional_deltas_still_scroll() -> None:
    """Trackpads report fractions (0.1, 0.3…): they must not be thrown away."""
    assert rows_for_delta(0.1) == -1
    assert rows_for_delta(-0.3) == 1
    assert rows_for_delta(0.999) == -1
    assert rows_for_delta(-1.5) == 1


def test_touchpad_delta_is_unpacked_like_tk_does() -> None:
    """Tk 9 packs both deltas: ``deltaX << 16 | deltaY``."""
    assert unpack_touchpad_delta(0) == (0, 0)
    assert unpack_touchpad_delta(1) == (0, 1)
    assert unpack_touchpad_delta(-1) == (-1, -1)
    assert unpack_touchpad_delta(3) == (0, 3)
    assert unpack_touchpad_delta(-3) == (-1, -3)
    assert unpack_touchpad_delta(65537) == (1, 1)


def test_touchpad_rows_follow_the_pixels() -> None:
    assert touchpad_rows(0) == 0
    assert touchpad_rows(None) == 0
    # o Tk manda pixels: um "entalhe" de trackpad costuma vir pequeno
    assert touchpad_rows(1) == -1
    assert touchpad_rows(-1) == 1
    assert touchpad_rows(PIXELS_PER_ROW) == -1
    assert touchpad_rows(-PIXELS_PER_ROW * 3) == 3
    assert touchpad_rows(-PIXELS_PER_ROW * 99) == MAX_ROWS_PER_EVENT
    # delta puramente horizontal não rola na vertical
    assert touchpad_rows(65536) == 0

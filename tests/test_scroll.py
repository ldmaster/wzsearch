from wzsearch.scroll import LINES_PER_NOTCH, MAX_ROWS_PER_EVENT, rows_for_delta


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

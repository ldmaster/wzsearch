from wzsearch.scroll import MAX_ROWS_PER_EVENT, rows_for_delta


def test_direction_follows_the_delta() -> None:
    assert rows_for_delta(1) < 0  # wheel up scrolls back
    assert rows_for_delta(-1) > 0


def test_macos_small_deltas_move_one_row() -> None:
    assert rows_for_delta(1) == -1
    assert rows_for_delta(-1) == 1


def test_windows_notches_move_proportionally() -> None:
    assert rows_for_delta(120) == -1
    assert rows_for_delta(-240) == 2


def test_large_deltas_are_capped() -> None:
    assert abs(rows_for_delta(-1200)) == MAX_ROWS_PER_EVENT
    assert abs(rows_for_delta(50)) == MAX_ROWS_PER_EVENT


def test_zero_delta_does_nothing() -> None:
    assert rows_for_delta(0) == 0

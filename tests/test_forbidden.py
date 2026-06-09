from omok.board import Board
from omok.constants import BLACK, WHITE
from omok.rules import RuleEngine


def test_double_three_is_illegal():
    board = Board()
    rules = RuleEngine()
    for pos in ((9, 8), (9, 10), (8, 9), (10, 9)):
        board.place(pos[0], pos[1], BLACK)
    assert rules.is_double_three(board, 9, 9, BLACK)
    assert not rules.is_legal_move(board, 9, 9, BLACK)


def test_broken_double_three_is_allowed():
    board = Board()
    rules = RuleEngine()
    for pos in ((9, 8), (9, 11), (8, 9), (11, 9)):
        board.place(pos[0], pos[1], BLACK)

    assert not rules.is_double_three(board, 9, 9, BLACK)
    assert rules.is_legal_move(board, 9, 9, BLACK)


def test_only_connected_double_three_is_forbidden():
    rules = RuleEngine()

    example1 = Board()
    for pos in ((9, 8), (9, 11), (8, 9), (11, 9)):
        example1.place(pos[0], pos[1], BLACK)
    assert rules.is_legal_move(example1, 9, 9, BLACK)

    example2 = Board()
    for pos in ((9, 8), (9, 10), (8, 9), (10, 9)):
        example2.place(pos[0], pos[1], BLACK)
    assert not rules.is_legal_move(example2, 9, 9, BLACK)

    example3 = Board()
    for pos in ((9, 8), (9, 10), (8, 9), (11, 9)):
        example3.place(pos[0], pos[1], BLACK)
    assert rules.is_legal_move(example3, 9, 9, BLACK)


def test_double_four_is_illegal():
    board = Board()
    rules = RuleEngine()
    for pos in ((9, 6), (9, 7), (9, 8), (6, 9), (7, 9), (8, 9)):
        board.place(pos[0], pos[1], BLACK)
    assert rules.is_double_four(board, 9, 9, BLACK)
    assert not rules.is_legal_move(board, 9, 9, BLACK)


def _place_connected_open_four_stones(board, direction):
    stones_by_direction = {
        "horizontal": ((9, 6), (9, 7), (9, 8)),
        "vertical": ((6, 9), (7, 9), (8, 9)),
        "diag_down": ((6, 6), (7, 7), (8, 8)),
        "diag_up": ((6, 12), (7, 11), (8, 10)),
    }
    for r, c in stones_by_direction[direction]:
        board.place(r, c, BLACK)


def test_double_four_allowed_option_permits_connected_open_44():
    board = Board()
    rules = RuleEngine(allow_double_four=True)
    _place_connected_open_four_stones(board, "horizontal")
    _place_connected_open_four_stones(board, "vertical")

    assert rules.is_double_four(board, 9, 9, BLACK) is False
    assert rules.is_legal_move(board, 9, 9, BLACK)


def test_double_four_allowed_option_still_rejects_blocked_or_occupied():
    rules = RuleEngine(allow_double_four=True)
    blocked = Board(blocked_cells=[(10, 10)])
    occupied = Board()
    occupied.place(9, 9, BLACK)

    assert not rules.is_legal_move(blocked, 9, 9, BLACK)
    assert not rules.is_legal_move(occupied, 9, 9, BLACK)


def test_connected_open_44_is_illegal_by_default():
    board = Board()
    rules = RuleEngine()
    _place_connected_open_four_stones(board, "horizontal")
    _place_connected_open_four_stones(board, "vertical")

    assert rules.is_double_four(board, 9, 9, BLACK)
    assert not rules.is_legal_move(board, 9, 9, BLACK)


def test_broken_44_is_legal_for_double_four_rule():
    board = Board()
    rules = RuleEngine()
    board.place(9, 5, WHITE)
    board.place(8, 6, WHITE)
    for pos in ((9, 7), (9, 8), (9, 10), (10, 6), (11, 6), (13, 6)):
        board.place(pos[0], pos[1], BLACK)

    assert not rules.is_double_four(board, 9, 6, BLACK)
    assert rules.is_legal_move(board, 9, 6, BLACK)


def test_split_44_is_legal_for_double_four_rule():
    board = Board()
    rules = RuleEngine()
    board.place(12, 7, WHITE)
    for pos in ((9, 8), (9, 10), (9, 11), (7, 7), (10, 7), (11, 7)):
        board.place(pos[0], pos[1], BLACK)

    assert not rules.is_double_four(board, 9, 7, BLACK)
    assert rules.is_legal_move(board, 9, 7, BLACK)


def test_closed_44_is_legal_for_double_four_rule():
    board = Board()
    rules = RuleEngine()
    board.place(9, 5, WHITE)
    board.place(13, 9, WHITE)
    for pos in ((9, 6), (9, 7), (9, 8), (10, 9), (11, 9), (12, 9)):
        board.place(pos[0], pos[1], BLACK)

    assert not rules.is_double_four(board, 9, 9, BLACK)
    assert rules.is_legal_move(board, 9, 9, BLACK)


def test_winning_move_overrides_connected_open_44():
    board = Board()
    rules = RuleEngine()
    for pos in ((9, 5), (9, 6), (9, 7), (9, 8), (6, 9), (7, 9), (8, 9)):
        board.place(pos[0], pos[1], BLACK)

    assert rules.is_legal_move(board, 9, 9, BLACK)


def test_connected_open_44_all_direction_pairs():
    directions = ("horizontal", "vertical", "diag_down", "diag_up")
    rules = RuleEngine()
    for idx, first in enumerate(directions):
        for second in directions[idx + 1:]:
            board = Board()
            _place_connected_open_four_stones(board, first)
            _place_connected_open_four_stones(board, second)

            assert rules.is_double_four(board, 9, 9, BLACK), (first, second)
            assert not rules.is_legal_move(board, 9, 9, BLACK), (first, second)


def test_winning_move_overrides_double_forbidden_shape():
    board = Board()
    rules = RuleEngine()
    for pos in ((9, 5), (9, 6), (9, 7), (9, 8), (6, 9), (7, 9), (8, 9)):
        board.place(pos[0], pos[1], BLACK)
    assert rules.is_legal_move(board, 9, 9, BLACK)
    board.place(9, 9, BLACK)
    assert rules.check_win(board, 9, 9, BLACK)

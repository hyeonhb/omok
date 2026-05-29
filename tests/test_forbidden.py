from omok.board import Board
from omok.constants import BLACK
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


def test_winning_move_overrides_double_forbidden_shape():
    board = Board()
    rules = RuleEngine()
    for pos in ((9, 5), (9, 6), (9, 7), (9, 8), (6, 9), (7, 9), (8, 9)):
        board.place(pos[0], pos[1], BLACK)
    assert rules.is_legal_move(board, 9, 9, BLACK)
    board.place(9, 9, BLACK)
    assert rules.check_win(board, 9, 9, BLACK)

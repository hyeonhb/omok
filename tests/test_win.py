from omok.board import Board
from omok.constants import BLACK
from omok.rules import RuleEngine


def test_horizontal_five_wins():
    board = Board()
    rules = RuleEngine()
    for c in range(5):
        board.place(9, c, BLACK)
    assert rules.check_win(board, 9, 2, BLACK)


def test_vertical_five_wins():
    board = Board()
    rules = RuleEngine()
    for r in range(5):
        board.place(r, 9, BLACK)
    assert rules.check_win(board, 2, 9, BLACK)


def test_diagonal_five_wins():
    board = Board()
    rules = RuleEngine()
    for i in range(5):
        board.place(i, i, BLACK)
    assert rules.check_win(board, 2, 2, BLACK)


def test_six_or_more_wins():
    board = Board()
    rules = RuleEngine()
    for c in range(6):
        board.place(9, c, BLACK)
    assert rules.check_win(board, 9, 3, BLACK)


def test_four_does_not_win():
    board = Board()
    rules = RuleEngine()
    for c in range(4):
        board.place(9, c, BLACK)
    assert not rules.check_win(board, 9, 2, BLACK)

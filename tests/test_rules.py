from omok.board import Board
from omok.constants import BLACK
from omok.patterns import PatternAnalyzer
from omok.rules import RuleEngine


def test_blocked_cell_is_illegal():
    board = Board(blocked_cells=[(10, 10)])
    rules = RuleEngine()
    assert not rules.is_legal_move(board, 9, 9, BLACK)


def test_blocked_cell_is_wall_for_open_three_pattern():
    board = Board(blocked_cells=[(10, 8)])
    analyzer = PatternAnalyzer()
    for c in (8, 9, 10):
        board.place(9, c, BLACK)
    assert not analyzer.has_open_three_in_direction(board, 9, 9, BLACK, 0, 1)


def test_coordinate_conversion_is_external_one_based():
    from omok.constants import to_external, to_internal

    assert to_internal((10, 10)) == (9, 9)
    assert to_external((9, 9)) == (10, 10)
    assert to_internal((1, 1)) == (18, 0)
    assert to_external((18, 0)) == (1, 1)
    assert to_internal((19, 19)) == (0, 18)
    assert to_external((0, 18)) == (19, 19)

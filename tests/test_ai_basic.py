import time

from omok.ai import OmokAI
from omok.constants import BLACK, to_internal
from omok.rules import RuleEngine


def test_black_first_move_is_center_external_coordinate():
    ai = OmokAI(color=BLACK)
    assert ai.choose_move() == (10, 10)


def test_ai_returns_legal_move_under_three_seconds():
    ai = OmokAI(color=BLACK, blocked_cells=[(10, 10), (3, 3), (15, 7)], time_limit=3.0)
    start = time.time()
    move = ai.choose_move()
    elapsed = time.time() - start
    r, c = to_internal(move)
    assert elapsed < 3.0
    assert move != (10, 10)
    assert RuleEngine().check_win(ai.board, r, c, BLACK) or ai.board.get(r, c) == BLACK


def test_ai_does_not_play_blocked_cell():
    ai = OmokAI(color=BLACK, blocked_cells=[(10, 10), (10, 11), (11, 10)], time_limit=1.0)
    move = ai.choose_move()
    assert move not in {(10, 10), (10, 11), (11, 10)}

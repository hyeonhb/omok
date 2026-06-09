import time
from unittest.mock import patch

from omok.board import Board
from omok.constants import BLACK, WHITE
from omok.search import SearchEngine
from omok.search_config import USE_PVS


def test_use_pvs_enabled_by_default():
    assert USE_PVS is True


def test_search_resets_heuristics_at_start():
    engine = SearchEngine()
    engine.killer_moves[2] = [(8, 8)]
    engine.history_scores[(7, 7)] = 100
    board = Board()
    board.place(9, 9, BLACK)
    with patch.object(engine, "_reset_search_heuristics", wraps=engine._reset_search_heuristics) as reset:
        engine.search(board, BLACK, time.time() + 1.0, fallback=(9, 10))
    reset.assert_called_once()


def test_record_killer_on_beta_cutoff():
    engine = SearchEngine()
    engine._record_killer(3, (9, 10))
    engine._record_killer(3, (8, 10))
    engine._record_killer(3, (9, 9))
    assert engine.killer_moves[3][0] == (9, 9)
    assert len(engine.killer_moves[3]) <= 2


def test_record_history_on_cutoff_and_decay():
    engine = SearchEngine()
    for i in range(600):
        engine._record_history((i % 19, (i * 2) % 19), 2)
    assert len(engine.history_scores) <= 600
    assert all(score >= 0 for score in engine.history_scores.values())


def test_pv_move_ordered_first():
    engine = SearchEngine()
    board = Board()
    board.place(9, 9, BLACK)
    moves = [(9, 8), (9, 10), (8, 9)]
    ordered = engine._order_moves_for_search(
        board,
        BLACK,
        2,
        moves,
        deadline=time.time() + 1.0,
        pv_move=(8, 9),
    )
    assert ordered[0] == (8, 9)


def test_root_search_does_not_define_search_child():
    assert "_search_child" not in SearchEngine.__dict__


def test_root_pvs_passes_full_then_null_window_to_negamax():
    engine = SearchEngine()
    board = Board()
    board.place(9, 9, BLACK)
    windows = []

    def spy_negamax(board_arg, depth, alpha, beta, color, deadline):
        windows.append((alpha, beta))
        return 0

    engine.negamax = spy_negamax
    engine._limited_candidates = lambda board, color, depth, deadline: [(9, 8), (9, 10), (8, 9)]
    engine._root_search(board, 2, BLACK, time.time() + 1.0)
    assert len(windows) >= 2
    assert windows[0][1] - windows[0][0] > 1000
    assert windows[1][1] - windows[1][0] <= 1


def test_pvs_fallback_when_disabled():
    board = Board()
    board.place(9, 9, BLACK)
    with patch("omok.search.USE_PVS", False):
        engine = SearchEngine()
        move = engine.search(board, BLACK, time.time() + 1.0, fallback=(9, 10))
    assert move is not None


def test_choose_move_within_three_seconds():
    from omok.ai import OmokAI
    from omok.constants import to_internal

    board_setup = [(9, 9, BLACK), (10, 10, BLACK), (9, 10, WHITE)]
    ai = OmokAI(color=BLACK, blocked_cells=[(3, 3), (10, 12), (15, 7)], time_limit=3.0)
    for r, c, stone in board_setup:
        ai.board.place(r, c, stone)
    start = time.time()
    move = ai.choose_move()
    assert time.time() - start < 3.0
    r, c = to_internal(move)
    assert ai.board.get(r, c) == BLACK

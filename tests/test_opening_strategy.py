import time
from unittest.mock import patch

from omok.ai import OmokAI
from omok.board import Board
from omok.constants import BLACK, WHITE, to_internal
from omok.evaluator import Evaluator
from omok.move_generator import MoveGenerator
from omok.search import SearchEngine
from omok.strategy_config import (
    ENABLE_BLACK_OPENING_SEED,
    ENABLE_PLAN_CANDIDATES,
    ENABLE_WHITE_OPENING_DISRUPTION,
    OPENING_STRATEGY_MAX_MOVES,
)


def test_default_strategy_weights_are_neutral():
    ai = OmokAI(color=BLACK)
    weights = ai.strategy_weights
    assert weights.black_initiative_weight == 1.0
    assert weights.plan_candidate_weight == 0.0
    assert weights.leaf_next_threat_weight == 0.0


def test_color_specific_opening_flags():
    assert ENABLE_BLACK_OPENING_SEED is True
    assert ENABLE_WHITE_OPENING_DISRUPTION is False


def test_opening_multi_direction_seed_scores_for_black_only():
    board = Board()
    board.place(9, 9, BLACK)
    evaluator = Evaluator()
    assert evaluator.evaluate_opening_multi_direction_seed(board, 9, 10, BLACK) > 0
    assert evaluator.evaluate_opening_multi_direction_seed(board, 9, 10, WHITE) == 0


def test_black_root_deep_score_includes_opening_bonus():
    board = Board()
    board.place(9, 9, BLACK)
    evaluator = Evaluator()
    base = evaluator.quick_score_candidate(board, 9, 10, BLACK)
    deep = evaluator.deep_score_candidate(board, 9, 10, BLACK, root_eval=True)
    assert deep > base


def test_white_root_deep_score_excludes_opening_bonus():
    board = Board()
    board.place(9, 9, BLACK)
    board.place(8, 10, BLACK)
    evaluator = Evaluator()
    base = evaluator.quick_score_candidate(board, 10, 9, WHITE)
    deep = evaluator.deep_score_candidate(board, 10, 9, WHITE, root_eval=True)
    assert deep == base


def test_white_disruption_not_applied_when_disabled():
    board = Board()
    board.place(9, 9, BLACK)
    board.place(8, 10, BLACK)
    evaluator = Evaluator()
    assert evaluator.evaluate_opening_disruption(board, 10, 9, WHITE) == 0
    assert evaluator._root_opening_bonus(board, 10, 9, WHITE) == 0


def test_opening_scores_zero_after_max_moves():
    board = Board()
    evaluator = Evaluator()
    for i in range(OPENING_STRATEGY_MAX_MOVES):
        board.place(i % 19, (i * 2) % 19, BLACK if i % 2 == 0 else WHITE)
    assert evaluator.evaluate_opening_multi_direction_seed(board, 5, 5, BLACK) == 0
    assert evaluator.evaluate_opening_disruption(board, 5, 6, WHITE) == 0


def test_plan_candidates_excluded_by_default():
    assert ENABLE_PLAN_CANDIDATES is False
    board = Board()
    board.place(9, 9, BLACK)
    generator = MoveGenerator()
    seen = {}

    original = generator.generate_tactical_moves

    def wrapper(*args, **kwargs):
        seen["include_plan_candidates"] = kwargs.get("include_plan_candidates")
        return original(*args, **kwargs)

    generator.generate_tactical_moves = wrapper
    generator.generate_search_candidates(board, BLACK, max_moves=1)
    assert seen["include_plan_candidates"] is False


def test_leaf_next_threat_skipped_by_default():
    evaluator = Evaluator()
    with patch.object(evaluator, "evaluate_next_threat_potential", return_value=999_999) as mocked:
        evaluator._pattern_score(Board(), BLACK)
    mocked.assert_not_called()


def test_search_engine_does_not_call_opening_evaluations():
    engine = SearchEngine()
    board = Board()
    board.place(9, 9, BLACK)
    observed = {"seed": 0, "disruption": 0}

    def spy_seed(*args, **kwargs):
        observed["seed"] += 1
        return 0

    def spy_disruption(*args, **kwargs):
        observed["disruption"] += 1
        return 0

    engine.evaluator.evaluate_opening_multi_direction_seed = spy_seed
    engine.evaluator.evaluate_opening_disruption = spy_disruption
    engine._limited_candidates(board, BLACK, depth=2, deadline=time.time() + 1.0)
    assert observed == {"seed": 0, "disruption": 0}


def test_omok_ai_black_uses_opening_seed_path():
    ai = OmokAI(color=BLACK)
    assert ai.color == BLACK


def test_omok_ai_white_does_not_apply_opening_disruption_in_deep_score():
    board = Board()
    board.place(9, 9, BLACK)
    evaluator = Evaluator()
    ai = OmokAI(color=WHITE)
    ai.board = board.copy()
    base = evaluator.quick_score_candidate(board, 10, 9, WHITE)
    deep = ai.generator.evaluator.deep_score_candidate(board, 10, 9, WHITE, root_eval=True)
    assert deep == base


def test_choose_move_returns_legal_move_within_three_seconds():
    for color, setup in ((BLACK, "opening"), (BLACK, "midgame"), (WHITE, "opening")):
        ai = OmokAI(color=color, blocked_cells=[(3, 3), (10, 12), (15, 7)], time_limit=3.0)
        if setup == "midgame":
            for r, c, stone in (
                (9, 9, WHITE),
                (9, 10, BLACK),
                (10, 10, WHITE),
                (8, 10, BLACK),
                (8, 8, WHITE),
                (10, 8, BLACK),
            ):
                ai.board.place(r, c, stone)
        start = time.time()
        move = ai.choose_move()
        elapsed = time.time() - start
        r, c = to_internal(move)
        assert elapsed < 3.0, (color, setup)
        assert ai.board.get(r, c) == color, (color, setup)

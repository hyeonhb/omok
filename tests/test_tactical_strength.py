import time

from omok.ai import OmokAI
from omok.board import Board
from omok.constants import BLACK, WHITE, to_internal
from omok.evaluator import Evaluator
from omok.move_generator import MoveGenerator
from omok.patterns import PatternAnalyzer
from omok.rules import RuleEngine
from omok.threat_search import ThreatSearch


def test_analyze_board_counts_broken_open_three():
    board = Board()
    analyzer = PatternAnalyzer()
    board.place(9, 8, BLACK)
    board.place(9, 9, BLACK)
    board.place(9, 11, BLACK)

    counts = analyzer.analyze_board(board, BLACK)

    assert counts["broken_open_three"] >= 1


def test_broken_open_three_scores_without_forbidden_penalty():
    board = Board()
    analyzer = PatternAnalyzer()
    evaluator = Evaluator()
    board.place(9, 8, BLACK)
    board.place(9, 11, BLACK)

    counts = analyzer.analyze_move(board, 9, 9, BLACK)
    broken_score = evaluator.score_candidate(board, 9, 9, BLACK)
    quiet_score = evaluator.score_candidate(board, 5, 5, BLACK)

    assert counts["broken_open_three"] >= 1
    assert RuleEngine().is_legal_move(board, 9, 9, BLACK)
    assert broken_score > quiet_score


def test_legal_double_three_threat_gets_high_score():
    board = Board()
    evaluator = Evaluator()
    rules = RuleEngine()
    for pos in ((9, 8), (9, 11), (8, 9), (11, 9)):
        board.place(pos[0], pos[1], BLACK)

    assert rules.is_legal_move(board, 9, 9, BLACK)
    assert evaluator.score_candidate(board, 9, 9, BLACK) >= 900_000


def test_opponent_legal_double_three_threat_is_essential_candidate():
    board = Board()
    generator = MoveGenerator()
    for pos in ((9, 8), (9, 11), (8, 9), (11, 9)):
        board.place(pos[0], pos[1], WHITE)

    candidates = generator.generate_search_candidates(board, BLACK, max_moves=1)

    assert (9, 9) in candidates


def test_ai_blocks_opponent_four_three_move():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    for pos in ((9, 6), (9, 7), (9, 8), (8, 9), (11, 9)):
        ai.board.place(pos[0], pos[1], WHITE)

    assert ai.choose_move() == (10, 10)


def test_defensive_tss_detects_opponent_open_four_creation():
    board = Board()
    tss = ThreatSearch()
    for c in (6, 7, 8):
        board.place(9, c, WHITE)

    defense = tss.find_opponent_forcing_attack(
        board,
        opponent_color=WHITE,
        defender_color=BLACK,
        deadline=time.time() + 0.4,
        max_depth=4,
    )

    assert defense in {(9, 5), (9, 9)}


def test_defensive_tss_detects_opponent_four_three_creation():
    board = Board()
    tss = ThreatSearch()
    for pos in ((9, 6), (9, 7), (9, 8), (8, 9), (11, 9)):
        board.place(pos[0], pos[1], WHITE)

    defense = tss.find_opponent_forcing_attack(
        board,
        opponent_color=WHITE,
        defender_color=BLACK,
        deadline=time.time() + 0.4,
        max_depth=4,
    )

    assert defense == (9, 9)


def test_defensive_tss_excludes_illegal_defense_points():
    board = Board(blocked_cells=[(10, 10), (1, 1), (19, 19)])
    tss = ThreatSearch()
    for c in (6, 7, 8):
        board.place(9, c, WHITE)

    replies = tss._direct_defense_replies(board, WHITE, BLACK)

    assert (9, 9) not in replies


def test_defensive_tss_deadline_returns_promptly():
    board = Board()
    tss = ThreatSearch()
    for pos in ((9, 6), (9, 7), (9, 8), (8, 9), (11, 9)):
        board.place(pos[0], pos[1], WHITE)

    start = time.time()
    result = tss.find_opponent_forcing_attack(
        board,
        opponent_color=WHITE,
        defender_color=BLACK,
        deadline=time.time() - 0.01,
        max_depth=6,
    )

    assert result is None
    assert time.time() - start < 0.1


def test_ai_prefers_future_four_three_setup_over_single_open_three():
    board = Board()
    evaluator = Evaluator()
    for pos in ((9, 7), (9, 8), (8, 10), (11, 10)):
        board.place(pos[0], pos[1], BLACK)
    for pos in ((3, 3), (15, 15)):
        board.place(pos[0], pos[1], WHITE)

    setup_score = evaluator.score_candidate(board, 9, 10, BLACK)
    simple_three_score = evaluator.score_candidate(board, 4, 4, BLACK)

    assert setup_score > simple_three_score


def test_future_four_three_setup_scores_above_single_open_three():
    board = Board()
    evaluator = Evaluator()
    for pos in ((9, 7), (9, 8), (8, 10), (11, 10)):
        board.place(pos[0], pos[1], BLACK)
    board.place(4, 4, BLACK)
    board.place(4, 6, BLACK)

    setup_score = evaluator.deep_score_candidate(board, 9, 10, BLACK)
    open_three_score = evaluator.deep_score_candidate(board, 4, 5, BLACK)

    assert setup_score > open_three_score


def test_resilient_future_four_three_setup_scores_higher():
    board = Board()
    evaluator = Evaluator()
    for pos in ((9, 7), (9, 8), (8, 10), (11, 10), (7, 7), (8, 8), (10, 6), (11, 5)):
        board.place(pos[0], pos[1], BLACK)

    resilient = evaluator.evaluate_resilient_future_four_three_setup(board, (8, 9), BLACK)
    simple = evaluator.evaluate_future_threat_potential(board, (8, 9), BLACK)

    assert resilient > simple


def test_candidate_allowing_opponent_open_four_gets_large_penalty():
    board = Board()
    evaluator = Evaluator()
    for c in (6, 7, 8):
        board.place(9, c, WHITE)
    board.place(3, 3, BLACK)
    board.place(3, 5, BLACK)

    risky = evaluator.deep_score_candidate(board, 3, 4, BLACK)
    block = evaluator.deep_score_candidate(board, 9, 9, BLACK)

    assert block > risky


def test_deep_score_deadline_skips_heavy_calculations():
    board = Board()
    evaluator = Evaluator()
    board.place(9, 8, BLACK)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("heavy calculation should be skipped")

    evaluator.evaluate_resilient_future_four_three_setup = fail_if_called
    evaluator.evaluate_opponent_best_reply_penalty = fail_if_called

    score = evaluator.deep_score_candidate(board, 9, 9, BLACK, deadline=time.time() - 0.01)

    assert score > 0


def test_future_setup_order_uses_resilient_score():
    board = Board()
    generator = MoveGenerator()
    board.place(9, 9, BLACK)
    board.place(9, 10, WHITE)

    generator.evaluator.evaluate_future_threat_potential = lambda board, move, color, deadline=None: 400_000
    generator.evaluator.evaluate_resilient_future_four_three_setup = (
        lambda board, move, color, deadline=None: 1_500_000 if move == (9, 8) else 0
    )

    moves = generator.find_future_four_three_setup_moves(board, BLACK, deadline=time.time() + 1.0)

    assert moves[0] == (9, 8)


def test_many_small_patterns_do_not_outscore_four_three():
    board = Board()
    evaluator = Evaluator()
    for pos in ((9, 6), (9, 7), (9, 8), (8, 9), (11, 9)):
        board.place(pos[0], pos[1], BLACK)
    for pos in ((3, 3), (3, 5), (5, 3), (5, 5), (14, 14), (14, 16), (16, 14), (16, 16)):
        board.place(pos[0], pos[1], BLACK)

    four_three_score = evaluator.quick_score_candidate(board, 9, 9, BLACK)
    small_patterns_score = evaluator.quick_score_candidate(board, 4, 4, BLACK)

    assert four_three_score > small_patterns_score


def test_leaf_evaluate_open_twos_do_not_outscore_four_three():
    evaluator = Evaluator()
    four_three_board = Board()
    for pos in ((9, 6), (9, 7), (9, 8), (8, 9), (11, 9)):
        four_three_board.place(pos[0], pos[1], BLACK)
    four_three_board.place(9, 9, BLACK)

    small_board = Board()
    for pos in ((3, 3), (3, 5), (5, 3), (5, 5), (14, 14), (14, 16), (16, 14), (16, 16)):
        small_board.place(pos[0], pos[1], BLACK)

    assert evaluator.evaluate(four_three_board, BLACK) > evaluator.evaluate(small_board, BLACK)


def test_leaf_evaluate_open_threes_do_not_outscore_open_four():
    evaluator = Evaluator()
    open_four_board = Board()
    for c in (6, 7, 8, 9):
        open_four_board.place(9, c, BLACK)

    threes_board = Board()
    for pos in ((3, 3), (3, 4), (3, 5), (10, 10), (10, 11), (10, 12)):
        threes_board.place(pos[0], pos[1], BLACK)

    assert evaluator.evaluate(open_four_board, BLACK) > evaluator.evaluate(threes_board, BLACK)


def test_root_deep_rerank_does_not_override_immediate_win():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    for c in range(5, 9):
        ai.board.place(9, c, BLACK)

    ai._root_deep_rerank = lambda deadline, fallback: (_ for _ in ()).throw(
        AssertionError("deep rerank should not be called before immediate win")
    )

    move = ai.choose_move()

    assert move in {(10, 5), (10, 10)}


def test_root_deep_rerank_can_choose_better_general_candidate():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    ai.board.place(9, 9, BLACK)
    ai.board.place(10, 10, WHITE)
    empty = {
        "immediate_win": [],
        "open_four": [],
        "four_three": [],
        "legal_double_three_threat": [],
        "closed_four": [],
        "open_three": [],
        "broken_open_three": [],
    }
    ai.generator.fallback_move = lambda board, color, deadline=None: (9, 8)
    ai.generator.classify_tactical_moves = lambda board, color, radius=4, deadline=None: empty
    ai.generator.find_future_four_three_setup_moves = lambda board, color, deadline=None: []
    ai.threat_search.find_forcing_attack = lambda board, color, deadline: None
    ai.threat_search.find_forcing_defense = lambda board, color, deadline: None
    ai.generator.generate_search_candidates = lambda *args, **kwargs: [(9, 8), (9, 10)]
    ai.generator.evaluator.deep_score_candidate = (
        lambda board, r, c, color, deadline=None: 500_000 if (r, c) == (9, 10) else 1
    )

    assert ai._choose_move_internal(time.time() + 1.0) == (9, 10)


def test_root_deep_rerank_returns_none_below_threshold():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    ai.board.place(9, 9, BLACK)
    ai.board.place(10, 10, WHITE)
    ai.generator.generate_search_candidates = lambda *args, **kwargs: [(9, 8), (9, 10)]
    ai.generator.evaluator.deep_score_candidate = (
        lambda board, r, c, color, deadline=None: 399_999 if (r, c) == (9, 10) else 1
    )

    assert ai._root_deep_rerank(time.time() + 1.0, fallback=(9, 8)) is None


def test_root_deep_rerank_returns_move_at_threshold():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    ai.board.place(9, 9, BLACK)
    ai.board.place(10, 10, WHITE)
    ai.generator.generate_search_candidates = lambda *args, **kwargs: [(9, 8), (9, 10)]
    ai.generator.evaluator.deep_score_candidate = (
        lambda board, r, c, color, deadline=None: 400_000 if (r, c) == (9, 10) else 1
    )

    assert ai._root_deep_rerank(time.time() + 1.0, fallback=(9, 8)) == (9, 10)


def test_ambiguous_root_deep_rerank_allows_search_engine():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    ai.board.place(9, 9, BLACK)
    ai.board.place(10, 10, WHITE)
    empty = {
        "immediate_win": [],
        "open_four": [],
        "four_three": [],
        "legal_double_three_threat": [],
        "closed_four": [],
        "open_three": [],
        "broken_open_three": [],
    }
    called = {"search": False}
    ai.generator.fallback_move = lambda board, color, deadline=None: (9, 8)
    ai.generator.classify_tactical_moves = lambda board, color, radius=4, deadline=None: empty
    ai.generator.find_future_four_three_setup_moves = lambda board, color, deadline=None: []
    ai.threat_search.find_forcing_attack = lambda board, color, deadline: None
    ai.threat_search.find_forcing_defense = lambda board, color, deadline: None
    ai.generator.generate_search_candidates = lambda *args, **kwargs: [(9, 8), (9, 10)]
    ai.generator.evaluator.deep_score_candidate = lambda *args, **kwargs: 10

    def fake_search(board, color, deadline, fallback=None):
        called["search"] = True
        return (9, 10)

    ai.search_engine.search = fake_search

    assert ai._choose_move_internal(time.time() + 1.0) == (9, 10)
    assert called["search"]


def test_root_deep_rerank_candidate_generation_skips_future_setup():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    ai.board.place(9, 9, BLACK)
    ai.board.place(10, 10, WHITE)
    captured = {}

    def fake_generate(*args, **kwargs):
        captured.update(kwargs)
        return [(9, 8)]

    def fail_future(*args, **kwargs):
        raise AssertionError("future setup should not run during root candidate generation")

    ai.generator.generate_search_candidates = fake_generate
    ai.generator.find_future_four_three_setup_moves = fail_future
    ai.generator.evaluator.deep_score_candidate = lambda *args, **kwargs: 500_000

    assert ai._root_deep_rerank(time.time() + 1.0, fallback=None) == (9, 8)
    assert captured["include_future_setup"] is False
    assert captured["use_deep_score"] is False


def test_root_deep_rerank_deep_score_can_use_heavy_eval():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    ai.board.place(9, 9, BLACK)
    ai.board.place(10, 10, WHITE)
    called = {"deep": False}
    ai.generator.generate_search_candidates = lambda *args, **kwargs: [(9, 8)]

    def fake_deep(*args, **kwargs):
        called["deep"] = True
        assert kwargs.get("deadline") is not None
        return 500_000

    ai.generator.evaluator.deep_score_candidate = fake_deep

    assert ai._root_deep_rerank(time.time() + 1.0, fallback=None) == (9, 8)
    assert called["deep"]


def test_ai_prefers_four_three_over_simple_closed_four():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    for pos in ((9, 6), (9, 7), (9, 8), (8, 9), (11, 9)):
        ai.board.place(pos[0], pos[1], BLACK)
    for pos in ((4, 4), (4, 5), (4, 6)):
        ai.board.place(pos[0], pos[1], BLACK)
    ai.board.place(4, 3, WHITE)

    assert ai.choose_move() == (10, 10)


def test_existing_opponent_open_four_has_two_winning_ends():
    board = Board()
    generator = MoveGenerator()
    for c in range(6, 10):
        board.place(9, c, WHITE)

    wins = generator.find_immediate_wins(board, WHITE)

    assert (9, 5) in wins
    assert (9, 10) in wins
    assert generator.has_unblockable_open_four(board, WHITE, BLACK)


def test_opponent_open_four_creation_is_defense_candidate():
    board = Board()
    generator = MoveGenerator()
    for c in range(6, 9):
        board.place(9, c, WHITE)

    candidates = generator.generate_search_candidates(board, BLACK, max_moves=1)

    assert (9, 5) in candidates or (9, 9) in candidates


def test_own_four_three_can_precede_opponent_open_four_prevention():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    for pos in ((9, 6), (9, 7), (9, 8), (8, 9), (11, 9)):
        ai.board.place(pos[0], pos[1], BLACK)
    for pos in ((4, 4), (4, 5), (4, 6)):
        ai.board.place(pos[0], pos[1], WHITE)

    assert ai.choose_move() == (10, 10)


def test_opponent_future_setup_checked_before_own_future_setup():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    ai.board.place(9, 9, WHITE)
    ai.board.place(9, 10, BLACK)
    empty = {
        "immediate_win": [],
        "open_four": [],
        "four_three": [],
        "legal_double_three_threat": [],
        "closed_four": [],
        "open_three": [],
        "broken_open_three": [],
    }

    ai.generator.fallback_move = lambda board, color, deadline=None: (9, 8)
    ai.generator.classify_tactical_moves = lambda board, color, radius=4, deadline=None: empty
    ai.generator.find_immediate_wins = lambda board, color, deadline=None: []
    ai.generator.find_moves_by_pattern = lambda board, color, pattern_type: []
    ai.generator.find_four_three_moves = lambda board, color: []
    ai.generator.find_legal_double_three_threats = lambda board, color: []
    ai.generator.find_future_four_three_setup_moves = (
        lambda board, color, deadline=None: [(9, 7)] if color == ai.opponent_color else [(9, 11)]
    )
    ai.threat_search.find_forcing_attack = lambda board, color, deadline: None
    ai.threat_search.find_forcing_defense = lambda board, color, deadline: None
    ai._root_deep_rerank = lambda soft_deadline, hard_deadline=None, fallback=None: None
    ai.search_engine.search = lambda board, color, deadline, fallback=None: (9, 7)

    assert ai._choose_move_internal(time.time() + 1.0) == (9, 7)


def test_broken_four_not_counted_as_closed_four():
    board = Board()
    analyzer = PatternAnalyzer()
    for c in (7, 8, 10):
        board.place(9, c, BLACK)

    counts = analyzer.analyze_move(board, 9, 6, BLACK)

    assert counts["broken_four"] == 1
    assert counts["closed_four"] == 0


def test_single_direction_broken_four_is_not_four_three():
    board = Board()
    analyzer = PatternAnalyzer()
    for c in (7, 8, 10):
        board.place(9, c, BLACK)

    counts = analyzer.analyze_move(board, 9, 6, BLACK)

    assert counts["broken_four"] == 1
    assert counts["four_three"] == 0


def test_horizontal_four_vertical_three_is_four_three():
    board = Board()
    analyzer = PatternAnalyzer()
    for pos in ((9, 6), (9, 7), (9, 8), (8, 9), (11, 9)):
        board.place(pos[0], pos[1], BLACK)

    counts = analyzer.analyze_move(board, 9, 9, BLACK)

    assert counts["four_three"] == 1


def test_diagonal_four_horizontal_three_is_four_three():
    board = Board()
    analyzer = PatternAnalyzer()
    for pos in ((6, 6), (7, 7), (8, 8), (9, 10), (9, 11)):
        board.place(pos[0], pos[1], BLACK)

    counts = analyzer.analyze_move(board, 9, 9, BLACK)

    assert counts["four_three"] == 1


def test_legal_double_three_requires_different_directions():
    board = Board()
    analyzer = PatternAnalyzer()
    board.place(9, 8, BLACK)
    board.place(9, 11, BLACK)

    same_direction = analyzer.analyze_move(board, 9, 9, BLACK)
    assert same_direction["legal_double_three_threat"] == 0

    board.place(8, 9, BLACK)
    board.place(11, 9, BLACK)
    different_directions = analyzer.analyze_move(board, 9, 9, BLACK)
    assert different_directions["legal_double_three_threat"] == 1


def test_two_broken_open_threes_in_different_directions_are_legal_double_three():
    board = Board()
    analyzer = PatternAnalyzer()
    for pos in ((9, 8), (9, 11), (8, 9), (11, 9)):
        board.place(pos[0], pos[1], BLACK)

    counts = analyzer.analyze_move(board, 9, 9, BLACK)

    assert counts["broken_open_three"] == 2
    assert counts["legal_double_three_threat"] == 1


def test_single_direction_broken_open_three_is_not_legal_double_three():
    board = Board()
    analyzer = PatternAnalyzer()
    board.place(9, 8, BLACK)
    board.place(9, 11, BLACK)

    counts = analyzer.analyze_move(board, 9, 9, BLACK)

    assert counts["broken_open_three"] == 1
    assert counts["legal_double_three_threat"] == 0


def test_search_candidates_can_skip_future_setup():
    board = Board()
    generator = MoveGenerator()
    board.place(9, 9, BLACK)
    board.place(9, 10, WHITE)

    with_future = generator.generate_search_candidates(board, BLACK, max_moves=2, include_future_setup=True)
    without_future = generator.generate_search_candidates(board, BLACK, max_moves=2, include_future_setup=False)

    assert len(with_future) >= len(without_future)


def test_generate_tactical_moves_skips_future_setup_when_disabled():
    board = Board()
    generator = MoveGenerator()
    board.place(9, 9, BLACK)
    called = {"future": False}

    def fail_if_called(*args, **kwargs):
        called["future"] = True
        return []

    generator.find_future_four_three_setup_moves = fail_if_called
    generator.generate_tactical_moves(board, BLACK, include_future_setup=False)

    assert not called["future"]


def test_future_four_three_setup_deadline_returns_safely():
    board = Board()
    generator = MoveGenerator()
    for pos in ((9, 9), (9, 10), (10, 9), (8, 8)):
        board.place(pos[0], pos[1], BLACK)

    moves = generator.find_future_four_three_setup_moves(board, BLACK, deadline=time.time() - 0.01)

    assert isinstance(moves, list)


def test_set_blocked_cells_clears_search_caches():
    ai = OmokAI(color=BLACK)
    ai.search_engine.transposition_table[(123, BLACK)] = object()
    ai.search_engine.eval_cache[(456, BLACK)] = 10

    ai.set_blocked_cells([(1, 1), (2, 2), (3, 3)])

    assert ai.search_engine.transposition_table == {}
    assert ai.search_engine.eval_cache == {}


def test_score_candidate_prioritizes_immediate_block():
    board = Board()
    evaluator = Evaluator()
    for c in range(5, 9):
        board.place(9, c, WHITE)

    block_score = evaluator.score_candidate(board, 9, 4, BLACK)
    quiet_score = evaluator.score_candidate(board, 5, 5, BLACK)

    assert block_score > quiet_score


def test_candidate_allowing_opponent_immediate_win_is_penalized():
    board = Board()
    evaluator = Evaluator()
    for c in range(5, 9):
        board.place(9, c, WHITE)
    board.place(3, 3, BLACK)
    board.place(3, 5, BLACK)

    risky_attack = evaluator.deep_score_candidate(board, 3, 4, BLACK)
    direct_block = evaluator.deep_score_candidate(board, 9, 4, BLACK)

    assert direct_block > risky_attack


def test_weak_attack_blocking_opponent_four_three_scores_higher():
    board = Board()
    evaluator = Evaluator()
    for pos in ((9, 6), (9, 7), (9, 8), (8, 9), (11, 9)):
        board.place(pos[0], pos[1], WHITE)
    board.place(3, 3, BLACK)

    blocking_move = evaluator.deep_score_candidate(board, 9, 9, BLACK)
    quiet_attack = evaluator.deep_score_candidate(board, 3, 4, BLACK)

    assert blocking_move > quiet_attack


def test_defense_points_include_broken_three_gap():
    board = Board()
    generator = MoveGenerator()
    board.place(9, 8, WHITE)
    board.place(9, 9, WHITE)
    board.place(9, 11, WHITE)

    points = generator.get_defense_points_for_threats(board, WHITE, BLACK)

    assert (9, 10) in points


def test_defense_points_include_broken_four_gap():
    board = Board()
    generator = MoveGenerator()
    for c in (6, 7, 8, 10):
        board.place(9, c, WHITE)

    points = generator.get_defense_points_for_threats(board, WHITE, BLACK)

    assert (9, 9) in points


def test_search_candidates_keep_essential_over_max_moves():
    board = Board()
    generator = MoveGenerator()
    for c in range(5, 9):
        board.place(9, c, BLACK)

    candidates = generator.generate_search_candidates(board, BLACK, max_moves=1)

    assert (9, 4) in candidates or (9, 9) in candidates
    assert len(candidates) > 1


def test_ai_plays_immediate_win():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    for c in range(5, 9):
        ai.board.place(9, c, BLACK)

    move = ai.choose_move()

    assert move in {(10, 5), (10, 10)}
    assert RuleEngine().check_win(ai.board, *to_internal(move), BLACK)


def test_ai_blocks_opponent_immediate_win():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    for c in range(5, 9):
        ai.board.place(9, c, WHITE)

    move = ai.choose_move()

    assert move in {(10, 5), (10, 10)}


def test_ai_creates_open_four():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    for c in range(6, 9):
        ai.board.place(9, c, BLACK)

    move = ai.choose_move()

    assert move in {(10, 6), (10, 10)}


def test_ai_blocks_opponent_open_four_creation():
    ai = OmokAI(color=BLACK, time_limit=1.0)
    for c in range(6, 9):
        ai.board.place(9, c, WHITE)

    move = ai.choose_move()

    assert move in {(10, 6), (10, 10)}


def test_blocked_good_move_is_not_candidate():
    board = Board(blocked_cells=[(10, 5), (1, 1), (19, 19)])
    generator = MoveGenerator()
    for c in range(5, 9):
        board.place(9, c, BLACK)

    candidates = generator.generate_search_candidates(board, BLACK, max_moves=4)

    assert (9, 4) not in candidates


def test_forbidden_rules_still_apply_after_tactical_changes():
    board = Board()
    rules = RuleEngine()
    for pos in ((9, 8), (9, 10), (8, 9), (10, 9)):
        board.place(pos[0], pos[1], BLACK)

    assert not rules.is_legal_move(board, 9, 9, BLACK)


def test_complex_midgame_choose_move_under_three_seconds_and_legal():
    ai = OmokAI(color=BLACK, blocked_cells=[(3, 3), (10, 12), (15, 7)], time_limit=3.0)
    stones = [
        (9, 9, WHITE),
        (9, 10, BLACK),
        (10, 10, WHITE),
        (8, 10, BLACK),
        (8, 8, WHITE),
        (10, 8, BLACK),
        (7, 9, WHITE),
        (11, 9, BLACK),
        (12, 12, WHITE),
        (6, 8, BLACK),
        (13, 13, WHITE),
        (5, 7, BLACK),
    ]
    for r, c, color in stones:
        ai.board.place(r, c, color)

    start = time.time()
    move = ai.choose_move()
    elapsed = time.time() - start

    assert elapsed < 3.0
    assert RuleEngine().check_win(ai.board, *to_internal(move), BLACK) or ai.board.get(*to_internal(move)) == BLACK


def test_repeated_midgame_choose_move_stays_under_three_seconds():
    base_stones = [
        (9, 9, WHITE),
        (9, 10, BLACK),
        (10, 10, WHITE),
        (8, 10, BLACK),
        (8, 8, WHITE),
        (10, 8, BLACK),
        (7, 9, WHITE),
        (11, 9, BLACK),
        (12, 12, WHITE),
        (6, 8, BLACK),
    ]
    max_elapsed = 0
    for extra in range(3):
        ai = OmokAI(color=BLACK, blocked_cells=[(3, 3), (10, 12), (15, 7)], time_limit=3.0)
        for r, c, color in base_stones:
            ai.board.place(r, c, color)
        ai.board.place(4 + extra, 13, WHITE)
        ai.board.place(5 + extra, 14, BLACK)

        start = time.time()
        move = ai.choose_move()
        elapsed = time.time() - start
        max_elapsed = max(max_elapsed, elapsed)

        assert elapsed < 3.0
        assert ai.board.get(*to_internal(move)) == BLACK
    assert max_elapsed < 3.0


def test_fallback_move_returns_quickly():
    board = Board()
    generator = MoveGenerator()
    for pos in ((9, 9), (9, 10), (10, 9), (8, 8), (7, 7)):
        board.place(pos[0], pos[1], BLACK)

    start = time.time()
    move = generator.fallback_move(board, WHITE, deadline=time.time() + 0.01)

    assert move is not None
    assert time.time() - start < 0.1


def test_search_engine_returns_fallback_when_candidate_deadline_passed():
    from omok.search import SearchEngine

    board = Board()
    board.place(9, 9, BLACK)
    engine = SearchEngine()
    fallback = (9, 10)

    assert engine.search(board, BLACK, deadline=time.time() - 0.01, fallback=fallback) == fallback

import time

from omok.ai import OmokAI
from omok.board import Board
from omok.constants import BLACK, WHITE, to_internal
from omok.evaluator import Evaluator
from omok.move_generator import MoveGenerator
from omok.patterns import PatternAnalyzer
from omok.rules import RuleEngine


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

    ai.generator.fallback_move = lambda board, color: (9, 8)
    ai.generator.find_immediate_wins = lambda board, color: []
    ai.generator.find_moves_by_pattern = lambda board, color, pattern_type: []
    ai.generator.find_four_three_moves = lambda board, color: []
    ai.generator.find_legal_double_three_threats = lambda board, color: []
    ai.generator.find_future_four_three_setup_moves = (
        lambda board, color: [(9, 7)] if color == ai.opponent_color else [(9, 11)]
    )

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


def test_score_candidate_prioritizes_immediate_block():
    board = Board()
    evaluator = Evaluator()
    for c in range(5, 9):
        board.place(9, c, WHITE)

    block_score = evaluator.score_candidate(board, 9, 4, BLACK)
    quiet_score = evaluator.score_candidate(board, 5, 5, BLACK)

    assert block_score > quiet_score


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

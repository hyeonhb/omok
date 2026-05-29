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

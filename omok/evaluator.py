from __future__ import annotations

from .constants import (
    BROKEN_OPEN_THREE,
    CLOSED_FOUR,
    CLOSED_THREE,
    CLOSED_TWO,
    FIVE_OR_MORE,
    FOUR_THREE,
    ILLEGAL_MOVE,
    OPEN_FOUR,
    OPEN_THREE,
    OPEN_TWO,
    opponent,
)
from .patterns import PatternAnalyzer
from .rules import RuleEngine


DEFENSE_WEIGHT = 1.30
CANDIDATE_DEFENSE_WEIGHT = 1.35


class Evaluator:
    def __init__(self):
        self.patterns = PatternAnalyzer()
        self.rules = RuleEngine()

    def evaluate(self, board, color):
        my_score = self._pattern_score(board, color)
        opponent_score = self._pattern_score(board, opponent(color))
        return int(my_score - opponent_score * DEFENSE_WEIGHT)

    def score_candidate(self, board, r, c, color):
        if not self.rules.is_legal_move(board, r, c, color):
            return ILLEGAL_MOVE

        board.place(r, c, color)
        try:
            if self.rules.check_win(board, r, c, color):
                return FIVE_OR_MORE
            attack = self._local_move_score(board, r, c, color)
        finally:
            board.undo(r, c)

        opp = opponent(color)
        if board.is_empty(r, c) and self.rules.is_legal_move(board, r, c, opp):
            board.place(r, c, opp)
            try:
                defense = self._local_move_score(board, r, c, opp)
                if self.rules.check_win(board, r, c, opp):
                    defense = FIVE_OR_MORE
            finally:
                board.undo(r, c)
        else:
            defense = 0
        center_bonus = 40 - (abs(r - 9) + abs(c - 9))
        return attack + int(defense * CANDIDATE_DEFENSE_WEIGHT) + center_bonus

    def _local_move_score(self, board, r, c, color):
        counts = self.patterns.analyze_move(board, r, c, color)
        four_count = counts["open_four"] + counts["closed_four"] + counts["broken_four"]
        three_count = counts["open_three"] + counts["broken_open_three"]
        if four_count and three_count:
            combo = FOUR_THREE
        else:
            combo = 0
        return (
            counts["five"] * FIVE_OR_MORE
            + counts["open_four"] * OPEN_FOUR
            + counts["closed_four"] * CLOSED_FOUR
            + counts["broken_four"] * CLOSED_FOUR
            + combo
            + counts["open_three"] * OPEN_THREE
            + counts["broken_open_three"] * BROKEN_OPEN_THREE
            + counts["closed_three"] * CLOSED_THREE
            + counts["open_two"] * OPEN_TWO
            + counts["closed_two"] * CLOSED_TWO
        )

    def _pattern_score(self, board, color):
        counts = self.patterns.analyze_board(board, color)
        return (
            counts["five"] * FIVE_OR_MORE
            + counts["open_four"] * OPEN_FOUR
            + counts["closed_four"] * CLOSED_FOUR
            + counts["broken_four"] * CLOSED_FOUR
            + counts["open_three"] * OPEN_THREE
            + counts["broken_open_three"] * BROKEN_OPEN_THREE
            + counts["closed_three"] * CLOSED_THREE
            + counts["open_two"] * OPEN_TWO
            + counts["closed_two"] * CLOSED_TWO
        )

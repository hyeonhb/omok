from __future__ import annotations

from .constants import (
    BROKEN_OPEN_THREE,
    BOARD_SIZE,
    CLOSED_FOUR,
    CLOSED_THREE,
    CLOSED_TWO,
    FIVE_OR_MORE,
    FOUR_THREE,
    FUTURE_FOUR_THREE_SETUP,
    ILLEGAL_MOVE,
    LEGAL_DOUBLE_THREE_THREAT,
    OPEN_FOUR,
    OPEN_THREE,
    OPEN_TWO,
    opponent,
)
from .patterns import PatternAnalyzer
from .rules import RuleEngine


DEFENSE_WEIGHT = 1.30
CANDIDATE_DEFENSE_WEIGHT = 1.35
FUTURE_DEFENSE_BONUS = 500_000
OPPONENT_FOUR_THREE_PENALTY = 3_000_000


class Evaluator:
    def __init__(self):
        self.patterns = PatternAnalyzer()
        self.rules = RuleEngine()

    def evaluate(self, board, color):
        my_score = self._pattern_score(board, color)
        opponent_score = self._pattern_score(board, opponent(color))
        return int(my_score - opponent_score * DEFENSE_WEIGHT)

    def score_candidate(self, board, r, c, color):
        return self.deep_score_candidate(board, r, c, color)

    def quick_score_candidate(self, board, r, c, color):
        if not self.rules.is_legal_move(board, r, c, color):
            return ILLEGAL_MOVE

        opp = opponent(color)
        board.place(r, c, color)
        try:
            if self.rules.check_win(board, r, c, color):
                return FIVE_OR_MORE
            attack = self._local_move_score(board, r, c, color)
        finally:
            board.undo(r, c)

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

    def deep_score_candidate(self, board, r, c, color):
        if not self.rules.is_legal_move(board, r, c, color):
            return ILLEGAL_MOVE

        opp = opponent(color)
        board.place(r, c, color)
        try:
            if self.rules.check_win(board, r, c, color):
                return FIVE_OR_MORE
            attack = self._local_move_score(board, r, c, color)
            future_attack = self.evaluate_future_threat_potential(board, (r, c), color, already_placed=True)
            opponent_next_four_threes = self.count_future_four_three_moves(board, opp, radius=2, limit=14)
            opponent_wins = self._count_immediate_wins(board, opp, limit=3)
            danger_penalty = OPPONENT_FOUR_THREE_PENALTY if opponent_next_four_threes else 0
            if opponent_wins >= 2:
                danger_penalty += FIVE_OR_MORE
        finally:
            board.undo(r, c)

        if board.is_empty(r, c) and self.rules.is_legal_move(board, r, c, opp):
            board.place(r, c, opp)
            try:
                defense = self._local_move_score(board, r, c, opp)
                if self.rules.check_win(board, r, c, opp):
                    defense = FIVE_OR_MORE
                future_defense = self.evaluate_future_threat_potential(board, (r, c), opp, already_placed=True)
            finally:
                board.undo(r, c)
        else:
            defense = 0
            future_defense = 0
        center_bonus = 40 - (abs(r - 9) + abs(c - 9))
        return (
            attack
            + future_attack
            + int((defense + future_defense) * CANDIDATE_DEFENSE_WEIGHT)
            - danger_penalty
            + center_bonus
        )

    def evaluate_future_threat_potential(self, board, move, color, already_placed=False):
        r, c = move
        placed = False
        if not already_placed:
            if not self.rules.is_legal_move(board, r, c, color):
                return 0
            board.place(r, c, color)
            placed = True
        try:
            future_four_threes = self.count_future_four_three_moves(board, color, radius=2, limit=12)
            future_open_fours = self._count_future_pattern_moves(board, color, "open_four", radius=2, limit=12)
            future_double_threes = self._count_future_pattern_moves(
                board, color, "legal_double_three_threat", radius=2, limit=12
            )
            score = 0
            if future_four_threes >= 2:
                score += 1_000_000
            elif future_four_threes == 1:
                score += FUTURE_FOUR_THREE_SETUP
            if future_open_fours:
                score += 600_000
            if future_double_threes:
                score += 250_000
            return score
        finally:
            if placed:
                board.undo(r, c)

    def count_future_four_three_moves(self, board, color, radius=2, limit=12):
        count = 0
        for r, c in self._ordered_future_candidates(board, color, radius=radius, limit=limit):
            counts = self.patterns.analyze_move(board, r, c, color)
            if counts["four_three"]:
                count += 1
        return count

    def _local_move_score(self, board, r, c, color):
        counts = self.patterns.analyze_move(board, r, c, color)
        return (
            counts["five"] * FIVE_OR_MORE
            + counts["four_three"] * FOUR_THREE
            + counts["open_four"] * OPEN_FOUR
            + counts["closed_four"] * CLOSED_FOUR
            + counts["broken_four"] * CLOSED_FOUR
            + counts["legal_double_three_threat"] * LEGAL_DOUBLE_THREE_THREAT
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

    def _count_future_pattern_moves(self, board, color, pattern_type, radius=2, limit=12):
        count = 0
        for r, c in self._ordered_future_candidates(board, color, radius=radius, limit=limit):
            counts = self.patterns.analyze_move(board, r, c, color)
            if pattern_type == "open_four" and counts["open_four"]:
                count += 1
            elif pattern_type == "legal_double_three_threat" and counts["legal_double_three_threat"]:
                count += 1
        return count

    def _ordered_future_candidates(self, board, color, radius=2, limit=12):
        legal_moves = [
            move
            for move in self._nearby_moves(board, radius=radius)
            if self.rules.is_legal_move(board, move[0], move[1], color)
        ]
        scored = [
            (self._quick_future_order_score(board, r, c, color), r, c)
            for r, c in legal_moves
        ]
        scored.sort(reverse=True)
        return [(r, c) for _, r, c in scored[:limit]]

    def _quick_future_order_score(self, board, r, c, color):
        counts = self.patterns.analyze_move(board, r, c, color)
        center_bonus = 40 - (abs(r - 9) + abs(c - 9))
        return (
            counts["five"] * FIVE_OR_MORE
            + counts["four_three"] * FOUR_THREE
            + counts["open_four"] * OPEN_FOUR
            + counts["legal_double_three_threat"] * LEGAL_DOUBLE_THREE_THREAT
            + counts["closed_four"] * CLOSED_FOUR
            + counts["broken_four"] * CLOSED_FOUR
            + counts["open_three"] * OPEN_THREE
            + counts["broken_open_three"] * BROKEN_OPEN_THREE
            + center_bonus
        )

    def _count_immediate_wins(self, board, color, limit=3):
        wins = 0
        for r, c in self._nearby_moves(board, radius=4):
            if not self.rules.is_legal_move(board, r, c, color):
                continue
            board.place(r, c, color)
            try:
                if self.rules.check_win(board, r, c, color):
                    wins += 1
                    if wins >= limit:
                        return wins
            finally:
                board.undo(r, c)
        return wins

    def _nearby_moves(self, board, radius=2):
        stones = [(r, c) for r, c, _ in board.occupied_cells()]
        if not stones:
            return [(9, 9)] if board.is_empty(9, 9) else list(board.legal_empty_cells())
        moves = set()
        for r, c in stones:
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board.is_empty(nr, nc):
                        moves.add((nr, nc))
        return sorted(moves, key=lambda pos: (abs(pos[0] - 9) + abs(pos[1] - 9), pos[0], pos[1]))

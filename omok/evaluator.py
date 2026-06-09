from __future__ import annotations

import time

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
OPPONENT_IMMEDIATE_WIN_REPLY = -100_000_000
OPPONENT_OPEN_FOUR_REPLY = -15_000_000
OPPONENT_FOUR_THREE_REPLY = -12_000_000
OPPONENT_LEGAL_DOUBLE_THREE_REPLY = -1_500_000
OPPONENT_CLOSED_FOUR_REPLY = -1_000_000
OPPONENT_OPEN_THREE_REPLY = -300_000
OPPONENT_BROKEN_OPEN_THREE_REPLY = -180_000


class Evaluator:
    def __init__(self, allow_double_four=False):
        self.allow_double_four = allow_double_four
        self.patterns = PatternAnalyzer()
        self.rules = RuleEngine(allow_double_four=allow_double_four)

    def set_allow_double_four(self, allow):
        self.allow_double_four = allow
        self.rules.allow_double_four = allow

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

    def deep_score_candidate(self, board, r, c, color, deadline=None):
        if not self.rules.is_legal_move(board, r, c, color):
            return ILLEGAL_MOVE

        opp = opponent(color)
        board.place(r, c, color)
        try:
            if self.rules.check_win(board, r, c, color):
                return FIVE_OR_MORE
            attack = self._local_move_score(board, r, c, color)
            if deadline is not None and time.time() >= deadline:
                future_attack = 0
                resilient_future_attack = 0
                reply_penalty = 0
                opponent_next_four_threes = 0
                opponent_wins = 0
            else:
                future_attack = self.evaluate_future_threat_potential(
                    board,
                    (r, c),
                    color,
                    deadline=deadline,
                    already_placed=True,
                )
                resilient_future_attack = self.evaluate_resilient_future_four_three_setup(
                    board,
                    (r, c),
                    color,
                    deadline=deadline,
                    already_placed=True,
                )
                reply_penalty = self.evaluate_opponent_best_reply_penalty(
                    board,
                    (r, c),
                    color,
                    deadline=deadline,
                    already_placed=True,
                )
                opponent_next_four_threes = self.count_future_four_three_moves(
                    board,
                    opp,
                    radius=2,
                    limit=14,
                    deadline=deadline,
                )
                opponent_wins = self._count_immediate_wins(board, opp, limit=3, deadline=deadline)
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
                if deadline is not None and time.time() >= deadline:
                    future_defense = 0
                else:
                    future_defense = self.evaluate_future_threat_potential(
                        board,
                        (r, c),
                        opp,
                        deadline=deadline,
                        already_placed=True,
                    )
            finally:
                board.undo(r, c)
        else:
            defense = 0
            future_defense = 0
        center_bonus = 40 - (abs(r - 9) + abs(c - 9))
        return (
            attack
            + future_attack
            + resilient_future_attack
            + reply_penalty
            + int((defense + future_defense) * CANDIDATE_DEFENSE_WEIGHT)
            - danger_penalty
            + center_bonus
        )

    def evaluate_resilient_future_four_three_setup(self, board, move, color, deadline=None, already_placed=False):
        r, c = move
        placed = False
        if not already_placed:
            if not self.rules.is_legal_move(board, r, c, color):
                return 0
            board.place(r, c, color)
            placed = True
        try:
            import time

            future_moves = self._future_four_three_moves(board, color, radius=2, limit=12, deadline=deadline)
            if not future_moves:
                return 0
            score = 900_000 if len(future_moves) >= 2 else FUTURE_FOUR_THREE_SETUP

            if deadline is not None and time.time() >= deadline:
                return score

            opp = opponent(color)
            remaining_after_best_defense = len(future_moves)
            for defense in self._ordered_future_candidates(board, opp, radius=2, limit=10):
                if deadline is not None and time.time() >= deadline:
                    return score
                dr, dc = defense
                board.place(dr, dc, opp)
                try:
                    remaining = len(self._future_four_three_moves(board, color, radius=2, limit=12, deadline=deadline))
                finally:
                    board.undo(dr, dc)
                remaining_after_best_defense = min(remaining_after_best_defense, remaining)
                if remaining_after_best_defense == 0:
                    break

            if remaining_after_best_defense > 0:
                score += 1_500_000
            elif len(future_moves) >= 2:
                score += 200_000
            return score
        finally:
            if placed:
                board.undo(r, c)

    def evaluate_opponent_best_reply_penalty(self, board, move, color, limit=16, deadline=None, already_placed=False):
        r, c = move
        placed = False
        if not already_placed:
            if not self.rules.is_legal_move(board, r, c, color):
                return 0
            board.place(r, c, color)
            placed = True
        try:
            opp = opponent(color)
            best_penalty = 0
            for rr, rc in self._ordered_future_candidates(board, opp, radius=2, limit=limit):
                if deadline is not None and time.time() >= deadline:
                    break
                board.place(rr, rc, opp)
                try:
                    if self.rules.check_win(board, rr, rc, opp):
                        return OPPONENT_IMMEDIATE_WIN_REPLY
                finally:
                    board.undo(rr, rc)

                counts = self.patterns.analyze_move(board, rr, rc, opp)
                best_penalty = min(best_penalty, self._reply_penalty_from_counts(counts))
            return best_penalty
        finally:
            if placed:
                board.undo(r, c)

    def _reply_penalty_from_counts(self, counts):
        if counts["open_four"]:
            return OPPONENT_OPEN_FOUR_REPLY
        if counts["four_three"]:
            return OPPONENT_FOUR_THREE_REPLY
        if counts["legal_double_three_threat"]:
            return OPPONENT_LEGAL_DOUBLE_THREE_REPLY
        if counts["closed_four"] or counts["broken_four"]:
            return OPPONENT_CLOSED_FOUR_REPLY
        if counts["open_three"]:
            return OPPONENT_OPEN_THREE_REPLY
        if counts["broken_open_three"]:
            return OPPONENT_BROKEN_OPEN_THREE_REPLY
        return 0

    def evaluate_future_threat_potential(self, board, move, color, deadline=None, already_placed=False):
        r, c = move
        placed = False
        if not already_placed:
            if not self.rules.is_legal_move(board, r, c, color):
                return 0
            board.place(r, c, color)
            placed = True
        try:
            future_four_threes = self.count_future_four_three_moves(
                board,
                color,
                radius=2,
                limit=12,
                deadline=deadline,
            )
            future_open_fours = self._count_future_pattern_moves(
                board,
                color,
                "open_four",
                radius=2,
                limit=12,
                deadline=deadline,
            )
            future_double_threes = self._count_future_pattern_moves(
                board,
                color,
                "legal_double_three_threat",
                radius=2,
                limit=12,
                deadline=deadline,
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

    def count_future_four_three_moves(self, board, color, radius=2, limit=12, deadline=None):
        return len(self._future_four_three_moves(board, color, radius=radius, limit=limit, deadline=deadline))

    def _future_four_three_moves(self, board, color, radius=2, limit=12, deadline=None):
        moves = []
        for r, c in self._ordered_future_candidates(board, color, radius=radius, limit=limit):
            if deadline is not None and time.time() >= deadline:
                break
            counts = self.patterns.analyze_move(board, r, c, color)
            if counts["four_three"]:
                moves.append((r, c))
        return moves

    def _local_move_score(self, board, r, c, color):
        counts = self.patterns.analyze_move(board, r, c, color)
        return self._threat_weighted_score(counts)

    def _threat_weighted_score(self, counts):
        threat_values = []
        threat_values.extend([FIVE_OR_MORE] * counts["five"])
        threat_values.extend([OPEN_FOUR] * counts["open_four"])
        threat_values.extend([FOUR_THREE] * counts["four_three"])
        threat_values.extend([CLOSED_FOUR] * (counts["closed_four"] + counts["broken_four"]))
        threat_values.extend([LEGAL_DOUBLE_THREE_THREAT] * counts["legal_double_three_threat"])
        threat_values.extend([OPEN_THREE] * counts["open_three"])
        threat_values.extend([BROKEN_OPEN_THREE] * counts["broken_open_three"])
        threat_values.extend([OPEN_TWO] * counts["open_two"])

        if not threat_values:
            return counts["closed_three"] * CLOSED_THREE + counts["closed_two"] * CLOSED_TWO

        threat_values.sort(reverse=True)
        main = threat_values[0]
        secondary = threat_values[1] if len(threat_values) > 1 else 0
        pattern_sum = sum(threat_values[2:]) + counts["closed_three"] * CLOSED_THREE + counts["closed_two"] * CLOSED_TWO
        return int(main + secondary * 0.35 + pattern_sum * 0.15)

    def _pattern_score(self, board, color):
        counts = self.patterns.analyze_board(board, color)
        weighted = self._threat_weighted_score(counts)
        sum_score = (
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
        return int(weighted + sum_score * 0.2)

    def _count_future_pattern_moves(self, board, color, pattern_type, radius=2, limit=12, deadline=None):
        count = 0
        for r, c in self._ordered_future_candidates(board, color, radius=radius, limit=limit):
            if deadline is not None and time.time() >= deadline:
                break
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

    def _count_immediate_wins(self, board, color, limit=3, deadline=None):
        wins = 0
        for r, c in self._nearby_moves(board, radius=4):
            if deadline is not None and time.time() >= deadline:
                break
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

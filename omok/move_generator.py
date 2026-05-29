from __future__ import annotations

from .constants import BLACK, BOARD_SIZE, WHITE, opponent
from .evaluator import Evaluator
from .patterns import PatternAnalyzer
from .rules import RuleEngine


class MoveGenerator:
    def __init__(self):
        self.rules = RuleEngine()
        self.evaluator = Evaluator()
        self.patterns = PatternAnalyzer()

    def generate_candidates(self, board, color, max_moves=None):
        return self.generate_search_candidates(board, color, max_moves=max_moves)

    def generate_tactical_moves(self, board, color, include_future_setup=True):
        essential = []
        seen = set()
        tactical_groups = [
            self.find_immediate_wins(board, color),
            self.find_immediate_wins(board, opponent(color)),
            self.find_moves_by_pattern(board, color, "open_four"),
            self.find_moves_by_pattern(board, opponent(color), "open_four"),
            self.find_four_three_moves(board, color),
            self.find_four_three_moves(board, opponent(color)),
            self.find_legal_double_three_threats(board, color),
            self.find_legal_double_three_threats(board, opponent(color)),
            self.find_moves_by_pattern(board, color, "closed_four"),
            self.find_moves_by_pattern(board, opponent(color), "closed_four"),
            self.find_moves_by_pattern(board, color, "open_three"),
            self.find_moves_by_pattern(board, opponent(color), "open_three"),
            self.find_moves_by_pattern(board, color, "broken_open_three"),
            self.find_moves_by_pattern(board, opponent(color), "broken_open_three"),
        ]
        if include_future_setup:
            tactical_groups.extend(
                [
                    self.find_future_four_three_setup_moves(board, color),
                    self.find_future_four_three_setup_moves(board, opponent(color)),
                ]
            )
        for group in tactical_groups:
            for move in group:
                if move not in seen and self.rules.is_legal_move(board, move[0], move[1], color):
                    seen.add(move)
                    essential.append(move)
        return self.order_moves(board, color, essential, use_deep_score=False)

    def generate_search_candidates(
        self, board, color, max_moves=None, include_future_setup=True, use_deep_score=True
    ):
        essential = self.generate_tactical_moves(board, color, include_future_setup=include_future_setup)
        essential_set = set(essential)
        raw_moves = self._nearby_moves(board, radius=2)
        legal_moves = [
            move
            for move in raw_moves
            if move not in essential_set and self.rules.is_legal_move(board, move[0], move[1], color)
        ]
        normal = self.order_moves(board, color, legal_moves, use_deep_score=use_deep_score)
        if max_moves is not None:
            normal = normal[:max_moves]
        return essential + normal

    def order_moves(self, board, color, moves, use_deep_score=False):
        scorer = self.evaluator.deep_score_candidate if use_deep_score else self.evaluator.quick_score_candidate
        scored = [(scorer(board, r, c, color), r, c) for r, c in moves]
        scored.sort(reverse=True)
        return [(r, c) for _, r, c in scored]

    def find_immediate_win(self, board, color):
        wins = self.find_immediate_wins(board, color)
        return wins[0] if wins else None

    def find_immediate_wins(self, board, color):
        wins = []
        for r, c in self._nearby_moves(board, radius=4):
            if not self.rules.is_legal_move(board, r, c, color):
                continue
            board.place(r, c, color)
            try:
                if self.rules.check_win(board, r, c, color):
                    wins.append((r, c))
            finally:
                board.undo(r, c)
        return self.order_moves(board, color, wins, use_deep_score=False)

    def find_immediate_block(self, board, color):
        opp = opponent(color)
        for r, c in self.find_immediate_wins(board, opp):
            if self.rules.is_legal_move(board, r, c, color):
                return r, c
        return None

    def has_unblockable_open_four(self, board, attacker_color, defender_color):
        attacker_wins = self.find_immediate_wins(board, attacker_color)
        defender_blocks = [
            move
            for move in attacker_wins
            if self.rules.is_legal_move(board, move[0], move[1], defender_color)
        ]
        return len(defender_blocks) < len(attacker_wins) or len(defender_blocks) >= 2

    def has_multiple_immediate_wins(self, board, attacker_color):
        return len(self.find_immediate_wins(board, attacker_color)) >= 2

    def find_moves_by_pattern(self, board, color, pattern_type):
        moves = []
        for r, c in self._nearby_moves(board, radius=4):
            if not self.rules.is_legal_move(board, r, c, color):
                continue
            counts = self.patterns.analyze_move(board, r, c, color)
            if self._matches_pattern(counts, pattern_type):
                moves.append((r, c))
        return self.order_moves(board, color, moves, use_deep_score=False)

    def find_legal_double_three_threats(self, board, color):
        return self.find_moves_by_pattern(board, color, "legal_double_three_threat")

    def find_four_three_moves(self, board, color):
        return self.find_moves_by_pattern(board, color, "four_three")

    def find_future_four_three_setup_moves(self, board, color):
        legal_moves = [
            move
            for move in self._nearby_moves(board, radius=2)
            if self.rules.is_legal_move(board, move[0], move[1], color)
        ]
        ordered = self.order_moves(board, color, legal_moves, use_deep_score=False)[:24]
        scored = []
        for r, c in ordered:
            score = self.evaluator.evaluate_future_threat_potential(board, (r, c), color)
            if score >= 400_000:
                scored.append((score, r, c))
        scored.sort(reverse=True)
        return [(r, c) for _, r, c in scored[:8]]

    def fallback_move(self, board, color):
        candidates = self.generate_search_candidates(
            board, color, max_moves=1, include_future_setup=False, use_deep_score=False
        )
        if candidates:
            return candidates[0]
        for r, c in board.legal_empty_cells():
            if self.rules.is_legal_move(board, r, c, color):
                return r, c
        return None

    def _matches_pattern(self, counts, pattern_type):
        if pattern_type == "five":
            return counts["five"] > 0
        if pattern_type == "open_four":
            return counts["open_four"] > 0
        if pattern_type == "closed_four":
            return counts["closed_four"] > 0 or counts["broken_four"] > 0
        if pattern_type == "broken_four":
            return counts["broken_four"] > 0
        if pattern_type == "open_three":
            return counts["open_three"] > 0
        if pattern_type == "broken_open_three":
            return counts["broken_open_three"] > 0
        if pattern_type == "four_three":
            return counts["four_three"] > 0
        if pattern_type == "legal_double_three_threat":
            return counts["legal_double_three_threat"] > 0
        raise ValueError(f"Unknown pattern type: {pattern_type}")

    def _nearby_moves(self, board, radius=2):
        stones = [(r, c) for r, c, color in board.occupied_cells() if color in (BLACK, WHITE)]
        if not stones:
            return self._center_moves(board)

        moves = set()
        for r, c in stones:
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if board.is_empty(nr, nc):
                        moves.add((nr, nc))
        if not moves:
            return self._center_moves(board)
        return sorted(moves, key=lambda pos: (abs(pos[0] - 9) + abs(pos[1] - 9), pos[0], pos[1]))

    def _center_moves(self, board):
        moves = []
        for radius in range(0, 4):
            for r in range(9 - radius, 9 + radius + 1):
                for c in range(9 - radius, 9 + radius + 1):
                    if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board.is_empty(r, c):
                        moves.append((r, c))
            if moves:
                return sorted(set(moves), key=lambda pos: (abs(pos[0] - 9) + abs(pos[1] - 9), pos[0], pos[1]))
        return [(r, c) for r, c in board.legal_empty_cells()]

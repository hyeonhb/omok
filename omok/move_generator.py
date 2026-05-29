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

    def generate_tactical_moves(self, board, color):
        essential = []
        seen = set()
        tactical_groups = [
            self.find_immediate_wins(board, color),
            self.find_immediate_wins(board, opponent(color)),
            self.find_moves_by_pattern(board, color, "open_four"),
            self.find_moves_by_pattern(board, opponent(color), "open_four"),
            self.find_moves_by_pattern(board, color, "closed_four"),
            self.find_moves_by_pattern(board, opponent(color), "closed_four"),
            self.find_moves_by_pattern(board, color, "open_three"),
            self.find_moves_by_pattern(board, opponent(color), "open_three"),
            self.find_moves_by_pattern(board, color, "broken_open_three"),
            self.find_moves_by_pattern(board, opponent(color), "broken_open_three"),
        ]
        for group in tactical_groups:
            for move in group:
                if move not in seen and self.rules.is_legal_move(board, move[0], move[1], color):
                    seen.add(move)
                    essential.append(move)
        return self.order_moves(board, color, essential)

    def generate_search_candidates(self, board, color, max_moves=None):
        essential = self.generate_tactical_moves(board, color)
        essential_set = set(essential)
        raw_moves = self._nearby_moves(board, radius=2)
        legal_moves = [
            move
            for move in raw_moves
            if move not in essential_set and self.rules.is_legal_move(board, move[0], move[1], color)
        ]
        normal = self.order_moves(board, color, legal_moves)
        if max_moves is not None:
            normal = normal[:max_moves]
        return essential + normal

    def order_moves(self, board, color, moves):
        scored = [(self.evaluator.score_candidate(board, r, c, color), r, c) for r, c in moves]
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
        return self.order_moves(board, color, wins)

    def find_immediate_block(self, board, color):
        opp = opponent(color)
        for r, c in self.find_immediate_wins(board, opp):
            if self.rules.is_legal_move(board, r, c, color):
                return r, c
        return None

    def find_moves_by_pattern(self, board, color, pattern_type):
        moves = []
        for r, c in self._nearby_moves(board, radius=4):
            if not self.rules.is_legal_move(board, r, c, color):
                continue
            counts = self.patterns.analyze_move(board, r, c, color)
            if self._matches_pattern(counts, pattern_type):
                moves.append((r, c))
        return self.order_moves(board, color, moves)

    def fallback_move(self, board, color):
        candidates = self.generate_search_candidates(board, color, max_moves=1)
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
            four_count = counts["open_four"] + counts["closed_four"] + counts["broken_four"]
            three_count = counts["open_three"] + counts["broken_open_three"]
            return four_count > 0 and three_count > 0
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

from __future__ import annotations

from .constants import DIRECTIONS
from .patterns import PatternAnalyzer


class RuleEngine:
    def __init__(self):
        self.patterns = PatternAnalyzer()

    def check_win(self, board, r, c, color) -> bool:
        if not board.is_inside(r, c) or board.get(r, c) != color:
            return False
        return any(self._count_line(board, r, c, color, dr, dc) >= 5 for dr, dc in DIRECTIONS)

    def is_legal_move(self, board, r, c, color) -> bool:
        if not board.is_inside(r, c) or not board.is_empty(r, c):
            return False

        board.place(r, c, color)
        try:
            if self.check_win(board, r, c, color):
                return True
            if self.is_double_three(board, r, c, color):
                return False
            if self.is_double_four(board, r, c, color):
                return False
            return True
        finally:
            board.undo(r, c)

    def is_double_three(self, board, r, c, color) -> bool:
        placed_here = board.get(r, c) == color
        if not placed_here:
            if not board.is_empty(r, c):
                return False
            board.place(r, c, color)
        try:
            if self.check_win(board, r, c, color):
                return False
            return self.patterns.count_connected_open_threes(board, r, c, color) >= 2
        finally:
            if not placed_here:
                board.undo(r, c)

    def is_double_four(self, board, r, c, color) -> bool:
        placed_here = board.get(r, c) == color
        if not placed_here:
            if not board.is_empty(r, c):
                return False
            board.place(r, c, color)
        try:
            if self.check_win(board, r, c, color):
                return False
            return self._count_forbidden_fours(board, r, c, color) >= 2
        finally:
            if not placed_here:
                board.undo(r, c)

    def _count_forbidden_fours(self, board, r, c, color):
        return self.patterns.count_four_threats(board, r, c, color)

    def _count_line(self, board, r, c, color, dr, dc):
        count = 1
        for sign in (1, -1):
            nr = r + dr * sign
            nc = c + dc * sign
            while board.is_inside(nr, nc) and board.get(nr, nc) == color:
                count += 1
                nr += dr * sign
                nc += dc * sign
        return count

from __future__ import annotations

import random
from copy import deepcopy

from .constants import BLACK, BOARD_SIZE, EMPTY, WHITE, to_internal


_RNG = random.Random(20240529)
_ZOBRIST = {
    BLACK: [[_RNG.getrandbits(64) for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)],
    WHITE: [[_RNG.getrandbits(64) for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)],
}


class Board:
    def __init__(self, blocked_cells=None):
        self.size = BOARD_SIZE
        self.grid = [[EMPTY for _ in range(self.size)] for _ in range(self.size)]
        self.blocked_cells = set()
        self.last_move = None
        self.move_count = 0
        self.history = []
        self.hash_value = 0
        if blocked_cells:
            self.set_blocked_cells(blocked_cells)

    def is_inside(self, r, c):
        return 0 <= r < self.size and 0 <= c < self.size

    def is_empty(self, r, c):
        return self.is_inside(r, c) and self.grid[r][c] == EMPTY and not self.is_blocked(r, c)

    def is_blocked(self, r, c):
        return (r, c) in self.blocked_cells

    def get(self, r, c):
        if not self.is_inside(r, c):
            return None
        return self.grid[r][c]

    def place(self, r, c, color):
        if color not in (BLACK, WHITE):
            raise ValueError(f"Invalid stone color: {color}")
        if not self.is_empty(r, c):
            raise ValueError(f"Cannot place at ({r}, {c})")
        self.grid[r][c] = color
        self.hash_value ^= _ZOBRIST[color][r][c]
        self.last_move = (r, c, color)
        self.move_count += 1
        self.history.append((r, c, color))

    def undo(self, r, c):
        color = self.grid[r][c]
        if color not in (BLACK, WHITE):
            raise ValueError(f"Cannot undo empty cell ({r}, {c})")
        self.grid[r][c] = EMPTY
        self.hash_value ^= _ZOBRIST[color][r][c]
        self.move_count -= 1
        if self.history and self.history[-1][:2] == (r, c):
            self.history.pop()
        else:
            self.history = [move for move in self.history if move[:2] != (r, c)]
        self.last_move = self.history[-1] if self.history else None

    def set_blocked_cells(self, cells, external=True):
        normalized = set()
        for cell in cells:
            r, c = to_internal(cell) if external else cell
            if not self.is_inside(r, c):
                raise ValueError(f"Blocked cell is outside board: {cell}")
            if self.grid[r][c] != EMPTY:
                raise ValueError(f"Blocked cell already occupied: {cell}")
            normalized.add((r, c))
        self.blocked_cells = normalized

    def copy(self):
        new_board = Board()
        new_board.grid = deepcopy(self.grid)
        new_board.blocked_cells = set(self.blocked_cells)
        new_board.last_move = self.last_move
        new_board.move_count = self.move_count
        new_board.history = list(self.history)
        new_board.hash_value = self.hash_value
        return new_board

    def occupied_cells(self):
        for r in range(self.size):
            for c in range(self.size):
                if self.grid[r][c] in (BLACK, WHITE):
                    yield r, c, self.grid[r][c]

    def legal_empty_cells(self):
        for r in range(self.size):
            for c in range(self.size):
                if self.is_empty(r, c):
                    yield r, c

from __future__ import annotations

from collections import Counter

from .constants import (
    BOARD_SIZE,
    BROKEN_OPEN_THREE,
    CLOSED_FOUR,
    CLOSED_THREE,
    CLOSED_TWO,
    DIRECTIONS,
    EMPTY,
    FIVE_OR_MORE,
    OPEN_FOUR,
    OPEN_THREE,
    OPEN_TWO,
)


class PatternAnalyzer:
    CONNECTED_OPEN_THREE_SHAPES = (".OOO.",)
    SIMPLE_OPEN_THREE_SHAPES = CONNECTED_OPEN_THREE_SHAPES
    BROKEN_OPEN_THREE_SHAPES = (".OO.O.", ".O.OO.")
    OPEN_THREE_SHAPES = SIMPLE_OPEN_THREE_SHAPES + BROKEN_OPEN_THREE_SHAPES
    OPEN_FOUR_SHAPES = (".OOOO.",)
    BROKEN_FOUR_SHAPES = ("OOO.O", "OO.OO", "O.OOO")
    CLOSED_FOUR_SHAPES = ("XOOOO.", ".OOOOX") + BROKEN_FOUR_SHAPES
    CLOSED_THREE_SHAPES = ("XOOO.", ".OOOX", "XOO.O.", ".O.OOX")
    OPEN_TWO_SHAPES = (".OO.", ".O.O.")
    CLOSED_TWO_SHAPES = ("XOO.", ".OOX")

    def cell_symbol(self, board, r, c, color):
        if not board.is_inside(r, c) or board.is_blocked(r, c):
            return "X"
        value = board.get(r, c)
        if value == color:
            return "O"
        if value == EMPTY:
            return "."
        return "X"

    def line_around(self, board, r, c, color, dr, dc, radius=5):
        chars = []
        for step in range(-radius, radius + 1):
            nr = r + dr * step
            nc = c + dc * step
            chars.append(self.cell_symbol(board, nr, nc, color))
        return "".join(chars)

    def has_open_three_in_direction(self, board, r, c, color, dr, dc):
        line = self.line_around(board, r, c, color, dr, dc)
        center = len(line) // 2
        for shape in self.OPEN_THREE_SHAPES:
            start = line.find(shape)
            while start != -1:
                if start <= center < start + len(shape):
                    return True
                start = line.find(shape, start + 1)
        return False

    def has_connected_open_three_in_direction(self, board, r, c, color, dr, dc):
        line = self.line_around(board, r, c, color, dr, dc)
        center = len(line) // 2
        for shape in self.CONNECTED_OPEN_THREE_SHAPES:
            start = line.find(shape)
            while start != -1:
                if start <= center < start + len(shape):
                    return True
                start = line.find(shape, start + 1)
        return False

    def has_broken_open_three_in_direction(self, board, r, c, color, dr, dc):
        line = self.line_around(board, r, c, color, dr, dc)
        center = len(line) // 2
        for shape in self.BROKEN_OPEN_THREE_SHAPES:
            start = line.find(shape)
            while start != -1:
                if start <= center < start + len(shape):
                    return True
                start = line.find(shape, start + 1)
        return False

    def has_open_four_in_direction(self, board, r, c, color, dr, dc):
        line = self.line_around(board, r, c, color, dr, dc)
        center = len(line) // 2
        for shape in self.OPEN_FOUR_SHAPES:
            start = line.find(shape)
            while start != -1:
                if start <= center < start + len(shape):
                    return True
                start = line.find(shape, start + 1)
        return False

    def winning_completion_cells(self, board, r, c, color, dr, dc):
        completions = set()
        for step in range(-4, 5):
            nr = r + dr * step
            nc = c + dc * step
            if not board.is_empty(nr, nc):
                continue
            board.place(nr, nc, color)
            if self._line_count(board, nr, nc, color, dr, dc) >= 5:
                completions.add((nr, nc))
            board.undo(nr, nc)
        return completions

    def has_four_threat_in_direction(self, board, r, c, color, dr, dc):
        return bool(self.winning_completion_cells(board, r, c, color, dr, dc))

    def count_open_threes(self, board, r, c, color):
        return sum(
            1
            for dr, dc in DIRECTIONS
            if self.has_open_three_in_direction(board, r, c, color, dr, dc)
        )

    def count_connected_open_threes(self, board, r, c, color):
        return sum(
            1
            for dr, dc in DIRECTIONS
            if self.has_connected_open_three_in_direction(board, r, c, color, dr, dc)
        )

    def count_four_threats(self, board, r, c, color):
        return sum(
            1
            for dr, dc in DIRECTIONS
            if self.has_four_threat_in_direction(board, r, c, color, dr, dc)
        )

    def analyze_move(self, board, r, c, color):
        placed_here = board.get(r, c) == color
        if not placed_here:
            if not board.is_empty(r, c):
                return Counter()
            board.place(r, c, color)

        try:
            counts = Counter()
            for dr, dc in DIRECTIONS:
                line = self.line_around(board, r, c, color, dr, dc)
                center = len(line) // 2
                if self._line_count(board, r, c, color, dr, dc) >= 5:
                    counts["five"] += 1
                counts["open_four"] += self._count_centered_patterns(line, self.OPEN_FOUR_SHAPES, center)
                counts["closed_four"] += self._count_centered_patterns(line, self.CLOSED_FOUR_SHAPES, center)
                counts["broken_four"] += self._count_centered_patterns(line, self.BROKEN_FOUR_SHAPES, center)
                counts["open_three"] += self._count_centered_patterns(
                    line, self.SIMPLE_OPEN_THREE_SHAPES, center
                )
                counts["connected_open_three"] += self._count_centered_patterns(
                    line, self.CONNECTED_OPEN_THREE_SHAPES, center
                )
                counts["broken_open_three"] += self._count_centered_patterns(
                    line, self.BROKEN_OPEN_THREE_SHAPES, center
                )
                counts["closed_three"] += self._count_centered_patterns(line, self.CLOSED_THREE_SHAPES, center)
                counts["open_two"] += self._count_centered_patterns(line, self.OPEN_TWO_SHAPES, center)
                counts["closed_two"] += self._count_centered_patterns(line, self.CLOSED_TWO_SHAPES, center)
            return counts
        finally:
            if not placed_here:
                board.undo(r, c)

    def move_pattern_score(self, board, r, c, color):
        if not board.is_empty(r, c):
            return -10**12
        board.place(r, c, color)
        try:
            if self._has_five_or_more(board, r, c, color):
                return FIVE_OR_MORE
            open_fours = sum(
                1 for dr, dc in DIRECTIONS if self.has_open_four_in_direction(board, r, c, color, dr, dc)
            )
            four_threats = self.count_four_threats(board, r, c, color)
            open_threes = self.count_open_threes(board, r, c, color)
        finally:
            board.undo(r, c)
        return open_fours * OPEN_FOUR + four_threats * CLOSED_FOUR + open_threes * OPEN_THREE

    def analyze_board(self, board, color):
        counts = Counter()
        for line in self._all_lines(board, color):
            counts["five"] += self._count_runs(line, "O", 5)
            counts["open_four"] += line.count(".OOOO.")
            counts["closed_four"] += self._count_any(line, self.CLOSED_FOUR_SHAPES)
            counts["broken_four"] += self._count_any(line, self.BROKEN_FOUR_SHAPES)
            counts["open_three"] += self._count_any(line, self.SIMPLE_OPEN_THREE_SHAPES)
            counts["connected_open_three"] += self._count_any(line, self.CONNECTED_OPEN_THREE_SHAPES)
            counts["broken_open_three"] += self._count_any(line, self.BROKEN_OPEN_THREE_SHAPES)
            counts["closed_three"] += self._count_any(line, self.CLOSED_THREE_SHAPES)
            counts["open_two"] += self._count_any(line, self.OPEN_TWO_SHAPES)
            counts["closed_two"] += self._count_any(line, self.CLOSED_TWO_SHAPES)
        return counts

    def _all_lines(self, board, color):
        lines = []
        for r in range(BOARD_SIZE):
            lines.append("X" + "".join(self.cell_symbol(board, r, c, color) for c in range(BOARD_SIZE)) + "X")
        for c in range(BOARD_SIZE):
            lines.append("X" + "".join(self.cell_symbol(board, r, c, color) for r in range(BOARD_SIZE)) + "X")
        for start_c in range(BOARD_SIZE):
            lines.append(self._diag_line(board, 0, start_c, 1, 1, color))
            lines.append(self._diag_line(board, 0, start_c, 1, -1, color))
        for start_r in range(1, BOARD_SIZE):
            lines.append(self._diag_line(board, start_r, 0, 1, 1, color))
            lines.append(self._diag_line(board, start_r, BOARD_SIZE - 1, 1, -1, color))
        return [line for line in lines if len(line) >= 7]

    def _diag_line(self, board, r, c, dr, dc, color):
        chars = ["X"]
        while board.is_inside(r, c):
            chars.append(self.cell_symbol(board, r, c, color))
            r += dr
            c += dc
        chars.append("X")
        return "".join(chars)

    def _line_count(self, board, r, c, color, dr, dc):
        count = 1
        for sign in (1, -1):
            nr, nc = r + dr * sign, c + dc * sign
            while board.is_inside(nr, nc) and board.get(nr, nc) == color:
                count += 1
                nr += dr * sign
                nc += dc * sign
        return count

    def _has_five_or_more(self, board, r, c, color):
        return any(self._line_count(board, r, c, color, dr, dc) >= 5 for dr, dc in DIRECTIONS)

    def _count_runs(self, line, char, min_len):
        total = 0
        current = 0
        for value in line:
            if value == char:
                current += 1
            else:
                if current >= min_len:
                    total += 1
                current = 0
        return total + (1 if current >= min_len else 0)

    def _count_any(self, line, patterns):
        return sum(line.count(pattern) for pattern in patterns)

    def _count_centered_patterns(self, line, patterns, center):
        total = 0
        for pattern in patterns:
            start = line.find(pattern)
            while start != -1:
                if start <= center < start + len(pattern):
                    total += 1
                start = line.find(pattern, start + 1)
        return total

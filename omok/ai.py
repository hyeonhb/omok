from __future__ import annotations

import time

from .board import Board
from .constants import BLACK, WHITE, opponent, to_external, to_internal
from .move_generator import MoveGenerator
from .rules import RuleEngine
from .search import SearchEngine
from .threat_search import ThreatSearch


class OmokAI:
    def __init__(self, color=BLACK, blocked_cells=None, time_limit=3.0):
        self.color = color
        self.opponent_color = opponent(color)
        self.time_limit = time_limit
        self.board = Board(blocked_cells=blocked_cells)
        self.rules = RuleEngine()
        self.generator = MoveGenerator()
        self.search_engine = SearchEngine()
        self.threat_search = ThreatSearch()

    def choose_color(self):
        return BLACK

    def set_blocked_cells(self, cells):
        self.board.set_blocked_cells(cells, external=True)

    def notify_opponent_move(self, row, col):
        r, c = to_internal((row, col))
        if not self.rules.is_legal_move(self.board, r, c, self.opponent_color):
            raise ValueError(f"Illegal opponent move: {(row, col)}")
        self.board.place(r, c, self.opponent_color)

    def choose_move(self):
        start = time.time()
        deadline = start + max(0.05, min(self.time_limit, 3.0) - 0.25)

        try:
            move = self._choose_move_internal(deadline)
        except Exception:
            move = self.generator.fallback_move(self.board, self.color)

        if move is None or not self.rules.is_legal_move(self.board, move[0], move[1], self.color):
            move = self._first_legal_move()
        if move is None:
            raise RuntimeError("No legal moves available")

        self.board.place(move[0], move[1], self.color)
        return to_external(move)

    def _choose_move_internal(self, deadline):
        if self.color == BLACK and self.board.move_count == 0:
            center = to_internal((10, 10))
            if self.rules.is_legal_move(self.board, center[0], center[1], self.color):
                return center

        fallback = self.generator.fallback_move(self.board, self.color)
        if fallback is None:
            return None

        immediate_win = self._first_legal(self.generator.find_immediate_wins(self.board, self.color))
        if immediate_win:
            return immediate_win

        immediate_block = self._first_legal(self.generator.find_immediate_wins(self.board, self.opponent_color))
        if immediate_block:
            return immediate_block

        open_four = self._first_legal(self.generator.find_moves_by_pattern(self.board, self.color, "open_four"))
        if open_four:
            return open_four

        block_open_four = self._first_legal(
            self.generator.find_moves_by_pattern(self.board, self.opponent_color, "open_four")
        )
        if block_open_four:
            return block_open_four

        closed_four = self._first_legal(self.generator.find_moves_by_pattern(self.board, self.color, "closed_four"))
        if closed_four:
            return closed_four

        block_closed_four = self._first_legal(
            self.generator.find_moves_by_pattern(self.board, self.opponent_color, "closed_four")
        )
        if block_closed_four:
            return block_closed_four

        four_three = self._first_legal(self.generator.find_moves_by_pattern(self.board, self.color, "four_three"))
        if four_three:
            return four_three

        block_four_three = self._first_legal(
            self.generator.find_moves_by_pattern(self.board, self.opponent_color, "four_three")
        )
        if block_four_three:
            return block_four_three

        try:
            attack_deadline = min(deadline, time.time() + 0.4)
            attack = self.threat_search.find_forcing_attack(self.board, self.color, attack_deadline)
            if attack:
                return attack
        except TimeoutError:
            pass

        try:
            defense_deadline = min(deadline, time.time() + 0.4)
            defense = self.threat_search.find_forcing_defense(self.board, self.color, defense_deadline)
            if defense:
                return defense
        except TimeoutError:
            pass

        if time.time() < deadline:
            searched = self.search_engine.search(self.board, self.color, deadline, fallback=fallback)
            if searched:
                return searched
        return fallback

    def _first_legal(self, moves):
        for r, c in moves:
            if self.rules.is_legal_move(self.board, r, c, self.color):
                return r, c
        return None

    def _first_legal_move(self):
        for r, c in self.board.legal_empty_cells():
            if self.rules.is_legal_move(self.board, r, c, self.color):
                return r, c
        return None

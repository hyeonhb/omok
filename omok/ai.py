from __future__ import annotations

import time

from .board import Board
from .constants import BLACK, WHITE, opponent, to_external, to_internal
from .move_generator import MoveGenerator
from .rules import RuleEngine
from .search import SearchEngine
from .threat_search import ThreatSearch


SAFETY_MARGIN = 0.20


class OmokAI:
    def __init__(self, color=BLACK, blocked_cells=None, time_limit=3.0, allow_double_four=False):
        self.color = color
        self.opponent_color = opponent(color)
        self.time_limit = time_limit
        self.allow_double_four = allow_double_four
        self.board = Board(blocked_cells=blocked_cells)
        self.rules = RuleEngine(allow_double_four=allow_double_four)
        self.generator = MoveGenerator(allow_double_four=allow_double_four)
        self.search_engine = SearchEngine(allow_double_four=allow_double_four)
        self.threat_search = ThreatSearch(allow_double_four=allow_double_four)

    def choose_color(self):
        return BLACK

    def set_blocked_cells(self, cells):
        self.board.set_blocked_cells(cells, external=True)
        self.search_engine.clear_cache()

    def set_allow_double_four(self, allow):
        self.allow_double_four = allow
        self.rules.allow_double_four = allow
        self.generator.set_allow_double_four(allow)
        self.search_engine.set_allow_double_four(allow)
        self.threat_search.set_allow_double_four(allow)

    def notify_opponent_move(self, row, col):
        r, c = to_internal((row, col))
        if not self.rules.is_legal_move(self.board, r, c, self.opponent_color):
            raise ValueError(f"Illegal opponent move: {(row, col)}")
        self.board.place(r, c, self.opponent_color)

    def choose_move(self):
        start = time.time()
        deadline = start + max(0.05, min(self.time_limit, 3.0) - SAFETY_MARGIN)

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

        if time.time() >= deadline:
            return fallback
        my_tactics = self.generator.classify_tactical_moves(self.board, self.color)
        if time.time() >= deadline:
            return fallback
        opponent_tactics = self.generator.classify_tactical_moves(self.board, self.opponent_color)

        immediate_win = self._first_legal(my_tactics["immediate_win"])
        if immediate_win:
            return immediate_win

        if time.time() >= deadline:
            return fallback
        immediate_block = self._first_legal(opponent_tactics["immediate_win"])
        if immediate_block:
            return immediate_block

        if time.time() >= deadline:
            return fallback
        open_four = self._first_legal(my_tactics["open_four"])
        if open_four:
            return open_four

        if time.time() >= deadline:
            return fallback
        four_three = self._first_legal(my_tactics["four_three"])
        if four_three:
            return four_three

        if time.time() >= deadline:
            return fallback
        prevent_opponent_open_four_creation = self._first_legal(opponent_tactics["open_four"])
        if prevent_opponent_open_four_creation:
            return prevent_opponent_open_four_creation

        if time.time() >= deadline:
            return fallback
        prevent_opponent_four_three_creation = self._first_legal(opponent_tactics["four_three"])
        if prevent_opponent_four_three_creation:
            return prevent_opponent_four_three_creation

        if time.time() >= deadline:
            return fallback
        block_double_three = self._first_legal(opponent_tactics["legal_double_three_threat"])
        if block_double_three:
            return block_double_three

        if time.time() >= deadline:
            return fallback
        double_three = self._first_legal(my_tactics["legal_double_three_threat"])
        if double_three:
            return double_three

        if time.time() + 0.45 < deadline:
            future_deadline = min(deadline, time.time() + 0.35)
            block_future_setup = self._first_legal(
                self.generator.find_future_four_three_setup_moves(
                    self.board,
                    self.opponent_color,
                    deadline=future_deadline,
                )
            )
            if block_future_setup:
                return block_future_setup

        if time.time() + 0.45 < deadline:
            future_deadline = min(deadline, time.time() + 0.35)
            future_setup = self._first_legal(
                self.generator.find_future_four_three_setup_moves(
                    self.board,
                    self.color,
                    deadline=future_deadline,
                )
            )
            if future_setup:
                return future_setup

        if time.time() >= deadline:
            return fallback
        closed_four = self._first_legal(my_tactics["closed_four"])
        if closed_four:
            return closed_four

        if time.time() >= deadline:
            return fallback
        block_closed_four = self._first_legal(opponent_tactics["closed_four"])
        if block_closed_four:
            return block_closed_four

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

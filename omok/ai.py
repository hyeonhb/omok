from __future__ import annotations

import time

from .board import Board
from .constants import BLACK, WHITE, opponent, to_external, to_internal
from .move_generator import MoveGenerator
from .rules import RuleEngine
from .search import SearchEngine
from .strategy_weights import StrategyWeights
from .threat_search import ThreatSearch


SAFETY_MARGIN = 0.10
ROOT_DEEP_RETURN_THRESHOLD = 400_000


class OmokAI:
    def __init__(
        self,
        color=BLACK,
        blocked_cells=None,
        time_limit=3.0,
        allow_double_four=False,
        strategy_weights=None,
    ):
        self.color = color
        self.opponent_color = opponent(color)
        self.time_limit = time_limit
        self.allow_double_four = allow_double_four
        self.strategy_weights = strategy_weights or StrategyWeights()
        self.board = Board(blocked_cells=blocked_cells)
        self.rules = RuleEngine(allow_double_four=allow_double_four)
        self.generator = MoveGenerator(
            allow_double_four=allow_double_four,
            strategy_weights=self.strategy_weights,
        )
        self.search_engine = SearchEngine(
            allow_double_four=allow_double_four,
            strategy_weights=self.strategy_weights,
        )
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
        effective_limit = min(self.time_limit, 3.0)
        soft_deadline = start + max(0.05, effective_limit - 0.45)
        hard_deadline = start + max(0.05, effective_limit - 0.15)

        try:
            move = self._choose_move_internal(soft_deadline, hard_deadline)
        except Exception:
            move = self.generator.fallback_move(self.board, self.color, deadline=hard_deadline)

        if move is None or not self.rules.is_legal_move(self.board, move[0], move[1], self.color):
            move = self._first_legal_move()
        if move is None:
            raise RuntimeError("No legal moves available")

        self.board.place(move[0], move[1], self.color)
        return to_external(move)

    def _choose_move_internal(self, soft_deadline, hard_deadline=None):
        if hard_deadline is None:
            hard_deadline = soft_deadline
        deadline = hard_deadline
        if self.color == BLACK and self.board.move_count == 0:
            center = to_internal((10, 10))
            if self.rules.is_legal_move(self.board, center[0], center[1], self.color):
                return center

        fallback = self.generator.fallback_move(self.board, self.color, deadline=hard_deadline)
        if fallback is None:
            return None

        if time.time() >= hard_deadline:
            return fallback
        my_tactics = self.generator.classify_tactical_moves(self.board, self.color, deadline=hard_deadline)
        if time.time() >= hard_deadline:
            return fallback
        opponent_tactics = self.generator.classify_tactical_moves(
            self.board,
            self.opponent_color,
            deadline=hard_deadline,
        )

        immediate_win = self._first_legal(my_tactics["immediate_win"])
        if immediate_win:
            return immediate_win

        if time.time() >= hard_deadline:
            return fallback
        immediate_block = self._first_legal(opponent_tactics["immediate_win"])
        if immediate_block:
            return immediate_block

        if time.time() >= hard_deadline:
            return fallback
        open_four = self._first_legal(my_tactics["open_four"])
        if open_four:
            return open_four

        if time.time() >= hard_deadline:
            return fallback
        four_three = self._first_legal(my_tactics["four_three"])
        if four_three:
            return four_three

        if time.time() >= hard_deadline:
            return fallback
        prevent_opponent_open_four_creation = self._first_legal(opponent_tactics["open_four"])
        if prevent_opponent_open_four_creation:
            return prevent_opponent_open_four_creation

        if time.time() >= hard_deadline:
            return fallback
        prevent_opponent_four_three_creation = self._first_legal(opponent_tactics["four_three"])
        if prevent_opponent_four_three_creation:
            return prevent_opponent_four_three_creation

        if time.time() + 0.20 < soft_deadline:
            try:
                attack_deadline = min(soft_deadline, time.time() + 0.35)
                attack = self.threat_search.find_forcing_attack(self.board, self.color, attack_deadline)
                if attack and self._is_clear_forcing_move(attack, self.color):
                    return attack
            except TimeoutError:
                pass

        if time.time() >= hard_deadline:
            return fallback
        if time.time() + 0.20 < soft_deadline:
            try:
                defense_deadline = min(soft_deadline, time.time() + 0.35)
                defense = self.threat_search.find_forcing_defense(self.board, self.color, defense_deadline)
                if defense and self.rules.is_legal_move(self.board, defense[0], defense[1], self.color):
                    return defense
            except TimeoutError:
                pass

        if time.time() >= hard_deadline:
            return fallback
        deep_choice = self._root_deep_rerank(soft_deadline, hard_deadline, fallback)
        if deep_choice:
            return deep_choice

        if time.time() >= hard_deadline:
            return fallback
        if time.time() < hard_deadline:
            searched = self.search_engine.search(self.board, self.color, hard_deadline, fallback=fallback)
            if searched:
                return searched
        return fallback

    def _is_clear_forcing_move(self, move, color):
        r, c = move
        if not self.rules.is_legal_move(self.board, r, c, color):
            return False
        self.board.place(r, c, color)
        try:
            if self.rules.check_win(self.board, r, c, color):
                return True
            counts = self.generator.patterns.analyze_move(self.board, r, c, color)
            return counts["open_four"] > 0 or counts["four_three"] > 0
        finally:
            self.board.undo(r, c)

    def _root_deep_rerank(self, soft_deadline, hard_deadline=None, fallback=None):
        if hard_deadline is None:
            hard_deadline = soft_deadline
        if time.time() + 0.20 >= soft_deadline or time.time() >= hard_deadline:
            return None

        candidates = self.generator.generate_search_candidates(
            self.board,
            self.color,
            max_moves=10,
            include_future_setup=False,
            use_deep_score=False,
            deadline=hard_deadline,
        )
        if not candidates:
            return None

        deep_deadline = min(soft_deadline, hard_deadline, time.time() + 0.18)
        best_move = None
        best_score = -10**18
        for r, c in candidates[:12]:
            if time.time() >= deep_deadline:
                break
            if not self.rules.is_legal_move(self.board, r, c, self.color):
                continue
            score = self.generator.evaluator.deep_score_candidate(
                self.board,
                r,
                c,
                self.color,
                deadline=deep_deadline,
                root_eval=True,
            )
            if score > best_score:
                best_score = score
                best_move = (r, c)

        if best_move is None or best_score < ROOT_DEEP_RETURN_THRESHOLD:
            return None
        if fallback and best_move == fallback:
            return None
        return best_move

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

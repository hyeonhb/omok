from __future__ import annotations

import time
from dataclasses import dataclass

from .constants import FIVE_OR_MORE, INF, opponent
from .evaluator import Evaluator
from .move_generator import MoveGenerator
from .rules import RuleEngine
from .strategy_weights import StrategyWeights


@dataclass
class TTEntry:
    depth: int
    score: int
    flag: str
    best_move: tuple[int, int] | None


class SearchEngine:
    def __init__(self, allow_double_four=False, strategy_weights=None):
        self.allow_double_four = allow_double_four
        self.strategy_weights = strategy_weights or StrategyWeights()
        self.evaluator = Evaluator(
            allow_double_four=allow_double_four,
            strategy_weights=self.strategy_weights,
        )
        self.generator = MoveGenerator(
            allow_double_four=allow_double_four,
            strategy_weights=self.strategy_weights,
        )
        self.rules = RuleEngine(allow_double_four=allow_double_four)
        self.transposition_table = {}
        self.eval_cache = {}

    def set_allow_double_four(self, allow):
        self.allow_double_four = allow
        self.evaluator.set_allow_double_four(allow)
        self.generator.set_allow_double_four(allow)
        self.rules.allow_double_four = allow
        self.clear_cache()

    def set_strategy_weights(self, strategy_weights):
        self.strategy_weights = strategy_weights or StrategyWeights()
        self.evaluator.set_strategy_weights(self.strategy_weights)
        self.generator.set_strategy_weights(self.strategy_weights)
        self.clear_cache()

    def clear_cache(self):
        self.transposition_table.clear()
        self.eval_cache.clear()

    def search(self, board, color, deadline, fallback=None):
        if fallback is None:
            fallback = self.generator.fallback_move(board, color, deadline=deadline)
        best_move = fallback
        max_depth = self._max_depth_for_position(board)

        for depth in range(1, max_depth + 1):
            if time.time() >= deadline:
                break
            try:
                score, move = self._root_search(board, depth, color, deadline)
                if move is not None:
                    best_move = move
            except TimeoutError:
                break
        return best_move

    def _root_search(self, board, depth, color, deadline):
        alpha = -INF
        beta = INF
        best_score = -INF
        best_move = None
        moves = self._limited_candidates(board, color, depth, deadline)

        for move in moves:
            if time.time() >= deadline:
                raise TimeoutError
            r, c = move
            board.place(r, c, color)
            try:
                score = -self.negamax(board, depth - 1, -beta, -alpha, opponent(color), deadline)
            finally:
                board.undo(r, c)
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
        return best_score, best_move

    def negamax(self, board, depth, alpha, beta, color, deadline):
        if time.time() >= deadline:
            raise TimeoutError

        terminal = self._terminal_score(board, color)
        if terminal is not None:
            return terminal
        if depth == 0:
            return self._cached_evaluate(board, color)

        key = (board.hash_value, color)
        original_alpha = alpha
        entry = self.transposition_table.get(key)
        if entry and entry.depth >= depth:
            if entry.flag == "EXACT":
                return entry.score
            if entry.flag == "LOWER":
                alpha = max(alpha, entry.score)
            elif entry.flag == "UPPER":
                beta = min(beta, entry.score)
            if alpha >= beta:
                return entry.score

        best_score = -INF
        best_move = None
        moves = self._limited_candidates(board, color, depth, deadline)
        if not moves:
            return self._cached_evaluate(board, color)

        for r, c in moves:
            if time.time() >= deadline:
                raise TimeoutError
            board.place(r, c, color)
            try:
                score = -self.negamax(board, depth - 1, -beta, -alpha, opponent(color), deadline)
            finally:
                board.undo(r, c)
            if score > best_score:
                best_score = score
                best_move = (r, c)
            alpha = max(alpha, score)
            if alpha >= beta:
                break

        flag = "EXACT"
        if best_score <= original_alpha:
            flag = "UPPER"
        elif best_score >= beta:
            flag = "LOWER"
        self.transposition_table[key] = TTEntry(depth, int(best_score), flag, best_move)
        return int(best_score)

    def _cached_evaluate(self, board, color):
        key = (board.hash_value, color)
        if key not in self.eval_cache:
            self.eval_cache[key] = self.evaluator.evaluate(board, color)
        return self.eval_cache[key]

    def _terminal_score(self, board, color):
        if not board.last_move:
            return None
        r, c, last_color = board.last_move
        if self.rules.check_win(board, r, c, last_color):
            return -FIVE_OR_MORE if last_color == opponent(color) else FIVE_OR_MORE
        return None

    def _limited_candidates(self, board, color, depth, deadline):
        if time.time() >= deadline:
            return []
        if board.move_count < 8:
            normal_limit = 12
        elif board.move_count < 30:
            normal_limit = 16 if depth < 3 else 12
        else:
            normal_limit = 22 if depth < 3 else 16
        return self.generator.generate_search_candidates(
            board,
            color,
            max_moves=normal_limit,
            include_future_setup=False,
            include_plan_candidates=False,
            use_deep_score=False,
            deadline=deadline,
        )

    def _max_depth_for_position(self, board):
        if board.move_count < 8:
            return 4
        if board.move_count < 40:
            return 3
        return 3

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

from .constants import FIVE_OR_MORE, INF, opponent
from .evaluator import Evaluator
from .move_generator import MoveGenerator
from .rules import RuleEngine
from .search_config import HISTORY_DECAY_THRESHOLD, MAX_KILLERS_PER_DEPTH, USE_PVS
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
        self.pv_move: tuple[int, int] | None = None
        self.killer_moves: dict[int, list[tuple[int, int]]] = defaultdict(list)
        self.history_scores: dict[tuple[int, int], int] = defaultdict(int)

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

    def _reset_search_heuristics(self):
        self.pv_move = None
        self.killer_moves = defaultdict(list)
        self.history_scores = defaultdict(int)

    def search(self, board, color, deadline, fallback=None):
        if fallback is None:
            fallback = self.generator.fallback_move(board, color, deadline=deadline)
        self._reset_search_heuristics()
        best_move = fallback
        max_depth = self._max_depth_for_position(board)

        for depth in range(1, max_depth + 1):
            if time.time() >= deadline:
                break
            try:
                score, move = self._root_search(board, depth, color, deadline)
                if move is not None:
                    best_move = move
                    self.pv_move = move
            except TimeoutError:
                break
        return best_move

    def _root_search(self, board, depth, color, deadline):
        alpha = -INF
        beta = INF
        best_score = -INF
        best_move = None
        raw_moves = self._limited_candidates(board, color, depth, deadline)
        tt_entry = self.transposition_table.get((board.hash_value, color))
        tt_move = tt_entry.best_move if tt_entry else None
        moves = self._order_moves_for_search(
            board,
            color,
            depth,
            raw_moves,
            deadline,
            pv_move=self.pv_move,
            tt_move=tt_move,
        )

        first = True
        opp = opponent(color)
        for move in moves:
            if time.time() >= deadline:
                raise TimeoutError
            r, c = move
            board.place(r, c, color)
            try:
                if self.rules.check_win(board, r, c, color):
                    score = FIVE_OR_MORE
                elif not USE_PVS or first:
                    score = -self.negamax(board, depth - 1, -beta, -alpha, opp, deadline)
                    first = False
                else:
                    score = -self.negamax(board, depth - 1, -alpha - 1, -alpha, opp, deadline)
                    if alpha < score < beta:
                        score = -self.negamax(board, depth - 1, -beta, -score, opp, deadline)
            finally:
                board.undo(r, c)

            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                self._record_killer(depth, move)
                self._record_history(move, depth)
                break
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
        tt_move = None
        entry = self.transposition_table.get(key)
        if entry and entry.depth >= depth:
            tt_move = entry.best_move
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
        raw_moves = self._limited_candidates(board, color, depth, deadline)
        if not raw_moves:
            return self._cached_evaluate(board, color)

        moves = self._order_moves_for_search(
            board,
            color,
            depth,
            raw_moves,
            deadline,
            pv_move=None,
            tt_move=tt_move,
        )

        first = True
        for move in moves:
            if time.time() >= deadline:
                raise TimeoutError
            r, c = move
            board.place(r, c, color)
            try:
                if not USE_PVS or first:
                    score = -self.negamax(
                        board, depth - 1, -beta, -alpha, opponent(color), deadline
                    )
                    first = False
                else:
                    score = -self.negamax(
                        board, depth - 1, -alpha - 1, -alpha, opponent(color), deadline
                    )
                    if alpha < score < beta:
                        score = -self.negamax(
                            board, depth - 1, -beta, -score, opponent(color), deadline
                        )
            finally:
                board.undo(r, c)

            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                self._record_killer(depth, move)
                self._record_history(move, depth)
                break

        flag = "EXACT"
        if best_score <= original_alpha:
            flag = "UPPER"
        elif best_score >= beta:
            flag = "LOWER"
        self.transposition_table[key] = TTEntry(depth, int(best_score), flag, best_move)
        return int(best_score)

    def _record_killer(self, depth, move):
        killers = self.killer_moves[depth]
        if move in killers:
            killers.remove(move)
        killers.insert(0, move)
        del killers[MAX_KILLERS_PER_DEPTH:]

    def _record_history(self, move, depth):
        self.history_scores[move] += depth * depth
        if len(self.history_scores) > HISTORY_DECAY_THRESHOLD:
            for key in list(self.history_scores.keys()):
                self.history_scores[key] //= 2
                if self.history_scores[key] == 0:
                    del self.history_scores[key]

    def _order_moves_for_search(
        self,
        board,
        color,
        depth,
        moves,
        deadline,
        pv_move=None,
        tt_move=None,
    ):
        if time.time() >= deadline:
            return []
        legal = [
            move
            for move in moves
            if self.rules.is_legal_move(board, move[0], move[1], color)
        ]
        if len(legal) <= 1:
            return legal

        my_tactics = self.generator.classify_tactical_moves(board, color, deadline=deadline)
        opp_tactics = self.generator.classify_tactical_moves(
            board, opponent(color), deadline=deadline
        )
        my_sets = {name: set(group) for name, group in my_tactics.items()}
        opp_sets = {name: set(group) for name, group in opp_tactics.items()}
        killer_index = {move: idx for idx, move in enumerate(self.killer_moves.get(depth, []))}

        def sort_key(move):
            if pv_move and move == pv_move:
                return (0, 0, 0, 0)
            if tt_move and move == tt_move:
                return (1, 0, 0, 0)
            if move in my_sets["immediate_win"]:
                return (2, 0, 0, 0)
            if move in opp_sets["immediate_win"]:
                return (3, 0, 0, 0)
            if move in my_sets["open_four"]:
                return (4, 0, 0, 0)
            if move in opp_sets["open_four"]:
                return (5, 0, 0, 0)
            if move in my_sets["four_three"]:
                return (6, 0, 0, 0)
            if move in opp_sets["four_three"]:
                return (7, 0, 0, 0)
            if move in killer_index:
                return (8, killer_index[move], 0, 0)
            history = self.history_scores.get(move, 0)
            quick = self.generator.evaluator.quick_score_candidate(board, move[0], move[1], color)
            return (20, 0, -history, -quick)

        return sorted(legal, key=sort_key)

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

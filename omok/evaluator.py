from __future__ import annotations

import time

from .constants import (
    BLACK,
    BROKEN_OPEN_THREE,
    BOARD_SIZE,
    CLOSED_FOUR,
    CLOSED_THREE,
    CLOSED_TWO,
    DIRECTIONS,
    FIVE_OR_MORE,
    FOUR_THREE,
    FUTURE_FOUR_THREE_SETUP,
    ILLEGAL_MOVE,
    LEGAL_DOUBLE_THREE_THREAT,
    OPEN_FOUR,
    OPEN_THREE,
    OPEN_TWO,
    WHITE,
    opponent,
)
from .patterns import PatternAnalyzer
from .rules import RuleEngine
from .strategy_config import (
    BLACK_OPENING_CENTER_CONNECTION_BONUS,
    BLACK_OPENING_FUTURE_43_MULTI_BONUS,
    BLACK_OPENING_OPEN_THREE_MULTI_DIR_BONUS,
    BLACK_OPENING_OPEN_TWO_MULTI_DIR_BONUS,
    BLACK_OPENING_SEED_SCORE_CAP,
    BLACK_OPENING_SEED_WEIGHT,
    BLACK_OPENING_THREE_DIRECTION_BONUS,
    BLACK_OPENING_TWO_DIRECTION_BONUS,
    ENABLE_BLACK_OPENING_SEED,
    ENABLE_GENERAL_PLAN_EVAL,
    ENABLE_INITIATIVE_EVAL,
    ENABLE_LEAF_NEXT_THREAT,
    ENABLE_OPPONENT_PLAN_BLOCKING,
    ENABLE_WHITE_OPENING_DISRUPTION,
    OPENING_STRATEGY_MAX_MOVES,
    WHITE_OPENING_DISRUPTION_WEIGHT,
)
from .strategy_weights import StrategyWeights


DEFENSE_WEIGHT = 1.30
CANDIDATE_DEFENSE_WEIGHT = 1.35
FUTURE_DEFENSE_BONUS = 500_000
OPPONENT_FOUR_THREE_PENALTY = 3_000_000
OPPONENT_IMMEDIATE_WIN_REPLY = -100_000_000
OPPONENT_OPEN_FOUR_REPLY = -15_000_000
OPPONENT_FOUR_THREE_REPLY = -12_000_000
OPPONENT_LEGAL_DOUBLE_THREE_REPLY = -1_500_000
OPPONENT_CLOSED_FOUR_REPLY = -1_000_000
OPPONENT_OPEN_THREE_REPLY = -300_000
OPPONENT_BROKEN_OPEN_THREE_REPLY = -180_000


class Evaluator:
    def __init__(self, allow_double_four=False, strategy_weights=None):
        self.allow_double_four = allow_double_four
        self.strategy_weights = strategy_weights or StrategyWeights()
        self.patterns = PatternAnalyzer()
        self.rules = RuleEngine(allow_double_four=allow_double_four)

    def set_allow_double_four(self, allow):
        self.allow_double_four = allow
        self.rules.allow_double_four = allow

    def set_strategy_weights(self, strategy_weights):
        self.strategy_weights = strategy_weights or StrategyWeights()

    def evaluate(self, board, color):
        my_score = self._pattern_score(board, color)
        opponent_score = self._pattern_score(board, opponent(color))
        return int(my_score - opponent_score * DEFENSE_WEIGHT)

    def score_candidate(self, board, r, c, color, deadline=None):
        return self.deep_score_candidate(board, r, c, color, deadline=deadline, root_eval=True)

    def quick_score_candidate(self, board, r, c, color):
        if not self.rules.is_legal_move(board, r, c, color):
            return ILLEGAL_MOVE

        opp = opponent(color)
        board.place(r, c, color)
        try:
            if self.rules.check_win(board, r, c, color):
                return FIVE_OR_MORE
            attack = self._local_move_score(board, r, c, color)
            local_counts = self.patterns.analyze_move(board, r, c, color)
        finally:
            board.undo(r, c)

        if board.is_empty(r, c) and self.rules.is_legal_move(board, r, c, opp):
            board.place(r, c, opp)
            try:
                defense = self._local_move_score(board, r, c, opp)
                if self.rules.check_win(board, r, c, opp):
                    defense = FIVE_OR_MORE
            finally:
                board.undo(r, c)
        else:
            defense = 0
        center_bonus = 40 - (abs(r - 9) + abs(c - 9))
        return attack + int(defense * CANDIDATE_DEFENSE_WEIGHT) + center_bonus

    def deep_score_candidate(self, board, r, c, color, deadline=None, root_eval=False):
        if not root_eval:
            return self.quick_score_candidate(board, r, c, color)

        base = self.quick_score_candidate(board, r, c, color)
        if base == ILLEGAL_MOVE:
            return ILLEGAL_MOVE

        opening_bonus = self._root_opening_bonus(board, r, c, color, deadline=deadline)

        if not ENABLE_GENERAL_PLAN_EVAL:
            return base + opening_bonus

        return base + opening_bonus + self._legacy_root_plan_bonus(
            board, r, c, color, deadline=deadline
        )

    def _root_opening_bonus(self, board, r, c, color, deadline=None):
        if board.move_count >= OPENING_STRATEGY_MAX_MOVES:
            return 0
        if deadline is not None and time.time() >= deadline:
            return 0

        if color == BLACK and ENABLE_BLACK_OPENING_SEED:
            opening_score = self.evaluate_opening_multi_direction_seed(
                board, r, c, color, deadline=deadline
            )
            opening_score = min(opening_score, BLACK_OPENING_SEED_SCORE_CAP)
            return int(opening_score * BLACK_OPENING_SEED_WEIGHT)

        if color == WHITE and ENABLE_WHITE_OPENING_DISRUPTION:
            return int(
                self.evaluate_opening_disruption(board, r, c, color, deadline=deadline)
                * WHITE_OPENING_DISRUPTION_WEIGHT
            )

        return 0

    def _legacy_root_plan_bonus(self, board, r, c, color, deadline=None):
        opp = opponent(color)
        board.place(r, c, color)
        try:
            if self.rules.check_win(board, r, c, color):
                return 0
            local_counts = self.patterns.analyze_move(board, r, c, color)
            if deadline is not None and time.time() >= deadline:
                return 0
            future_attack = self.evaluate_future_threat_potential(
                board, (r, c), color, deadline=deadline, already_placed=True
            )
            resilient_future_attack = 0
            reply_penalty = 0
            initiative_score = 0
            opponent_plan_block_score = 0
            if ENABLE_GENERAL_PLAN_EVAL:
                resilient_future_attack = self.evaluate_resilient_future_four_three_setup(
                    board, (r, c), color, deadline=deadline, already_placed=True
                )
                reply_penalty = self.evaluate_opponent_best_reply_penalty(
                    board, (r, c), color, deadline=deadline, already_placed=True
                )
            if ENABLE_INITIATIVE_EVAL:
                initiative_score = self.evaluate_initiative_potential(
                    board, r, c, color, deadline=deadline, already_placed=True
                )
            if ENABLE_OPPONENT_PLAN_BLOCKING:
                opponent_plan_block_score = self.evaluate_opponent_plan_blocking(
                    board, r, c, color, deadline=deadline, already_placed=True
                )
            opponent_next_four_threes = self.count_future_four_three_moves(
                board, opp, radius=2, limit=14, deadline=deadline
            )
            single_attack_penalty = 0
            if ENABLE_INITIATIVE_EVAL or ENABLE_OPPONENT_PLAN_BLOCKING:
                single_attack_penalty = self._single_attack_penalty(
                    local_counts,
                    initiative_score,
                    opponent_plan_block_score,
                    reply_penalty,
                    opponent_next_four_threes,
                )
        finally:
            board.undo(r, c)

        weights = self.strategy_weights
        initiative_weight = weights.initiative_weight_for(color)
        blocking_weight = weights.blocking_weight_for(color)
        danger_penalty = OPPONENT_FOUR_THREE_PENALTY if opponent_next_four_threes else 0
        return int(
            future_attack * weights.future_43_weight * initiative_weight
            + resilient_future_attack * weights.resilient_future_weight * initiative_weight
            + initiative_score * initiative_weight
            + opponent_plan_block_score * blocking_weight
            + reply_penalty * weights.opponent_reply_penalty_weight
            - danger_penalty
            + single_attack_penalty
        )

    def evaluate_opening_multi_direction_seed(self, board, r, c, color, deadline=None):
        if color != BLACK or not ENABLE_BLACK_OPENING_SEED:
            return 0
        if board.move_count >= OPENING_STRATEGY_MAX_MOVES:
            return 0
        if deadline is not None and time.time() >= deadline:
            return 0
        if not self.rules.is_legal_move(board, r, c, color):
            return 0

        board.place(r, c, color)
        try:
            features = self._opening_seed_features(board, r, c, color, deadline=deadline)
            return self._score_opening_seed_features(features, color)
        finally:
            board.undo(r, c)

    def evaluate_opening_disruption(self, board, r, c, color, deadline=None):
        if color != WHITE or not ENABLE_WHITE_OPENING_DISRUPTION:
            return 0
        if board.move_count >= OPENING_STRATEGY_MAX_MOVES:
            return 0
        if deadline is not None and time.time() >= deadline:
            return 0
        if not self.rules.is_legal_move(board, r, c, color):
            return 0

        before = self._black_opening_seed_pressure(board, deadline=deadline)
        if before["pressure"] <= 0:
            return 0

        board.place(r, c, color)
        try:
            after = self._black_opening_seed_pressure(board, deadline=deadline)
            return self._opening_disruption_bonus(before, after)
        finally:
            board.undo(r, c)

    def _opening_seed_features(self, board, r, c, color, deadline=None):
        growth_dirs = set()
        open_two_dirs = set()
        open_three_dirs = set()
        for dir_idx, (dr, dc) in enumerate(DIRECTIONS):
            if deadline is not None and time.time() >= deadline:
                break
            if self._direction_has_open_two(board, r, c, color, dr, dc):
                open_two_dirs.add(dir_idx)
                growth_dirs.add(dir_idx)
            if self.patterns.has_open_three_in_direction(board, r, c, color, dr, dc):
                open_three_dirs.add(dir_idx)
                growth_dirs.add(dir_idx)
            elif self._direction_has_own_neighbor(board, r, c, color, dr, dc):
                growth_dirs.add(dir_idx)

        future_43 = 0
        if deadline is None or time.time() < deadline:
            future_43 = len(self._future_four_three_moves(board, color, radius=2, limit=8, deadline=deadline))

        return {
            "growth_dirs": len(growth_dirs),
            "open_two_dirs": len(open_two_dirs),
            "open_three_dirs": len(open_three_dirs),
            "future_43": future_43,
            "near_center_link": self._connects_near_center(board, r, c, color),
            "center_distance": abs(r - 9) + abs(c - 9),
        }

    def _score_opening_seed_features(self, features, color):
        score = 0
        if features["growth_dirs"] >= 3:
            score += BLACK_OPENING_THREE_DIRECTION_BONUS
        elif features["growth_dirs"] >= 2:
            score += BLACK_OPENING_TWO_DIRECTION_BONUS

        if features["open_two_dirs"] >= 2:
            score += BLACK_OPENING_OPEN_TWO_MULTI_DIR_BONUS

        if features["open_three_dirs"] >= 2:
            score += BLACK_OPENING_OPEN_THREE_MULTI_DIR_BONUS
        elif features["open_three_dirs"] >= 1 and features["open_two_dirs"] >= 1:
            score += BLACK_OPENING_OPEN_THREE_MULTI_DIR_BONUS

        if features["future_43"] >= 2:
            score += BLACK_OPENING_FUTURE_43_MULTI_BONUS

        if features["near_center_link"]:
            score += BLACK_OPENING_CENTER_CONNECTION_BONUS

        if color == BLACK:
            if features["center_distance"] > 6:
                score -= 80_000
            if features["growth_dirs"] <= 1 and features["open_two_dirs"] == 0:
                score -= 100_000

        return max(0, score)

    def _black_opening_seed_pressure(self, board, deadline=None, limit=10):
        summary = {
            "two_dir": 0,
            "three_dir": 0,
            "future_43": 0,
            "good_moves": 0,
            "pressure": 0,
        }
        for move_r, move_c in self._ordered_future_candidates(board, BLACK, radius=2, limit=limit):
            if deadline is not None and time.time() >= deadline:
                break
            if not self.rules.is_legal_move(board, move_r, move_c, BLACK):
                continue
            board.place(move_r, move_c, BLACK)
            try:
                features = self._opening_seed_features(board, move_r, move_c, BLACK, deadline=deadline)
            finally:
                board.undo(move_r, move_c)
            seed_score = self._score_opening_seed_features(features, BLACK)
            if seed_score < 120_000:
                continue
            summary["good_moves"] += 1
            if features["growth_dirs"] >= 2:
                summary["two_dir"] += 1
            if features["growth_dirs"] >= 3:
                summary["three_dir"] += 1
            if features["future_43"] >= 2:
                summary["future_43"] += 1
            summary["pressure"] = max(summary["pressure"], seed_score)
        return summary

    def _opening_disruption_bonus(self, before, after):
        reduced_two = max(0, before["two_dir"] - after["two_dir"])
        reduced_three = max(0, before["three_dir"] - after["three_dir"])
        reduced_future = max(0, before["future_43"] - after["future_43"])
        reduced_good = max(0, before["good_moves"] - after["good_moves"])

        score = 0
        if reduced_two:
            score += 150_000
        if reduced_three:
            score += 300_000
        if reduced_future:
            score += 500_000
        if reduced_good >= 2:
            score += 700_000
        elif reduced_good == 1 and score == 0:
            score += 150_000
        return score

    def _direction_has_open_two(self, board, r, c, color, dr, dc):
        line = self.patterns.line_around(board, r, c, color, dr, dc)
        center = len(line) // 2
        for shape in self.patterns.OPEN_TWO_SHAPES:
            start = line.find(shape)
            while start != -1:
                if start <= center < start + len(shape):
                    return True
                start = line.find(shape, start + 1)
        return False

    def _direction_has_own_neighbor(self, board, r, c, color, dr, dc):
        for step in (-1, 1):
            nr, nc = r + dr * step, c + dc * step
            if board.get(nr, nc) == color:
                return True
        return False

    def _connects_near_center(self, board, r, c, color):
        if abs(r - 9) + abs(c - 9) <= 2:
            return True
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if board.get(nr, nc) == color and abs(nr - 9) + abs(nc - 9) <= 4:
                    return True
        return False

    def _single_attack_penalty(self, counts, initiative_score, opponent_plan_block_score, reply_penalty, opponent_next_four_threes):
        has_only_open_three = (
            counts["open_three"]
            and not counts["open_four"]
            and not counts["four_three"]
            and not counts["closed_four"]
            and not counts["broken_four"]
            and not counts["legal_double_three_threat"]
        )
        has_only_closed_four = (
            (counts["closed_four"] or counts["broken_four"])
            and not counts["open_four"]
            and not counts["four_three"]
            and not counts["legal_double_three_threat"]
        )
        if initiative_score >= 250_000 or opponent_plan_block_score > 0:
            return 0
        penalty = 0
        if has_only_open_three and reply_penalty <= OPPONENT_OPEN_THREE_REPLY:
            penalty -= 150_000
        if has_only_closed_four and reply_penalty <= OPPONENT_CLOSED_FOUR_REPLY:
            penalty -= 250_000
        if opponent_next_four_threes:
            penalty -= 400_000
        return penalty

    def evaluate_initiative_potential(self, board, r, c, color, deadline=None, already_placed=False):
        placed = False
        if not already_placed:
            if not self.rules.is_legal_move(board, r, c, color):
                return 0
            board.place(r, c, color)
            placed = True
        try:
            if deadline is not None and time.time() >= deadline:
                return 0
            future = self._future_threat_summary(board, color, limit=12, deadline=deadline)
            strong_count = (
                future["four_three"]
                + future["open_four"]
                + future["legal_double_three"]
                + future["closed_four"]
            )
            score = 0
            if strong_count >= 2:
                score += 700_000
            elif strong_count == 1:
                score += 250_000
            if future["direction_diverse"]:
                score += 400_000
            if self._future_threat_survives_best_defense(board, color, future["moves"], deadline):
                score += 800_000
            return score
        finally:
            if placed:
                board.undo(r, c)

    def evaluate_opponent_plan_blocking(self, board, r, c, color, deadline=None, already_placed=False):
        if deadline is not None and time.time() >= deadline:
            return 0
        opp = opponent(color)
        if already_placed:
            board.undo(r, c)
            try:
                before = self._plan_pressure_score(board, opp, deadline=deadline)
            finally:
                board.place(r, c, color)
            if before <= 0 or (deadline is not None and time.time() >= deadline):
                return 0
            after = self._plan_pressure_score(board, opp, deadline=deadline)
            return self._plan_block_bonus(before, after)

        before = self._plan_pressure_score(board, opp, deadline=deadline)
        if before <= 0:
            return 0

        placed = False
        if not already_placed:
            if not self.rules.is_legal_move(board, r, c, color):
                return 0
            board.place(r, c, color)
            placed = True
        try:
            if deadline is not None and time.time() >= deadline:
                return 0
            after = self._plan_pressure_score(board, opp, deadline=deadline)
            return self._plan_block_bonus(before, after)
        finally:
            if placed:
                board.undo(r, c)

    def _plan_block_bonus(self, before, after):
        reduced = max(0, before - after)
        if reduced >= 1_200_000:
            return 800_000
        if reduced >= 600_000:
            return 600_000
        if reduced >= 300_000:
            return 300_000
        return 0

    def evaluate_resilient_future_four_three_setup(self, board, move, color, deadline=None, already_placed=False):
        r, c = move
        placed = False
        if not already_placed:
            if not self.rules.is_legal_move(board, r, c, color):
                return 0
            board.place(r, c, color)
            placed = True
        try:
            import time

            future_moves = self._future_four_three_moves(board, color, radius=2, limit=12, deadline=deadline)
            if not future_moves:
                return 0
            score = 900_000 if len(future_moves) >= 2 else FUTURE_FOUR_THREE_SETUP

            if deadline is not None and time.time() >= deadline:
                return score

            opp = opponent(color)
            remaining_after_best_defense = len(future_moves)
            for defense in self._ordered_future_candidates(board, opp, radius=2, limit=10):
                if deadline is not None and time.time() >= deadline:
                    return score
                dr, dc = defense
                board.place(dr, dc, opp)
                try:
                    remaining = len(self._future_four_three_moves(board, color, radius=2, limit=12, deadline=deadline))
                finally:
                    board.undo(dr, dc)
                remaining_after_best_defense = min(remaining_after_best_defense, remaining)
                if remaining_after_best_defense == 0:
                    break

            if remaining_after_best_defense > 0:
                score += 1_500_000
            elif len(future_moves) >= 2:
                score += 200_000
            return score
        finally:
            if placed:
                board.undo(r, c)

    def evaluate_opponent_best_reply_penalty(self, board, move, color, limit=16, deadline=None, already_placed=False):
        r, c = move
        placed = False
        if not already_placed:
            if not self.rules.is_legal_move(board, r, c, color):
                return 0
            board.place(r, c, color)
            placed = True
        try:
            opp = opponent(color)
            best_penalty = 0
            for rr, rc in self._ordered_future_candidates(board, opp, radius=2, limit=limit):
                if deadline is not None and time.time() >= deadline:
                    break
                board.place(rr, rc, opp)
                try:
                    if self.rules.check_win(board, rr, rc, opp):
                        return OPPONENT_IMMEDIATE_WIN_REPLY
                finally:
                    board.undo(rr, rc)

                counts = self.patterns.analyze_move(board, rr, rc, opp)
                best_penalty = min(best_penalty, self._reply_penalty_from_counts(counts))
            return best_penalty
        finally:
            if placed:
                board.undo(r, c)

    def _reply_penalty_from_counts(self, counts):
        if counts["open_four"]:
            return OPPONENT_OPEN_FOUR_REPLY
        if counts["four_three"]:
            return OPPONENT_FOUR_THREE_REPLY
        if counts["legal_double_three_threat"]:
            return OPPONENT_LEGAL_DOUBLE_THREE_REPLY
        if counts["closed_four"] or counts["broken_four"]:
            return OPPONENT_CLOSED_FOUR_REPLY
        if counts["open_three"]:
            return OPPONENT_OPEN_THREE_REPLY
        if counts["broken_open_three"]:
            return OPPONENT_BROKEN_OPEN_THREE_REPLY
        return 0

    def evaluate_future_threat_potential(self, board, move, color, deadline=None, already_placed=False):
        r, c = move
        placed = False
        if not already_placed:
            if not self.rules.is_legal_move(board, r, c, color):
                return 0
            board.place(r, c, color)
            placed = True
        try:
            future_four_threes = self.count_future_four_three_moves(
                board,
                color,
                radius=2,
                limit=12,
                deadline=deadline,
            )
            future_open_fours = self._count_future_pattern_moves(
                board,
                color,
                "open_four",
                radius=2,
                limit=12,
                deadline=deadline,
            )
            future_double_threes = self._count_future_pattern_moves(
                board,
                color,
                "legal_double_three_threat",
                radius=2,
                limit=12,
                deadline=deadline,
            )
            score = 0
            if future_four_threes >= 2:
                score += 1_000_000
            elif future_four_threes == 1:
                score += FUTURE_FOUR_THREE_SETUP
            if future_open_fours:
                score += 600_000
            if future_double_threes:
                score += 250_000
            return score
        finally:
            if placed:
                board.undo(r, c)

    def count_future_four_three_moves(self, board, color, radius=2, limit=12, deadline=None):
        return len(self._future_four_three_moves(board, color, radius=radius, limit=limit, deadline=deadline))

    def _future_four_three_moves(self, board, color, radius=2, limit=12, deadline=None):
        moves = []
        for r, c in self._ordered_future_candidates(board, color, radius=radius, limit=limit):
            if deadline is not None and time.time() >= deadline:
                break
            counts = self.patterns.analyze_move(board, r, c, color)
            if counts["four_three"]:
                moves.append((r, c))
        return moves

    def _future_threat_summary(self, board, color, limit=12, deadline=None):
        summary = {
            "four_three": 0,
            "open_four": 0,
            "legal_double_three": 0,
            "closed_four": 0,
            "direction_diverse": False,
            "moves": [],
        }
        threat_dirs = set()
        for r, c in self._ordered_future_candidates(board, color, radius=2, limit=limit):
            if deadline is not None and time.time() >= deadline:
                break
            counts = self.patterns.analyze_move(board, r, c, color)
            if counts["four_three"]:
                summary["four_three"] += 1
                summary["moves"].append((r, c))
            if counts["open_four"]:
                summary["open_four"] += 1
                summary["moves"].append((r, c))
            if counts["legal_double_three_threat"]:
                summary["legal_double_three"] += 1
                summary["moves"].append((r, c))
            if counts["closed_four"] or counts["broken_four"]:
                summary["closed_four"] += 1
                summary["moves"].append((r, c))
            if counts["four_three"] or counts["open_four"] or counts["legal_double_three_threat"] or counts["closed_four"] or counts["broken_four"]:
                # Directional detail is already collapsed in analyze_move; approximate diversity by move spread.
                threat_dirs.add((r < 9, c < 9, abs(r - 9) >= abs(c - 9)))
        summary["moves"] = list(dict.fromkeys(summary["moves"]))
        summary["direction_diverse"] = len(threat_dirs) >= 2
        return summary

    def _future_threat_survives_best_defense(self, board, color, threat_moves, deadline=None):
        if len(threat_moves) < 2:
            return False
        opp = opponent(color)
        best_remaining = len(threat_moves)
        for dr, dc in self._ordered_future_candidates(board, opp, radius=2, limit=8):
            if deadline is not None and time.time() >= deadline:
                return False
            board.place(dr, dc, opp)
            try:
                remaining = len(self._future_threat_summary(board, color, limit=10, deadline=deadline)["moves"])
            finally:
                board.undo(dr, dc)
            best_remaining = min(best_remaining, remaining)
            if best_remaining == 0:
                return False
        return best_remaining > 0

    def _plan_pressure_score(self, board, color, deadline=None):
        summary = self._future_threat_summary(board, color, limit=10, deadline=deadline)
        return (
            summary["four_three"] * 500_000
            + summary["open_four"] * 600_000
            + summary["legal_double_three"] * 300_000
            + summary["closed_four"] * 200_000
        )

    def _local_move_score(self, board, r, c, color):
        counts = self.patterns.analyze_move(board, r, c, color)
        return self._threat_weighted_score(counts)

    def _threat_weighted_score(self, counts):
        threat_values = []
        threat_values.extend([FIVE_OR_MORE] * counts["five"])
        threat_values.extend([OPEN_FOUR] * counts["open_four"])
        threat_values.extend([FOUR_THREE] * counts["four_three"])
        threat_values.extend([CLOSED_FOUR] * (counts["closed_four"] + counts["broken_four"]))
        threat_values.extend([LEGAL_DOUBLE_THREE_THREAT] * counts["legal_double_three_threat"])
        threat_values.extend([OPEN_THREE] * counts["open_three"])
        threat_values.extend([BROKEN_OPEN_THREE] * counts["broken_open_three"])
        threat_values.extend([OPEN_TWO] * counts["open_two"])

        if not threat_values:
            return counts["closed_three"] * CLOSED_THREE + counts["closed_two"] * CLOSED_TWO

        threat_values.sort(reverse=True)
        main = threat_values[0]
        secondary = threat_values[1] if len(threat_values) > 1 else 0
        pattern_sum = sum(threat_values[2:]) + counts["closed_three"] * CLOSED_THREE + counts["closed_two"] * CLOSED_TWO
        return int(main + secondary * 0.35 + pattern_sum * 0.15)

    def _pattern_score(self, board, color):
        counts = self.patterns.analyze_board(board, color)
        weighted = self._threat_weighted_score(counts)
        sum_score = (
            counts["five"] * FIVE_OR_MORE
            + counts["open_four"] * OPEN_FOUR
            + counts["closed_four"] * CLOSED_FOUR
            + counts["broken_four"] * CLOSED_FOUR
            + counts["open_three"] * OPEN_THREE
            + counts["broken_open_three"] * BROKEN_OPEN_THREE
            + counts["closed_three"] * CLOSED_THREE
            + counts["open_two"] * OPEN_TWO
            + counts["closed_two"] * CLOSED_TWO
        )
        if ENABLE_LEAF_NEXT_THREAT and self.strategy_weights.leaf_next_threat_weight > 0:
            next_threat = self.evaluate_next_threat_potential(board, color)
            opp_next_threat = self.evaluate_next_threat_potential(board, opponent(color))
            leaf_my = next_threat * self.strategy_weights.leaf_my_factor()
            leaf_opp = opp_next_threat * self.strategy_weights.leaf_opponent_factor()
        else:
            leaf_my = 0
            leaf_opp = 0
        return int(weighted + sum_score * 0.2 + leaf_my - leaf_opp)

    def evaluate_next_threat_potential(self, board, color, deadline=None):
        summary = self._future_threat_summary(board, color, limit=8, deadline=deadline)
        return (
            summary["four_three"] * 500_000
            + summary["open_four"] * 600_000
            + summary["legal_double_three"] * 250_000
        )

    def _count_future_pattern_moves(self, board, color, pattern_type, radius=2, limit=12, deadline=None):
        count = 0
        for r, c in self._ordered_future_candidates(board, color, radius=radius, limit=limit):
            if deadline is not None and time.time() >= deadline:
                break
            counts = self.patterns.analyze_move(board, r, c, color)
            if pattern_type == "open_four" and counts["open_four"]:
                count += 1
            elif pattern_type == "legal_double_three_threat" and counts["legal_double_three_threat"]:
                count += 1
        return count

    def _ordered_future_candidates(self, board, color, radius=2, limit=12):
        legal_moves = [
            move
            for move in self._nearby_moves(board, radius=radius)
            if self.rules.is_legal_move(board, move[0], move[1], color)
        ]
        scored = [
            (self._quick_future_order_score(board, r, c, color), r, c)
            for r, c in legal_moves
        ]
        scored.sort(reverse=True)
        return [(r, c) for _, r, c in scored[:limit]]

    def _quick_future_order_score(self, board, r, c, color):
        counts = self.patterns.analyze_move(board, r, c, color)
        center_bonus = 40 - (abs(r - 9) + abs(c - 9))
        return (
            counts["five"] * FIVE_OR_MORE
            + counts["four_three"] * FOUR_THREE
            + counts["open_four"] * OPEN_FOUR
            + counts["legal_double_three_threat"] * LEGAL_DOUBLE_THREE_THREAT
            + counts["closed_four"] * CLOSED_FOUR
            + counts["broken_four"] * CLOSED_FOUR
            + counts["open_three"] * OPEN_THREE
            + counts["broken_open_three"] * BROKEN_OPEN_THREE
            + center_bonus
        )

    def _count_immediate_wins(self, board, color, limit=3, deadline=None):
        wins = 0
        for r, c in self._nearby_moves(board, radius=4):
            if deadline is not None and time.time() >= deadline:
                break
            if not self.rules.is_legal_move(board, r, c, color):
                continue
            board.place(r, c, color)
            try:
                if self.rules.check_win(board, r, c, color):
                    wins += 1
                    if wins >= limit:
                        return wins
            finally:
                board.undo(r, c)
        return wins

    def _nearby_moves(self, board, radius=2):
        stones = [(r, c) for r, c, _ in board.occupied_cells()]
        if not stones:
            return [(9, 9)] if board.is_empty(9, 9) else list(board.legal_empty_cells())
        moves = set()
        for r, c in stones:
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board.is_empty(nr, nc):
                        moves.add((nr, nc))
        return sorted(moves, key=lambda pos: (abs(pos[0] - 9) + abs(pos[1] - 9), pos[0], pos[1]))

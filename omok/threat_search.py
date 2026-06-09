from __future__ import annotations

import time

from .constants import opponent
from .move_generator import MoveGenerator
from .patterns import PatternAnalyzer
from .rules import RuleEngine


class ThreatSearch:
    def __init__(self, allow_double_four=False):
        self.allow_double_four = allow_double_four
        self.generator = MoveGenerator(allow_double_four=allow_double_four)
        self.rules = RuleEngine(allow_double_four=allow_double_four)
        self.patterns = PatternAnalyzer()

    def set_allow_double_four(self, allow):
        self.allow_double_four = allow
        self.generator.set_allow_double_four(allow)
        self.rules.allow_double_four = allow

    def find_forcing_attack(self, board, color, deadline):
        if time.time() >= deadline:
            return None
        immediate = self.generator.find_immediate_wins(board, color, deadline=deadline)
        immediate = immediate[0] if immediate else None
        if immediate:
            return immediate

        threat_moves = self.generator.generate_tactical_moves(
            board,
            color,
            include_future_setup=False,
            deadline=deadline,
        )
        if not threat_moves:
            threat_moves = self.generator.generate_search_candidates(
                board,
                color,
                max_moves=12,
                include_future_setup=False,
                deadline=deadline,
            )
        for move in threat_moves[:18]:
            if time.time() >= deadline:
                raise TimeoutError
            if self._creates_strong_threat(board, move, color):
                if not self._opponent_has_sufficient_defense(board, move, color, deadline):
                    return move
        return None

    def find_forcing_defense(self, board, color, deadline):
        opp = opponent(color)
        try:
            defense = self.find_opponent_forcing_attack(board, opp, color, deadline, max_depth=4)
        except TimeoutError:
            return None
        if defense:
            return defense
        try:
            attack = self.find_forcing_attack(board, opp, deadline)
        except TimeoutError:
            return None
        if attack and self.rules.is_legal_move(board, attack[0], attack[1], color):
            return attack
        return None

    def find_opponent_forcing_attack(self, board, opponent_color, defender_color, deadline, max_depth=6):
        attack = self._find_forcing_sequence(
            board,
            attacker=opponent_color,
            defender=defender_color,
            deadline=deadline,
            depth=max_depth,
        )
        if not attack:
            return None
        if self.rules.is_legal_move(board, attack[0], attack[1], defender_color):
            return attack

        board.place(attack[0], attack[1], opponent_color)
        try:
            replies = self._direct_defense_replies(board, opponent_color, defender_color)
        finally:
            board.undo(attack[0], attack[1])
        return replies[0] if replies else None

    def _find_forcing_sequence(self, board, attacker, defender, deadline, depth):
        if time.time() >= deadline or depth <= 0:
            return None

        immediate = self.generator.find_immediate_wins(board, attacker, deadline=deadline)
        immediate = immediate[0] if immediate else None
        if immediate:
            return immediate

        for attack in self._attacking_moves(board, attacker, deadline=deadline):
            if time.time() >= deadline:
                return None
            r, c = attack
            if not self.rules.is_legal_move(board, r, c, attacker):
                continue
            board.place(r, c, attacker)
            try:
                if self.rules.check_win(board, r, c, attacker):
                    return attack
                if not self._creates_strong_threat_after_place(board, r, c, attacker):
                    continue
                if self.generator.has_unblockable_open_four(board, attacker, defender):
                    return attack

                replies = self._direct_defense_replies(board, attacker, defender, deadline=deadline)
                if not replies:
                    return attack

                all_replies_fail = True
                for reply in replies[:8]:
                    if time.time() >= deadline:
                        return None
                    rr, rc = reply
                    board.place(rr, rc, defender)
                    try:
                        if self.rules.check_win(board, rr, rc, defender):
                            all_replies_fail = False
                            break
                        if self._find_forcing_sequence(board, attacker, defender, deadline, depth - 2) is None:
                            all_replies_fail = False
                            break
                    finally:
                        board.undo(rr, rc)
                if all_replies_fail:
                    return attack
            finally:
                board.undo(r, c)
        return None

    def _attacking_moves(self, board, attacker, deadline=None):
        tactics = self.generator.classify_tactical_moves(board, attacker, deadline=deadline)
        ordered_groups = (
            tactics["immediate_win"],
            tactics["open_four"],
            tactics["four_three"],
            tactics["legal_double_three_threat"],
            tactics["closed_four"],
            tactics["open_three"],
            tactics["broken_open_three"],
        )
        moves = []
        seen = set()
        for group in ordered_groups:
            for move in group:
                if deadline is not None and time.time() >= deadline:
                    break
                if move not in seen:
                    seen.add(move)
                    moves.append(move)
        return moves[:14]

    def _direct_defense_replies(self, board, attacker, defender, deadline=None):
        replies = []
        seen = set()

        for move in self.generator.find_immediate_wins(board, attacker, deadline=deadline):
            if deadline is not None and time.time() >= deadline:
                break
            if move not in seen and self.rules.is_legal_move(board, move[0], move[1], defender):
                seen.add(move)
                replies.append(move)

        for move in self.generator.get_defense_points_for_threats(board, attacker, defender, deadline=deadline):
            if deadline is not None and time.time() >= deadline:
                break
            if move not in seen and self.rules.is_legal_move(board, move[0], move[1], defender):
                seen.add(move)
                replies.append(move)

        return replies[:10]

    def _creates_strong_threat(self, board, move, color):
        r, c = move
        if not self.rules.is_legal_move(board, r, c, color):
            return False
        board.place(r, c, color)
        try:
            if self.rules.check_win(board, r, c, color):
                return True
            counts = self.patterns.analyze_move(board, r, c, color)
            fours = counts["open_four"] + counts["closed_four"] + counts["broken_four"]
            threes = counts["open_three"] + counts["broken_open_three"]
            return fours >= 1 or threes >= 2
        finally:
            board.undo(r, c)

    def _creates_strong_threat_after_place(self, board, r, c, color):
        if self.rules.check_win(board, r, c, color):
            return True
        counts = self.patterns.analyze_move(board, r, c, color)
        fours = counts["open_four"] + counts["closed_four"] + counts["broken_four"]
        threes = counts["open_three"] + counts["broken_open_three"]
        return (
            counts["open_four"] > 0
            or counts["four_three"] > 0
            or counts["legal_double_three_threat"] > 0
            or fours >= 1
            or threes >= 2
        )

    def _opponent_has_sufficient_defense(self, board, move, color, deadline):
        r, c = move
        board.place(r, c, color)
        try:
            opp = opponent(color)
            defensive_moves = self._defensive_replies(board, color, opp, deadline=deadline)
            if not defensive_moves:
                return False
            for reply in defensive_moves:
                if time.time() >= deadline:
                    raise TimeoutError
                rr, rc = reply
                board.place(rr, rc, opp)
                try:
                    if self.generator.find_immediate_win(board, color) is None:
                        return True
                finally:
                    board.undo(rr, rc)
            return False
        finally:
            board.undo(r, c)

    def _defensive_replies(self, board, attacker, defender, deadline=None):
        wins = self.generator.find_immediate_wins(board, attacker, deadline=deadline)
        winning = wins[0] if wins else None
        if winning:
            return [winning] if self.rules.is_legal_move(board, winning[0], winning[1], defender) else []
        return self._direct_defense_replies(board, attacker, defender, deadline=deadline)

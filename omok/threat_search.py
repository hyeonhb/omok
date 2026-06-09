from __future__ import annotations

import time
from dataclasses import dataclass

from .constants import opponent
from .move_generator import MoveGenerator
from .patterns import PatternAnalyzer
from .rules import RuleEngine


@dataclass
class ThreatSearchResult:
    move: tuple[int, int] | None
    proven: bool
    reason: str
    depth: int


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
        result = self.find_forced_win(board, color, opponent(color), deadline, max_depth=6)
        return result.move if result.proven else None

    def find_forcing_defense(self, board, color, deadline):
        opp = opponent(color)
        result = self.find_forced_defense(board, opp, color, deadline, max_depth=6)
        return result.move if result.proven else None

    def find_forced_win(self, board, attacker_color, defender_color, deadline, max_depth=8):
        if time.time() >= deadline:
            return ThreatSearchResult(None, False, "timeout", 0)

        for move in self.generate_forcing_attack_moves(board, attacker_color, deadline=deadline)[:12]:
            if time.time() >= deadline:
                return ThreatSearchResult(None, False, "timeout", max_depth)
            r, c = move
            if not self.rules.is_legal_move(board, r, c, attacker_color):
                continue
            board.place(r, c, attacker_color)
            try:
                if self.rules.check_win(board, r, c, attacker_color):
                    return ThreatSearchResult(move, True, "immediate_win", max_depth)
                if not self._creates_strong_threat_after_place(board, r, c, attacker_color):
                    continue
                if self.generator.has_unblockable_open_four(board, attacker_color, defender_color):
                    return ThreatSearchResult(move, True, "open_four_forced", max_depth)

                defenses = self.generate_forced_defense_moves(
                    board,
                    attacker_color,
                    defender_color,
                    move,
                    deadline=deadline,
                )
                if not defenses:
                    return ThreatSearchResult(move, True, "no_defense", max_depth)

                all_defenses_fail = True
                for defense in defenses[:8]:
                    if time.time() >= deadline:
                        return ThreatSearchResult(None, False, "timeout", max_depth)
                    dr, dc = defense
                    board.place(dr, dc, defender_color)
                    try:
                        if self.rules.check_win(board, dr, dc, defender_color):
                            all_defenses_fail = False
                            break
                        if not self._prove_forced_win(
                            board,
                            attacker_color,
                            defender_color,
                            max_depth - 2,
                            deadline,
                        ):
                            all_defenses_fail = False
                            break
                    finally:
                        board.undo(dr, dc)
                if all_defenses_fail:
                    return ThreatSearchResult(move, True, "all_defenses_fail", max_depth)
            finally:
                board.undo(r, c)
        return ThreatSearchResult(None, False, "not_found", max_depth)

    def find_forced_defense(self, board, attacker_color, defender_color, deadline, max_depth=8):
        result = self.find_forced_win(board, attacker_color, defender_color, deadline, max_depth=max_depth)
        if not result.proven or result.move is None:
            return ThreatSearchResult(None, False, result.reason, result.depth)

        attack = result.move
        if self.rules.is_legal_move(board, attack[0], attack[1], defender_color):
            return ThreatSearchResult(attack, True, result.reason, result.depth)

        board.place(attack[0], attack[1], attacker_color)
        try:
            defenses = self.generate_forced_defense_moves(
                board,
                attacker_color,
                defender_color,
                attack,
                deadline=deadline,
            )
        finally:
            board.undo(attack[0], attack[1])
        return ThreatSearchResult(defenses[0] if defenses else None, bool(defenses), result.reason, result.depth)

    def find_opponent_forcing_attack(self, board, opponent_color, defender_color, deadline, max_depth=6):
        result = self.find_forced_defense(
            board,
            attacker_color=opponent_color,
            defender_color=defender_color,
            deadline=deadline,
            max_depth=max_depth,
        )
        return result.move if result.proven else None

    def generate_forcing_attack_moves(self, board, color, deadline=None):
        tactics = self.generator.classify_tactical_moves(board, color, deadline=deadline)
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
                    return moves
                if move in seen:
                    continue
                if self.rules.is_legal_move(board, move[0], move[1], color):
                    seen.add(move)
                    moves.append(move)
        return moves[:14]

    def generate_forced_defense_moves(self, board, attacker_color, defender_color, attack_move, deadline=None):
        replies = []
        seen = set()
        for move in self.generator.find_immediate_wins(board, attacker_color, deadline=deadline):
            if deadline is not None and time.time() >= deadline:
                return replies
            if move not in seen and self.rules.is_legal_move(board, move[0], move[1], defender_color):
                seen.add(move)
                replies.append(move)
        for move in self.generator.get_defense_points_for_threats(
            board,
            attacker_color,
            defender_color,
            deadline=deadline,
        ):
            if deadline is not None and time.time() >= deadline:
                return replies
            if move not in seen and self.rules.is_legal_move(board, move[0], move[1], defender_color):
                seen.add(move)
                replies.append(move)
        return replies[:10]

    def _prove_forced_win(self, board, attacker, defender, depth, deadline):
        if time.time() >= deadline or depth <= 0:
            return False
        if self.generator.find_immediate_wins(board, attacker, deadline=deadline):
            return True
        for attack in self.generate_forcing_attack_moves(board, attacker, deadline=deadline)[:10]:
            if time.time() >= deadline:
                return False
            r, c = attack
            if not self.rules.is_legal_move(board, r, c, attacker):
                continue
            board.place(r, c, attacker)
            try:
                if self.rules.check_win(board, r, c, attacker):
                    return True
                if not self._creates_strong_threat_after_place(board, r, c, attacker):
                    continue
                defenses = self.generate_forced_defense_moves(board, attacker, defender, attack, deadline=deadline)
                if not defenses:
                    return True
                all_defenses_fail = True
                for defense in defenses[:8]:
                    if time.time() >= deadline:
                        return False
                    dr, dc = defense
                    board.place(dr, dc, defender)
                    try:
                        if self.rules.check_win(board, dr, dc, defender):
                            all_defenses_fail = False
                            break
                        if not self._prove_forced_win(board, attacker, defender, depth - 2, deadline):
                            all_defenses_fail = False
                            break
                    finally:
                        board.undo(dr, dc)
                if all_defenses_fail:
                    return True
            finally:
                board.undo(r, c)
        return False

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

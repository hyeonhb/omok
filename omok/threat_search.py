from __future__ import annotations

import time

from .constants import opponent
from .move_generator import MoveGenerator
from .patterns import PatternAnalyzer
from .rules import RuleEngine


class ThreatSearch:
    def __init__(self):
        self.generator = MoveGenerator()
        self.rules = RuleEngine()
        self.patterns = PatternAnalyzer()

    def find_forcing_attack(self, board, color, deadline):
        if time.time() >= deadline:
            return None
        immediate = self.generator.find_immediate_win(board, color)
        if immediate:
            return immediate

        threat_moves = self.generator.generate_tactical_moves(board, color, include_future_setup=False)
        if not threat_moves:
            threat_moves = self.generator.generate_search_candidates(
                board, color, max_moves=12, include_future_setup=False
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
        attack = self.find_forcing_attack(board, opp, deadline)
        if attack and self.rules.is_legal_move(board, attack[0], attack[1], color):
            return attack
        return None

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

    def _opponent_has_sufficient_defense(self, board, move, color, deadline):
        r, c = move
        board.place(r, c, color)
        try:
            opp = opponent(color)
            defensive_moves = self._defensive_replies(board, color, opp)
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

    def _defensive_replies(self, board, attacker, defender):
        winning = self.generator.find_immediate_win(board, attacker)
        if winning:
            return [winning] if self.rules.is_legal_move(board, winning[0], winning[1], defender) else []
        replies = []
        for move in self.generator.generate_search_candidates(
            board, defender, max_moves=16, include_future_setup=False
        ):
            r, c = move
            board.place(r, c, defender)
            try:
                if self.generator.find_immediate_win(board, attacker) is None:
                    replies.append(move)
            finally:
                board.undo(r, c)
        return replies

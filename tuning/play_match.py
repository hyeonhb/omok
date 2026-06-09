from __future__ import annotations

import random
import time
from typing import Any

from omok.ai import OmokAI
from omok.constants import BLACK, BOARD_SIZE, WHITE, opponent, to_internal
from omok.rules import RuleEngine


DEFAULT_MAX_MOVES = BOARD_SIZE * BOARD_SIZE
CENTER_EXTERNAL = (10, 10)


def random_blocked_cells(rng: random.Random, count: int = 3) -> list[tuple[int, int]]:
    candidates = [
        (row, col)
        for row in range(1, BOARD_SIZE + 1)
        for col in range(1, BOARD_SIZE + 1)
        if (row, col) != CENTER_EXTERNAL
    ]
    return rng.sample(candidates, count)


def _configure_players(
    black_ai: OmokAI,
    white_ai: OmokAI,
    blocked_cells: list[tuple[int, int]],
    allow_double_four: bool,
) -> None:
    black_ai.set_blocked_cells(blocked_cells)
    white_ai.set_blocked_cells(blocked_cells)
    black_ai.set_allow_double_four(allow_double_four)
    white_ai.set_allow_double_four(allow_double_four)


def _winner_label(color: int, black_label: str, white_label: str) -> str:
    if color == BLACK:
        return black_label
    return white_label


def _color_name(color: int) -> str:
    return "black" if color == BLACK else "white"


def play_match(
    black_ai: OmokAI,
    white_ai: OmokAI,
    black_label: str,
    white_label: str,
    blocked_cells: list[tuple[int, int]] | None = None,
    allow_double_four: bool = False,
    max_moves: int = DEFAULT_MAX_MOVES,
    move_timeout: float = 3.0,
) -> dict[str, Any]:
    if blocked_cells is None:
        blocked_cells = []
    _configure_players(black_ai, white_ai, blocked_cells, allow_double_four)
    rules = RuleEngine(allow_double_four=allow_double_four)

    moves: list[dict[str, Any]] = []
    move_times: list[float] = []
    current_color = BLACK
    illegal_move = False
    timeout = False
    winner: str | None = None
    winner_color: str | None = None

    def record_result(color: int) -> None:
        nonlocal winner, winner_color
        winner = _winner_label(color, black_label, white_label)
        winner_color = _color_name(color)

    def fail_current_player(reason: str) -> None:
        nonlocal illegal_move, timeout, winner, winner_color
        if reason == "illegal":
            illegal_move = True
        elif reason == "timeout":
            timeout = True
        winner = _winner_label(opponent(current_color), black_label, white_label)
        winner_color = _color_name(opponent(current_color))

    while len(moves) < max_moves:
        active_ai = black_ai if current_color == BLACK else white_ai
        start = time.time()
        try:
            move = active_ai.choose_move()
        except Exception:
            fail_current_player("illegal")
            break
        elapsed = time.time() - start
        move_times.append(elapsed)

        if elapsed > move_timeout:
            fail_current_player("timeout")
            break

        r, c = to_internal(move)
        moves.append(
            {
                "color": _color_name(current_color),
                "move": move,
                "elapsed": round(elapsed, 4),
                "player": black_label if current_color == BLACK else white_label,
            }
        )

        if rules.check_win(active_ai.board, r, c, current_color):
            record_result(current_color)
            break

        if current_color == BLACK:
            white_ai.notify_opponent_move(*move)
        else:
            black_ai.notify_opponent_move(*move)

        current_color = opponent(current_color)

    if winner is None:
        winner = "draw"
        winner_color = None

    candidate_color = "black" if black_label == "candidate" else "white"
    elapsed_max = max(move_times) if move_times else 0.0
    elapsed_avg = sum(move_times) / len(move_times) if move_times else 0.0

    return {
        "winner": winner,
        "winner_color": winner_color,
        "moves": moves,
        "candidate_color": candidate_color,
        "elapsed_max": round(elapsed_max, 4),
        "elapsed_avg": round(elapsed_avg, 4),
        "max_move_time": round(elapsed_max, 4),
        "avg_move_time": round(elapsed_avg, 4),
        "illegal_move": illegal_move,
        "timeout": timeout,
        "blocked_cells": blocked_cells,
        "move_count": len(moves),
    }

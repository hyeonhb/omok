from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.baseline import BaselineOmokAI
from engines.current import CurrentOmokAI
from omok.constants import BLACK, WHITE
from omok.strategy_weights import StrategyWeights
from tuning.play_match import play_match, random_blocked_cells


RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEFAULT_CSV_NAME = "weight_tuning_results.csv"
DEFAULT_BEST_NAME = "best_weights.json"
CSV_PATH = RESULTS_DIR / DEFAULT_CSV_NAME
BEST_PATH = RESULTS_DIR / DEFAULT_BEST_NAME

SEARCH_SPACE = {
    "black_initiative_weight": [1.05, 1.15, 1.25],
    "black_blocking_weight": [0.75, 0.85, 0.95],
    "white_initiative_weight": [0.90, 1.00, 1.10],
    "white_blocking_weight": [1.05, 1.15, 1.25],
    "opponent_reply_penalty_weight": [0.8, 1.0, 1.2],
    "leaf_next_threat_weight": [0.0, 0.05, 0.10],
}


def _all_combinations() -> list[dict[str, float]]:
    keys = list(SEARCH_SPACE.keys())
    combos: list[dict[str, float]] = []

    def build(index: int, current: dict[str, float]) -> None:
        if index == len(keys):
            combos.append(dict(current))
            return
        key = keys[index]
        for value in SEARCH_SPACE[key]:
            current[key] = value
            build(index + 1, current)

    build(0, {})
    return combos


def sample_configs(rng: random.Random, samples: int) -> list[StrategyWeights]:
    combos = _all_combinations()
    if samples >= len(combos):
        selected = combos
    else:
        selected = rng.sample(combos, samples)

    configs: list[StrategyWeights] = []
    for values in selected:
        configs.append(
            StrategyWeights(
                black_initiative_weight=values["black_initiative_weight"],
                black_blocking_weight=values["black_blocking_weight"],
                white_initiative_weight=values["white_initiative_weight"],
                white_blocking_weight=values["white_blocking_weight"],
                opponent_reply_penalty_weight=values["opponent_reply_penalty_weight"],
                future_43_weight=1.0,
                resilient_future_weight=1.0,
                plan_candidate_weight=1.0,
                leaf_next_threat_weight=values["leaf_next_threat_weight"],
            )
        )
    return configs


def resolve_output_paths(output_prefix: str | None = None) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if output_prefix:
        return (
            RESULTS_DIR / f"{output_prefix}_results.csv",
            RESULTS_DIR / f"{output_prefix}_best_weights.json",
        )
    return CSV_PATH, BEST_PATH


def load_configs_from_file(path: Path) -> list[tuple[str, StrategyWeights]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data if isinstance(data, list) else [data]

    configs: list[tuple[str, StrategyWeights]] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Config entry at index {index - 1} must be an object")
        if "weights" not in entry:
            raise ValueError(f"Config entry {entry.get('config_id', index)} is missing 'weights'")
        config_id = entry.get("config_id") or f"cfg_{index:03d}"
        configs.append((config_id, StrategyWeights.from_dict(entry["weights"])))
    return configs


def game_seed(base_seed: int, config_index: int, game_index: int) -> int:
    return base_seed * 1_000_000 + config_index * 10_000 + game_index


def _build_game_tasks(
    weights: StrategyWeights,
    config_index: int,
    base_seed: int,
    games_per_color: int,
    allow_double_four: bool,
    move_timeout: float,
    ai_time_limit: float,
    max_moves: int,
) -> list[dict]:
    tasks = []
    matchups = (
        [(BLACK, "candidate", "baseline")] * games_per_color
        + [(WHITE, "baseline", "candidate")] * games_per_color
    )
    for game_index, (candidate_color, black_label, white_label) in enumerate(matchups):
        tasks.append(
            {
                "game_index": game_index,
                "game_seed": game_seed(base_seed, config_index, game_index),
                "candidate_color": candidate_color,
                "black_label": black_label,
                "white_label": white_label,
                "weights": weights.to_dict(),
                "allow_double_four": allow_double_four,
                "move_timeout": move_timeout,
                "ai_time_limit": ai_time_limit,
                "max_moves": max_moves,
            }
        )
    return tasks


def _run_single_game(task: dict) -> dict:
    weights = StrategyWeights.from_dict(task["weights"])
    candidate_color = task["candidate_color"]
    blocked_cells = random_blocked_cells(random.Random(task["game_seed"]))

    if candidate_color == BLACK:
        black_ai = CurrentOmokAI(color=BLACK, strategy_weights=weights, time_limit=task["ai_time_limit"])
        white_ai = BaselineOmokAI(color=WHITE, time_limit=task["ai_time_limit"])
    else:
        black_ai = BaselineOmokAI(color=BLACK, time_limit=task["ai_time_limit"])
        white_ai = CurrentOmokAI(color=WHITE, strategy_weights=weights, time_limit=task["ai_time_limit"])

    result = play_match(
        black_ai=black_ai,
        white_ai=white_ai,
        black_label=task["black_label"],
        white_label=task["white_label"],
        blocked_cells=blocked_cells,
        allow_double_four=task["allow_double_four"],
        move_timeout=task["move_timeout"],
        max_moves=task["max_moves"],
    )
    return {
        "game_index": task["game_index"],
        "winner": result["winner"],
        "winner_color": result["winner_color"],
        "timeout": result["timeout"],
        "illegal_move": result["illegal_move"],
        "max_move_time": result["max_move_time"],
    }


def _aggregate_game_results(game_results: list[dict], games_per_color: int) -> dict:
    wins = 0
    black_wins = 0
    white_wins = 0
    draws = 0
    timeouts = 0
    illegals = 0
    move_times: list[float] = []

    for result in sorted(game_results, key=lambda row: row["game_index"]):
        if result["timeout"]:
            timeouts += 1
        if result["illegal_move"]:
            illegals += 1
        move_times.append(result["max_move_time"])

        if result["winner"] == "candidate":
            wins += 1
            if result["winner_color"] == "black":
                black_wins += 1
            elif result["winner_color"] == "white":
                white_wins += 1
        elif result["winner"] == "draw":
            draws += 1

    total_games = games_per_color * 2
    overall_win_rate = wins / total_games if total_games else 0.0
    black_win_rate = black_wins / games_per_color if games_per_color else 0.0
    white_win_rate = white_wins / games_per_color if games_per_color else 0.0
    draw_rate = draws / total_games if total_games else 0.0
    avg_time = sum(move_times) / len(move_times) if move_times else 0.0
    max_time = max(move_times) if move_times else 0.0

    color_balance_penalty = abs(black_win_rate - white_win_rate) * 0.15
    timeout_penalty = timeouts * 0.10
    illegal_penalty = illegals * 0.20
    score = overall_win_rate - color_balance_penalty - timeout_penalty - illegal_penalty

    return {
        "overall_win_rate": round(overall_win_rate, 4),
        "black_win_rate": round(black_win_rate, 4),
        "white_win_rate": round(white_win_rate, 4),
        "draw_rate": round(draw_rate, 4),
        "avg_time": round(avg_time, 4),
        "max_time": round(max_time, 4),
        "timeout_count": timeouts,
        "illegal_count": illegals,
        "score": round(score, 4),
    }


def evaluate_config(
    config_id: str,
    weights: StrategyWeights,
    config_index: int,
    base_seed: int,
    games_per_color: int,
    allow_double_four: bool,
    move_timeout: float,
    ai_time_limit: float,
    max_moves: int,
    workers: int = 1,
) -> dict:
    tasks = _build_game_tasks(
        weights=weights,
        config_index=config_index,
        base_seed=base_seed,
        games_per_color=games_per_color,
        allow_double_four=allow_double_four,
        move_timeout=move_timeout,
        ai_time_limit=ai_time_limit,
        max_moves=max_moves,
    )

    if workers <= 1:
        game_results = [_run_single_game(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            game_results = list(executor.map(_run_single_game, tasks))

    stats = _aggregate_game_results(game_results, games_per_color)
    row = {
        "config_id": config_id,
        **stats,
        **weights.to_dict(),
    }
    return row


def save_csv(rows: list[dict], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_best(best_row: dict, best_path: Path) -> None:
    best_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "config_id": best_row["config_id"],
        "score": best_row["score"],
        "overall_win_rate": best_row["overall_win_rate"],
        "black_win_rate": best_row["black_win_rate"],
        "white_win_rate": best_row["white_win_rate"],
        "weights": StrategyWeights.from_dict(best_row).to_dict(),
    }
    with best_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def print_summary(rows: list[dict], best_row: dict, csv_path: Path, best_path: Path) -> None:
    print("config_id,overall_win_rate,black_win_rate,white_win_rate,draw_rate,avg_time,max_time,score")
    for row in rows:
        print(
            f"{row['config_id']},{row['overall_win_rate']:.4f},{row['black_win_rate']:.4f},"
            f"{row['white_win_rate']:.4f},{row['draw_rate']:.4f},{row['avg_time']:.4f},"
            f"{row['max_time']:.4f},{row['score']:.4f}"
        )
    print()
    print(f"Best config: {best_row['config_id']}")
    print(f"Overall win rate vs baseline: {best_row['overall_win_rate']:.4f}")
    print(f"Candidate black win rate: {best_row['black_win_rate']:.4f}")
    print(f"Candidate white win rate: {best_row['white_win_rate']:.4f}")
    print(f"Average move time: {best_row['avg_time']:.4f}s")
    print(f"Max move time: {best_row['max_time']:.4f}s")
    if best_row["timeout_count"]:
        print(f"Timeouts: {best_row['timeout_count']}")
    if best_row["illegal_count"]:
        print(f"Illegal moves: {best_row['illegal_count']}")
    print(f"Saved CSV: {csv_path}")
    print(f"Saved best weights: {best_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune Omok AI strategy weights via self-play.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--games-per-color", type=int, default=10)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument(
        "--configs-file",
        type=str,
        default=None,
        help="Evaluate only configs listed in this JSON file (list or single-object format).",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default=None,
        help="Save results to tuning/results/{prefix}_results.csv and {prefix}_best_weights.json.",
    )
    parser.add_argument("--allow-double-four", action="store_true")
    parser.add_argument("--move-timeout", type=float, default=3.0)
    parser.add_argument("--ai-time-limit", type=float, default=1.0)
    parser.add_argument("--max-moves", type=int, default=120)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel game workers (1 = sequential).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, best_path = resolve_output_paths(args.output_prefix)

    if args.configs_file:
        print(
            f"Warning: --configs-file is set; ignoring --samples {args.samples}.",
            file=sys.stderr,
        )
        config_entries = load_configs_from_file(Path(args.configs_file))
    else:
        rng = random.Random(args.seed)
        weights_list = sample_configs(rng, args.samples)
        config_entries = [(f"cfg_{index:03d}", weights) for index, weights in enumerate(weights_list, start=1)]

    rows: list[dict] = []
    for index, (config_id, weights) in enumerate(config_entries, start=1):
        print(f"Evaluating {config_id} ({index}/{len(config_entries)})...", flush=True)
        rows.append(
            evaluate_config(
                config_id=config_id,
                weights=weights,
                config_index=index,
                base_seed=args.seed,
                games_per_color=args.games_per_color,
                allow_double_four=args.allow_double_four,
                move_timeout=args.move_timeout,
                ai_time_limit=args.ai_time_limit,
                max_moves=args.max_moves,
                workers=max(1, args.workers),
            )
        )

    rows.sort(key=lambda row: row["score"], reverse=True)
    ranked_rows = []
    for rank, row in enumerate(rows, start=1):
        ranked_rows.append({"rank": rank, **row})

    best_row = ranked_rows[0]
    save_csv(ranked_rows, csv_path)
    save_best(best_row, best_path)
    print_summary(rows, best_row, csv_path, best_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

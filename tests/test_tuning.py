import json
import random
import sys
import time
from pathlib import Path

from engines.baseline import BaselineOmokAI
from engines.current import CurrentOmokAI
from omok.constants import BLACK, WHITE
from omok.strategy_weights import StrategyWeights
from tuning import tune_weights
from tuning.play_match import play_match, random_blocked_cells
from tuning.tune_weights import evaluate_config, load_configs_from_file, resolve_output_paths, sample_configs


def test_baseline_uses_frozen_package_not_current_omok():
    from omok.ai import OmokAI as CurrentOmokAIClass

    assert BaselineOmokAI.__module__ == "engines.baseline.baseline_omok.ai"
    assert BaselineOmokAI is not CurrentOmokAIClass


def test_strategy_weights_default_is_neutral():
    weights = StrategyWeights()
    assert weights.initiative_weight_for(BLACK) == 1.0
    assert weights.blocking_weight_for(WHITE) == 1.0
    assert weights.plan_candidate_weight == 0.0
    assert weights.leaf_next_threat_weight == 0.0


def test_random_blocked_cells_exclude_center_and_are_unique():
    rng = random.Random(42)
    cells = random_blocked_cells(rng)
    assert len(cells) == 3
    assert len(set(cells)) == 3
    assert (10, 10) not in cells


def test_play_match_completes_with_candidate_black():
    blocked = [(3, 3), (10, 12), (15, 7)]
    result = play_match(
        black_ai=CurrentOmokAI(color=BLACK, time_limit=0.5),
        white_ai=BaselineOmokAI(color=WHITE, time_limit=0.5),
        black_label="candidate",
        white_label="baseline",
        blocked_cells=blocked,
        max_moves=10,
    )

    assert result["candidate_color"] == "black"
    assert result["winner"] in {"candidate", "baseline", "draw"}
    assert result["elapsed_max"] <= 3.0
    assert result["move_count"] > 0


def test_play_match_candidate_white_uses_search_path():
    result = play_match(
        black_ai=BaselineOmokAI(color=BLACK, time_limit=1.0),
        white_ai=CurrentOmokAI(color=WHITE, time_limit=1.0),
        black_label="baseline",
        white_label="candidate",
        blocked_cells=[(3, 3), (10, 12), (15, 7)],
        max_moves=12,
    )

    assert result["candidate_color"] == "white"
    assert result["winner"] in {"candidate", "baseline", "draw"}


def test_sample_configs_is_reproducible_with_seed():
    rng_a = random.Random(7)
    rng_b = random.Random(7)
    configs_a = sample_configs(rng_a, samples=5)
    configs_b = sample_configs(rng_b, samples=5)
    assert [cfg.to_dict() for cfg in configs_a] == [cfg.to_dict() for cfg in configs_b]


def test_parallel_workers_match_sequential_results():
    weights = StrategyWeights.recommended()
    common = dict(
        config_id="cfg_001",
        weights=weights,
        config_index=1,
        base_seed=99,
        games_per_color=1,
        allow_double_four=False,
        move_timeout=3.0,
        ai_time_limit=0.35,
        max_moves=10,
    )
    sequential = evaluate_config(**common, workers=1)
    parallel = evaluate_config(**common, workers=2)

    for key in (
        "overall_win_rate",
        "black_win_rate",
        "white_win_rate",
        "draw_rate",
        "timeout_count",
        "illegal_count",
        "score",
    ):
        assert sequential[key] == parallel[key]


def test_load_configs_from_file_supports_list_and_single_object(tmp_path):
    list_path = tmp_path / "list.json"
    list_path.write_text(
        json.dumps(
            [
                {"config_id": "cfg_a", "weights": StrategyWeights.baseline().to_dict()},
                {"config_id": "cfg_b", "weights": StrategyWeights.recommended().to_dict()},
            ]
        ),
        encoding="utf-8",
    )
    listed = load_configs_from_file(list_path)
    assert [config_id for config_id, _ in listed] == ["cfg_a", "cfg_b"]

    single_path = tmp_path / "single.json"
    single_path.write_text(
        json.dumps({"config_id": "best_cfg", "weights": StrategyWeights.baseline().to_dict()}),
        encoding="utf-8",
    )
    single = load_configs_from_file(single_path)
    assert single[0][0] == "best_cfg"


def test_resolve_output_paths_with_prefix():
    csv_path, best_path = resolve_output_paths("recheck_top3")
    assert csv_path.name == "recheck_top3_results.csv"
    assert best_path.name == "recheck_top3_best_weights.json"


def test_configs_file_smoke_run(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    monkeypatch.setattr(tune_weights, "RESULTS_DIR", results_dir)
    monkeypatch.setattr(tune_weights, "CSV_PATH", results_dir / "weight_tuning_results.csv")
    monkeypatch.setattr(tune_weights, "BEST_PATH", results_dir / "best_weights.json")

    configs_path = tmp_path / "configs.json"
    configs_path.write_text(
        json.dumps({"config_id": "cfg_smoke", "weights": StrategyWeights.baseline().to_dict()}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tune_weights.py",
            "--configs-file",
            str(configs_path),
            "--seed",
            "42",
            "--games-per-color",
            "1",
            "--ai-time-limit",
            "0.35",
            "--max-moves",
            "10",
            "--output-prefix",
            "smoke_configs",
        ],
    )

    assert tune_weights.main() == 0
    assert (results_dir / "smoke_configs_results.csv").exists()
    assert (results_dir / "smoke_configs_best_weights.json").exists()


def test_tune_weights_script_runs_and_writes_outputs(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    monkeypatch.setattr(tune_weights, "RESULTS_DIR", results_dir)
    monkeypatch.setattr(tune_weights, "CSV_PATH", results_dir / "weight_tuning_results.csv")
    monkeypatch.setattr(tune_weights, "BEST_PATH", results_dir / "best_weights.json")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tune_weights.py",
            "--seed",
            "42",
            "--games-per-color",
            "1",
            "--samples",
            "2",
            "--ai-time-limit",
            "0.4",
            "--max-moves",
            "12",
        ],
    )

    start = time.time()
    assert tune_weights.main() == 0
    elapsed = time.time() - start

    assert elapsed < 180
    assert (results_dir / "weight_tuning_results.csv").exists()
    best = json.loads((results_dir / "best_weights.json").read_text(encoding="utf-8"))
    assert "weights" in best
    assert "overall_win_rate" in best

import gui
from engines.baseline import BaselineOmokAI
from omok.ai import OmokAI as ExperimentalOmokAI


def test_gui_defaults_to_baseline_engine():
    gui.configure_engine("stable")
    assert gui.OmokAI is BaselineOmokAI
    assert gui.OmokAI.__module__ == "engines.baseline.baseline_omok.ai"


def test_gui_can_load_experimental_engine():
    gui.configure_engine("experimental")
    assert gui.OmokAI is ExperimentalOmokAI
    assert gui.OmokAI.__module__ == "omok.ai"
    gui.configure_engine("stable")


def test_baseline_ai_choose_move_within_three_seconds():
    import time

    from engines.baseline.baseline_omok.constants import BLACK, to_internal

    ai = BaselineOmokAI(
        color=BLACK,
        blocked_cells=[(3, 3), (10, 12), (15, 7)],
        time_limit=3.0,
    )
    start = time.time()
    move = ai.choose_move()
    assert time.time() - start < 3.0
    r, c = to_internal(move)
    assert ai.board.get(r, c) == BLACK

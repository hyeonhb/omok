from __future__ import annotations

from omok.ai import OmokAI
from omok.constants import BLACK
from omok.strategy_weights import StrategyWeights


class BaselineOmokAI(OmokAI):
    """Fixed-weight baseline opponent for self-play tuning."""

    def __init__(
        self,
        color=BLACK,
        blocked_cells=None,
        time_limit=3.0,
        allow_double_four=False,
    ):
        super().__init__(
            color=color,
            blocked_cells=blocked_cells,
            time_limit=time_limit,
            allow_double_four=allow_double_four,
            strategy_weights=StrategyWeights.baseline(),
        )

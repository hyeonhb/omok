from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class StrategyWeights:
    black_initiative_weight: float = 1.0
    black_blocking_weight: float = 1.0
    white_initiative_weight: float = 1.0
    white_blocking_weight: float = 1.0
    opponent_reply_penalty_weight: float = 1.0
    future_43_weight: float = 1.0
    resilient_future_weight: float = 1.0
    plan_candidate_weight: float = 0.0
    leaf_next_threat_weight: float = 0.0

    @classmethod
    def baseline(cls) -> StrategyWeights:
        return cls()

    @classmethod
    def recommended(cls) -> StrategyWeights:
        return cls()

    def initiative_weight_for(self, color: int) -> float:
        from .constants import BLACK

        if color == BLACK:
            return self.black_initiative_weight
        return self.white_initiative_weight

    def blocking_weight_for(self, color: int) -> float:
        from .constants import BLACK

        if color == BLACK:
            return self.black_blocking_weight
        return self.white_blocking_weight

    def leaf_my_factor(self) -> float:
        return 0.15 + self.leaf_next_threat_weight

    def leaf_opponent_factor(self) -> float:
        return 0.20 + self.leaf_next_threat_weight * 1.33

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> StrategyWeights:
        return cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})

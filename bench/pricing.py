"""USD per 1M tokens. Verify against https://www.anthropic.com/pricing before trusting cost numbers.

Cache writes are billed at 1.25x input (5-minute TTL) and 2x input (1-hour TTL).
Override or add models by dropping a `pricing.json` next to the repo root with the same shape.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float

    @property
    def cache_write_5m(self) -> float:
        return self.input * 1.25

    @property
    def cache_write_1h(self) -> float:
        return self.input * 2.0


PRICES: dict[str, Price] = {
    "claude-fable-5-2": Price(8.00, 40.00, 0.20),
    "claude-opus-5-5": Price(4.00, 20.00, 0.20),
    "claude-opus-5": Price(5.00, 25.00, 0.50),
    "claude-sonnet-5-5": Price(2.00, 10.00, 0.10),
    "claude-sonnet-5": Price(2.00, 10.00, 0.20),
    "claude-haiku-5-5": Price(0.10, 0.50, 0.01),
}

_override = Path(__file__).resolve().parent.parent / "pricing.json"
if _override.exists():
    for name, p in json.loads(_override.read_text()).items():
        PRICES[name] = Price(p["input"], p["output"], p["cache_read"])


def price_for(model: str) -> Price:
    if model not in PRICES:
        raise KeyError(f"No pricing for {model!r}; add it to bench/pricing.py or pricing.json")
    return PRICES[model]

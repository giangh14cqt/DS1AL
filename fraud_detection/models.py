from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class Transaction:
    tx_id: str
    timestamp: datetime
    account_id: str
    merchant_id: str
    amount: float
    country: str
    channel: str

@dataclass
class Decision:
    tx_id: str
    decision: str  # ALLOW_FAST | REVIEW_SLOW | BLOCK
    reason: str
    score: Optional[float] = None

@dataclass
class AccountStats:
    """
    Per-account streaming statistics used for anomaly detection.
    Using O(1) streaming updates to maintain efficiency.
    """
    n: int = 0
    ewma_mean: float = 0.0
    ewma_var: float = 0.0

    last_minute_key: Optional[int] = None
    minute_count: int = 0

    def update_amount_ewma(self, x: float, *, alpha: float) -> None:
        """Update EWMA mean/variance for transaction amounts in O(1)."""
        if not (0.0 < alpha <= 1.0):
            raise ValueError("alpha must be in (0, 1]")

        if self.n == 0:
            self.n = 1
            self.ewma_mean = x
            self.ewma_var = 0.0
            return

        self.n += 1
        prev_mean = self.ewma_mean
        self.ewma_mean = (1.0 - alpha) * self.ewma_mean + alpha * x

        diff = x - prev_mean
        self.ewma_var = (1.0 - alpha) * self.ewma_var + alpha * (diff * diff)

    def stddev(self) -> float:
        if self.n < 2:
            return 0.0
        return math.sqrt(self.ewma_var) if self.ewma_var > 0.0 else 0.0

    def update_velocity(self, ts: datetime) -> None:
        """Tracks transaction frequency per minute in O(1)."""
        minute_key = int(ts.timestamp() // 60)
        if self.last_minute_key != minute_key:
            self.last_minute_key = minute_key
            self.minute_count = 0
        self.minute_count += 1

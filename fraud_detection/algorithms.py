import sys
import heapq
from typing import Dict, List, Optional, Tuple
from .models import Transaction, Decision, AccountStats

class FraudGatekeeperSystem:
    """
    Algorithm chain (3 stages):
    A) Gatekeeper (fast filter): allow known-safe patterns in O(1).
    B) Feature aggregation (streaming): update per-account stats in O(1).
    C) Anomaly scoring: compute a statistical score in O(1) for escalated txs.
    
    Technical Justification:
    - We use Hash Maps (Python dicts) for O(1) account lookups, which is critical for
      processing thousands of transactions per second.
    - We use a Min-Heap to maintain the Top-K suspicious transactions in O(log K).
    """

    def __init__(self, cfg: dict, top_k_size: int = 5) -> None:
        self.safe_merchants = set(cfg["safe_merchants"])
        self.safe_pairs = {tuple(x) for x in cfg["safe_pairs"]}
        self.merchant_limits = dict(cfg["merchant_limits"])

        # O(1) Lookup Table for accounts
        self.accounts: Dict[str, AccountStats] = {}

        self.ewma_alpha = float(cfg["ewma_alpha"])
        self.velocity_threshold_per_minute = int(cfg["velocity_threshold_per_minute"])
        self.min_history_for_zscore = int(cfg["min_history_for_zscore"])
        self.cold_start_review_amount = float(cfg["cold_start_review_amount"])
        self.review_threshold = float(cfg["review_threshold"])
        self.block_threshold = float(cfg["block_threshold"])
        
        # O(log K) Top-K tracker (using a min-heap)
        self.top_k_size = top_k_size
        self.top_suspicious: List[Tuple[float, str]] = []

    def _get_account(self, account_id: str) -> AccountStats:
        """Retrieves account stats in O(1)."""
        st = self.accounts.get(account_id)
        if st is None:
            st = AccountStats()
            self.accounts[account_id] = st
        return st

    def gatekeeper(self, tx: Transaction) -> Tuple[bool, str]:
        """Algorithm A: Fast path check using Hash Set lookups in O(1)."""
        if (tx.account_id, tx.merchant_id) in self.safe_pairs:
            limit = self.merchant_limits.get(tx.merchant_id, float("inf"))
            if tx.amount <= limit:
                return True, "SAFE_PAIR_UNDER_LIMIT"

        if tx.merchant_id in self.safe_merchants:
            limit = self.merchant_limits.get(tx.merchant_id, float("inf"))
            if tx.amount <= limit:
                return True, "SAFE_MERCHANT_UNDER_LIMIT"

        return False, "ESCALATE"

    def update_features(self, tx: Transaction) -> AccountStats:
        """Algorithm B: Streaming feature update in O(1)."""
        st = self._get_account(tx.account_id)
        st.update_velocity(tx.timestamp)
        return st

    def update_history_amount(self, tx: Transaction, st: AccountStats) -> None:
        """Algorithm B (part 2): EWMA update in O(1)."""
        st.update_amount_ewma(tx.amount, alpha=self.ewma_alpha)

    def anomaly_score(self, tx: Transaction, st: AccountStats) -> Tuple[float, str]:
        """Algorithm C: Statistical scoring in O(1)."""
        reasons = []

        if st.n < self.min_history_for_zscore and tx.amount >= self.cold_start_review_amount:
            reasons.append(f"COLD_START_HIGH_AMOUNT({tx.amount:.2f})")
            return self.review_threshold + 1.0, "+".join(reasons)

        std = st.stddev()
        mean = st.ewma_mean

        if std <= 1e-9 or st.n < self.min_history_for_zscore:
            z = 0.0
            reasons.append("LOW_HISTORY")
        else:
            z = abs((tx.amount - mean) / std)
            reasons.append(f"Z={z:.2f}")

        velocity = st.minute_count
        if velocity > self.velocity_threshold_per_minute:
            reasons.append(f"VELOCITY_SPIKE({velocity})")

        score = z + (3.0 if velocity > self.velocity_threshold_per_minute else 0.0)
        
        # Maintain Top-K suspicious in O(log K)
        if score > 0:
            if len(self.top_suspicious) < self.top_k_size:
                heapq.heappush(self.top_suspicious, (score, tx.tx_id))
            elif score > self.top_suspicious[0][0]:
                heapq.heapreplace(self.top_suspicious, (score, tx.tx_id))
                
        return score, "+".join(reasons)

    def process(self, tx: Transaction, *, debug: bool = False) -> Decision:
        allowed_fast, reason = self.gatekeeper(tx)
        st = self.update_features(tx)

        if allowed_fast:
            self.update_history_amount(tx, st)
            return Decision(tx_id=tx.tx_id, decision="ALLOW_FAST", reason=reason)

        score, score_reason = self.anomaly_score(tx, st)
        self.update_history_amount(tx, st)

        if score >= self.block_threshold:
            decision = "BLOCK"
        elif score >= self.review_threshold:
            decision = "REVIEW_SLOW"
        else:
            decision = "ALLOW_FAST"
            score_reason = "ESCALATED_BUT_LOW_SCORE"

        return Decision(tx_id=tx.tx_id, decision=decision, reason=score_reason, score=score)

    def get_top_suspicious(self) -> List[Tuple[float, str]]:
        """Returns the Top-K suspicious transactions sorted by score descending."""
        return sorted(self.top_suspicious, key=lambda x: x[0], reverse=True)

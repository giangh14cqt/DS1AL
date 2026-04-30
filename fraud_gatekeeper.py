from __future__ import annotations

"""
Fraud Gatekeeper — final submission script (same logic as fraud_gatekeeper.py).

Run from project directory:
  python3 fraud_gatekeeper.py        # uses default CSV if present
  python3 fraud_gatekeeper.py --debug generated_transactions.csv >/dev/null   # same + DEBUG lines on stderr
  # >/dev/null hides stdout only; 2>/dev/null hides stderr (debug). Omit both to see everything.
"""

import csv
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

# --- Data shapes: one row from the CSV, the final decision, and per-account state ---

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
    """Per-account streaming statistics used for anomaly detection."""

    n: int = 0
    ewma_mean: float = 0.0
    ewma_var: float = 0.0

    last_minute_key: Optional[int] = None
    minute_count: int = 0

    def update_amount_ewma(self, x: float, *, alpha: float) -> None:
        """Update EWMA mean/variance for transaction amounts."""
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
        minute_key = int(ts.timestamp() // 60)
        if self.last_minute_key != minute_key:
            self.last_minute_key = minute_key
            self.minute_count = 0
        self.minute_count += 1

# --- Read CSV: turn each file row into a Transaction (ISO timestamp string -> datetime) ---

def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def read_transactions(csv_path: str) -> Iterable[Transaction]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"tx_id", "timestamp", "account_id", "merchant_id", "amount", "country", "channel"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must have header containing: {sorted(required)}")

        for row in reader:
            yield Transaction(
                tx_id=row["tx_id"].strip(),
                timestamp=parse_iso(row["timestamp"].strip()),
                account_id=row["account_id"].strip(),
                merchant_id=row["merchant_id"].strip(),
                amount=float(row["amount"]),
                country=row["country"].strip(),
                channel=row["channel"].strip(),
            )

# --- Core system: load rules from config.json, then run gatekeeper -> features -> anomaly score ---

class FraudGatekeeperSystem:
    """
    Algorithm chain (3 stages):
    A) Gatekeeper (fast filter): allow known-safe patterns in ~O(1)
    B) Feature aggregation (streaming): update per-account stats in O(1)
    C) Anomaly scoring: compute a statistical score in O(1) for escalated txs
    """

    def __init__(self, *, config_path: Optional[str] = None) -> None:
        script_dir = Path(__file__).resolve().parent
        cfg_path = Path(config_path) if config_path else (script_dir / "config.json")

        cfg = self._load_config(cfg_path)

        self.safe_merchants = set(cfg["safe_merchants"])
        self.safe_pairs = {tuple(x) for x in cfg["safe_pairs"]}
        self.merchant_limits = dict(cfg["merchant_limits"])

        self.accounts: Dict[str, AccountStats] = {}

        self.ewma_alpha = float(cfg["ewma_alpha"])
        self.velocity_threshold_per_minute = int(cfg["velocity_threshold_per_minute"])
        self.min_history_for_zscore = int(cfg["min_history_for_zscore"])
        self.cold_start_review_amount = float(cfg["cold_start_review_amount"])
        self.review_threshold = float(cfg["review_threshold"])
        self.block_threshold = float(cfg["block_threshold"])

    @staticmethod
    def _load_config(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(
                f"Config file not found: {path}. Expected a config.json next to the script."
            )
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        required = {
            "safe_merchants",
            "safe_pairs",
            "merchant_limits",
            "ewma_alpha",
            "velocity_threshold_per_minute",
            "min_history_for_zscore",
            "cold_start_review_amount",
            "review_threshold",
            "block_threshold",
        }
        missing = required.difference(cfg.keys())
        if missing:
            raise ValueError(f"Config missing keys: {sorted(missing)}")
        return cfg

    def _get_account(self, account_id: str) -> AccountStats:
        st = self.accounts.get(account_id)
        if st is None:
            st = AccountStats()
            self.accounts[account_id] = st
        return st

    # Algorithm A: fast path — if the transaction matches a known-safe pattern, skip heavy checks.

    def gatekeeper(self, tx: Transaction) -> Tuple[bool, str]:
        """
        Returns (allowed_fast, reason).
        """
        if (tx.account_id, tx.merchant_id) in self.safe_pairs and tx.amount <= self.merchant_limits.get(tx.merchant_id, float("inf")):
            return True, "SAFE_PAIR_UNDER_LIMIT"

        if tx.merchant_id in self.safe_merchants and tx.amount <= self.merchant_limits.get(tx.merchant_id, float("inf")):
            return True, "SAFE_MERCHANT_UNDER_LIMIT"

        return False, "ESCALATE"

    # Algorithm B (part 1): update cheap per-transaction features (here: how many txs in this minute).

    def update_features(self, tx: Transaction) -> AccountStats:
        """
        Updates (B) per-account state used later by Algorithm C.
        """
        st = self._get_account(tx.account_id)
        st.update_velocity(tx.timestamp)
        return st

    # Algorithm B (part 2): update amount history (EWMA mean/variance) after we finish scoring this row.

    def update_history_amount(self, tx: Transaction, st: AccountStats) -> None:
        """
        Updates the transaction amount history (mean/stddev) for future scoring.
        """
        st.update_amount_ewma(tx.amount, alpha=self.ewma_alpha)

    # Algorithm C: only for non-fast transactions — z-score vs EWMA + velocity spike; cold-start rule for big amounts.

    def anomaly_score(self, tx: Transaction, st: AccountStats) -> Tuple[float, str]:
        """
        Returns (score, reason).

        For the demo we combine two simple anomaly signals:
        - z-score of amount vs account historical mean/std
        - velocity spike (too many tx in a minute)
        """
        reasons = []

        # Cold start: if we don't know the account yet, still escalate big amounts.
        if st.n < self.min_history_for_zscore and tx.amount >= self.cold_start_review_amount:
            reasons.append(f"COLD_START_HIGH_AMOUNT(amount={tx.amount:.2f})")
            # Return a score that will always trigger at least REVIEW_SLOW
            return self.review_threshold + 1.0, "+".join(reasons)

        # We score based on "past behavior", so we compute stats *excluding* the current tx.
        # This keeps the anomaly signal stronger and easier to explain in the demo.
        std = st.stddev()
        mean = st.ewma_mean

        if std <= 1e-9 or st.n < self.min_history_for_zscore:
            z = 0.0
            reasons.append("LOW_HISTORY_NO_ZSCORE")
        else:
            z = abs((tx.amount - mean) / std)
            reasons.append(f"Z={z:.2f}")

        velocity = st.minute_count
        if velocity > self.velocity_threshold_per_minute:
            reasons.append(f"VELOCITY_SPIKE(count={velocity})")

        score = z + (2.0 if velocity > self.velocity_threshold_per_minute else 0.0)
        return score, "+".join(reasons)

    # Tie it together: ALLOW_FAST, REVIEW_SLOW, or BLOCK; optional DEBUG lines to stderr.

    def process(self, tx: Transaction, *, debug: bool = False) -> Decision:
        allowed_fast, reason = self.gatekeeper(tx)  # A

        st = self.update_features(tx)  # B (velocity etc.)
        if debug:
            print(
                "DEBUG\t"
                f"tx_id={tx.tx_id}\t"
                f"A.allowed_fast={allowed_fast}\tA.reason={reason}\t"
                f"B.minute_count={st.minute_count}\tB.n_amounts={st.n}\tB.ewma_mean={st.ewma_mean:.2f}\tB.ewma_std={st.stddev():.2f}",
                file=sys.stderr,
            )

        if allowed_fast:
            self.update_history_amount(tx, st)
            if debug:
                print(
                    "DEBUG\t"
                    f"tx_id={tx.tx_id}\t"
                    "C.skipped=true (fast allowed)\t"
                    f"B_after.n_amounts={st.n}\tB_after.ewma_mean={st.ewma_mean:.2f}\tB_after.ewma_std={st.stddev():.2f}",
                    file=sys.stderr,
                )
            return Decision(tx_id=tx.tx_id, decision="ALLOW_FAST", reason=reason)

        score, score_reason = self.anomaly_score(tx, st)  # C
        if debug:
            print(
                "DEBUG\t"
                f"tx_id={tx.tx_id}\t"
                f"C.score={score:.2f}\tC.reason={score_reason}\t"
                f"review_threshold={self.review_threshold:.2f}\tblock_threshold={self.block_threshold:.2f}",
                file=sys.stderr,
            )

        if score >= self.block_threshold:
            self.update_history_amount(tx, st)
            if debug:
                print(
                    "DEBUG\t"
                    f"tx_id={tx.tx_id}\t"
                    "decision=BLOCK\t"
                    f"B_after.n_amounts={st.n}\tB_after.ewma_mean={st.ewma_mean:.2f}\tB_after.ewma_std={st.stddev():.2f}",
                    file=sys.stderr,
                )
            return Decision(tx_id=tx.tx_id, decision="BLOCK", reason=score_reason, score=score)

        if score >= self.review_threshold:
            self.update_history_amount(tx, st)
            if debug:
                print(
                    "DEBUG\t"
                    f"tx_id={tx.tx_id}\t"
                    "decision=REVIEW_SLOW\t"
                    f"B_after.n_amounts={st.n}\tB_after.ewma_mean={st.ewma_mean:.2f}\tB_after.ewma_std={st.stddev():.2f}",
                    file=sys.stderr,
                )
            return Decision(tx_id=tx.tx_id, decision="REVIEW_SLOW", reason=score_reason, score=score)

        self.update_history_amount(tx, st)
        if debug:
            print(
                "DEBUG\t"
                f"tx_id={tx.tx_id}\t"
                "decision=ALLOW_FAST (low score)\t"
                f"B_after.n_amounts={st.n}\tB_after.ewma_mean={st.ewma_mean:.2f}\tB_after.ewma_std={st.stddev():.2f}",
                file=sys.stderr,
            )
        return Decision(tx_id=tx.tx_id, decision="ALLOW_FAST", reason="ESCALATED_BUT_LOW_SCORE", score=score)

# --- CLI: parse arguments, pick CSV path, run the pipeline line by line ---

def _first_existing_csv(script_dir: Path) -> Optional[Path]:
    for name in ("generated_transactions.csv",):
        p = script_dir / name
        if p.exists():
            return p
    return None


def main(argv: list[str]) -> int:
    script_dir = Path(__file__).resolve().parent

    debug = False
    args = list(argv[1:])
    if "--debug" in args:
        debug = True
        args.remove("--debug")

    if len(args) == 0:
        default_csv = _first_existing_csv(script_dir)
        if default_csv is not None:
            csv_path = str(default_csv)
            print(f"(No CSV provided; using: {csv_path})", file=sys.stderr)
        else:
            print(
                "Usage: python3 fraud_gatekeeper.py [--debug] <transactions.csv>\n"
                f"  (Or add sample_transactions.csv or generated_transactions.csv under {script_dir})",
                file=sys.stderr,
            )
            return 2
    elif len(args) == 1:
        csv_path = args[0]
    else:
        print("Usage: python3 fraud_gatekeeper.py [--debug] <transactions.csv>", file=sys.stderr)
        return 2

    system = FraudGatekeeperSystem()
    for tx in read_transactions(csv_path):
        d = system.process(tx, debug=debug)
        if d.score is None:
            print(f"{d.tx_id}\t{d.decision}\t{d.reason}")
        else:
            print(f"{d.tx_id}\t{d.decision}\t{d.reason}\tscore={d.score:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

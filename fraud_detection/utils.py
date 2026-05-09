import csv
import json
from pathlib import Path
from typing import Iterable, Optional
from datetime import datetime
from .models import Transaction

def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)

def read_transactions(csv_path: str) -> Iterable[Transaction]:
    """Reads transactions from CSV line by line to minimize memory footprint."""
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

def load_config(config_path: Optional[str] = None) -> dict:
    """Loads system configuration from JSON."""
    script_dir = Path(__file__).resolve().parent.parent
    path = Path(config_path) if config_path else (script_dir / "config.json")
    
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
        
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg

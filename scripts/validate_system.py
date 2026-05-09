import sys
import time
import csv
from pathlib import Path
from datetime import datetime

# Ensure the root directory is in the path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fraud_detection.utils import read_transactions, load_config
from fraud_detection.algorithms import FraudGatekeeperSystem
from fraud_detection.models import Transaction

def validate_system(csv_path: str):
    if not Path(csv_path).exists():
        print(f"Error: {csv_path} not found. Run generate_data.py first.")
        return

    print(f"--- Starting Validation (Input: {csv_path}) ---\n")

    cfg = load_config()
    system = FraudGatekeeperSystem(cfg)
    
    # Statistical counters
    total_tx = 0
    total_fraud = 0
    captured_blocked = 0
    captured_review = 0
    missed_fraud = 0
    false_alarms = 0
    
    total_blocked = 0

    start_time = time.perf_counter()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx = Transaction(
                tx_id=row["tx_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                account_id=row["account_id"],
                merchant_id=row["merchant_id"],
                amount=float(row["amount"]),
                country=row["country"],
                channel=row["channel"]
            )
            
            label = row.get("label", "LEGIT")
            is_fraud = label != "LEGIT"
            
            decision = system.process(tx)
            
            total_tx += 1
            if is_fraud:
                total_fraud += 1
                if decision.decision == "BLOCK":
                    captured_blocked += 1
                elif decision.decision == "REVIEW_SLOW":
                    captured_review += 1
                else:
                    missed_fraud += 1
            else:
                if decision.decision != "ALLOW_FAST":
                    false_alarms += 1
            
            if decision.decision == "BLOCK":
                total_blocked += 1

    end_time = time.perf_counter()
    duration = end_time - start_time
    
    # Metrics
    recall = (captured_blocked + captured_review) / total_fraud if total_fraud > 0 else 0.0
    precision = captured_blocked / total_blocked if total_blocked > 0 else 0.0
    latency_ms = (duration / total_tx) * 1000 if total_tx > 0 else 0.0
    throughput = total_tx / duration if duration > 0 else 0.0

    print("========================================")
    print("STATISTICAL PERFORMANCE")
    print("========================================")
    print(f"Total Transactions:  {total_tx}")
    print(f"Total Fraud Cases:   {total_fraud}")
    print(f"Captured (Blocked):  {captured_blocked}")
    print(f"Captured (Review):   {captured_review}")
    print(f"Missed Fraud:        {missed_fraud}")
    print(f"False Alarms:        {false_alarms}")
    print("----------------------------------------")
    print(f"Recall (Detection):  {recall:.2%}")
    print(f"Precision (Block):   {precision:.2%}")

    print("\n========================================")
    print("ALGORITHMIC PERFORMANCE (O(1) Check)")
    print("========================================")
    print(f"Total Time:          {duration:.4f} seconds")
    print(f"Avg Latency:         {latency_ms:.4f} ms/tx")
    print(f"Throughput:          {throughput:,.0f} tx/second")

if __name__ == "__main__":
    csv_file = "validation_data.csv"
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    validate_system(csv_file)

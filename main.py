import sys
from pathlib import Path
from fraud_detection.utils import read_transactions, load_config
from fraud_detection.algorithms import FraudGatekeeperSystem

def main(argv: list[str]) -> int:
    debug = "--debug" in argv
    args = [a for a in argv[1:] if a != "--debug"]

    if len(args) == 0:
        csv_path = "generated_transactions.csv"
        if not Path(csv_path).exists():
            print("Usage: python main.py [--debug] <transactions.csv>")
            return 2
    else:
        csv_path = args[0]

    try:
        cfg = load_config()
        system = FraudGatekeeperSystem(cfg)
        
        print(f"{'TX_ID':<10} | {'DECISION':<12} | {'REASON':<30} | {'SCORE'}")
        print("-" * 70)

        for tx in read_transactions(csv_path):
            d = system.process(tx, debug=debug)
            score_str = f"{d.score:.2f}" if d.score is not None else "N/A"
            print(f"{d.tx_id:<10} | {d.decision:<12} | {d.reason:<30} | {score_str}")

        print("\n" + "="*30)
        print("TOP 5 SUSPICIOUS TRANSACTIONS")
        print("="*30)
        for score, tx_id in system.get_top_suspicious():
            print(f"Score: {score:.2f} | ID: {tx_id}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))

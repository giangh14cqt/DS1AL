import csv
import random
from datetime import datetime, timedelta

def generate_transactions(output_path: str, target_count: int = 100000):
    merchants = ["AMAZON_US", "STARBUCKS_01", "GROCERY_99", "COFFEE_03", "FUEL_12", "NETFLIX", "APPLE_STORE", "LOCAL_BAKERY"]
    countries = ["US", "PL", "DE", "UK", "FR", "ES"]
    channels = ["ONLINE", "POS", "MOBILE"]
    
    transactions = []
    base_time = datetime(2026, 5, 1, 0, 0, 0)
    
    # We'll simulate a realistic distribution
    # ~99.5% Legit, ~0.5% Suspect/Fraud
    
    tx_counter = 100000
    
    # Track accounts to keep them consistent
    account_ids = [f"ACC_{i:05}" for i in range(2000)]
    
    print(f"Generating {target_count} transactions...")

    # For speed, we'll write directly to file instead of keeping everything in memory
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["tx_id", "timestamp", "account_id", "merchant_id", "amount", "country", "channel", "label"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        current_count = 0
        while current_count < target_count:
            # Decide scenario
            dice = random.random()
            
            # Normal Legit
            if dice < 0.995:
                acc = random.choice(account_ids)
                writer.writerow({
                    "tx_id": f"TX_{tx_counter}",
                    "timestamp": (base_time + timedelta(seconds=current_count)).isoformat(),
                    "account_id": acc,
                    "merchant_id": random.choice(merchants),
                    "amount": round(random.uniform(5, 150), 2),
                    "country": random.choice(countries),
                    "channel": random.choice(channels),
                    "label": "LEGIT"
                })
                current_count += 1
                tx_counter += 1
            
            # Velocity Spike (Fraudulent)
            elif dice < 0.998:
                acc = random.choice(account_ids)
                spike_time = base_time + timedelta(seconds=current_count)
                for _ in range(12): # 12 tx in 1 sec
                    writer.writerow({
                        "tx_id": f"TX_{tx_counter}",
                        "timestamp": spike_time.isoformat(),
                        "account_id": acc,
                        "merchant_id": "FAST_FOOD",
                        "amount": round(random.uniform(5, 20), 2),
                        "country": "US",
                        "channel": "POS",
                        "label": "SUSPICIOUS_VELOCITY"
                    })
                    current_count += 1
                    tx_counter += 1
                    if current_count >= target_count: break

            # High Amount (Fraudulent)
            else:
                acc = random.choice(account_ids)
                writer.writerow({
                    "tx_id": f"TX_{tx_counter}",
                    "timestamp": (base_time + timedelta(seconds=current_count)).isoformat(),
                    "account_id": acc,
                    "merchant_id": "LUXURY_EXCHANGE",
                    "amount": round(random.uniform(2000, 5000), 2),
                    "country": "KY",
                    "channel": "ONLINE",
                    "label": "SUSPICIOUS_AMOUNT"
                })
                current_count += 1
                tx_counter += 1

    print(f"Finished generating {target_count} transactions to {output_path}")

if __name__ == "__main__":
    import sys
    count = 100000
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    generate_transactions("validation_data.csv", count)

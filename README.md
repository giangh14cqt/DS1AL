# Fraud Gatekeeper System

A high-performance algorithmic pipeline designed to filter bank transactions at scale. This system chains multiple algorithms to provide an "instant" gatekeeper for safe transactions while escalating suspicious outliers for statistical analysis.

---
DS1AL Project

Student:
- Aldaheir Leonardo
- Truong Giang Do
---

## Project Overview
This project was designed to solve the challenge of processing thousands of transactions per second. It uses a three-stage algorithmic chain:
1.  **Gatekeeper (Filter)**: Fast $O(1)$ lookup for known-safe patterns.
2.  **Streaming Aggregator**: Maintains per-account statistics in $O(1)$ time.
3.  **Anomaly Scorer**: Computes risk scores and tracks Top-K outliers using a **Min-Heap**.

## Project Structure
```text
.
├── main.py                     # Entry point for the system
├── config.json                 # System thresholds and safe-lists
├── fraud_detection/            # Core package
│   ├── __init__.py
│   ├── algorithms.py           # Algorithmic logic (Gatekeeper, Scorer, Top-K)
│   ├── models.py               # Data structures and streaming stats
│   └── utils.py                # CSV and config utilities
├── scripts/                    # Validation & data generation tools
│   ├── generate_data.py        # Synthetic transaction generator
│   └── validate_system.py      # Statistical & performance validation
├── validation_data.csv         # Generated synthetic dataset (100k rows)
└── README.md                   # This file
```

## Installation & Usage
Requires **Python 3.7+**. No external dependencies.

### Running the system on a CSV file:
```bash
python3 main.py generated_transactions.csv
```

### Debug Mode:
```bash
python3 main.py --debug generated_transactions.csv
```

### Generate synthetic data and validate:
```bash
# Generate 100,000 synthetic transactions with labeled fraud scenarios
python3 scripts/generate_data.py 100000

# Run the full statistical and performance validation report
python3 scripts/validate_system.py
```

## Validation Results (100,000 Transactions)

The following results were produced by the validation pipeline on a synthetic dataset with a realistic fraud rate (~3.6%).

```
========================================
STATISTICAL PERFORMANCE
========================================
Total Transactions:  100,000
Total Fraud Cases:   ~3,600
Captured (Blocked):  ~190
Captured (Review):   ~2,000
Missed Fraud:        ~1,400
False Alarms:        ~5,000
----------------------------------------
Recall (Detection):  61.62%
Precision (Block):   26.83%

========================================
ALGORITHMIC PERFORMANCE (O(1) Check)
========================================
Total Time:          ~1.0 seconds
Avg Latency:         0.0100 ms/tx
Throughput:          ~99,000 tx/second
```

**Key takeaways:**
- **~99,000 tx/second** throughput validates the $O(1)$ architecture for high-speed banking environments.
- **61.62% Recall** means the system detects the majority of suspicious transactions without a trained ML model.
- The system is configurable — thresholds in `config.json` can be tuned to trade off Recall vs. False Alarms.

## Algorithmic Deep Dive

### Stage 1: Gatekeeper (Algorithm A)
- **Data Structure**: Hash Sets/Maps (`set`, `dict`).
- **Complexity**: $O(1)$.
- **Rationale**: We prioritize maximum throughput. Hash lookups allow us to bypass heavy scoring for the majority of "safe" transactions instantly. A balanced BST would only offer $O(\log N)$, which would create a bottleneck at thousands of transactions per second.

### Stage 2: Streaming Statistics (Algorithm B)
- **Data Structure**: Class-based state tracker (EWMA + velocity counter).
- **Complexity**: $O(1)$ update time.
- **Rationale**: We use Exponentially Weighted Moving Averages (EWMA) and per-minute velocity counters to track account behavior without storing the entire transaction history. Memory per account stays constant regardless of history length.

### Stage 3: Anomaly Scoring & Top-K (Algorithm C)
- **Data Structure**: Statistical Z-Score + **Min-Heap** (`heapq`).
- **Complexity**: $O(1)$ for score, $O(\log K)$ to update Top-K.
- **Rationale**: The **Min-Heap** allows us to maintain a live "Top-K Most Suspicious" list without sorting the entire dataset. Only transactions escalated by the Gatekeeper (Stage A) reach this stage.

### Data Transformation & Chaining
The system demonstrates a clear data flow where the output of one stage informs or enables the next:
1.  **Stage A → Stage C (Control Signal)**: The Gatekeeper output is a boolean flag that determines whether the compute-intensive Anomaly Scorer is invoked.
2.  **Stage B → Stage C (State Input)**: The Streaming Aggregator transforms raw transactions into a condensed `AccountStats` object (mean, variance, velocity) which serves as the primary input for Algorithm C's Z-score calculation.

## Configurable Thresholds (`config.json`)

| Parameter | Value | Description |
|---|---|---|
| `velocity_threshold_per_minute` | `5` | Transactions/minute above this trigger a velocity spike penalty |
| `review_threshold` | `2.0` | Score above this → `REVIEW_SLOW` |
| `block_threshold` | `4.0` | Score above this → `BLOCK` |
| `cold_start_review_amount` | `$400` | New accounts with amounts above this are flagged |
| `ewma_alpha` | `0.2` | Controls how fast the EWMA adapts to new amounts |

## System Bottlenecks
The primary bottleneck is **Memory usage**. Since the system maintains state for every unique account in a Hash Map, memory scales as $O(N)$ where $N$ is the number of accounts. For production use, an LRU (Least Recently Used) cache or TTL-based eviction would be required to manage RAM limits at scale.

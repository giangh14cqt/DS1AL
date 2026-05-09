# Fraud Gatekeeper System

A high-performance algorithmic pipeline designed to filter bank transactions at scale. This system chains multiple algorithms to provide an "instant" gatekeeper for safe transactions while escalating suspicious outliers for statistical analysis.

## 🚀 Project Overview
This project was designed to solve the challenge of processing thousands of transactions per second. It uses a three-stage algorithmic chain:
1.  **Gatekeeper (Filter)**: Fast $O(1)$ lookup for known-safe patterns.
2.  **Streaming Aggregator**: Maintains per-account statistics in $O(1)$ time.
3.  **Anomaly Scorer**: Computes risk scores and tracks Top-K outliers using a **Min-Heap**.

## 📂 Project Structure
```text
.
├── main.py                 # Entry point for the system
├── config.json             # System thresholds and safe-lists
├── fraud_detection/        # Core package
│   ├── __init__.py
│   ├── algorithms.py       # Algorithmic logic (Gatekeeper, Scorer, Top-K)
│   ├── models.py           # Data structures and streaming stats
│   └── utils.py            # CSV and config utilities
├── generated_transactions.csv # Sample transaction data
└── README.md               # This file
```

## 🛠️ Installation & Usage
Requires **Python 3.7+**. No external dependencies.

### Running the system:
```bash
python3 main.py generated_transactions.csv
```

### Debug Mode:
To see detailed scoring and internal state:
```bash
python3 main.py --debug generated_transactions.csv
```

## 🧠 Algorithmic Deep Dive

### Stage 1: Gatekeeper (Algorithm A)
- **Data Structure**: Hash Sets/Maps (`set`, `dict`).
- **Complexity**: $O(1)$.
- **Rationale**: We prioritize maximum throughput. Hash lookups allow us to bypass heavy scoring for ~90% of "safe" transactions instantly.

### Stage 2: Streaming Statistics (Algorithm B)
- **Data Structure**: Class-based state tracker.
- **Complexity**: $O(1)$ update time.
- **Rationale**: We use Exponentially Weighted Moving Averages (EWMA) and velocity counters to track behavior without storing the entire transaction history, keeping memory usage per account constant.

### Stage 3: Anomaly Scoring & Top-K (Algorithm C)
- **Data Structure**: Statistical Z-Score + **Min-Heap** (`heapq`).
- **Complexity**: $O(1)$ for score, $O(\log K)$ to update Top-K.
- **Rationale**: The **Min-Heap** allows us to maintain a live list of the most suspicious transactions without sorting the entire dataset.

## ⚠️ System Bottlenecks
The primary bottleneck is **Memory usage**. Since the system maintains state for every unique account in a Hash Map, memory scales as $O(N)$ where $N$ is the number of accounts. For production use, an LRU (Least Recently Used) cache or TTL-based eviction would be required to manage RAM limits.

---
*Created for the Algorithmic Systems Design project.*

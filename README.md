# Fraud Gatekeeper — student guide

This small project is a **streaming fraud-style gatekeeper**: it reads transactions from a CSV file **one row at a time** (like a live feed) and labels each one as **allow quickly**, **send to slow review**, or **block**. It is meant for learning how rules + simple statistics can work together.

You only need **Python 3** (no extra packages).

---

## What’s in this folder?

| File | What it’s for |
|------|----------------|
| **`fraud_gatekeeper.py`** | The whole program: reads the CSV, loads settings, runs the three-step logic, prints one result line per transaction. |
| **`config.json`** | The “control panel”: safe merchants, limits, and numeric thresholds. Edit this to change behavior without rewriting Python. |
| **`generated_transactions.csv`** | Example input data. You can add your own CSV as long as the columns match (see below). |
| **`README.md`** | This file — how everything fits together. |

---

## How to run it

Open a terminal in this folder (the same folder as `fraud_gatekeeper.py`), then:

```bash
python3 fraud_gatekeeper.py
```

If you don’t pass a file name, the script looks for a **default** CSV in the code (see `_first_existing_csv` near the bottom of `fraud_gatekeeper.py`). Right now that list is set up for `generated_transactions.csv` in this project.

To **choose your own file**:

```bash
python3 fraud_gatekeeper.py my_transactions.csv
```

### Debug mode (extra detail)

Add `--debug` to print extra lines to **stderr** (they start with `DEBUG`) so you can see scores, thresholds, and internal counters while you learn:

```bash
python3 fraud_gatekeeper.py --debug generated_transactions.csv
```

Normal output (one line per transaction) still goes to the usual output; debug is the “behind the scenes” channel.

---

## What your CSV must look like

The first row must be a **header** with these columns (names spelled exactly like this):

`tx_id`, `timestamp`, `account_id`, `merchant_id`, `amount`, `country`, `channel`

- **`timestamp`** should be ISO-style, e.g. `2026-04-30T12:00:00`
- **`amount`** is a number (decimals are fine)

If a column is missing, the program stops with a clear error about the header.

---

## What `config.json` does (in plain language)

Think of it as three kinds of knobs: **who we trust a bit more**, **how much they can spend there**, and **when to flag weird behavior**.

- **`safe_merchants`** — Merchant IDs we treat as “usually okay” *if* the amount is under that merchant’s limit.
- **`safe_pairs`** — Pairs `[account_id, merchant_id]` that are trusted together (again, with a limit).
- **`merchant_limits`** — Max amount for those safe paths. If a merchant isn’t listed here, the code uses a very high default for the safe checks only.
- **`ewma_alpha`** — How fast we “forget” old amounts when updating the running average for an account (between 0 and 1).
- **`velocity_threshold_per_minute`** — If an account does **more than this many transactions in the same clock minute**, we treat it as a velocity spike.
- **`min_history_for_zscore`** — How many past amounts we want before we trust a z-score style comparison.
- **`cold_start_review_amount`** — For new accounts with little history: if the amount is **this big or bigger**, we escalate to at least review.
- **`review_threshold`** / **`block_threshold`** — If the anomaly score is high enough, we output **REVIEW_SLOW** or **BLOCK**.

You can change numbers, save the file, and run again — no need to touch Python for tuning.

---

## How the program thinks (three steps)

The main class is `FraudGatekeeperSystem`. Each transaction goes through:

### Step A — Gatekeeper (fast path)

Cheap checks against `config.json`:

- Is this a **safe pair** or **safe merchant** and under the **limit**?  
  → If yes: **`ALLOW_FAST`** and we skip the heavy scoring (we still update history for next time).

If not, we **escalate** to the next steps.

### Step B — Features (streaming, per account)

For each account we keep small rolling stats:

- **How many transactions in the current minute** (velocity).
- **EWMA mean and variance** of past amounts (so we can spot unusual amounts later).

Important detail: the **current** transaction’s amount is used for scoring **before** it is folded into the EWMA, so the score is “compared to past behavior,” not to a average that already includes this row.

### Step C — Anomaly score (only if not allowed in Step A)

We combine ideas like:

- **Z-style signal**: how far is this amount from what we expect for this account?
- **Velocity**: too many txs in one minute adds to the score.

Then we compare the score to **`review_threshold`** and **`block_threshold`**:

- **`ALLOW_FAST`** — Either from the gatekeeper, or escalated but score stayed low (`ESCALATED_BUT_LOW_SCORE`).
- **`REVIEW_SLOW`** — Suspicious but not the worst case.
- **`BLOCK`** — Score crossed the block line.

Each printed line includes a **reason** string so you can see *why* the program chose that label.

---

## Tips if something breaks

- **`Config file not found`** — Put `config.json` in the **same folder** as `fraud_gatekeeper.py`, or pass a custom path if you extend the code to support that.
- **Usage message when you run with no CSV** — The default file from `_first_existing_csv` wasn’t found. Either pass the CSV path on the command line or add the file name to that tuple in the code (remember: a one-item tuple needs a comma, e.g. `("my.csv",)`).
- **Want only debug lines on screen** — You can hide normal output when debugging:  
  `python3 fraud_gatekeeper.py --debug your.csv >/dev/null`  
  (on Mac/Linux; that sends the main output away and leaves stderr, where DEBUG goes).

---

## Learning takeaway

This project shows a common pattern: **fast business rules first**, then **lightweight streaming statistics**, then **a simple score** for the cases that need a closer look — similar in spirit to real risk systems, but small enough to read in one sitting.

Good luck with your course or experiments.

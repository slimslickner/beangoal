# beangoal

Savings goals tracking for beancount v3.

Reads a beancount ledger and a goals file to track progress toward savings goals, compute available surplus, and suggest allocations.

## Prerequisites

- [mise](https://mise.jdx.dev/) — manages the Python version
- [uv](https://docs.astral.sh/uv/) — manages dependencies and the virtual environment

## Setup

```bash
# Install the correct Python version
mise install

# Install dependencies and create .venv
uv sync

# Verify the install
uv run beangoal --help
```

## Usage

All commands take `--ledger` (required) and `--goals` (defaults to `goals.beancount`) as global options, passed before the subcommand.

### Show goal progress

```bash
uv run beangoal --ledger ledger.beancount --goals goals.beancount status
```

Add `--show-archived` to include archived goals in the output.

### Show allocatable surplus

```bash
uv run beangoal --ledger ledger.beancount --goals goals.beancount surplus
```

Computes cash total minus an operating buffer (default: 3 months of average expenses). Override with `--buffer-months` and `--trailing-months`.

### Suggest an allocation

```bash
uv run beangoal --ledger ledger.beancount --goals goals.beancount allocate 2000
```

Distributes the given amount across active goals by urgency (larger gap + closer deadline = higher share). Prints a ready-to-paste beancount transaction — nothing is written to any file.

### Archive a goal

```bash
uv run beangoal --ledger ledger.beancount --goals goals.beancount archive house-down-payment
```

Prints the directive change to make in your goals file — nothing is written automatically.

## Global options

| Option | Default | Description |
|---|---|---|
| `--ledger` | required | Path to main beancount ledger |
| `--goals` | `goals.beancount` | Path to goals file |
| `--currency` | `USD` | Currency for all computations |
| `--trailing-months` | `6` | Window for average expense calculation |
| `--buffer-months` | `3` | Operating buffer multiplier |

## Goals file format

A separate beancount file using `custom` directives. Keep it alongside your main ledger and pass it via `--goals`.

```beancount
; Active savings goals: "savings-goal" <name> <target> <deadline>
2024-01-01 custom "savings-goal" "house-down-payment" "100000" "2027-06-01"
2024-01-01 custom "savings-goal" "college-fund"       "200000" "2036-09-01"

; Archived goals (hidden from status by default)
; 2024-01-01 custom "savings-goal-archived" "emergency-fund" "25000" "2023-01-01"

; Liquid accounts included in the cash pool
2024-01-01 custom "cash-account" "Assets:Checking"
2024-01-01 custom "cash-account" "Assets:Savings:HYSA"

; Account roots used to compute average monthly expenses
2024-01-01 custom "expense-accounts" "Expenses"
2024-01-01 custom "income-accounts"  "Income"

; Sub-trees excluded from the expense average (e.g. taxes, one-time transfers)
2024-01-01 custom "expense-exclude" "Expenses:Taxes"

; Which account balances count toward each goal
2024-01-01 custom "goal-account" "house-down-payment" "Assets:Savings:HYSA"
2024-01-01 custom "goal-account" "college-fund"       "Assets:Investments:529"
```

See `example/goals.beancount` for a full working example.

## Running tests

```bash
uv run pytest
```

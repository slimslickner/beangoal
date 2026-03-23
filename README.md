# beangoal

Savings goals tracking for beancount v3.

Reads a beancount ledger and a goals file to track progress toward savings goals, compute available surplus, and suggest allocations.

## How it works

All savings accounts are treated as a single **pool**. Goals draw from that pool in one of two ways:

- **Manual** — you record dated `goal-allocation` entries in your goals file. The sum of all entries for a goal is its current balance. This gives you a full history of contributions over time.
- **Auto** — goals with no allocation entries are distributed from whatever pool balance remains after manual goals are reserved. The split is weighted by urgency: closer deadline and larger remaining gap = higher share.

Nothing is ever written to your files automatically. Every command prints what to paste.

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

```
  Pool: $137,900.00

  house-down-payment     ████░░░░░░░░   37%   $    37,511 / $   100,000   auto    deadline: 2027-06-01   behind  ✗
  college-fund           ██░░░░░░░░░░   18%   $    36,000 / $   200,000   manual  deadline: 2036-09-01   on pace ✓
  car                    ████████████  429%   $    64,389 / $    15,000   auto    deadline: 2026-12-01   on pace ✓
```

Flags:
- `--show-archived` — include archived goals in a separate section
- `--show-contributions` — list each dated contribution under manual goals

```bash
uv run beangoal --ledger ledger.beancount --goals goals.beancount status --show-contributions
```

```
  college-fund           ██░░░░░░░░░░   18%   $    36,000 / $   200,000   manual  deadline: 2036-09-01   on pace ✓
    2024-06-01   +$ 10,000.00
    2024-12-01   +$  8,000.00
    2025-06-01   +$  9,000.00
    2026-01-01   +$  9,000.00
                               = $ 36,000.00
```

### Show allocatable surplus

```bash
uv run beangoal --ledger ledger.beancount --goals goals.beancount surplus
```

```
   Cash accounts total:               $137,900.00
   Avg monthly expenses:                $3,100.00     (trailing months)
   Operating buffer (3 mo):             $9,300.00

   Allocatable surplus:               $128,600.00
```

Computes pool total minus an operating buffer (default: 3 months of average expenses). Override with `--buffer-months` and `--trailing-months`.

### Suggest an allocation

```bash
uv run beangoal --ledger ledger.beancount --goals goals.beancount allocate 2000
```

```
  Suggested allocation of $2,000.00:
  ──────────────────────────────────────────────────────
  house-down-payment      $  1,739.24  (86%)   436 days left, 37% funded  [auto]
  college-fund            $    260.76  (13%)   3816 days left, 18% funded  [manual]

  Paste into your ledger:

  2026-03-22 * "Savings allocation"
    Assets:Checking                            2,000.00 USD   ; adjust destination as needed
    Assets:Checking                           -2,000.00 USD   ; adjust source as needed

  Paste into goals.beancount:

  2026-03-22 custom "goal-allocation" "house-down-payment" "1739.24"
  2026-03-22 custom "goal-allocation" "college-fund" "260.76"
```

The transaction is a template — adjust source and destination accounts as needed. The `goal-allocation` directives record how you attributed the money across goals. Paste only the ones you want to track manually; auto goals don't need entries.

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
; ── Savings goals ──────────────────────────────────────────────
; Format: "savings-goal" <name> <target-amount> <deadline>
2024-01-01 custom "savings-goal" "house-down-payment" "100000" "2027-06-01"
2024-01-01 custom "savings-goal" "college-fund"       "200000" "2036-09-01"
2024-01-01 custom "savings-goal" "car"                "15000"  "2026-12-01"

; ── Archived goals ─────────────────────────────────────────────
; Format: "savings-goal-archived" <name> <target-amount> <deadline>
; 2023-06-01 custom "savings-goal-archived" "emergency-fund" "25000" "2023-01-01"

; ── Cash accounts ──────────────────────────────────────────────
; All accounts whose balances form the savings pool
2024-01-01 custom "cash-account" "Assets:Checking"
2024-01-01 custom "cash-account" "Assets:Savings:HYSA"
2024-01-01 custom "cash-account" "Assets:Investments:529"
2024-01-01 custom "cash-account" "Liabilities:CreditCard:Chase"

; ── Expense and income account roots ───────────────────────────
2024-01-01 custom "expense-accounts" "Expenses"
2024-01-01 custom "income-accounts"  "Income"

; ── Expense exclusions ─────────────────────────────────────────
2024-01-01 custom "expense-exclude" "Expenses:Taxes"
2024-01-01 custom "expense-exclude" "Expenses:Transfers"

; ── Manual goal allocations ────────────────────────────────────
; Each entry records a dated contribution to a specific goal.
; Goals with no entries are distributed automatically from the pool.
; Format: "goal-allocation" <goal-name> <amount>
;
; Append new entries over time to build a contribution history.
; The sum of all entries is the goal's current attributed balance.
2024-06-01 custom "goal-allocation" "college-fund" "10000"
2024-12-01 custom "goal-allocation" "college-fund" "8000"
2025-06-01 custom "goal-allocation" "college-fund" "9000"
2026-01-01 custom "goal-allocation" "college-fund" "9000"
```

### Directive reference

| Directive | Args | Purpose |
|---|---|---|
| `savings-goal` | name, target, deadline | Active goal |
| `savings-goal-archived` | name, target, deadline | Archived goal (hidden from default views) |
| `cash-account` | account | Account included in the savings pool |
| `expense-accounts` | account root | Root of expense account tree |
| `income-accounts` | account root | Root of income account tree |
| `expense-exclude` | account | Sub-tree excluded from expense average |
| `goal-allocation` | goal-name, amount | Dated manual contribution to a goal |

See `example/goals.beancount` for a full working example.

## Running tests

```bash
uv run pytest
```

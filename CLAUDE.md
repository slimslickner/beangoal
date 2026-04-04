# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv run pytest                        # run all tests
uv run pytest tests/test_ledger.py   # run a single test file
uv run pytest -k test_name           # run a single test by name
uv run ruff check .                  # lint
uv run ruff format .                 # format
uv run ty check                      # type check
uv run beangoal --ledger example/ledger.beancount status  # manual smoke test
```

## Architecture

**Data flow:** `cli.py` loads the ledger via `beancount.loader`, passes entries to `loader.load_config()` to extract the `Config`, then calls `ledger.py` functions to compute balances/averages, feeds those into `allocator.py`, and renders via `report.py`.

**`models.py`** — two dataclasses: `Goal` (name, target, deadline, contributions list) and `Config` (goals, cash accounts, expense roots, excludes, expense transfer accounts). `Goal.is_manual` is True when it has `allocate` contributions; `Goal.manual_balance` sums them.

**`loader.py`** — reads beancount `Open` directives (for account metadata) and `Custom "beangoal"` directives (for goals and config). Goal state is derived by processing actions in date order: `create-goal` → `allocate`\* → `archive`. Unknown actions are hard errors; unknown goal references in `allocate`/`archive` are warnings. Returns `(Config, warnings, errors)`. Config lives in the ledger itself, often via beancount's `include` directive from a separate goals file.

**`ledger.py`** — thin wrappers around `beanquery.query.run_query`. Uses SQL-like BQL queries. The expense average uses `account ~` regex matching on account trees. Transfer expenses use `any_meta('matched_transfer_account') IS NOT NULL` to detect postings matched by the beancount zerosum plugin.

**`allocator.py`** — two-pass pool distribution: (1) manual goals get their declared `manual_balance`, prorated if pool is insufficient; (2) auto goals split the remainder weighted by `1/days_remaining`, capped at target with excess redistributed iteratively.

**Pool calculation:** `pool = cash_total - (avg_regular_expenses + avg_transfer_expenses) * buffer_months`

## Configuration metadata

beangoal reads two kinds of config from the ledger:

**Account `open` directive metadata:**

- `cash-account: TRUE` — includes account in the savings pool
- `beangoal-expense-transfer: TRUE` — transfers to this account counted as expenses (for zerosum-matched transfers)

**`custom "beangoal"` directives** — all use `custom "beangoal" "<action>" ...`:

- `"create-goal" <name> <target> <deadline>` — define a goal
- `"allocate" <name> <amount>` — manual allocation to a goal (bare number, no quotes)
- `"archive" <name>` — mark a goal archived (processed in date order, so can appear after create-goal)
- `"expense-accounts" <root>` — expense account tree for buffer calculation
- `"income-accounts" <root>` — income account tree
- `"expense-exclude" <account>` — exclude subtree from expense average

## Testing patterns

Tests use `beancount.loader.load_string` with inline ledger strings — no fixtures on disk. `date.today()` is patched via `monkeypatch.setattr` on the module-level `date` name in `beangoal.ledger` to control the trailing expense window.

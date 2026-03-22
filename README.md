# beangoal

Savings goals tracking for beancount v3.

Reads a beancount ledger and a goals file to track progress toward savings goals, compute available surplus, and suggest allocations.

## Setup

```bash
mise install
uv sync
uv run beangoal --help
```

## Usage

```bash
# Show goal status
uv run beangoal --ledger example/ledger.beancount --goals example/goals.beancount status

# Show surplus
uv run beangoal --ledger example/ledger.beancount --goals example/goals.beancount surplus

# Suggest allocation
uv run beangoal --ledger example/ledger.beancount --goals example/goals.beancount allocate 2000

# Archive a goal
uv run beangoal --ledger example/ledger.beancount --goals example/goals.beancount archive car
```

## Goals file format

See `example/goals.beancount` for a complete example.

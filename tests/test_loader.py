import tempfile
import textwrap
from datetime import date
from decimal import Decimal

import pytest

from beangoal.loader import load_config
from beangoal.models import Config, Goal


def write_goals(content: str) -> str:
    """Write goals content to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".beancount", delete=False)
    f.write(textwrap.dedent(content))
    f.flush()
    return f.name


def test_basic_goal_parsed():
    path = write_goals("""
        2024-01-01 custom "savings-goal" "house" "100000" "2027-06-01"
    """)
    config = load_config(path)
    assert len(config.goals) == 1
    g = config.goals[0]
    assert g.name == "house"
    assert g.target == Decimal("100000")
    assert g.deadline == date(2027, 6, 1)
    assert g.archived is False


def test_archived_goal_parsed():
    path = write_goals("""
        2024-01-01 custom "savings-goal-archived" "old-goal" "5000" "2023-01-01"
    """)
    config = load_config(path)
    assert len(config.goals) == 1
    assert config.goals[0].archived is True
    assert config.goals[0].name == "old-goal"


def test_multiple_goals():
    path = write_goals("""
        2024-01-01 custom "savings-goal" "house" "100000" "2027-06-01"
        2024-01-01 custom "savings-goal" "car"   "15000"  "2026-12-01"
    """)
    config = load_config(path)
    names = {g.name for g in config.goals}
    assert names == {"house", "car"}


def test_cash_accounts_parsed():
    path = write_goals("""
        2024-01-01 custom "cash-account" "Assets:Checking"
        2024-01-01 custom "cash-account" "Assets:Savings:HYSA"
    """)
    config = load_config(path)
    assert config.cash_accounts == ["Assets:Checking", "Assets:Savings:HYSA"]


def test_expense_and_income_roots():
    path = write_goals("""
        2024-01-01 custom "expense-accounts" "Expenses"
        2024-01-01 custom "income-accounts"  "Income"
    """)
    config = load_config(path)
    assert config.expense_roots == ["Expenses"]
    assert config.income_roots == ["Income"]


def test_expense_excludes():
    path = write_goals("""
        2024-01-01 custom "expense-exclude" "Expenses:Taxes"
        2024-01-01 custom "expense-exclude" "Expenses:Transfers"
    """)
    config = load_config(path)
    assert config.expense_excludes == ["Expenses:Taxes", "Expenses:Transfers"]


def test_goal_account_links():
    path = write_goals("""
        2024-01-01 custom "savings-goal"  "house" "100000" "2027-06-01"
        2024-01-01 custom "goal-account"  "house" "Assets:Savings:HYSA"
    """)
    config = load_config(path)
    assert config.goals[0].linked_accounts == ["Assets:Savings:HYSA"]


def test_goal_account_multiple_links():
    path = write_goals("""
        2024-01-01 custom "savings-goal"  "house" "100000" "2027-06-01"
        2024-01-01 custom "goal-account"  "house" "Assets:Savings:HYSA"
        2024-01-01 custom "goal-account"  "house" "Assets:Investments:Brokerage"
    """)
    config = load_config(path)
    assert config.goals[0].linked_accounts == [
        "Assets:Savings:HYSA",
        "Assets:Investments:Brokerage",
    ]


def test_goal_account_for_unknown_goal_is_ignored():
    """goal-account referencing a nonexistent goal should not crash."""
    path = write_goals("""
        2024-01-01 custom "goal-account" "nonexistent" "Assets:Checking"
    """)
    config = load_config(path)
    assert config.goals == []


def test_empty_goals_file():
    path = write_goals("")
    config = load_config(path)
    assert config.goals == []
    assert config.cash_accounts == []
    assert config.expense_roots == []
    assert config.income_roots == []
    assert config.expense_excludes == []


def test_full_config():
    path = write_goals("""
        2024-01-01 custom "savings-goal"         "house"  "100000" "2027-06-01"
        2024-01-01 custom "savings-goal-archived" "car"    "15000"  "2025-01-01"
        2024-01-01 custom "cash-account"          "Assets:Checking"
        2024-01-01 custom "expense-accounts"      "Expenses"
        2024-01-01 custom "income-accounts"       "Income"
        2024-01-01 custom "expense-exclude"       "Expenses:Taxes"
        2024-01-01 custom "goal-account"          "house"  "Assets:Savings:HYSA"
    """)
    config = load_config(path)
    assert len(config.goals) == 2
    active = [g for g in config.goals if not g.archived]
    archived = [g for g in config.goals if g.archived]
    assert len(active) == 1
    assert len(archived) == 1
    assert active[0].linked_accounts == ["Assets:Savings:HYSA"]
    assert config.cash_accounts == ["Assets:Checking"]
    assert config.expense_roots == ["Expenses"]
    assert config.income_roots == ["Income"]
    assert config.expense_excludes == ["Expenses:Taxes"]

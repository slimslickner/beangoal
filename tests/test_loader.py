import textwrap
from datetime import date
from decimal import Decimal

from beancount import loader as beancount_loader

from beangoal.loader import load_config
from beangoal.models import Config, Goal


def load(content: str) -> Config:
    """Parse a beancount string and return the resulting Config."""
    entries, _, _ = beancount_loader.load_string(textwrap.dedent(content))
    return load_config(entries)


def test_basic_goal_parsed():
    config = load('2024-01-01 custom "savings-goal" "house" "100000" "2027-06-01"')
    assert len(config.goals) == 1
    g = config.goals[0]
    assert g.name == "house"
    assert g.target == Decimal("100000")
    assert g.deadline == date(2027, 6, 1)
    assert g.archived is False


def test_archived_goal_parsed():
    config = load('2024-01-01 custom "savings-goal-archived" "old-goal" "5000" "2023-01-01"')
    assert len(config.goals) == 1
    assert config.goals[0].archived is True
    assert config.goals[0].name == "old-goal"


def test_multiple_goals():
    config = load("""\
        2024-01-01 custom "savings-goal" "house" "100000" "2027-06-01"
        2024-01-01 custom "savings-goal" "car"   "15000"  "2026-12-01"
    """)
    names = {g.name for g in config.goals}
    assert names == {"house", "car"}


def test_cash_accounts_parsed():
    config = load("""\
        2024-01-01 custom "cash-account" "Assets:Checking"
        2024-01-01 custom "cash-account" "Assets:Savings:HYSA"
    """)
    assert config.cash_accounts == ["Assets:Checking", "Assets:Savings:HYSA"]


def test_expense_and_income_roots():
    config = load("""\
        2024-01-01 custom "expense-accounts" "Expenses"
        2024-01-01 custom "income-accounts"  "Income"
    """)
    assert config.expense_roots == ["Expenses"]
    assert config.income_roots == ["Income"]


def test_expense_excludes():
    config = load("""\
        2024-01-01 custom "expense-exclude" "Expenses:Taxes"
        2024-01-01 custom "expense-exclude" "Expenses:Transfers"
    """)
    assert config.expense_excludes == ["Expenses:Taxes", "Expenses:Transfers"]


def test_goal_allocation_single():
    config = load("""\
        2024-01-01 custom "savings-goal"    "college" "200000" "2036-09-01"
        2024-06-01 custom "goal-allocation" "college" "10000"
    """)
    g = config.goals[0]
    assert g.is_manual is True
    assert g.manual_balance == Decimal("10000")
    assert len(g.contributions) == 1
    assert g.contributions[0] == (date(2024, 6, 1), Decimal("10000"))


def test_goal_allocation_multiple_contributions_accumulate():
    config = load("""\
        2024-01-01 custom "savings-goal"    "college" "200000" "2036-09-01"
        2024-06-01 custom "goal-allocation" "college" "10000"
        2024-12-01 custom "goal-allocation" "college" "8000"
        2025-06-01 custom "goal-allocation" "college" "9000"
    """)
    g = config.goals[0]
    assert g.manual_balance == Decimal("27000")
    assert len(g.contributions) == 3
    assert [d for d, _ in g.contributions] == [date(2024, 6, 1), date(2024, 12, 1), date(2025, 6, 1)]


def test_goal_without_allocation_is_auto():
    config = load('2024-01-01 custom "savings-goal" "house" "100000" "2027-06-01"')
    assert config.goals[0].is_manual is False
    assert config.goals[0].manual_balance == Decimal("0")
    assert config.goals[0].contributions == []


def test_goal_allocation_for_unknown_goal_is_ignored():
    config = load('2024-01-01 custom "goal-allocation" "nonexistent" "5000"')
    assert config.goals == []


def test_empty_entries():
    config = load_config([])
    assert config.goals == []
    assert config.cash_accounts == []
    assert config.expense_roots == []
    assert config.income_roots == []
    assert config.expense_excludes == []


def test_full_config():
    config = load("""\
        2024-01-01 custom "savings-goal"          "house"   "100000" "2027-06-01"
        2024-01-01 custom "savings-goal"          "college" "200000" "2036-09-01"
        2024-01-01 custom "savings-goal-archived" "car"     "15000"  "2025-01-01"
        2024-01-01 custom "cash-account"          "Assets:Checking"
        2024-01-01 custom "expense-accounts"      "Expenses"
        2024-01-01 custom "income-accounts"       "Income"
        2024-01-01 custom "expense-exclude"       "Expenses:Taxes"
        2024-06-01 custom "goal-allocation"       "college" "10000"
        2024-12-01 custom "goal-allocation"       "college" "8000"
    """)
    assert len(config.goals) == 3
    active = [g for g in config.goals if not g.archived]
    archived = [g for g in config.goals if g.archived]
    assert len(active) == 2
    assert len(archived) == 1

    college = next(g for g in active if g.name == "college")
    assert college.manual_balance == Decimal("18000")
    assert len(college.contributions) == 2

    house = next(g for g in active if g.name == "house")
    assert house.is_manual is False

    assert config.cash_accounts == ["Assets:Checking"]
    assert config.expense_roots == ["Expenses"]
    assert config.income_roots == ["Income"]
    assert config.expense_excludes == ["Expenses:Taxes"]

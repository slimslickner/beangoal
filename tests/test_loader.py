import textwrap
from datetime import date
from decimal import Decimal

from beancount import loader as beancount_loader

from beangoal.loader import load_config
from beangoal.models import Config


def load(content: str) -> Config:
    """Parse a beancount string and return the resulting Config."""
    entries, _, _ = beancount_loader.load_string(textwrap.dedent(content))
    config, _, _ = load_config(entries)
    return config


def load_with_diagnostics(content: str) -> tuple[Config, list[str], list[str]]:
    entries, _, _ = beancount_loader.load_string(textwrap.dedent(content))
    return load_config(entries)


def test_basic_goal_parsed():
    config = load('2024-01-01 custom "beangoal" "create-goal" "house" "100000" "2027-06-01"')
    assert len(config.goals) == 1
    g = config.goals[0]
    assert g.name == "house"
    assert g.target == Decimal("100000")
    assert g.deadline == date(2027, 6, 1)
    assert g.archived is False


def test_archived_goal_parsed():
    config = load("""\
        2024-01-01 custom "beangoal" "create-goal" "old-goal" "5000" "2023-01-01"
        2024-06-01 custom "beangoal" "archive"     "old-goal"
    """)
    assert len(config.goals) == 1
    assert config.goals[0].archived is True
    assert config.goals[0].name == "old-goal"


def test_archive_before_create_in_file_works():
    """archive can appear before create-goal in the file; beancount sorts by date."""
    config = load("""\
        2024-06-01 custom "beangoal" "archive"     "house"
        2024-01-01 custom "beangoal" "create-goal" "house" "100000" "2027-06-01"
    """)
    assert config.goals[0].archived is True


def test_multiple_goals():
    config = load("""\
        2024-01-01 custom "beangoal" "create-goal" "house" "100000" "2027-06-01"
        2024-01-01 custom "beangoal" "create-goal" "car"   "15000"  "2026-12-01"
    """)
    names = {g.name for g in config.goals}
    assert names == {"house", "car"}


def test_cash_accounts_parsed():
    config = load("""\
        2020-01-01 open Assets:Checking         USD
          cash-account: TRUE
        2020-01-01 open Assets:Savings:HYSA     USD
          cash-account: TRUE
        2020-01-01 open Assets:Investments:529  USD
    """)
    assert config.cash_accounts == ["Assets:Checking", "Assets:Savings:HYSA"]


def test_cash_account_without_flag_excluded():
    config = load("""\
        2020-01-01 open Assets:Checking     USD
        2020-01-01 open Assets:Savings:HYSA USD
          cash-account: TRUE
    """)
    assert config.cash_accounts == ["Assets:Savings:HYSA"]


def test_expense_and_income_roots():
    config = load("""\
        2024-01-01 custom "beangoal" "expense-accounts" "Expenses"
        2024-01-01 custom "beangoal" "income-accounts"  "Income"
    """)
    assert config.expense_roots == ["Expenses"]
    assert config.income_roots == ["Income"]


def test_expense_excludes():
    config = load("""\
        2024-01-01 custom "beangoal" "expense-exclude" "Expenses:Taxes"
        2024-01-01 custom "beangoal" "expense-exclude" "Expenses:Transfers"
    """)
    assert config.expense_excludes == ["Expenses:Taxes", "Expenses:Transfers"]


def test_goal_allocation_single():
    config = load("""\
        2024-01-01 custom "beangoal" "create-goal" "college" "200000" "2036-09-01"
        2024-06-01 custom "beangoal" "allocate"    "college" 10000
    """)
    g = config.goals[0]
    assert g.is_manual is True
    assert g.manual_balance == Decimal("10000")
    assert len(g.contributions) == 1
    assert g.contributions[0] == (date(2024, 6, 1), Decimal("10000"))


def test_goal_allocation_multiple_contributions_accumulate():
    config = load("""\
        2024-01-01 custom "beangoal" "create-goal" "college" "200000" "2036-09-01"
        2024-06-01 custom "beangoal" "allocate"    "college" 10000
        2024-12-01 custom "beangoal" "allocate"    "college" 8000
        2025-06-01 custom "beangoal" "allocate"    "college" 9000
    """)
    g = config.goals[0]
    assert g.manual_balance == Decimal("27000")
    assert len(g.contributions) == 3
    assert [d for d, _ in g.contributions] == [
        date(2024, 6, 1),
        date(2024, 12, 1),
        date(2025, 6, 1),
    ]


def test_goal_without_allocation_is_auto():
    config = load('2024-01-01 custom "beangoal" "create-goal" "house" "100000" "2027-06-01"')
    assert config.goals[0].is_manual is False
    assert config.goals[0].manual_balance == Decimal("0")
    assert config.goals[0].contributions == []


def test_allocate_for_unknown_goal_emits_warning():
    config, warnings, errors = load_with_diagnostics(
        '2024-01-01 custom "beangoal" "allocate" "nonexistent" 5000'
    )
    assert config.goals == []
    assert len(warnings) == 1
    assert "nonexistent" in warnings[0]
    assert errors == []


def test_archive_for_unknown_goal_emits_warning():
    config, warnings, errors = load_with_diagnostics(
        '2024-01-01 custom "beangoal" "archive" "nonexistent"'
    )
    assert config.goals == []
    assert len(warnings) == 1
    assert "nonexistent" in warnings[0]
    assert errors == []


def test_unknown_action_emits_error():
    config, warnings, errors = load_with_diagnostics('2024-01-01 custom "beangoal" "typo" "house"')
    assert len(errors) == 1
    assert "typo" in errors[0]
    assert warnings == []


def test_expense_transfer_accounts_parsed():
    config = load("""\
        2020-01-01 open Assets:House      USD
          beangoal-expense-transfer: TRUE
        2020-01-01 open Assets:Brokerage  USD
    """)
    assert config.expense_transfer_accounts == ["Assets:House"]


def test_empty_entries():
    config, warnings, errors = load_config([])
    assert config.goals == []
    assert config.cash_accounts == []
    assert config.expense_roots == []
    assert config.income_roots == []
    assert config.expense_excludes == []
    assert config.expense_transfer_accounts == []


def test_full_config():
    config = load("""\
        2020-01-01 open Assets:Checking USD
          cash-account: TRUE
        2024-01-01 custom "beangoal" "create-goal"      "house"   "100000" "2027-06-01"
        2024-01-01 custom "beangoal" "create-goal"      "college" "200000" "2036-09-01"
        2024-01-01 custom "beangoal" "create-goal"      "car"     "15000"  "2025-01-01"
        2024-06-01 custom "beangoal" "archive"          "car"
        2024-01-01 custom "beangoal" "expense-accounts" "Expenses"
        2024-01-01 custom "beangoal" "income-accounts"  "Income"
        2024-01-01 custom "beangoal" "expense-exclude"  "Expenses:Taxes"
        2024-06-01 custom "beangoal" "allocate"         "college" 10000
        2024-12-01 custom "beangoal" "allocate"         "college" 8000
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

from decimal import Decimal

import pytest
from beancount import loader as beancount_loader

from beangoal.ledger import get_account_balance, get_avg_monthly_expenses, get_avg_monthly_transfer_expenses, get_cash_total

LEDGER = """\
option "operating_currency" "USD"

2020-01-01 open Assets:Checking              USD
2020-01-01 open Assets:Savings:HYSA          USD
2020-01-01 open Assets:Investments:529       USD
2020-01-01 open Liabilities:CreditCard:Chase USD
2020-01-01 open Income:Salary                USD
2020-01-01 open Expenses:Food                USD
2020-01-01 open Expenses:Housing             USD
2020-01-01 open Expenses:Taxes               USD
2020-01-01 open Equity:Opening               USD

2024-01-01 * "Opening balances"
  Assets:Checking                5000.00 USD
  Assets:Savings:HYSA           20000.00 USD
  Liabilities:CreditCard:Chase  -1000.00 USD
  Equity:Opening

; Six months of income + expenses around a known date range
2025-09-01 * "Paycheck"
  Assets:Checking    8000.00 USD
  Income:Salary

2025-10-01 * "Paycheck"
  Assets:Checking    8000.00 USD
  Income:Salary

2025-11-01 * "Paycheck"
  Assets:Checking    8000.00 USD
  Income:Salary

2025-12-01 * "Paycheck"
  Assets:Checking    8000.00 USD
  Income:Salary

2026-01-01 * "Paycheck"
  Assets:Checking    8000.00 USD
  Income:Salary

2026-02-01 * "Paycheck"
  Assets:Checking    8000.00 USD
  Income:Salary

; Consistent $3100/mo expenses over 6 months
2025-09-05 * "Rent"        ; Expenses:Housing 2500 + Food 600 = 3100/mo
  Expenses:Housing   2500.00 USD
  Assets:Checking

2025-09-15 * "Groceries"
  Expenses:Food       600.00 USD
  Assets:Checking

2025-10-05 * "Rent"
  Expenses:Housing   2500.00 USD
  Assets:Checking

2025-10-15 * "Groceries"
  Expenses:Food       600.00 USD
  Assets:Checking

2025-11-05 * "Rent"
  Expenses:Housing   2500.00 USD
  Assets:Checking

2025-11-15 * "Groceries"
  Expenses:Food       600.00 USD
  Assets:Checking

2025-12-05 * "Rent"
  Expenses:Housing   2500.00 USD
  Assets:Checking

2025-12-15 * "Groceries"
  Expenses:Food       600.00 USD
  Assets:Checking

2026-01-05 * "Rent"
  Expenses:Housing   2500.00 USD
  Assets:Checking

2026-01-15 * "Groceries"
  Expenses:Food       600.00 USD
  Assets:Checking

2026-02-05 * "Rent"
  Expenses:Housing   2500.00 USD
  Assets:Checking

2026-02-15 * "Groceries"
  Expenses:Food       600.00 USD
  Assets:Checking

; Tax expense that should be excludable
2025-10-15 * "Taxes"
  Expenses:Taxes     6000.00 USD
  Assets:Checking
"""

LEDGER_WITH_TRANSFERS = """\
option "operating_currency" "USD"

2020-01-01 open Assets:Checking              USD
2020-01-01 open Assets:House                 USD
2020-01-01 open Assets:Brokerage             USD
2020-01-01 open Equity:Opening               USD

; $1000/mo transfer to house — should count as expense (no metadata needed)
; Six transfers from Nov 2025–Apr 2026; today=2026-04-01, start=2025-10-02, all within window
2025-11-01 * "House transfer"
  Assets:House        1000.00 USD
  Assets:Checking    -1000.00 USD

2025-12-01 * "House transfer"
  Assets:House        1000.00 USD
  Assets:Checking    -1000.00 USD

2026-01-01 * "House transfer"
  Assets:House        1000.00 USD
  Assets:Checking    -1000.00 USD

2026-02-01 * "House transfer"
  Assets:House        1000.00 USD
  Assets:Checking    -1000.00 USD

2026-03-01 * "House transfer"
  Assets:House        1000.00 USD
  Assets:Checking    -1000.00 USD

2026-04-01 * "House transfer"
  Assets:House        1000.00 USD
  Assets:Checking    -1000.00 USD

; Transfer to brokerage — NOT tagged as expense transfer, should be ignored
2026-01-15 * "Brokerage transfer"
  Assets:Brokerage    2000.00 USD
  Assets:Checking    -2000.00 USD
"""


@pytest.fixture(scope="module")
def ledger():
    entries, errors, options = beancount_loader.load_string(LEDGER)
    return entries, options


def test_account_balance_checking(ledger):
    entries, options = ledger
    bal = get_account_balance(entries, options, "Assets:Checking")
    # 5000 opening + 6*8000 income - 6*2500 rent - 6*600 groceries - 6000 taxes
    # = 5000 + 48000 - 15000 - 3600 - 6000 = 28400
    assert bal == Decimal("28400")


def test_account_balance_hysa(ledger):
    entries, options = ledger
    bal = get_account_balance(entries, options, "Assets:Savings:HYSA")
    assert bal == Decimal("20000")


def test_account_balance_nonexistent(ledger):
    entries, options = ledger
    bal = get_account_balance(entries, options, "Assets:DoesNotExist")
    assert bal == Decimal("0")


def test_account_balance_liability(ledger):
    entries, options = ledger
    bal = get_account_balance(entries, options, "Liabilities:CreditCard:Chase")
    assert bal == Decimal("-1000")


def test_cash_total(ledger):
    entries, options = ledger
    total = get_cash_total(
        entries, options, ["Assets:Checking", "Assets:Savings:HYSA", "Liabilities:CreditCard:Chase"]
    )
    assert total == Decimal("28400") + Decimal("20000") + Decimal("-1000")


def test_cash_total_empty_list(ledger):
    entries, options = ledger
    total = get_cash_total(entries, options, [])
    assert total == Decimal("0")


def test_avg_monthly_expenses_excludes_taxes(ledger, monkeypatch):
    """With taxes excluded, avg should be 3100/mo (rent+food only).

    today = 2026-03-01, start = 2026-03-01 - 180 days = 2025-09-02.
    All six months of test data (Sep–Feb) fall within the window.
    """
    from datetime import date

    import beangoal.ledger as ledger_mod

    monkeypatch.setattr(
        ledger_mod, "date", type("_D", (), {"today": staticmethod(lambda: date(2026, 3, 1))})()
    )

    entries, options = ledger
    avg = get_avg_monthly_expenses(
        entries,
        options,
        expense_roots=["Expenses"],
        excludes=["Expenses:Taxes"],
        trailing_months=6,
    )
    # 6 months * (2500 + 600) / 6 = 3100
    assert avg == Decimal("3100")


@pytest.fixture(scope="module")
def ledger_with_transfers():
    entries, errors, options = beancount_loader.load_string(LEDGER_WITH_TRANSFERS)
    return entries, options


def test_avg_monthly_expenses_includes_taxes(ledger, monkeypatch):
    """Without exclusions, taxes are included: (18600 + 6000) / 6 = 4100."""
    from datetime import date

    import beangoal.ledger as ledger_mod

    monkeypatch.setattr(
        ledger_mod, "date", type("_D", (), {"today": staticmethod(lambda: date(2026, 3, 1))})()
    )

    entries, options = ledger
    avg = get_avg_monthly_expenses(
        entries,
        options,
        expense_roots=["Expenses"],
        excludes=[],
        trailing_months=6,
    )
    # (6 * 3100 + 6000) / 6 = 4100
    assert avg == Decimal("4100")


def test_avg_monthly_transfer_expenses(ledger_with_transfers, monkeypatch):
    """Transfers to Assets:House at $1000/mo average to $1000/mo."""
    from datetime import date

    import beangoal.ledger as ledger_mod

    monkeypatch.setattr(
        ledger_mod, "date", type("_D", (), {"today": staticmethod(lambda: date(2026, 4, 1))})()
    )

    entries, options = ledger_with_transfers
    avg = get_avg_monthly_transfer_expenses(
        entries,
        options,
        expense_transfer_accounts=["Assets:House"],
        trailing_months=6,
    )
    # 6 * 1000 / 6 = 1000
    assert avg == Decimal("1000")


def test_avg_monthly_transfer_expenses_ignores_untagged_accounts(ledger_with_transfers, monkeypatch):
    """Transfers to Assets:Brokerage are not counted when not in the list."""
    from datetime import date

    import beangoal.ledger as ledger_mod

    monkeypatch.setattr(
        ledger_mod, "date", type("_D", (), {"today": staticmethod(lambda: date(2026, 4, 1))})()
    )

    entries, options = ledger_with_transfers
    avg = get_avg_monthly_transfer_expenses(
        entries,
        options,
        expense_transfer_accounts=["Assets:House"],
        trailing_months=6,
    )
    # Brokerage transfers are excluded — only house $1000/mo counts
    assert avg == Decimal("1000")


def test_avg_monthly_transfer_expenses_empty_list(ledger_with_transfers):
    """Empty account list returns zero without querying."""
    entries, options = ledger_with_transfers
    avg = get_avg_monthly_transfer_expenses(entries, options, expense_transfer_accounts=[])
    assert avg == Decimal("0")

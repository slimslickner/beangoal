import sys
from datetime import date, timedelta
from decimal import Decimal

from beanquery import query


def get_account_balance(entries, options, account: str, currency: str = "USD") -> Decimal:
    """Sum balance of a single account, converting commodities to currency via price data."""
    try:
        _, rows = query.run_query(
            entries,
            options,
            f"SELECT CONVERT(sum(position), '{currency}') WHERE account = '{account}'",
        )
        if rows and rows[0][0] is not None:
            inv = rows[0][0]
            total = Decimal("0")
            for pos in inv:
                if pos.units.currency == currency:
                    total += Decimal(str(pos.units.number))
            return total
    except Exception as e:
        print(f"Warning: could not query balance for {account}: {e}", file=sys.stderr)
    return Decimal("0")


def get_cash_total(entries, options, cash_accounts: list[str], currency: str = "USD") -> Decimal:
    """Sum balances across all cash accounts."""
    total = Decimal("0")
    for account in cash_accounts:
        total += get_account_balance(entries, options, account, currency)
    return total


def get_avg_monthly_transfer_expenses(
    entries,
    options,
    expense_transfer_accounts: list[str],
    trailing_months: int = 6,
    currency: str = "USD",
) -> Decimal:
    """
    Compute average monthly expenses from transfers to designated accounts,
    identified by the presence of matched_transfer_account posting metadata
    (set by the beancount zerosum plugin).
    """
    if not expense_transfer_accounts:
        return Decimal("0")

    end = date.today()
    start = end - timedelta(days=trailing_months * 30)

    account_filter = " OR ".join(f"account = '{a}'" for a in expense_transfer_accounts)
    where = (
        f"({account_filter})"
        f" AND date >= {start.isoformat()} AND date <= {end.isoformat()}"
        f" AND currency = '{currency}'"
    )

    try:
        _, rows = query.run_query(
            entries,
            options,
            f"SELECT sum(position) WHERE {where}",
        )
        total = Decimal("0")
        if rows and rows[0][0] is not None:
            pos = rows[0][0].get_only_position()
            if pos is not None:
                total = Decimal(str(pos.units.number))
        return total / trailing_months
    except Exception as e:
        print(f"Warning: could not compute transfer expense average: {e}", file=sys.stderr)
        return Decimal("0")


def get_avg_monthly_expenses(
    entries,
    options,
    expense_roots: list[str],
    excludes: list[str],
    trailing_months: int = 6,
    currency: str = "USD",
) -> Decimal:
    """
    Compute average monthly expenses over trailing N months,
    excluding specified sub-trees.
    """
    end = date.today()
    start = end - timedelta(days=trailing_months * 30)

    root_filters = " OR ".join(f"account ~ '^{r}'" for r in expense_roots)
    exclude_filters = " AND ".join(f"account !~ '^{e}'" for e in excludes)

    where = f"({root_filters})"
    if excludes:
        where += f" AND {exclude_filters}"
    where += f" AND date >= {start.isoformat()} AND date <= {end.isoformat()}"
    where += f" AND currency = '{currency}'"

    try:
        _, rows = query.run_query(
            entries,
            options,
            f"SELECT sum(position) WHERE {where}",
        )
        total = Decimal("0")
        if rows and rows[0][0] is not None:
            pos = rows[0][0].get_only_position()
            if pos is not None:
                total = Decimal(str(pos.units.number))
        return total / trailing_months
    except Exception as e:
        print(f"Warning: could not compute expense average: {e}", file=sys.stderr)
        return Decimal("0")

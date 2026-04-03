import sys
from datetime import date
from decimal import Decimal

import click
from beancount import loader as beancount_loader
from rich.console import Console

from beangoal.allocator import compute_urgency_scores_with_balances, distribute_pool
from beangoal.ledger import (
    get_avg_monthly_expenses,
    get_avg_monthly_transfer_expenses,
    get_avg_monthly_transfer_expenses_by_account,
    get_cash_balances,
    get_cash_total,
)
from beangoal.loader import load_config
from beangoal.report import console, render_status, render_surplus

err_console = Console(stderr=True)


@click.group()
@click.option(
    "--ledger", required=True, type=click.Path(exists=True), help="Path to main beancount ledger"
)
@click.option("--currency", default=None, help="Override operating currency (default: from ledger)")
@click.option("--trailing-months", default=6, show_default=True, type=int)
@click.option("--buffer-months", default=3, show_default=True, type=int)
@click.pass_context
def cli(
    ctx: click.Context, ledger: str, currency: str | None, trailing_months: int, buffer_months: int
) -> None:
    """beangoal — savings goals tracking for beancount v3"""
    ctx.ensure_object(dict)

    entries, errors, options = beancount_loader.load_file(ledger)
    if errors:
        for err in errors:
            print(f"Warning: {err}", file=sys.stderr)

    config, config_warnings = load_config(entries)
    for w in config_warnings:
        print(f"Warning: {w}", file=sys.stderr)

    if currency is None:
        operating = options.get("operating_currency", ["USD"])
        currency = operating[0] if operating else "USD"

    ctx.obj["entries"] = entries
    ctx.obj["options"] = options
    ctx.obj["config"] = config
    ctx.obj["currency"] = currency
    ctx.obj["trailing_months"] = trailing_months
    ctx.obj["buffer_months"] = buffer_months


@cli.command()
@click.option("--show-archived", is_flag=True, default=False)
@click.option(
    "--show-contributions",
    is_flag=True,
    default=False,
    help="List individual contributions for manual goals",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Show pool breakdown and per-goal allocation detail",
)
@click.pass_context
def status(ctx: click.Context, show_archived: bool, show_contributions: bool, verbose: bool) -> None:
    """Show progress for each active goal."""
    obj = ctx.obj
    entries = obj["entries"]
    options = obj["options"]
    config = obj["config"]
    currency = obj["currency"]
    trailing_months = obj["trailing_months"]
    buffer_months = obj["buffer_months"]

    today = date.today()
    cash_total = get_cash_total(entries, options, config.cash_accounts, currency)
    avg_regular_expenses = get_avg_monthly_expenses(
        entries, options, config.expense_roots, config.expense_excludes, trailing_months, currency
    )
    avg_transfer_expenses_by_account = get_avg_monthly_transfer_expenses_by_account(
        entries, options, config.expense_transfer_accounts, trailing_months, currency
    )
    avg_transfer_expenses = sum(avg_transfer_expenses_by_account.values(), Decimal("0"))
    avg_expenses = avg_regular_expenses + avg_transfer_expenses
    pool_total = max(cash_total - avg_expenses * buffer_months, Decimal("0"))
    attributed = distribute_pool(config.goals, pool_total, today)

    cash_balances = get_cash_balances(entries, options, config.cash_accounts, currency) if verbose else None

    render_status(
        config.goals,
        attributed,
        pool_total=pool_total,
        show_archived=show_archived,
        show_contributions=show_contributions,
        today=today,
        verbose=verbose,
        cash_total=cash_total,
        avg_expenses=avg_expenses,
        avg_regular_expenses=avg_regular_expenses,
        avg_transfer_expenses_by_account=avg_transfer_expenses_by_account,
        buffer_months=buffer_months,
        cash_balances=cash_balances,
    )


@cli.command()
@click.pass_context
def surplus(ctx: click.Context) -> None:
    """Show available cash after subtracting the operating buffer."""
    obj = ctx.obj
    entries = obj["entries"]
    options = obj["options"]
    config = obj["config"]
    currency = obj["currency"]
    trailing_months = obj["trailing_months"]
    buffer_months = obj["buffer_months"]

    cash_total = get_cash_total(entries, options, config.cash_accounts, currency)
    avg_expenses = get_avg_monthly_expenses(
        entries, options, config.expense_roots, config.expense_excludes, trailing_months, currency
    ) + get_avg_monthly_transfer_expenses(
        entries, options, config.expense_transfer_accounts, trailing_months, currency
    )

    render_surplus(cash_total, avg_expenses, buffer_months, currency)


@cli.command()
@click.argument("amount", type=Decimal)
@click.pass_context
def allocate(ctx: click.Context, amount: Decimal) -> None:
    """Suggest an allocation of AMOUNT across active goals."""
    obj = ctx.obj
    entries = obj["entries"]
    options = obj["options"]
    config = obj["config"]
    currency = obj["currency"]
    trailing_months = obj["trailing_months"]
    buffer_months = obj["buffer_months"]

    today = date.today()
    cash_total = get_cash_total(entries, options, config.cash_accounts, currency)
    avg_expenses = get_avg_monthly_expenses(
        entries, options, config.expense_roots, config.expense_excludes, trailing_months, currency
    ) + get_avg_monthly_transfer_expenses(
        entries, options, config.expense_transfer_accounts, trailing_months, currency
    )
    pool_total = max(cash_total - avg_expenses * buffer_months, Decimal("0"))
    attributed = distribute_pool(config.goals, pool_total, today)
    scores = compute_urgency_scores_with_balances(config.goals, attributed, today)

    if not scores:
        console.print("No active goals to allocate to.")
        return

    allocations: dict[str, Decimal] = {
        name: (weight * amount).quantize(Decimal("0.01")) for name, weight in scores.items()
    }

    active_goals = {g.name: g for g in config.goals if not g.archived and g.deadline > today}

    console.print(f"\n  Suggested allocation of [bold]${amount:,.2f}[/bold]:")
    console.print("  " + "─" * 54)

    for name, alloc in allocations.items():
        goal = active_goals[name]
        current = attributed.get(name, Decimal("0"))
        days_left = (goal.deadline - today).days
        pct = int(float(alloc / amount) * 100) if amount else 0
        funded_pct = int(float(current / goal.target) * 100) if goal.target else 0
        label = "manual" if goal.is_manual else "auto"
        console.print(
            f"  [bold]{name:<22}[/bold]  [cyan]${alloc:>10,.2f}[/cyan]  ({pct}%)"
            f"   {days_left} days left, {funded_pct}% funded  [{label}]"
        )

    # Ledger transaction — single pool deposit, user adjusts destination
    source = config.cash_accounts[0] if config.cash_accounts else "Assets:Checking"
    today_str = today.isoformat()

    console.print()
    console.print("  Paste into your ledger:")
    console.print()
    console.print(f'  {today_str} * "Savings allocation"')
    console.print(f"    {source:<40} {amount:>10,.2f} {currency}   ; adjust destination as needed")
    console.print(f"    {source:<40} {-amount:>10,.2f} {currency}   ; adjust source as needed")

    # goal-allocation directives
    console.print()
    console.print("  Paste into goals.beancount:")
    console.print()
    for name, alloc in allocations.items():
        console.print(f'  {today_str} custom "goal-allocation" "{name}" "{alloc}"')
    console.print()


@cli.command()
@click.argument("goal_name")
@click.pass_context
def archive(ctx: click.Context, goal_name: str) -> None:
    """Print instructions to archive a goal in goals.beancount."""
    config = ctx.obj["config"]

    goal = next((g for g in config.goals if g.name == goal_name), None)
    if goal is None:
        console.print(f"[red]Goal '{goal_name}' not found.[/red]")
        raise SystemExit(1)

    date_str = "2024-01-01"  # placeholder — user sets the date
    console.print("\n  To archive this goal, replace in goals.beancount:\n")
    console.print("  REMOVE:")
    console.print(
        f'  {date_str} custom "savings-goal"'
        f'"{goal.name}" "{goal.target}" "{goal.deadline.isoformat()}"'
    )
    console.print()
    console.print("  ADD:")
    console.print(
        f'  {date_str} custom "savings-goal-archived"'
        f'"{goal.name}" "{goal.target}" "{goal.deadline.isoformat()}"'
    )
    console.print()
    console.print("  Archived goals are hidden from `status` by default.")
    console.print("  Use `beangoal status --show-archived` to display them.")

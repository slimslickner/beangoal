import sys
from datetime import date
from decimal import Decimal

import click
from beancount import loader as beancount_loader
from rich.console import Console

from beangoal.allocator import compute_urgency_scores_with_balances
from beangoal.ledger import get_account_balance, get_avg_monthly_expenses, get_cash_total
from beangoal.loader import load_config
from beangoal.report import console, render_status, render_surplus

err_console = Console(stderr=True)


@click.group()
@click.option("--ledger", required=True, type=click.Path(exists=True), help="Path to main beancount ledger")
@click.option("--goals", default="goals.beancount", show_default=True, type=click.Path(exists=True), help="Path to goals file")
@click.option("--currency", default="USD", show_default=True)
@click.option("--trailing-months", default=6, show_default=True, type=int)
@click.option("--buffer-months", default=3, show_default=True, type=int)
@click.pass_context
def cli(ctx: click.Context, ledger: str, goals: str, currency: str, trailing_months: int, buffer_months: int) -> None:
    """beangoal — savings goals tracking for beancount v3"""
    ctx.ensure_object(dict)

    entries, errors, options = beancount_loader.load_file(ledger)
    if errors:
        for err in errors:
            print(f"Warning: {err}", file=sys.stderr)

    config = load_config(goals)

    ctx.obj["entries"] = entries
    ctx.obj["options"] = options
    ctx.obj["config"] = config
    ctx.obj["currency"] = currency
    ctx.obj["trailing_months"] = trailing_months
    ctx.obj["buffer_months"] = buffer_months


@cli.command()
@click.option("--show-archived", is_flag=True, default=False)
@click.pass_context
def status(ctx: click.Context, show_archived: bool) -> None:
    """Show progress for each active goal."""
    obj = ctx.obj
    entries = obj["entries"]
    options = obj["options"]
    config = obj["config"]
    currency = obj["currency"]

    today = date.today()
    balances: dict[str, Decimal] = {}

    for goal in config.goals:
        total = Decimal("0")
        for account in goal.linked_accounts:
            bal = get_account_balance(entries, options, account, currency)
            total += bal
        balances[goal.name] = total

    render_status(config.goals, balances, show_archived=show_archived, today=today)


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

    today = date.today()
    balances: dict[str, Decimal] = {}

    for goal in config.goals:
        total = Decimal("0")
        for account in goal.linked_accounts:
            bal = get_account_balance(entries, options, account, currency)
            total += bal
        balances[goal.name] = total

    scores = compute_urgency_scores_with_balances(config.goals, balances, today)

    if not scores:
        console.print("No active goals to allocate to.")
        return

    active_goals = {g.name: g for g in config.goals if not g.archived and g.deadline > today}

    console.print(f"\n  Suggested allocation of [bold]${amount:,.2f}[/bold]:")
    console.print("  " + "─" * 54)

    allocations: dict[str, Decimal] = {}
    for name, weight in scores.items():
        allocations[name] = (weight * amount).quantize(Decimal("0.01"))

    for name, alloc in allocations.items():
        goal = active_goals[name]
        current = balances.get(name, Decimal("0"))
        days_left = (goal.deadline - today).days
        pct = int(float(alloc / amount) * 100) if amount else 0
        funded_pct = int(float(current / goal.target) * 100) if goal.target else 0
        console.print(
            f"  [bold]{name:<22}[/bold]  [cyan]${alloc:>10,.2f}[/cyan]  ({pct}%)"
            f"   {days_left} days left, {funded_pct}% funded"
        )

    # Group by destination account
    console.print()
    console.print("  Paste into your ledger:")
    console.print()

    account_allocs: dict[str, list[tuple[str, Decimal]]] = {}
    for name, alloc in allocations.items():
        goal = active_goals[name]
        # Use last linked account as destination (or first)
        dest = goal.linked_accounts[0] if goal.linked_accounts else "Assets:Savings"
        account_allocs.setdefault(dest, []).append((name, alloc))

    source = config.cash_accounts[0] if config.cash_accounts else "Assets:Checking"
    today_str = today.isoformat()

    console.print(f'  {today_str} * "Savings allocation"')
    for account, items in account_allocs.items():
        names_comment = " + ".join(n for n, _ in items)
        acct_total = sum(a for _, a in items)
        console.print(f"    {account:<40} {acct_total:>10,.2f} {currency}   ; {names_comment}")
    console.print(f"    {source:<40} {-amount:>10,.2f} {currency}   ; adjust source as needed")
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
    console.print(f"\n  To archive this goal, replace in goals.beancount:\n")
    console.print(f"  REMOVE:")
    console.print(
        f'  {date_str} custom "savings-goal" "{goal.name}" "{goal.target}" "{goal.deadline.isoformat()}"'
    )
    console.print()
    console.print(f"  ADD:")
    console.print(
        f'  {date_str} custom "savings-goal-archived" "{goal.name}" "{goal.target}" "{goal.deadline.isoformat()}"'
    )
    console.print()
    console.print("  Archived goals are hidden from `status` by default.")
    console.print("  Use `beangoal status --show-archived` to display them.")

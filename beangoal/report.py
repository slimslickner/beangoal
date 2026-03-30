from datetime import date
from decimal import Decimal

from rich import box
from rich.console import Console
from rich.table import Table

from beangoal.models import Goal

console = Console()


def render_progress_bar(fraction: float, width: int = 12) -> str:
    filled = int(fraction * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def render_status(
    goals: list[Goal],
    balances: dict[str, Decimal],
    pool_total: Decimal,
    show_archived: bool = False,
    show_contributions: bool = False,
    today: date | None = None,
    verbose: bool = False,
    cash_total: Decimal | None = None,
    avg_expenses: Decimal | None = None,
    avg_regular_expenses: Decimal | None = None,
    avg_transfer_expenses_by_account: dict[str, Decimal] | None = None,
    buffer_months: int | None = None,
    cash_balances: dict[str, Decimal] | None = None,
) -> None:
    if today is None:
        today = date.today()

    active = [g for g in goals if not g.archived]
    archived = [g for g in goals if g.archived]

    if verbose and cash_total is not None and avg_expenses is not None and buffer_months is not None:
        buffer = avg_expenses * buffer_months
        console.print(
            f"\n  Pool: [bold cyan]${pool_total:,.2f}[/bold cyan]"
            f"  [dim](cash ${cash_total:,.2f} − {buffer_months}mo buffer ${buffer:,.2f})[/dim]"
        )

        # Per-account cash breakdown
        if cash_balances:
            sorted_cash = sorted(cash_balances.items())
            col_w = max(len(a) for a, _ in sorted_cash)
            console.print()
            console.print("  [dim]Cash accounts:[/dim]")
            for acct, bal in sorted_cash:
                console.print(f"    [dim]{acct:<{col_w}}  ${bal:>{12},.2f}[/dim]")

        # Expense breakdown
        expense_rows: list[tuple[str, Decimal, str]] = []
        if avg_regular_expenses is not None:
            expense_rows.append(("regular", avg_regular_expenses, ""))
        if avg_transfer_expenses_by_account:
            for acct, avg in sorted(avg_transfer_expenses_by_account.items()):
                expense_rows.append((acct, avg, "  [italic](transfer)[/italic]"))
        if expense_rows:
            exp_col_w = max(len(label) for label, _, _ in expense_rows)
            console.print()
            console.print("  [dim]Avg monthly expenses (trailing):[/dim]")
            for label, val, suffix in expense_rows:
                console.print(f"    [dim]{label:<{exp_col_w}}  ${val:>{12},.2f}{suffix}[/dim]")
        console.print()
    else:
        console.print(f"\n  Pool: [bold cyan]${pool_total:,.2f}[/bold cyan]\n")

    # Compute normalized pool weights for auto goals (for verbose display)
    auto_active = [g for g in active if not g.is_manual and g.deadline > today and (g.deadline - today).days > 0]
    raw_weights = {g.name: Decimal("1") / Decimal(str((g.deadline - today).days)) for g in auto_active}
    total_weight = sum(raw_weights.values())
    pool_weights = {name: w / total_weight for name, w in raw_weights.items()} if total_weight else {}

    def render_group(group: list[Goal], dim: bool = False) -> None:
        for goal in group:
            current = balances.get(goal.name, Decimal("0"))
            fraction = float(current / goal.target) if goal.target else 0.0
            pct = int(fraction * 100)
            bar = render_progress_bar(fraction)
            label = "[dim]manual[/dim]" if goal.is_manual else "[dim]auto[/dim]"

            deadline_passed = goal.deadline < today
            if deadline_passed and fraction >= 1.0:
                status_str = "[green]FUNDED  ✓[/green]"
            elif deadline_passed:
                short = goal.target - current
                status_str = f"[red]MISSED (${short:,.0f} short) ✗[/red]"
            else:
                total_days = (goal.deadline - date(today.year - 1, today.month, today.day)).days
                elapsed = (today - date(today.year - 1, today.month, today.day)).days
                time_fraction = elapsed / total_days if total_days > 0 else 1.0
                if fraction >= time_fraction:
                    status_str = "[green]on pace ✓[/green]"
                else:
                    status_str = "[yellow]behind  ✗[/yellow]"

            style = "dim" if dim else ""
            console.print(
                f"  [bold]{goal.name:<22}[/bold] {bar}  {pct:>3}%"
                f"   [cyan]${current:>10,.0f}[/cyan] / [cyan]${goal.target:>10,.0f}[/cyan]"
                f"   {label}   deadline: {goal.deadline.isoformat()}   {status_str}",
                style=style,
            )

            if not dim and (show_contributions or verbose):
                if goal.is_manual:
                    for contrib_date, amount in goal.contributions:
                        console.print(f"    [dim]{contrib_date.isoformat()}   +${amount:>10,.2f}[/dim]")
                    console.print(f"    [dim]{'':>30} = ${goal.manual_balance:>10,.2f}[/dim]")
                elif verbose and goal.name in pool_weights:
                    days_remaining = (goal.deadline - today).days
                    weight_pct = int(pool_weights[goal.name] * 100)
                    console.print(f"    [dim]pool weight: {weight_pct}%  ({days_remaining} days remaining)[/dim]")

    render_group(active)

    if show_archived and archived:
        console.print()
        console.print("  [dim]── Archived ──[/dim]")
        render_group(archived, dim=True)


def render_surplus(
    cash_total: Decimal,
    avg_expenses: Decimal,
    buffer_months: int,
    currency: str = "USD",
) -> None:
    buffer = avg_expenses * buffer_months
    surplus = cash_total - buffer

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="bold", min_width=30)
    table.add_column(justify="right", style="cyan")
    table.add_column()

    table.add_row("Cash accounts total:", f"${cash_total:,.2f}", "")
    table.add_row("Avg monthly expenses:", f"${avg_expenses:,.2f}", "(trailing months)")
    table.add_row(f"Operating buffer ({buffer_months} mo):", f"${buffer:,.2f}", "")
    table.add_section()
    table.add_row(
        "[bold]Allocatable surplus:[/bold]",
        f"[bold green]${surplus:,.2f}[/bold green]",
        "",
    )

    console.print(table)

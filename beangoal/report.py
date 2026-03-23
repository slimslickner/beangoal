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
) -> None:
    if today is None:
        today = date.today()

    active = [g for g in goals if not g.archived]
    archived = [g for g in goals if g.archived]

    console.print(f"\n  Pool: [bold cyan]${pool_total:,.2f}[/bold cyan]\n")

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

            if show_contributions and goal.is_manual and not dim:
                for contrib_date, amount in goal.contributions:
                    console.print(f"    [dim]{contrib_date.isoformat()}   +${amount:>10,.2f}[/dim]")
                console.print(f"    [dim]{'':>30} = ${goal.manual_balance:>10,.2f}[/dim]")

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
    table.add_row("Avg monthly expenses:", f"${avg_expenses:,.2f}", f"(trailing months)")
    table.add_row(f"Operating buffer ({buffer_months} mo):", f"${buffer:,.2f}", "")
    table.add_section()
    table.add_row(
        "[bold]Allocatable surplus:[/bold]",
        f"[bold green]${surplus:,.2f}[/bold green]",
        "",
    )

    console.print(table)

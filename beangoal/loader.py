from datetime import date
from decimal import Decimal

from beancount.core.data import Custom, Open

from beangoal.models import Config, Goal


def load_config(entries) -> tuple[Config, list[str]]:
    goals_map: dict[str, Goal] = {}
    warnings: list[str] = []
    cash_accounts: list[str] = []
    expense_roots: list[str] = []
    income_roots: list[str] = []
    expense_excludes: list[str] = []
    expense_transfer_accounts: list[str] = []

    for entry in entries:
        if isinstance(entry, Open):
            if entry.meta.get("beangoal-cash-account"):
                cash_accounts.append(entry.account)
            if entry.meta.get("beangoal-expense-transfer"):
                expense_transfer_accounts.append(entry.account)
            continue

        if not isinstance(entry, Custom):
            continue

        t = entry.type
        vals = [v.value for v in entry.values]

        if t == "savings-goal":
            name, target, deadline = vals[0], Decimal(vals[1]), date.fromisoformat(vals[2])
            goals_map[name] = Goal(name=name, target=target, deadline=deadline)

        elif t == "savings-goal-archived":
            name, target, deadline = vals[0], Decimal(vals[1]), date.fromisoformat(vals[2])
            goals_map[name] = Goal(name=name, target=target, deadline=deadline, archived=True)

        elif t == "expense-accounts":
            expense_roots.append(vals[0])

        elif t == "income-accounts":
            income_roots.append(vals[0])

        elif t == "expense-exclude":
            expense_excludes.append(vals[0])

        elif t == "goal-allocation":
            goal_name = vals[0]
            amount = Decimal(vals[1])
            if goal_name in goals_map:
                goals_map[goal_name].contributions.append((entry.date, amount))
            else:
                warnings.append(f"goal-allocation references unknown goal '{goal_name}' ({entry.meta['filename']}:{entry.meta['lineno']})")

    return Config(
        goals=list(goals_map.values()),
        cash_accounts=cash_accounts,
        expense_roots=expense_roots,
        income_roots=income_roots,
        expense_excludes=expense_excludes,
        expense_transfer_accounts=expense_transfer_accounts,
    ), warnings

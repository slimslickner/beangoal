from decimal import Decimal
from datetime import date

from beancount.core.data import Custom

from beangoal.models import Config, Goal


def load_config(entries) -> Config:
    goals_map: dict[str, Goal] = {}
    cash_accounts: list[str] = []
    expense_roots: list[str] = []
    income_roots: list[str] = []
    expense_excludes: list[str] = []

    for entry in entries:
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

        elif t == "cash-account":
            cash_accounts.append(vals[0])

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

    return Config(
        goals=list(goals_map.values()),
        cash_accounts=cash_accounts,
        expense_roots=expense_roots,
        income_roots=income_roots,
        expense_excludes=expense_excludes,
    )

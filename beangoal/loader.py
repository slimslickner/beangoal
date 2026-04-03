from datetime import date
from decimal import Decimal

from beancount.core.data import Custom, Open

from beangoal.models import Config, Goal


def load_config(entries) -> tuple[Config, list[str], list[str]]:
    goals_map: dict[str, Goal] = {}
    warnings: list[str] = []
    errors: list[str] = []
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

        if entry.type != "beangoal":
            continue

        loc = f"{entry.meta['filename']}:{entry.meta['lineno']}"
        vals = [v.value for v in entry.values]

        if not vals:
            errors.append(f"beangoal directive missing action ({loc})")
            continue

        action = vals[0]
        args = vals[1:]

        if action == "create-goal":
            name, target, deadline = args[0], Decimal(args[1]), date.fromisoformat(args[2])
            goals_map[name] = Goal(name=name, target=target, deadline=deadline)

        elif action == "archive":
            goal_name = args[0]
            if goal_name in goals_map:
                goals_map[goal_name].archived = True
            else:
                warnings.append(f"archive references unknown goal '{goal_name}' ({loc})")

        elif action == "allocate":
            goal_name = args[0]
            amount = Decimal(args[1])
            if goal_name in goals_map:
                goals_map[goal_name].contributions.append((entry.date, amount))
            else:
                warnings.append(f"allocate references unknown goal '{goal_name}' ({loc})")

        elif action == "expense-accounts":
            expense_roots.append(args[0])

        elif action == "income-accounts":
            income_roots.append(args[0])

        elif action == "expense-exclude":
            expense_excludes.append(args[0])

        else:
            errors.append(f"unknown beangoal action '{action}' ({loc})")

    return Config(
        goals=list(goals_map.values()),
        cash_accounts=cash_accounts,
        expense_roots=expense_roots,
        income_roots=income_roots,
        expense_excludes=expense_excludes,
        expense_transfer_accounts=expense_transfer_accounts,
    ), warnings, errors

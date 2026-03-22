from datetime import date
from decimal import Decimal

from beangoal.models import Goal


def compute_urgency_scores(goals: list[Goal], today: date | None = None) -> dict[str, Decimal]:
    """
    urgency_score = gap_fraction / days_remaining
    Returns normalized scores for active, unfunded goals with future deadlines.
    """
    if today is None:
        today = date.today()

    scores: dict[str, Decimal] = {}
    for goal in goals:
        if goal.archived:
            continue
        if goal.deadline <= today:
            continue
        days_remaining = (goal.deadline - today).days
        if days_remaining <= 0:
            continue
        # gap_fraction: how much of the target is unfunded (placeholder — actual balance passed separately)
        scores[goal.name] = Decimal("1") / Decimal(str(days_remaining))

    total = sum(scores.values())
    if total == 0:
        return {}

    return {name: score / total for name, score in scores.items()}


def compute_urgency_scores_with_balances(
    goals: list[Goal],
    balances: dict[str, Decimal],
    today: date | None = None,
) -> dict[str, Decimal]:
    """
    urgency_score = gap_fraction / days_remaining, normalized.
    gap_fraction = (target - current) / target
    """
    if today is None:
        today = date.today()

    scores: dict[str, Decimal] = {}
    for goal in goals:
        if goal.archived:
            continue
        if goal.deadline <= today:
            continue
        days_remaining = (goal.deadline - today).days
        if days_remaining <= 0:
            continue
        current = balances.get(goal.name, Decimal("0"))
        gap = goal.target - current
        if gap <= 0:
            continue
        gap_fraction = gap / goal.target
        scores[goal.name] = gap_fraction / Decimal(str(days_remaining))

    total = sum(scores.values())
    if total == 0:
        return {}

    return {name: score / total for name, score in scores.items()}

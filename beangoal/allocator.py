from datetime import date
from decimal import Decimal

from beangoal.models import Goal


def distribute_pool(
    goals: list[Goal],
    pool_total: Decimal,
    today: date | None = None,
) -> dict[str, Decimal]:
    """
    Two-pass pool distribution.

    Pass 1 — manual goals (any goal-allocation entries):
      Get their manual_balance. If the sum of all manual balances exceeds the
      pool, prorate them proportionally.

    Pass 2 — auto goals (no goal-allocation entries):
      Split the remaining pool by urgency: 1 / days_remaining, normalized.
      Goals with passed deadlines receive zero.

    Returns attributed balance per goal name (active goals only).
    """
    if today is None:
        today = date.today()

    active = [g for g in goals if not g.archived]
    manual = [g for g in active if g.is_manual]
    auto = [g for g in active if not g.is_manual]

    attributed: dict[str, Decimal] = {}

    # Pass 1: manual goals
    manual_total = sum(g.manual_balance for g in manual)
    if manual_total > pool_total and manual_total > 0:
        for g in manual:
            attributed[g.name] = (g.manual_balance / manual_total) * pool_total
    else:
        for g in manual:
            attributed[g.name] = g.manual_balance

    reserved = sum(attributed.values())
    remaining = max(pool_total - reserved, Decimal("0"))

    # Pass 2: auto goals — weight by 1/days_remaining
    scores: dict[str, Decimal] = {}
    for g in auto:
        if g.deadline <= today:
            continue
        days_remaining = (g.deadline - today).days
        if days_remaining <= 0 or g.target <= 0:
            continue
        scores[g.name] = Decimal("1") / Decimal(str(days_remaining))

    total_score = sum(scores.values())
    for g in auto:
        if g.name in scores and total_score > 0:
            attributed[g.name] = (scores[g.name] / total_score) * remaining
        else:
            attributed[g.name] = Decimal("0")

    return attributed


def compute_urgency_scores_with_balances(
    goals: list[Goal],
    balances: dict[str, Decimal],
    today: date | None = None,
) -> dict[str, Decimal]:
    """
    urgency_score = gap_fraction / days_remaining, normalized.
    gap_fraction = (target - current) / target

    Excludes archived goals, goals with passed deadlines, and fully funded goals.
    Accepts balances as attributed pool balances (from distribute_pool) or
    any per-goal balance dict.
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

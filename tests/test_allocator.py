from datetime import date
from decimal import Decimal

import pytest

from beangoal.allocator import compute_urgency_scores_with_balances, distribute_pool
from beangoal.models import Goal


TODAY = date(2026, 3, 22)


def make_goal(
    name: str,
    target: float,
    deadline: date,
    archived: bool = False,
    contributions: list[tuple[date, float]] | None = None,
) -> Goal:
    g = Goal(name=name, target=Decimal(str(target)), deadline=deadline, archived=archived)
    if contributions:
        g.contributions = [(d, Decimal(str(a))) for d, a in contributions]
    return g


# ── compute_urgency_scores_with_balances ──────────────────────────────────────


def test_single_goal_gets_full_weight():
    goals = [make_goal("house", 100_000, date(2027, 6, 1))]
    balances = {"house": Decimal("50000")}
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    assert scores == {"house": Decimal("1")}


def test_archived_goals_excluded():
    goals = [
        make_goal("house", 100_000, date(2027, 6, 1)),
        make_goal("car", 15_000, date(2026, 12, 1), archived=True),
    ]
    balances = {"house": Decimal("0"), "car": Decimal("0")}
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    assert "car" not in scores
    assert "house" in scores


def test_past_deadline_excluded():
    goals = [
        make_goal("house", 100_000, date(2027, 6, 1)),
        make_goal("old", 5_000, date(2025, 1, 1)),
    ]
    balances = {"house": Decimal("0"), "old": Decimal("0")}
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    assert "old" not in scores
    assert "house" in scores


def test_fully_funded_goal_excluded():
    goals = [
        make_goal("house", 100_000, date(2027, 6, 1)),
        make_goal("car", 15_000, date(2026, 12, 1)),
    ]
    balances = {"house": Decimal("0"), "car": Decimal("15000")}
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    assert "car" not in scores
    assert "house" in scores


def test_scores_sum_to_one():
    goals = [
        make_goal("house", 100_000, date(2027, 6, 1)),
        make_goal("college", 200_000, date(2036, 9, 1)),
        make_goal("car", 15_000, date(2026, 12, 1)),
    ]
    balances = {"house": Decimal("67000"), "college": Decimal("36000"), "car": Decimal("5000")}
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    total = sum(scores.values())
    assert abs(total - Decimal("1")) < Decimal("0.0001")


def test_closer_deadline_gets_higher_weight():
    goals = [
        make_goal("urgent", 10_000, date(2026, 6, 1)),
        make_goal("distant", 10_000, date(2028, 6, 1)),
    ]
    balances = {"urgent": Decimal("5000"), "distant": Decimal("5000")}
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    assert scores["urgent"] > scores["distant"]


def test_larger_gap_gets_higher_weight():
    goals = [
        make_goal("big-gap", 100_000, date(2027, 6, 1)),
        make_goal("small-gap", 100_000, date(2027, 6, 1)),
    ]
    balances = {"big-gap": Decimal("10000"), "small-gap": Decimal("80000")}
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    assert scores["big-gap"] > scores["small-gap"]


def test_no_eligible_goals_returns_empty():
    goals = [make_goal("done", 10_000, date(2026, 12, 1), archived=True)]
    balances = {"done": Decimal("0")}
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    assert scores == {}


def test_all_fully_funded_returns_empty():
    goals = [make_goal("house", 100_000, date(2027, 6, 1))]
    balances = {"house": Decimal("100000")}
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    assert scores == {}


# ── distribute_pool ───────────────────────────────────────────────────────────


def test_all_auto_goals_split_remaining_pool():
    goals = [
        make_goal("house", 100_000, date(2027, 6, 1)),
        make_goal("car", 15_000, date(2026, 12, 1)),
    ]
    attributed = distribute_pool(goals, Decimal("50000"), TODAY)
    # Both are auto; pool should be fully distributed (sums to pool_total)
    total = sum(attributed.values())
    assert abs(total - Decimal("50000")) < Decimal("0.01")


def test_auto_closer_deadline_gets_more():
    goals = [
        make_goal("urgent", 10_000, date(2026, 6, 1)),   # closer
        make_goal("distant", 10_000, date(2028, 6, 1)),  # farther
    ]
    attributed = distribute_pool(goals, Decimal("10000"), TODAY)
    assert attributed["urgent"] > attributed["distant"]


def test_manual_goal_gets_its_exact_balance():
    goals = [
        make_goal("college", 200_000, date(2036, 9, 1), contributions=[(date(2024, 6, 1), 36_000)]),
        make_goal("house", 100_000, date(2027, 6, 1)),
    ]
    attributed = distribute_pool(goals, Decimal("100000"), TODAY)
    assert attributed["college"] == Decimal("36000")
    # house gets the remaining 64000
    assert abs(attributed["house"] - Decimal("64000")) < Decimal("0.01")


def test_manual_goals_prorated_when_exceed_pool():
    """If manual allocations sum to more than the pool, they're prorated."""
    goals = [
        make_goal("a", 100_000, date(2027, 6, 1), contributions=[(date(2024, 1, 1), 60_000)]),
        make_goal("b", 100_000, date(2027, 6, 1), contributions=[(date(2024, 1, 1), 60_000)]),
    ]
    pool = Decimal("100000")
    attributed = distribute_pool(goals, pool, TODAY)
    # Both have equal manual balance so should each get 50000
    assert abs(attributed["a"] - Decimal("50000")) < Decimal("0.01")
    assert abs(attributed["b"] - Decimal("50000")) < Decimal("0.01")
    total = sum(attributed.values())
    assert abs(total - pool) < Decimal("0.01")


def test_archived_goals_excluded_from_distribution():
    goals = [
        make_goal("house", 100_000, date(2027, 6, 1)),
        make_goal("old", 5_000, date(2025, 1, 1), archived=True),
    ]
    attributed = distribute_pool(goals, Decimal("50000"), TODAY)
    assert "old" not in attributed
    assert "house" in attributed


def test_past_deadline_auto_goal_gets_zero():
    goals = [
        make_goal("house", 100_000, date(2027, 6, 1)),
        make_goal("missed", 10_000, date(2025, 1, 1)),  # past, auto
    ]
    attributed = distribute_pool(goals, Decimal("50000"), TODAY)
    assert attributed["missed"] == Decimal("0")
    # house gets the full pool since missed is excluded from scoring
    assert abs(attributed["house"] - Decimal("50000")) < Decimal("0.01")


def test_auto_goal_capped_at_target_excess_redistributed():
    """A small-target urgent goal should not receive more than its target."""
    goals = [
        make_goal("house", 100_000, date(2030, 5, 1)),       # large target, far deadline
        make_goal("fridge", 1_200, date(2026, 12, 1)),        # small target, near deadline
    ]
    attributed = distribute_pool(goals, Decimal("117609"), TODAY)
    assert attributed["fridge"] <= Decimal("1200")
    assert attributed["house"] <= Decimal("100000")
    # Both goals can be fully funded; excess stays in pool (unallocated)
    total = sum(attributed.values())
    assert total <= Decimal("117609")


def test_multiple_auto_goals_capped_excess_redistributed():
    """Multiple small-target urgent goals should all be capped; excess goes to larger goals."""
    goals = [
        make_goal("house", 80_000, date(2030, 5, 1)),
        make_goal("car", 40_000, date(2028, 9, 1)),
        make_goal("fridge", 1_200, date(2026, 12, 1)),
        make_goal("dishwasher", 700, date(2026, 12, 1)),
    ]
    attributed = distribute_pool(goals, Decimal("117609"), TODAY)
    assert attributed["fridge"] <= Decimal("1200")
    assert attributed["dishwasher"] <= Decimal("700")
    assert attributed["car"] <= Decimal("40000")
    assert attributed["house"] <= Decimal("80000")
    total = sum(attributed.values())
    assert abs(total - Decimal("117609")) < Decimal("0.01")


def test_multiple_manual_contributions_use_sum():
    goals = [
        make_goal(
            "college", 200_000, date(2036, 9, 1),
            contributions=[
                (date(2024, 6, 1), 10_000),
                (date(2024, 12, 1), 8_000),
                (date(2025, 6, 1), 9_000),
            ],
        ),
    ]
    attributed = distribute_pool(goals, Decimal("100000"), TODAY)
    assert attributed["college"] == Decimal("27000")

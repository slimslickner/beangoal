from datetime import date
from decimal import Decimal

import pytest

from beangoal.allocator import compute_urgency_scores_with_balances
from beangoal.models import Goal


TODAY = date(2026, 3, 22)


def make_goal(name: str, target: float, deadline: date, archived: bool = False) -> Goal:
    return Goal(name=name, target=Decimal(str(target)), deadline=deadline, archived=archived)


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
        make_goal("old", 5_000, date(2025, 1, 1)),  # past
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
    balances = {"house": Decimal("0"), "car": Decimal("15000")}  # car fully funded
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    assert "car" not in scores
    assert "house" in scores


def test_scores_sum_to_one():
    goals = [
        make_goal("house", 100_000, date(2027, 6, 1)),
        make_goal("college", 200_000, date(2036, 9, 1)),
        make_goal("car", 15_000, date(2026, 12, 1)),
    ]
    balances = {
        "house": Decimal("67000"),
        "college": Decimal("36000"),
        "car": Decimal("5000"),
    }
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    total = sum(scores.values())
    assert abs(total - Decimal("1")) < Decimal("0.0001")


def test_closer_deadline_gets_higher_weight():
    """A goal with a closer deadline and same gap fraction should score higher."""
    goals = [
        make_goal("urgent", 10_000, date(2026, 6, 1)),   # ~70 days away
        make_goal("distant", 10_000, date(2028, 6, 1)),  # ~800 days away
    ]
    balances = {"urgent": Decimal("5000"), "distant": Decimal("5000")}
    scores = compute_urgency_scores_with_balances(goals, balances, TODAY)
    assert scores["urgent"] > scores["distant"]


def test_larger_gap_gets_higher_weight():
    """Same deadline, bigger remaining gap → higher score."""
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

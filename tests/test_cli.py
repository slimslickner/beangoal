import tempfile
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from beangoal.cli import cli

EXAMPLE_DIR = Path(__file__).parent.parent / "example"
LEDGER = str(EXAMPLE_DIR / "ledger.beancount")
GOALS = str(EXAMPLE_DIR / "goals.beancount")


@pytest.fixture
def runner():
    return CliRunner()


def invoke(runner, *args):
    return runner.invoke(cli, ["--ledger", LEDGER, "--goals", GOALS, *args])


# ── status ────────────────────────────────────────────────────────────────────


def test_status_exits_zero(runner):
    result = invoke(runner, "status")
    assert result.exit_code == 0


def test_status_shows_pool_total(runner):
    result = invoke(runner, "status")
    assert "Pool" in result.output


def test_status_shows_goal_names(runner):
    result = invoke(runner, "status")
    assert "house-down-payment" in result.output
    assert "college-fund" in result.output
    assert "car" in result.output


def test_status_shows_progress_bar(runner):
    result = invoke(runner, "status")
    assert "█" in result.output


def test_status_shows_manual_and_auto_labels(runner):
    result = invoke(runner, "status")
    assert "manual" in result.output  # college-fund has contributions
    assert "auto" in result.output    # house and car are auto


def test_status_hides_archived_by_default(runner):
    result = invoke(runner, "status")
    assert "Archived" not in result.output


def test_status_show_archived_flag(runner):
    goals = tempfile.NamedTemporaryFile(mode="w", suffix=".beancount", delete=False)
    goals.write(textwrap.dedent("""\
        2024-01-01 custom "savings-goal"          "house" "100000" "2027-06-01"
        2024-01-01 custom "savings-goal-archived" "done"  "5000"   "2023-01-01"
        2024-01-01 custom "cash-account"          "Assets:Checking"
        2024-01-01 custom "expense-accounts"      "Expenses"
    """))
    goals.flush()

    result = runner.invoke(cli, ["--ledger", LEDGER, "--goals", goals.name, "status", "--show-archived"])
    assert result.exit_code == 0
    assert "Archived" in result.output
    assert "done" in result.output


def test_status_show_contributions_flag(runner):
    result = invoke(runner, "status", "--show-contributions")
    assert result.exit_code == 0
    # college-fund has contributions — individual dates should appear
    assert "2024-06-01" in result.output
    assert "2024-12-01" in result.output


# ── surplus ───────────────────────────────────────────────────────────────────


def test_surplus_exits_zero(runner):
    result = invoke(runner, "surplus")
    assert result.exit_code == 0


def test_surplus_shows_labels(runner):
    result = invoke(runner, "surplus")
    assert "Cash accounts total" in result.output
    assert "Avg monthly expenses" in result.output
    assert "Operating buffer" in result.output
    assert "Allocatable surplus" in result.output


def test_surplus_buffer_months_flag(runner):
    r1 = invoke(runner, "--buffer-months", "1", "surplus")
    r6 = invoke(runner, "--buffer-months", "6", "surplus")
    assert r1.exit_code == 0
    assert r6.exit_code == 0
    assert r1.output != r6.output


# ── allocate ──────────────────────────────────────────────────────────────────


def test_allocate_exits_zero(runner):
    result = invoke(runner, "allocate", "2000")
    assert result.exit_code == 0


def test_allocate_shows_amount(runner):
    result = invoke(runner, "allocate", "2000")
    assert "2,000.00" in result.output


def test_allocate_shows_transaction(runner):
    result = invoke(runner, "allocate", "1000")
    assert "Savings allocation" in result.output


def test_allocate_shows_goal_allocation_directives(runner):
    result = invoke(runner, "allocate", "1000")
    assert 'goal-allocation' in result.output


def test_allocate_no_eligible_goals(runner):
    """All goals archived → graceful message."""
    goals = tempfile.NamedTemporaryFile(mode="w", suffix=".beancount", delete=False)
    goals.write(textwrap.dedent("""\
        2024-01-01 custom "savings-goal-archived" "old" "5000" "2023-01-01"
        2024-01-01 custom "cash-account" "Assets:Checking"
        2024-01-01 custom "expense-accounts" "Expenses"
    """))
    goals.flush()

    result = runner.invoke(cli, ["--ledger", LEDGER, "--goals", goals.name, "allocate", "1000"])
    assert result.exit_code == 0
    assert "No active goals" in result.output


# ── archive ───────────────────────────────────────────────────────────────────


def test_archive_exits_zero(runner):
    result = invoke(runner, "archive", "car")
    assert result.exit_code == 0


def test_archive_shows_remove_and_add(runner):
    result = invoke(runner, "archive", "car")
    assert "REMOVE" in result.output
    assert "ADD" in result.output
    assert "savings-goal-archived" in result.output
    assert "car" in result.output


def test_archive_unknown_goal_exits_nonzero(runner):
    result = invoke(runner, "archive", "nonexistent-goal")
    assert result.exit_code != 0


# ── error handling ────────────────────────────────────────────────────────────


def test_missing_ledger_exits_nonzero(runner):
    result = runner.invoke(cli, ["--ledger", "/nonexistent/path.beancount", "--goals", GOALS, "status"])
    assert result.exit_code != 0


def test_missing_goals_exits_nonzero(runner):
    result = runner.invoke(cli, ["--ledger", LEDGER, "--goals", "/nonexistent/goals.beancount", "status"])
    assert result.exit_code != 0

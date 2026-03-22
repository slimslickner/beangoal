from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class Goal:
    name: str
    target: Decimal
    deadline: date
    linked_accounts: list[str] = field(default_factory=list)
    archived: bool = False


@dataclass
class Config:
    goals: list[Goal]
    cash_accounts: list[str]
    expense_roots: list[str]
    income_roots: list[str]
    expense_excludes: list[str]

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class Goal:
    name: str
    target: Decimal
    deadline: date
    contributions: list[tuple[date, Decimal]] = field(default_factory=list)
    archived: bool = False

    @property
    def manual_balance(self) -> Decimal:
        return sum((amount for _, amount in self.contributions), Decimal("0"))

    @property
    def is_manual(self) -> bool:
        return bool(self.contributions)


@dataclass
class Config:
    goals: list[Goal]
    cash_accounts: list[str]
    expense_roots: list[str]
    income_roots: list[str]
    expense_excludes: list[str]
    expense_transfer_accounts: list[str] = field(default_factory=list)

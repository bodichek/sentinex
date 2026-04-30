"""Specialist agents registry."""

from __future__ import annotations

from apps.agents.base import BaseSpecialist
from apps.agents.specialists.finance import FinanceSpecialist
from apps.agents.specialists.knowledge import KnowledgeSpecialist
from apps.agents.specialists.ops import OpsSpecialist
from apps.agents.specialists.people import PeopleSpecialist
from apps.agents.specialists.strategic import StrategicSpecialist

REGISTRY: dict[str, type[BaseSpecialist]] = {
    StrategicSpecialist.name: StrategicSpecialist,
    FinanceSpecialist.name: FinanceSpecialist,
    PeopleSpecialist.name: PeopleSpecialist,
    OpsSpecialist.name: OpsSpecialist,
    KnowledgeSpecialist.name: KnowledgeSpecialist,
}

__all__ = [
    "REGISTRY",
    "FinanceSpecialist",
    "KnowledgeSpecialist",
    "OpsSpecialist",
    "PeopleSpecialist",
    "StrategicSpecialist",
]

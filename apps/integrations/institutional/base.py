"""Contrato InstitutionalDataProvider (SPEC §39).

La lógica de negocio solo conoce este contrato: sustituir `LocalProvider` por
`SGAProvider` (BE-T19) no debe cambiar nada fuera de `get_provider()`.
Los métodos devuelven estructuras inmutables y solo datos del propio usuario.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal


class ProviderError(Exception):
    """Fallo del proveedor (caído, timeout, respuesta inválida). La solicitud no se pierde."""


class StudentNotFound(ProviderError):
    """El usuario no figura en el sistema institucional (sin `external_id` o sin registro)."""


@dataclass(frozen=True)
class ScheduleEntry:
    day: date
    start: time
    end: time
    subject: str
    room: str


@dataclass(frozen=True)
class Grade:
    subject: str
    period: str
    value: Decimal
    status: str  # p. ej. «Aprobado», «En curso»


@dataclass(frozen=True)
class DebtItem:
    concept: str
    amount: Decimal
    due_date: date


@dataclass(frozen=True)
class DebtSummary:
    total: Decimal
    currency: str
    items: tuple[DebtItem, ...]


@dataclass(frozen=True)
class Enrollment:
    period: str
    program: str
    status: str


@dataclass(frozen=True)
class Subject:
    code: str
    name: str
    credits: int


class InstitutionalDataProvider(ABC):
    @abstractmethod
    def get_schedule(self, user, date=None) -> list[ScheduleEntry]: ...

    @abstractmethod
    def get_grades(self, user, period=None) -> list[Grade]: ...

    @abstractmethod
    def get_debt(self, user) -> DebtSummary: ...

    @abstractmethod
    def get_enrollment(self, user, period=None) -> Enrollment: ...

    @abstractmethod
    def get_subjects(self, user, period=None) -> list[Subject]: ...

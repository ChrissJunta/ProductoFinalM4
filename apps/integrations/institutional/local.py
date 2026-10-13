"""LocalProvider (SPEC §40): datos institucionales simulados para el MVP.

Los datos viven en `local_data.json`, indexados por `User.external_id`. No son
tablas: el MVP no administra datos académicos, solo los consulta.
"""

import json
from datetime import time, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path

from django.utils import timezone

from .base import (
    DebtItem,
    DebtSummary,
    Enrollment,
    Grade,
    InstitutionalDataProvider,
    ScheduleEntry,
    StudentNotFound,
    Subject,
)

DATA_FILE = Path(__file__).with_name("local_data.json")
WEEKDAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


@cache
def _load(path=DATA_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class LocalProvider(InstitutionalDataProvider):
    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file

    def _student(self, user):
        external_id = getattr(user, "external_id", "")
        record = _load(self.data_file)["students"].get(external_id) if external_id else None
        if record is None:
            raise StudentNotFound(f"Sin registro institucional para {user.username}.")
        return record

    def _period(self, record, period):
        return period or record["current_period"]

    def get_schedule(self, user, date=None):
        record = self._student(user)
        day = date or timezone.localdate()
        weekday = WEEKDAYS[day.weekday()]
        return [
            ScheduleEntry(
                day=day,
                start=time.fromisoformat(s["start"]),
                end=time.fromisoformat(s["end"]),
                subject=s["subject"],
                room=s["room"],
            )
            for s in record["schedule"]
            if s["day"] == weekday
        ]

    def get_grades(self, user, period=None):
        record = self._student(user)
        period = self._period(record, period)
        return [
            Grade(
                subject=g["subject"],
                period=period,
                value=Decimal(g["value"]),
                status=g["status"],
            )
            for g in record["grades"].get(period, [])
        ]

    def get_debt(self, user):
        record = self._student(user)
        today = timezone.localdate()
        items = tuple(
            DebtItem(
                concept=d["concept"],
                amount=Decimal(d["amount"]),
                due_date=today + timedelta(days=d["due_in_days"]),
            )
            for d in record["debt"]
        )
        return DebtSummary(
            total=sum((i.amount for i in items), Decimal("0")),
            currency=record.get("currency", "USD"),
            items=items,
        )

    def get_enrollment(self, user, period=None):
        record = self._student(user)
        period = self._period(record, period)
        e = record["enrollment"].get(period)
        if e is None:
            return Enrollment(period=period, program=record["program"], status="Sin matrícula")
        return Enrollment(period=period, program=record["program"], status=e["status"])

    def get_subjects(self, user, period=None):
        record = self._student(user)
        period = self._period(record, period)
        return [
            Subject(code=s["code"], name=s["name"], credits=s["credits"])
            for s in record["subjects"].get(period, [])
        ]

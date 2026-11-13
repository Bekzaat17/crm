"""Период отчёта: даты в часовом поясе пользователя и шаг группировки."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone

from crm.core.errors import ApiError

MAX_DAYS = 731
DEFAULT_DAYS = 30


@dataclass(frozen=True)
class Period:
    first: date
    last: date  # включительно
    tz: ZoneInfo

    @property
    def days(self):
        return (self.last - self.first).days + 1

    @property
    def start(self):
        return datetime.combine(self.first, time.min, self.tz)

    @property
    def end(self):
        return datetime.combine(self.last + timedelta(days=1), time.min, self.tz)

    @property
    def bucket(self):
        if self.days <= 7:
            return "day"
        return "week" if self.days <= 92 else "month"

    def previous(self):
        length = timedelta(days=self.days)
        return Period(self.first - length, self.first - timedelta(days=1), self.tz)

    def bucket_of(self, moment):
        day = timezone.localtime(moment, self.tz).date()
        if self.bucket == "week":
            return day - timedelta(days=day.weekday())
        if self.bucket == "month":
            return day.replace(day=1)
        return day

    def buckets(self):
        current, result = self.bucket_of(self.start), []
        while current <= self.last:
            result.append(current)
            if self.bucket == "day":
                current += timedelta(days=1)
            elif self.bucket == "week":
                current += timedelta(days=7)
            else:
                current = (current + timedelta(days=32)).replace(day=1)
        return result


def _zone(value):
    try:
        return ZoneInfo(value or settings.TIME_ZONE)
    except (ZoneInfoNotFoundError, ValueError):
        raise ApiError("Неизвестный часовой пояс.")


def _date(value, label):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ApiError(f"Укажите {label} в формате ГГГГ-ММ-ДД.")


def parse_period(query):
    tz = _zone(query.get("tz"))
    today = timezone.localtime(timezone.now(), tz).date()
    last = _date(query["to"], "дату окончания") if query.get("to") else today
    first = (
        _date(query["from"], "дату начала")
        if query.get("from")
        else last - timedelta(days=DEFAULT_DAYS - 1)
    )
    if first > last:
        raise ApiError("Дата начала позже даты окончания.")
    if (last - first).days + 1 > MAX_DAYS:
        raise ApiError("Период не может быть длиннее двух лет.")
    return Period(first, last, tz)

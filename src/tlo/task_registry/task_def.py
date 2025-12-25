"""Data structures describing background task registrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from string import Formatter
from typing import TYPE_CHECKING, Any, Final, Protocol, runtime_checkable

from hv_utils.cron import parse_cron

from tlo.errors import TloConfigError

if TYPE_CHECKING:
    from tlo.tlo_types import FuncName, TTaskFunc


DECEMBER: Final[int] = 12
ALL_DAYS_OF_MONTH: Final[tuple[int, ...]] = tuple(range(1, 32))
ALL_DAYS_OF_WEEK: Final[tuple[int, ...]] = tuple(range(7))


@runtime_checkable
class ScheduleProtocol(Protocol):
    """Interface for defining execution schedules."""

    def next_run_after(self, last_run: datetime) -> datetime:
        """Calculate the next execution time after the given timestamp.

        :param last_run: The timestamp of the last execution (or creation time).
        :return: The next scheduled execution time.
        """


class CronSchedule(ScheduleProtocol):
    """Schedule based on a cron expression."""

    def __init__(self, expression: str) -> None:
        """Initialize a cron schedule.

        :param expression: A standard 5-field cron expression.
        """
        self.expression = expression
        self.schedule = parse_cron(expression)

    def next_run_after(self, last_run: datetime) -> datetime:
        """Calculate the next run time based on the cron schedule."""
        # Start checking from the next minute to avoid immediate re-execution
        # if last_run matches the schedule exactly.
        current = last_run.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Safety limit to prevent infinite loops (e.g., searching for Feb 30th)
        # 10 years seems like a reasonable upper bound for a next run.
        limit = current + timedelta(days=365 * 10)

        while current < limit:
            if current.month not in self.schedule.month:
                # Jump to next month
                if current.month == DECEMBER:
                    current = current.replace(year=current.year + 1, month=1, day=1, hour=0, minute=0)
                else:
                    current = current.replace(month=current.month + 1, day=1, hour=0, minute=0)
                continue

            # Check day of week
            # Python's weekday(): Mon=0, Sun=6.
            # Cron's day_of_week: Sun=0, Sat=6.
            # So we map Python's (d + 1) % 7 to get Cron's.
            cron_dow = (current.weekday() + 1) % 7

            dom_matches = current.day in self.schedule.day_of_month
            dow_matches = cron_dow in self.schedule.day_of_week

            dom_wildcard = self.schedule.day_of_month == ALL_DAYS_OF_MONTH
            dow_wildcard = self.schedule.day_of_week == ALL_DAYS_OF_WEEK

            # Cron spec: when both DOM and DOW are constrained, the expression matches if either
            # field matches. If one field is wildcard, the other must match.
            if dom_wildcard and dow_wildcard:
                pass
            elif (
                (dom_wildcard and not dow_matches)
                or (dow_wildcard and not dom_matches)
                or not (dom_matches or dow_matches)
            ):
                current += timedelta(days=1)
                current = current.replace(hour=0, minute=0)
                continue

            if current.hour not in self.schedule.hour:
                # Jump to next hour
                current += timedelta(hours=1)
                current = current.replace(minute=0)
                continue

            if current.minute not in self.schedule.minute:
                # Jump to next minute
                current += timedelta(minutes=1)
                continue

            return current

        msg = f"Could not find next run time for cron expression {self.expression!r} within 10 years."
        raise TloConfigError(msg)


class IntervalSchedule(ScheduleProtocol):
    """Schedule based on a fixed interval."""

    __slots__ = ("interval",)

    def __init__(self, interval: timedelta | int) -> None:
        """Initialise a schedule based on a fixed interval."""
        self.interval = self._initialize_interval(interval)

    def _initialize_interval(self, interval: timedelta | int) -> timedelta:
        if isinstance(interval, int):
            interval = timedelta(seconds=interval)
        if interval <= timedelta(0):
            msg = f"Interval must be positive, got {interval!r} instead."
            raise TloConfigError(msg)
        return interval

    def next_run_after(self, last_run: datetime) -> datetime:
        """Return the next run time by adding the interval to the last run time."""
        return last_run + self.interval


@dataclass(slots=True)
class TaskDef:
    """Store metadata about a callable that was registered as a background task.

    :param func: Callable executed when the task is dispatched.
    :param name: Name under which the task is registered.
    :param extra: Arbitrary metadata provided at registration time.
    :param schedule: Optional schedule definition.
    :param exclusive: Whether the task must be executed exclusively.
    """

    func: TTaskFunc
    name: FuncName
    extra: dict[str, Any] = field(default_factory=dict)
    schedule: ScheduleProtocol | None = None
    exclusive_template: str | None = None

    def render_exclusive_key(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
        """Return rendered exclusivity key using ``str.format`` with task call args/kwargs."""
        if self.exclusive_template is None:
            return None

        formatter = Formatter()
        try:
            return formatter.vformat(self.exclusive_template, args, kwargs)
        except KeyError as exc:
            msg = f"Missing key {exc!s} required for exclusive template {self.exclusive_template!r}"
            raise TloConfigError(msg) from exc

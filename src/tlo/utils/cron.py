"""Cron expression parser utilities.

This module provides functionality to parse standard five-field cron expressions
into explicit integer schedules.
"""

from __future__ import annotations

from typing import Final, NamedTuple

__all__ = ["CronSchedule", "parse_cron"]

EXPECTED_FIELD_COUNT: Final[int] = 5

FIELD_RANGES = {
    "minutes": tuple(range(60)),
    "hours": tuple(range(24)),
    "day_of_month": tuple(range(1, 32)),
    "month": tuple(range(1, 13)),
    "day_of_week": tuple(range(7)),
}

DAY_NAME_TO_INDEX = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}
MONTH_NAME_TO_INDEX = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


class CronSchedule(NamedTuple):
    """Structured representation of the five cron fields.

    Each attribute contains a tuple of integer values that represent the
    concrete schedule derived from the raw cron expression.
    """

    minute: tuple[int, ...]
    hour: tuple[int, ...]
    day_of_month: tuple[int, ...]
    month: tuple[int, ...]
    day_of_week: tuple[int, ...]

    @property
    def dom(self) -> tuple[int, ...]:
        """Alias for ``day_of_month`` property."""
        return self.day_of_month

    @property
    def dow(self) -> tuple[int, ...]:
        """Alias for ``day_of_week`` property."""
        return self.day_of_week


def parse_cron(expression: str) -> CronSchedule:
    """Parse a cron expression into explicit field values.

    The parser expects the traditional five-field format: minute, hour,
    day of month, month, and day of week. Each field supports single
    values, ranges, steps (``*/n``), and comma-separated lists.

    :param expression: Raw cron expression using space-separated fields.
    :returns: A :class:`CronSchedule` with sorted integer values per field.
    :raises ValueError: If the expression has invalid syntax or values.
    """
    expression_parts = expression.split()
    if len(expression_parts) != EXPECTED_FIELD_COUNT:
        raise _invalid_cron_expression(expression)

    minutes, hours, day_of_month, month, day_of_week = expression_parts
    try:
        return CronSchedule(
            minute=_parse_expression(minutes, FIELD_RANGES["minutes"]),
            hour=_parse_expression(hours, FIELD_RANGES["hours"]),
            day_of_month=_parse_expression(day_of_month, FIELD_RANGES["day_of_month"]),
            month=_parse_expression(
                month, FIELD_RANGES["month"], transform_map=MONTH_NAME_TO_INDEX
            ),
            day_of_week=_parse_expression(
                day_of_week, FIELD_RANGES["day_of_week"], transform_map=DAY_NAME_TO_INDEX
            ),
        )
    except ValueError as exc:
        raise _invalid_cron_expression(expression) from exc


def _parse_expression(
    expr: str, allowed: tuple[int, ...], transform_map: dict[str, int] | None = None
) -> tuple[int, ...]:
    """Expand a comma-delimited cron field into explicit integers."""
    parts = expr.split(",")
    result: set[int] = set()
    try:
        for part in parts:
            values = _parse_part(part, allowed, transform_map)
            result.update(values)
    except ValueError as exc:
        raise _invalid_cron_expression(expr) from exc

    return tuple(sorted(result))


def _parse_part(
    part: str, allowed: tuple[int, ...], transform_map: dict[str, int] | None = None
) -> tuple[int, ...]:
    """Interpret a single cron token."""
    transform_map = transform_map or {}
    value_expr, step_expr = _expr_to_parts(part)

    if step_expr >= len(allowed):
        raise _invalid_cron_expression(part)

    if value_expr in transform_map:
        value_expr = str(transform_map[value_expr])

    if value_expr.isdigit():
        if step_expr != 1:
            raise _invalid_cron_expression(part)
        if int(value_expr) not in allowed:
            raise _invalid_cron_expression(part)
        return (int(value_expr),)

    if value_expr == "*":
        return tuple(range(allowed[0], allowed[-1] + 1, step_expr))

    if "-" in value_expr and (
        result := _parse_range(value_expr, allowed, step_expr, transform_map)
    ):
        return result

    raise _invalid_cron_expression(part)


def _parse_range(
    value_expr: str, allowed: tuple[int, ...], step_expr: int, transform_map: dict[str, int]
) -> tuple[int, ...]:
    start, end = value_expr.split("-")
    if start in transform_map:
        start = str(transform_map[start])
    if end in transform_map:
        end = str(transform_map[end])
    start_int, end_int = int(start), int(end)
    if start_int not in allowed or end_int not in allowed:
        raise _invalid_cron_expression(value_expr)
    if start_int > end_int:
        raise _invalid_cron_expression(value_expr)
    result = tuple(range(start_int, end_int + 1, step_expr))
    if not result:
        raise _invalid_cron_expression(value_expr)
    return result


def _invalid_cron_expression(expr: str) -> ValueError:
    """Build a standardised :class:`ValueError` for invalid cron input."""
    return ValueError(f"{expr!r} is not valid cron expression.")


def _expr_to_parts(expr: str) -> tuple[str, int]:
    """Split a cron token into its base expression and step."""
    if "/" in expr:
        value_expr, step_expr = expr.split("/")
        if not step_expr.isdigit():
            raise _invalid_cron_expression(expr)
        step_expr_int = int(step_expr)
    else:
        value_expr, step_expr_int = expr, 1

    return value_expr, step_expr_int

"""Integration-style tests for schedule calculation helpers."""

from datetime import UTC, datetime, timedelta

from tlo.task_registry.task_def import CronSchedule, IntervalSchedule


def test_interval_schedule_next_run() -> None:
    """IntervalSchedule should advance by configured delta."""
    start = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    schedule = IntervalSchedule(timedelta(minutes=10))

    next_run = schedule.next_run_after(start)
    assert next_run == start + timedelta(minutes=10)


def test_cron_schedule_next_run_simple() -> None:
    """CronSchedule should schedule the next minute for wildcard cron."""
    # Every minute
    schedule = CronSchedule("* * * * *")
    start = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)

    next_run = schedule.next_run_after(start)
    assert next_run == datetime(2023, 1, 1, 12, 1, 0, tzinfo=UTC)


def test_cron_schedule_next_run_specific_time() -> None:
    """CronSchedule should return the next matching daily window."""
    # At 12:30 every day
    schedule = CronSchedule("30 12 * * *")
    start = datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)

    next_run = schedule.next_run_after(start)
    assert next_run == datetime(2023, 1, 1, 12, 30, 0, tzinfo=UTC)

    # If run at 12:30, next run should be tomorrow
    next_run_2 = schedule.next_run_after(next_run)
    assert next_run_2 == datetime(2023, 1, 2, 12, 30, 0, tzinfo=UTC)


def test_cron_schedule_next_run_complex() -> None:
    """CronSchedule should advance across months for sparse schedules."""
    # At minute 5 past hour 4 on day-of-month 1
    schedule = CronSchedule("5 4 1 * *")
    start = datetime(2023, 1, 20, 12, 0, 0, tzinfo=UTC)

    # Should jump to Feb 1st
    next_run = schedule.next_run_after(start)
    assert next_run == datetime(2023, 2, 1, 4, 5, 0, tzinfo=UTC)


def test_cron_schedule_dom_or_dow_semantics() -> None:
    """CronSchedule should fire when either day-of-month or day-of-week matches."""
    # At 09:00 on the 1st of the month OR every Monday
    schedule = CronSchedule("0 9 1 * MON")
    start = datetime(2023, 1, 1, 9, 0, 0, tzinfo=UTC)  # Sunday, 1st of the month

    next_run = schedule.next_run_after(start)
    assert next_run == datetime(2023, 1, 2, 9, 0, 0, tzinfo=UTC)  # Monday (day-of-week match)

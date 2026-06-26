from datetime import date, datetime, time, timedelta, timezone


def working_days(start: date, end: date) -> int:
    """Count Mon-Fri days inclusive between two dates."""
    days = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # 0=Mon ... 4=Fri
            days += 1
        cur += timedelta(days=1)
    return days


def sprint_end_date(start: date, weeks: int = 2) -> date:
    """Last working day (Friday) of a sprint that starts on a Monday.

    A 2-week sprint Mon->Fri spans 10 working days; the final Friday is
    start + (weeks*7 - 3) days.
    """
    return start + timedelta(days=weeks * 7 - 3)


def _to_dt(d: date, end_of_day: bool = False) -> datetime:
    t = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(d, t, tzinfo=timezone.utc)


def build_sprints(
    start: date,
    count: int,
    weeks: int = 2,
    name_prefix: str = "Sprint",
    manday: float | None = None,
) -> list[dict]:
    """Generate `count` consecutive sprints. Each starts on a Monday and ends
    on the Friday of its final week. The next sprint starts the following
    Monday."""
    if start.weekday() != 0:
        # snap forward to the next Monday
        start = start + timedelta(days=(7 - start.weekday()) % 7)

    sprints: list[dict] = []
    cur = start
    for i in range(1, count + 1):
        end = sprint_end_date(cur, weeks)
        sprints.append(
            {
                "name": f"{name_prefix} {i}",
                "start_date": _to_dt(cur),
                "end_date": _to_dt(end, end_of_day=True),
                "working_days": working_days(cur, end),
                "weeks": weeks,
                "goal": "",
                "status": "planned",
                "manday": manday,
            }
        )
        cur = cur + timedelta(weeks=weeks)  # next Monday
    return sprints

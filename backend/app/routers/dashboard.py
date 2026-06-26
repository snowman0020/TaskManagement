from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _hours_between(a: datetime, b: datetime) -> float:
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return round((b - a).total_seconds() / 3600.0, 2)


@router.get("/overview")
async def overview(
    sprint_id: str | None = Query(default=None),
    _=Depends(get_current_user),
):
    db = get_db()
    query: dict = {}
    if sprint_id:
        query["sprint_id"] = sprint_id

    cols = await db.status_columns.find().sort("order", 1).to_list(100)
    done_keys = {c["key"] for c in cols if c.get("is_done")}
    if not done_keys and cols:
        done_keys = {cols[-1]["key"]}

    tasks = await db.tasks.find(query).to_list(10000)

    total = len(tasks)
    by_status: dict[str, int] = {c["key"]: 0 for c in cols}
    by_priority: dict[str, int] = {}
    by_assignee: dict[str, int] = {}
    points_total = 0
    points_done = 0

    lead_times: list[float] = []   # created -> done
    cycle_times: list[float] = []  # started -> done

    for t in tasks:
        by_status[t.get("status", "")] = by_status.get(t.get("status", ""), 0) + 1
        by_priority[t.get("priority", "medium")] = (
            by_priority.get(t.get("priority", "medium"), 0) + 1
        )
        a = t.get("assignee_id") or "unassigned"
        by_assignee[a] = by_assignee.get(a, 0) + 1

        sp = t.get("story_points") or 0
        points_total += sp

        if t.get("status") in done_keys and t.get("done_at"):
            points_done += sp
            if t.get("created_at"):
                lead_times.append(_hours_between(t["created_at"], t["done_at"]))
            if t.get("started_at"):
                cycle_times.append(_hours_between(t["started_at"], t["done_at"]))

    done_count = sum(by_status.get(k, 0) for k in done_keys)

    def avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    return {
        "total_tasks": total,
        "done_tasks": done_count,
        "completion_rate": round(done_count / total * 100, 1) if total else 0.0,
        "by_status": by_status,
        "by_priority": by_priority,
        "by_assignee": by_assignee,
        "story_points": {"total": points_total, "done": points_done},
        "leadtime_hours": {
            "avg": avg(lead_times),
            "min": round(min(lead_times), 2) if lead_times else 0.0,
            "max": round(max(lead_times), 2) if lead_times else 0.0,
            "samples": len(lead_times),
        },
        "cycletime_hours": {
            "avg": avg(cycle_times),
            "samples": len(cycle_times),
        },
    }

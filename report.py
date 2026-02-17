"""HTML report generation using Jinja2."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ics_parser import build_timeslots, group_by_day
from models import CET, Profile, ScoredEvent

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent / "output"

# Conflict group colors for visual distinction
CONFLICT_COLORS = [
    "#dc2626", "#2563eb", "#9333ea", "#ca8a04",
    "#0891b2", "#c026d3", "#059669", "#e11d48",
]


def _build_conflict_groups(timeslot_events: list[ScoredEvent]) -> list[list[int]]:
    """Build groups of mutually conflicting event indices."""
    n = len(timeslot_events)
    visited = [False] * n
    groups = []

    for i in range(n):
        if visited[i]:
            continue
        group = [i]
        visited[i] = True
        for j in range(i + 1, n):
            if visited[j]:
                continue
            # Check if j conflicts with any event already in group
            for gi in group:
                if timeslot_events[gi].event.conflicts_with(timeslot_events[j].event):
                    group.append(j)
                    visited[j] = True
                    break
        if len(group) > 1:
            groups.append(group)

    return groups


def _annotate_conflicts(timeslot_events: list[ScoredEvent]) -> list[dict]:
    """Annotate each event with conflict info for the template."""
    groups = _build_conflict_groups(timeslot_events)

    # Map event index -> (group_id, color, conflicting_titles)
    conflict_map: dict[int, dict] = {}
    for gid, group in enumerate(groups):
        color = CONFLICT_COLORS[gid % len(CONFLICT_COLORS)]
        titles = [timeslot_events[i].event.summary for i in group]
        for idx in group:
            others = [t for t in titles if t != timeslot_events[idx].event.summary]
            conflict_map[idx] = {
                "group_id": gid + 1,
                "color": color,
                "conflicts_with": others,
                "group_size": len(group),
                "best_in_group": idx == max(group, key=lambda i: timeslot_events[i].score),
            }

    annotated = []
    for i, se in enumerate(timeslot_events):
        info = conflict_map.get(i)
        annotated.append({
            "scored_event": se,
            "conflict": info,
        })
    return annotated


def generate_report(
    scored_events: list[ScoredEvent],
    profile: Profile,
    provider_name: str = "",
    output_path: str | Path | None = None,
    min_score: int = 0,
) -> Path:
    """Generate an HTML report from scored events."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        safe_name = profile.name.lower().replace(" ", "_")
        output_path = OUTPUT_DIR / f"kubecon_{safe_name}.html"
    else:
        output_path = Path(output_path)

    # Filter by min score
    if min_score > 0:
        scored_events = [se for se in scored_events if se.score >= min_score]

    # Group by day and build timeslots per day
    by_day = group_by_day(scored_events)

    total_conflicts = 0
    days = {}
    for day_key, day_events in by_day.items():
        timeslots = build_timeslots(day_events)
        # Annotate each timeslot's events with conflict info
        annotated_timeslots = []
        for ts in timeslots:
            annotated_events = _annotate_conflicts(ts.events)
            conflict_count = sum(1 for ae in annotated_events if ae["conflict"])
            total_conflicts += conflict_count
            annotated_timeslots.append({
                "timeslot": ts,
                "events": annotated_events,
                "conflict_count": conflict_count,
            })
        display = day_events[0].event.day_display if day_events else day_key
        days[day_key] = {
            "display": display,
            "event_count": len(day_events),
            "timeslots": annotated_timeslots,
        }

    # Collect all unique categories
    all_cats = set()
    for se in scored_events:
        all_cats.update(se.event.categories)
    categories = sorted(all_cats)

    # Stats
    total_events = len(scored_events)
    must_attend = sum(1 for se in scored_events if se.score >= 85)
    recommended = sum(1 for se in scored_events if se.score >= 70)
    avg_score = (
        round(sum(se.score for se in scored_events) / total_events)
        if total_events
        else 0
    )

    # Top picks per day (best non-conflicting schedule)
    top_picks = {}
    for day_key, day_events in by_day.items():
        sorted_day = sorted(day_events, key=lambda se: -se.score)
        picks = []
        for se in sorted_day:
            if se.score < 50:
                continue
            if not any(se.event.conflicts_with(p.event) for p in picks):
                picks.append(se)
        top_picks[day_key] = sorted(picks, key=lambda se: se.event.dtstart)

    # Render
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("report.html")

    html = template.render(
        profile=profile,
        days=days,
        categories=categories,
        total_events=total_events,
        must_attend=must_attend,
        recommended=recommended,
        avg_score=avg_score,
        total_conflicts=total_conflicts,
        top_picks=top_picks,
        min_score=min_score,
        provider_name=provider_name,
        generated_at=datetime.now(CET).strftime("%Y-%m-%d %H:%M CET"),
    )

    output_path.write_text(html)
    return output_path

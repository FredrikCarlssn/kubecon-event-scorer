"""HTML report generation using Jinja2."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ics_parser import build_timeslots, group_by_day
from models import CET, Profile, ScoredEvent

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent / "output"


def _annotate_direct_conflicts(events: list[ScoredEvent]) -> list[dict]:
    """Annotate each event with only its DIRECT time overlaps (not transitive)."""
    annotated = []
    for i, se in enumerate(events):
        direct = []
        for j, other in enumerate(events):
            if i == j:
                continue
            if se.event.conflicts_with(other.event):
                direct.append(other)
        # Sort direct conflicts by score descending
        direct.sort(key=lambda x: -x.score)

        if direct:
            # Show top 3 conflict names, summarize the rest
            top_names = [d.event.summary for d in direct[:3]]
            extra = len(direct) - 3
            annotated.append({
                "scored_event": se,
                "has_conflict": True,
                "conflict_count": len(direct),
                "conflict_names": top_names,
                "conflict_extra": extra if extra > 0 else 0,
                "best_alternative": direct[0] if direct[0].score > se.score else None,
            })
        else:
            annotated.append({
                "scored_event": se,
                "has_conflict": False,
                "conflict_count": 0,
                "conflict_names": [],
                "conflict_extra": 0,
                "best_alternative": None,
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

    total_conflict_slots = 0
    days = {}
    for day_key, day_events in by_day.items():
        timeslots = build_timeslots(day_events)
        annotated_timeslots = []
        for ts in timeslots:
            annotated_events = _annotate_direct_conflicts(ts.events)
            has_conflicts = any(ae["has_conflict"] for ae in annotated_events)
            if has_conflicts:
                total_conflict_slots += 1
            annotated_timeslots.append({
                "timeslot": ts,
                "events": annotated_events,
                "has_conflicts": has_conflicts,
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

    # Build JSON event data for calendar JS
    event_data = []
    for se in scored_events:
        start_cet = se.event.start_cet
        end_cet = se.event.end_cet
        has_conflict = any(
            se.event.conflicts_with(other.event)
            for other in scored_events
            if other is not se and other.event.day == se.event.day
        )
        event_data.append({
            "uid": se.event.uid,
            "title": se.event.summary,
            "day": se.event.day,
            "dayDisplay": se.event.day_display,
            "timeRange": se.event.time_range,
            "startMin": start_cet.hour * 60 + start_cet.minute,
            "endMin": end_cet.hour * 60 + end_cet.minute,
            "duration": se.event.duration_minutes,
            "location": se.event.location,
            "categories": se.event.categories,
            "url": se.event.url,
            "description": se.event.description,
            "score": se.score,
            "tier": se.score_tier,
            "scoreColor": se.score_color,
            "role": se.role_relevance,
            "topic": se.topic_alignment,
            "strategic": se.strategic_value,
            "reasoning": se.reasoning,
            "hasConflict": has_conflict,
        })

    # Render
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)
    template = env.get_template("report.html")

    html = template.render(
        profile=profile,
        days=days,
        categories=categories,
        total_events=total_events,
        must_attend=must_attend,
        recommended=recommended,
        avg_score=avg_score,
        total_conflict_slots=total_conflict_slots,
        top_picks=top_picks,
        min_score=min_score,
        provider_name=provider_name,
        generated_at=datetime.now(CET).strftime("%Y-%m-%d %H:%M CET"),
        event_data=json.dumps(event_data),
    )

    output_path.write_text(html)
    return output_path

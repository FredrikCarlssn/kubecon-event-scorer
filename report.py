"""HTML report generation using Jinja2."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ics_parser import build_timeslots, group_by_day
from models import CET, Profile, ScoredEvent

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent / "output"


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

    days = {}
    for day_key, day_events in by_day.items():
        timeslots = build_timeslots(day_events)
        display = day_events[0].event.day_display if day_events else day_key
        days[day_key] = {
            "display": display,
            "event_count": len(day_events),
            "timeslots": timeslots,
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
        min_score=min_score,
        provider_name=provider_name,
        generated_at=datetime.now(CET).strftime("%Y-%m-%d %H:%M CET"),
    )

    output_path.write_text(html)
    return output_path

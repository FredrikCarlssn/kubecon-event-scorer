"""ICS download, parsing, filtering, and conflict detection."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from icalendar import Calendar

from models import CET, Event, ScoredEvent, TimeSlot

ICS_URL = "https://kccnceu2026.sched.com/all.ics"
DEFAULT_CACHE_DIR = Path(__file__).parent / "cache"


def download_ics(
    url: str = ICS_URL,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force_refresh: bool = False,
) -> Path:
    """Download ICS feed with 24h caching."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "events.ics"

    if not force_refresh and cache_path.exists():
        age_hours = (
            datetime.now().timestamp() - cache_path.stat().st_mtime
        ) / 3600
        if age_hours < 24:
            return cache_path

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    cache_path.write_bytes(resp.content)
    return cache_path


def ics_content_hash(ics_path: Path) -> str:
    """Return a short hash of the ICS file for cache keying."""
    return hashlib.sha256(ics_path.read_bytes()).hexdigest()[:12]


def parse_ics(ics_path: Path) -> list[Event]:
    """Parse an ICS file into Event objects."""
    cal = Calendar.from_ical(ics_path.read_bytes())
    events = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get("uid", ""))
        summary = str(component.get("summary", ""))
        description = str(component.get("description", ""))
        location = str(component.get("location", ""))
        url = str(component.get("url", ""))

        # Parse categories - handle both string and vCategory objects
        raw_cats = component.get("categories")
        categories = []
        if raw_cats is not None:
            cat_list = raw_cats if isinstance(raw_cats, list) else [raw_cats]
            for cat_group in cat_list:
                if hasattr(cat_group, "cats"):
                    categories.extend(str(c) for c in cat_group.cats)
                else:
                    categories.append(str(cat_group))

        # Parse dates - ensure timezone-aware
        dtstart = component.get("dtstart")
        dtend = component.get("dtend")
        if dtstart is None or dtend is None:
            continue

        dt_start = dtstart.dt
        dt_end = dtend.dt

        # Skip all-day events (date objects, not datetime)
        if not isinstance(dt_start, datetime) or not isinstance(dt_end, datetime):
            continue

        # Ensure UTC
        if dt_start.tzinfo is None:
            dt_start = dt_start.replace(tzinfo=timezone.utc)
        if dt_end.tzinfo is None:
            dt_end = dt_end.replace(tzinfo=timezone.utc)

        events.append(
            Event(
                uid=uid,
                summary=summary,
                description=description,
                dtstart=dt_start,
                dtend=dt_end,
                location=location,
                categories=categories,
                url=url,
            )
        )

    # Sort by start time
    events.sort(key=lambda e: e.dtstart)
    return events


def filter_scorable(
    events: list[Event],
    exclude_categories: list[str] | None = None,
) -> list[Event]:
    """Remove non-scorable events (registration, breaks, etc.)."""
    default_exclude = {"REGISTRATION", "BREAKS", "BREAK", "MEAL", "LUNCH"}
    exclude = default_exclude | {
        c.upper() for c in (exclude_categories or [])
    }

    skip_keywords = {
        "registration", "breakfast", "lunch", "coffee break",
        "badge pick", "networking break", "shuttle",
    }

    filtered = []
    for event in events:
        cats_upper = {c.upper() for c in event.categories}
        if cats_upper & exclude:
            continue
        summary_lower = event.summary.lower()
        if any(kw in summary_lower for kw in skip_keywords):
            continue
        filtered.append(event)

    return filtered


def group_by_day(scored_events: list[ScoredEvent]) -> dict[str, list[ScoredEvent]]:
    """Group scored events by CET date, sorted by day then score."""
    days: dict[str, list[ScoredEvent]] = defaultdict(list)
    for se in scored_events:
        days[se.event.day].append(se)

    # Sort each day's events by start time then by score descending
    for day in days:
        days[day].sort(key=lambda se: (se.event.dtstart, -se.score))

    return dict(sorted(days.items()))


def build_timeslots(scored_events: list[ScoredEvent]) -> list[TimeSlot]:
    """Build timeslots from scored events, merging overlapping intervals."""
    if not scored_events:
        return []

    # Sort by start time
    sorted_events = sorted(scored_events, key=lambda se: se.event.dtstart)

    timeslots: list[TimeSlot] = []
    current_start = sorted_events[0].event.dtstart
    current_end = sorted_events[0].event.dtend
    current_events = [sorted_events[0]]

    for se in sorted_events[1:]:
        if se.event.dtstart < current_end:
            # Overlaps with current timeslot
            current_end = max(current_end, se.event.dtend)
            current_events.append(se)
        else:
            # New timeslot
            timeslots.append(
                TimeSlot(
                    start=current_start,
                    end=current_end,
                    events=sorted(current_events, key=lambda x: -x.score),
                )
            )
            current_start = se.event.dtstart
            current_end = se.event.dtend
            current_events = [se]

    # Don't forget the last timeslot
    timeslots.append(
        TimeSlot(
            start=current_start,
            end=current_end,
            events=sorted(current_events, key=lambda x: -x.score),
        )
    )

    return timeslots

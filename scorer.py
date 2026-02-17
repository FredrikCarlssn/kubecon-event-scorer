"""Scoring orchestration: profile loading, batching, caching, progress."""

from __future__ import annotations

import json
import time
from pathlib import Path

import yaml
from tqdm import tqdm

from ics_parser import ics_content_hash
from models import Event, Profile, ScoredEvent
from providers.base import AIProvider

CACHE_DIR = Path(__file__).parent / "cache"


def load_profile(yaml_path: str | Path) -> Profile:
    """Load and validate a YAML profile."""
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if not data.get("name") or not data.get("role"):
        raise ValueError("Profile must have 'name' and 'role' fields")

    return Profile(
        name=data["name"],
        role=data["role"],
        organization=data.get("organization", ""),
        experience_level=data.get("experience_level", "intermediate"),
        interests=data.get("interests", {}),
        priorities=data.get("priorities", []),
        exclude_categories=data.get("exclude_categories", []),
        preferences=data.get("preferences", {}),
        context=data.get("context", ""),
    )


def create_batches(events: list[Event], batch_size: int = 12) -> list[list[Event]]:
    """Split events into batches for API calls."""
    return [events[i : i + batch_size] for i in range(0, len(events), batch_size)]


def _cache_path(profile: Profile, content_hash: str) -> Path:
    """Generate cache file path for a profile+ICS combination."""
    safe_name = profile.name.lower().replace(" ", "_")
    return CACHE_DIR / f"scores_{safe_name}_{content_hash}.json"


def _load_cached_scores(
    cache_file: Path, events: list[Event]
) -> list[ScoredEvent] | None:
    """Load cached scores if available."""
    if not cache_file.exists():
        return None

    try:
        with open(cache_file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    event_map = {e.uid: e for e in events}
    scored = []
    for item in data:
        event = event_map.get(item["uid"])
        if event is None:
            continue
        scored.append(
            ScoredEvent(
                event=event,
                score=item["score"],
                role_relevance=item["role_relevance"],
                topic_alignment=item["topic_alignment"],
                strategic_value=item["strategic_value"],
                reasoning=item["reasoning"],
            )
        )

    # Only use cache if we have scores for all events
    if len(scored) == len(events):
        return scored
    return None


def _save_scores(cache_file: Path, scored_events: list[ScoredEvent]) -> None:
    """Save scored events to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "uid": se.event.uid,
            "score": se.score,
            "role_relevance": se.role_relevance,
            "topic_alignment": se.topic_alignment,
            "strategic_value": se.strategic_value,
            "reasoning": se.reasoning,
        }
        for se in scored_events
    ]
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)


def score_all_events(
    events: list[Event],
    profile: Profile,
    provider: AIProvider,
    ics_path: Path,
    batch_size: int = 12,
    no_cache: bool = False,
    max_retries: int = 2,
) -> list[ScoredEvent]:
    """Main scoring pipeline with progress bar, caching, and retries."""
    content_hash = ics_content_hash(ics_path)
    cache_file = _cache_path(profile, content_hash)

    # Check cache
    if not no_cache:
        cached = _load_cached_scores(cache_file, events)
        if cached is not None:
            print(f"  Using cached scores from {cache_file.name}")
            return cached

    batches = create_batches(events, batch_size)
    all_scored: list[ScoredEvent] = []

    print(f"  Scoring {len(events)} events in {len(batches)} batches "
          f"using {provider.name} ({provider.model})")

    for batch in tqdm(batches, desc="  Scoring", unit="batch"):
        for attempt in range(max_retries + 1):
            try:
                scored = provider.score_batch(batch, profile)
                all_scored.extend(scored)
                break
            except Exception as e:
                if attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    tqdm.write(f"  Retry {attempt + 1}/{max_retries} after error: {e}")
                    time.sleep(wait)
                else:
                    tqdm.write(f"  Failed batch after {max_retries} retries: {e}")
                    # Add unscored events
                    all_scored.extend(
                        ScoredEvent(event=ev, reasoning=f"Scoring failed: {e}")
                        for ev in batch
                    )

    # Sort by score descending
    all_scored.sort(key=lambda se: -se.score)

    # Cache results
    if not no_cache:
        _save_scores(cache_file, all_scored)
        print(f"  Scores cached to {cache_file.name}")

    return all_scored

"""Abstract AI provider with prompt building and response parsing."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

from models import Event, Profile, ScoredEvent


class AIProvider(ABC):
    """Base class for AI scoring providers."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or self.default_model
        self.api_key = api_key

    @property
    @abstractmethod
    def default_model(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def _call_api(self, system: str, user: str) -> str:
        """Call the AI API and return the text response."""
        ...

    def score_batch(
        self, events: list[Event], profile: Profile
    ) -> list[ScoredEvent]:
        """Score a batch of events against a profile."""
        system = self._build_system_prompt(profile)
        user = self._build_user_prompt(events)
        response = self._call_api(system, user)
        return self._parse_response(response, events)

    def _build_system_prompt(self, profile: Profile) -> str:
        primary = ", ".join(profile.interests.get("primary", []))
        secondary = ", ".join(profile.interests.get("secondary", []))
        priorities = "\n".join(f"  - {p}" for p in profile.priorities)
        prefs = ""
        if profile.preferences:
            pref_lines = []
            if profile.preferences.get("prefer_hands_on"):
                pref_lines.append("  - Prefers hands-on workshops and demos")
            if profile.preferences.get("prefer_deep_dives"):
                pref_lines.append("  - Prefers deep technical dives over introductory content")
            if profile.preferences.get("avoid_vendor_pitches"):
                pref_lines.append("  - Penalize vendor-heavy marketing talks")
            prefs = "\n".join(pref_lines)

        return f"""You are a KubeCon + CloudNativeCon EU 2026 conference session evaluator.

## Attendee Profile
- Name: {profile.name}
- Role: {profile.role}
- Organization: {profile.organization}
- Experience Level: {profile.experience_level}
- Primary Interests: {primary}
- Secondary Interests: {secondary}
- Priorities:
{priorities}
{f"- Preferences:\\n{prefs}" if prefs else ""}
{f"- Context: {profile.context}" if profile.context else ""}

## Scoring Rubric (total: 0-100)
Score each event on three components:

1. **role_relevance** (0-35): How relevant is this session to the attendee's role and daily responsibilities?
   - 30-35: Directly addresses core job functions
   - 20-29: Strongly related to role
   - 10-19: Tangentially related
   - 0-9: Not relevant to role

2. **topic_alignment** (0-35): How well does the topic match the attendee's stated interests and priorities?
   - 30-35: Directly matches primary interests/priorities
   - 20-29: Matches secondary interests
   - 10-19: Loosely related
   - 0-9: No alignment

3. **strategic_value** (0-30): What unique strategic value does this session offer?
   - 25-30: Unique insights, hard to get elsewhere, actionable takeaways
   - 15-24: Good learning opportunity
   - 5-14: Standard content, available elsewhere
   - 0-4: Low strategic value

## Calibration Guidelines
- A perfect 100 should be extremely rare (1-2 sessions max)
- Aim for a natural distribution: most sessions between 30-70
- Reserve 85+ for truly exceptional matches
- Introductory talks should score lower for advanced/expert attendees
- Vendor-specific talks score lower unless the tool is directly relevant
- Hands-on workshops get a bonus if the profile prefers them

## Output Format
Return a JSON array. Each element MUST have these exact fields:
- "uid": the event UID (string, copy exactly from input)
- "score": total score (integer 0-100, must equal sum of components)
- "role_relevance": component score (integer 0-35)
- "topic_alignment": component score (integer 0-35)
- "strategic_value": component score (integer 0-30)
- "reasoning": 1-2 sentence explanation (string)

Return ONLY the JSON array, no markdown fences, no extra text."""

    def _build_user_prompt(self, events: list[Event]) -> str:
        parts = ["Score the following KubeCon EU 2026 sessions:\n"]
        for i, event in enumerate(events, 1):
            cats = ", ".join(event.categories) if event.categories else "N/A"
            desc = event.description[:500] if event.description else "No description"
            parts.append(
                f"--- Session {i} ---\n"
                f"UID: {event.uid}\n"
                f"Title: {event.summary}\n"
                f"Categories: {cats}\n"
                f"Duration: {event.duration_minutes} min\n"
                f"Description: {desc}\n"
            )
        return "\n".join(parts)

    def _parse_response(
        self, response: str, events: list[Event]
    ) -> list[ScoredEvent]:
        """Parse JSON response and map scores back to events."""
        event_map = {e.uid: e for e in events}

        # Try direct JSON parse first
        scores = None
        try:
            scores = json.loads(response)
        except json.JSONDecodeError:
            pass

        # Fallback: extract JSON array from response
        if scores is None:
            match = re.search(r'\[[\s\S]*\]', response)
            if match:
                try:
                    scores = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        if not scores or not isinstance(scores, list):
            # Last resort: return events with zero scores
            return [ScoredEvent(event=e, reasoning="Scoring failed") for e in events]

        scored = []
        for item in scores:
            uid = item.get("uid", "")
            event = event_map.get(uid)
            if event is None:
                continue

            role = _clamp(item.get("role_relevance", 0), 0, 35)
            topic = _clamp(item.get("topic_alignment", 0), 0, 35)
            strategic = _clamp(item.get("strategic_value", 0), 0, 30)
            total = role + topic + strategic

            scored.append(
                ScoredEvent(
                    event=event,
                    score=total,
                    role_relevance=role,
                    topic_alignment=topic,
                    strategic_value=strategic,
                    reasoning=item.get("reasoning", ""),
                )
            )

        # Add any events that weren't in the response
        scored_uids = {se.event.uid for se in scored}
        for event in events:
            if event.uid not in scored_uids:
                scored.append(ScoredEvent(event=event, reasoning="Not scored by AI"))

        return scored


def _clamp(value: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return 0

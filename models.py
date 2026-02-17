"""Data models for KubeCon Event Scorer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

CET = ZoneInfo("Europe/Amsterdam")


@dataclass
class Event:
    uid: str
    summary: str
    description: str
    dtstart: datetime
    dtend: datetime
    location: str = ""
    categories: list[str] = field(default_factory=list)
    url: str = ""

    @property
    def start_cet(self) -> datetime:
        return self.dtstart.astimezone(CET)

    @property
    def end_cet(self) -> datetime:
        return self.dtend.astimezone(CET)

    @property
    def day(self) -> str:
        return self.start_cet.strftime("%Y-%m-%d")

    @property
    def day_display(self) -> str:
        return self.start_cet.strftime("%A, %B %d")

    @property
    def time_range(self) -> str:
        return f"{self.start_cet.strftime('%H:%M')} - {self.end_cet.strftime('%H:%M')}"

    @property
    def duration_minutes(self) -> int:
        return int((self.dtend - self.dtstart).total_seconds() / 60)

    def conflicts_with(self, other: Event) -> bool:
        return self.dtstart < other.dtend and other.dtstart < self.dtend


@dataclass
class ScoredEvent:
    event: Event
    score: int = 0
    role_relevance: int = 0
    topic_alignment: int = 0
    strategic_value: int = 0
    reasoning: str = ""

    @property
    def score_tier(self) -> str:
        if self.score >= 85:
            return "must-attend"
        elif self.score >= 70:
            return "recommended"
        elif self.score >= 50:
            return "consider"
        elif self.score >= 30:
            return "low"
        return "skip"

    @property
    def score_color(self) -> str:
        if self.score >= 85:
            return "#16a34a"  # green
        elif self.score >= 70:
            return "#2563eb"  # blue
        elif self.score >= 50:
            return "#d97706"  # amber
        elif self.score >= 30:
            return "#6b7280"  # gray
        return "#d1d5db"  # light gray


@dataclass
class TimeSlot:
    start: datetime
    end: datetime
    events: list[ScoredEvent] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        for i, a in enumerate(self.events):
            for b in self.events[i + 1 :]:
                if a.event.conflicts_with(b.event):
                    return True
        return False

    @property
    def start_cet(self) -> datetime:
        return self.start.astimezone(CET)

    @property
    def end_cet(self) -> datetime:
        return self.end.astimezone(CET)

    @property
    def time_range(self) -> str:
        return f"{self.start_cet.strftime('%H:%M')} - {self.end_cet.strftime('%H:%M')}"


@dataclass
class Profile:
    name: str
    role: str
    organization: str = ""
    experience_level: str = "intermediate"
    interests: dict[str, list[str]] = field(default_factory=dict)
    priorities: list[str] = field(default_factory=list)
    exclude_categories: list[str] = field(default_factory=list)
    preferences: dict[str, bool] = field(default_factory=dict)
    context: str = ""

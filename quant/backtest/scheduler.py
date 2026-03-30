from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Scheduler:
    timeline_points: list[datetime]

    def timeline(self) -> list[datetime]:
        return list(self.timeline_points)

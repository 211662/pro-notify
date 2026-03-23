"""
Scheduler Module
Simple time-based scheduler for periodic tasks (gold price, weather, etc).
No external dependencies — uses only stdlib.
"""

import logging
from datetime import datetime, time as dtime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """A task that runs on a schedule."""
    name: str
    interval_minutes: int = 0           # Run every N minutes (0 = disabled)
    daily_times: list[str] = field(default_factory=list)  # Run at specific times ["07:00", "12:00", "18:00"]
    last_run: datetime | None = None
    enabled: bool = True

    def should_run(self, now: datetime | None = None) -> bool:
        """Check if this task should run now."""
        if not self.enabled:
            return False

        if now is None:
            now = datetime.now()

        # Interval-based
        if self.interval_minutes > 0:
            if self.last_run is None:
                return True
            elapsed = (now - self.last_run).total_seconds() / 60
            if elapsed >= self.interval_minutes:
                return True

        # Time-based (daily at specific times)
        if self.daily_times:
            current_time = now.strftime("%H:%M")
            for schedule_time in self.daily_times:
                if current_time == schedule_time:
                    # Don't run twice in the same minute
                    if self.last_run is None:
                        return True
                    if self.last_run.strftime("%H:%M %Y-%m-%d") != f"{schedule_time} {now.strftime('%Y-%m-%d')}":
                        return True

        return False

    def mark_done(self, now: datetime | None = None) -> None:
        """Mark this task as just completed."""
        self.last_run = now or datetime.now()

    def next_run_info(self) -> str:
        """Human-readable description of schedule."""
        parts = []
        if self.interval_minutes > 0:
            if self.interval_minutes >= 60:
                parts.append(f"mỗi {self.interval_minutes // 60}h")
            else:
                parts.append(f"mỗi {self.interval_minutes} phút")
        if self.daily_times:
            parts.append(f"lúc {', '.join(self.daily_times)}")
        return " & ".join(parts) if parts else "disabled"


def parse_schedule_config(config: dict) -> ScheduledTask:
    """
    Parse schedule config from YAML.

    Example configs:
        interval: 60          # every 60 minutes
        times: ["07:00", "18:00"]  # daily at 7am, 6pm
        enabled: true
    """
    return ScheduledTask(
        name=config.get("name", "unnamed"),
        interval_minutes=int(config.get("interval", 0)),
        daily_times=config.get("times", []),
        enabled=config.get("enabled", True),
    )

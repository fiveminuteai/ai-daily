"""The clock: starts the daily post and each Reel slot on time, without GitHub's scheduler.

GitHub's cron is best effort and dropped the 05:45 post (31 Oct, 1 Nov) and the 13:00 and 19:00 Reels (1 Nov). Runs
started by workflow_dispatch are not dropped. So clock.yml sleeps inside a job until the next event, starts that
event's workflow, then starts the next clock run: one chain, always running. A job may last 6 hours, so a gap longer
than MAX_SLEEP is crossed in hops that start nothing. The crons and the laptop trigger stay as backups and restart the
chain if it ever stops (a lost runner, a GitHub outage).

The times come from `schedule:` in config/site.yaml (India time; the control app edits them). A missing or invalid
value falls back to the default below, so a bad edit can never stop the clock.

Standard library only: the job runs `python3 fma/clock.py` without installing anything.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# India time. Limits: the daily post between 03:00 and 07:00 (the laptop backup trigger fires at 07:30 and the
# fixed cron backups from 05:45, see daily_not_yet); 1-5 Reels (3 until 7 Nov 2026), at least 90 minutes after the post and 30 apart,
# by 23:00; stats between 20:00 and 23:45, after the last Reel.
DEFAULT = {"daily": "05:45", "reels": ("09:00", "13:00", "19:00"), "stats": "23:30"}
IST = timedelta(hours=5, minutes=30)
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
MAX_SLEEP = timedelta(hours=5, minutes=30)     # under the 6-hour job limit with room for setup
LATE = timedelta(seconds=15)                   # start just after the slot, so the item is already due


def _mins(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def schedule(cfg: dict | None) -> dict:
    """The schedule to use: each valid field of `cfg`, the default for anything missing or out of bounds."""
    cfg = cfg if isinstance(cfg, dict) else {}
    out = dict(DEFAULT)
    daily = cfg.get("daily")
    if isinstance(daily, str) and _HHMM.match(daily) and _mins("03:00") <= _mins(daily) <= _mins("07:00"):
        out["daily"] = daily
    reels = cfg.get("reels")
    if (isinstance(reels, (list, tuple)) and 1 <= len(reels) <= 5 and all(isinstance(r, str) and _HHMM.match(r) for r in reels)
            and _mins(reels[0]) >= _mins(out["daily"]) + 90 and _mins(reels[-1]) <= _mins("23:00")
            and all(_mins(b) - _mins(a) >= 30 for a, b in zip(reels, reels[1:]))):
        out["reels"] = tuple(reels)
    stats = cfg.get("stats")
    if (isinstance(stats, str) and _HHMM.match(stats) and _mins("20:00") <= _mins(stats) <= _mins("23:45")
            and _mins(stats) > _mins(out["reels"][-1])):
        out["stats"] = stats                    # (the default 23:30 is always after the last Reel: they end by 23:00)
    return out


def read_schedule(text: str) -> dict:
    """`schedule:` from the text of config/site.yaml, without a YAML library (the clock job installs nothing)."""
    m = re.search(r"^schedule:[ \t]*\n((?:[ \t]+.*\n?)*)", text, re.M)
    block = m.group(1) if m else ""
    one = lambda key: (re.search(rf"^[ \t]+{key}:[ \t]*\"?(\d\d:\d\d)\"?", block, re.M) or [None, None])[1]  # noqa: E731
    lst = re.search(r"^[ \t]+reels:[ \t]*\[([^\]]*)\]", block, re.M)
    reels = re.findall(r"\d\d:\d\d", lst.group(1)) if lst else None
    return schedule({"daily": one("daily"), "reels": reels, "stats": one("stats")})


def to_utc(hhmm: str) -> str:
    return f"{(_mins(hhmm) - 330) % 1440 // 60:02d}:{(_mins(hhmm) - 330) % 60:02d}"


def events(sched: dict) -> tuple[tuple[str, str], ...]:
    """(UTC time, workflow), in UTC order."""
    ev = [(to_utc(sched["daily"]), "daily.yml"), *[(to_utc(r), "post-scheduled.yml") for r in sched["reels"]],
          (to_utc(sched["stats"]), "collect-stats.yml")]       # the day's numbers, then the learning loop (fma/learn.py)
    return tuple(sorted(ev))


EVENTS = events(DEFAULT)                        # 00:15 UTC is 05:45 India time


def daily_not_yet(now: datetime, sched: dict) -> bool:
    """True before the configured daily time (India time). The cron backups in daily.yml can't read the config, so a
    cron run that fires before the post's time skips itself instead of posting early."""
    return (now.astimezone(timezone(IST)).hour * 60 + now.astimezone(timezone(IST)).minute) < _mins(sched["daily"])


def next_event(now: datetime, ev: tuple[tuple[str, str], ...] = EVENTS) -> tuple[datetime, str]:
    """The first event strictly after `now`."""
    for day in (0, 1):
        for hhmm, workflow in ev:
            h, m = map(int, hhmm.split(":"))
            when = (now + timedelta(days=day)).replace(hour=h, minute=m, second=0, microsecond=0) + LATE
            if when > now:
                return when, workflow
    raise AssertionError("unreachable")


def plan(now: datetime, max_sleep: timedelta = MAX_SLEEP, ev: tuple[tuple[str, str], ...] = EVENTS) -> tuple[int, str]:
    """(seconds to sleep, workflow to start after the sleep or "" for a hop that only passes time)."""
    when, workflow = next_event(now, ev)
    if when - now > max_sleep:
        return int(max_sleep.total_seconds()), ""
    return max(0, int((when - now).total_seconds()) + 1), workflow


if __name__ == "__main__":
    test_hop = os.environ.get("CLOCK_TEST_HOP_MINUTES")      # a short hop, to check the chain by hand
    site = Path(__file__).resolve().parents[1] / "config" / "site.yaml"
    sched = read_schedule(site.read_text(encoding="utf-8")) if site.exists() else dict(DEFAULT)
    seconds, workflow = plan(datetime.now(timezone.utc), timedelta(minutes=int(test_hop)) if test_hop else MAX_SLEEP,
                             events(sched))
    print(f"sleep={seconds}\nworkflow={workflow}")
    sys.exit(0)

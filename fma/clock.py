"""The clock: starts the daily post and each Reel slot on time, without GitHub's scheduler.

GitHub's cron is best effort and dropped the 05:45 post (31 Oct, 1 Nov) and the 13:00 and 19:00 Reels (1 Nov). Runs
started by workflow_dispatch are not dropped. So clock.yml sleeps inside a job until the next event, starts that
event's workflow, then starts the next clock run: one chain, always running. A job may last 6 hours, so a gap longer
than MAX_SLEEP is crossed in hops that start nothing. The crons and the laptop trigger stay as backups and restart the
chain if it ever stops (a lost runner, a GitHub outage).

Standard library only: the job runs `python3 fma/clock.py` without installing anything.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

# (UTC time, workflow). 00:15 UTC is 05:45 India time; the Reel times match social_queue.REEL_SLOTS.
EVENTS = (("00:15", "daily.yml"),
          ("03:30", "post-scheduled.yml"),     # 09:00 India time
          ("07:30", "post-scheduled.yml"),     # 13:00
          ("13:30", "post-scheduled.yml"))     # 19:00
MAX_SLEEP = timedelta(hours=5, minutes=30)     # under the 6-hour job limit with room for setup
LATE = timedelta(seconds=15)                   # start just after the slot, so the item is already due


def next_event(now: datetime) -> tuple[datetime, str]:
    """The first event strictly after `now`."""
    for day in (0, 1):
        for hhmm, workflow in EVENTS:
            h, m = map(int, hhmm.split(":"))
            when = (now + timedelta(days=day)).replace(hour=h, minute=m, second=0, microsecond=0) + LATE
            if when > now:
                return when, workflow
    raise AssertionError("unreachable")


def plan(now: datetime, max_sleep: timedelta = MAX_SLEEP) -> tuple[int, str]:
    """(seconds to sleep, workflow to start after the sleep or "" for a hop that only passes time)."""
    when, workflow = next_event(now)
    if when - now > max_sleep:
        return int(max_sleep.total_seconds()), ""
    return max(0, int((when - now).total_seconds()) + 1), workflow


if __name__ == "__main__":
    test_hop = os.environ.get("CLOCK_TEST_HOP_MINUTES")      # a short hop, to check the chain by hand
    seconds, workflow = plan(datetime.now(timezone.utc), timedelta(minutes=int(test_hop)) if test_hop else MAX_SLEEP)
    print(f"sleep={seconds}\nworkflow={workflow}")
    sys.exit(0)

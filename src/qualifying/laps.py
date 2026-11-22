"""Which laps count as valid timed attempts (REQ-LAP-1, REQ-LAP-2)."""

from __future__ import annotations

from .models import Lap

RED_FLAG = "5"   # track-status code; `status` lists every code seen during the lap


def is_valid(lap: Lap) -> bool:
    """A timed lap that isn't deleted, an out/in-lap, red-flagged or FastF1-generated.

    Deletion comes only from the ``del`` field; ``delR``'s lap number is off by one in the
    source data, so it's never read (REQ-LAP-2).
    """
    return (
        lap.time is not None
        and lap.deleted is not True
        and lap.pout is None
        and lap.pin is None
        and RED_FLAG not in lap.status
        and lap.ff1g is not True
    )

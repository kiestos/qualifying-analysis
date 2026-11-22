"""Segment bests, who reached each segment, and the final classification.

Implements REQ-SEG-*, REQ-ADV-1/2 and REQ-CLS-* from specs/driver-lookup.md.

The whole order comes from one comparison, ``_order(drivers, segment)``:
  1. drivers with a valid time in ``segment`` first, by (time, when it was set)   REQ-CLS-2/5
  2. then drivers without one, by their times in earlier segments, latest first   REQ-CLS-3/4
  3. driver code as the final, deterministic tie-break                             REQ-RT-3
The same function decides who advances (applied to one segment) and the final result
(applied to each group of drivers who got equally far).
"""

from __future__ import annotations

from .laps import is_valid
from .models import (NO_TIME, NOT_REACHED, SEGMENTS, TIMED, DriverResult, Lap,
                     SegmentResult)

# Drivers advancing into each segment: 2026 regulations, 22-car grid (REQ-ADV-2).
ADVANCE = {"Q2": 16, "Q3": 10}

NC_NOTE = "No valid lap set"


# A best is (time, session time it was set); the second part breaks ties (REQ-CLS-5).
Best = tuple[float, float]
_NEVER = float("inf")


def segment_bests(laps: list[Lap]) -> dict[tuple[str, str], Best]:
    """Best valid (time, sesT) per (driver, segment) (REQ-SEG-1)."""
    bests: dict[tuple[str, str], Best] = {}
    for lap in laps:
        if not is_valid(lap):
            continue
        key = (lap.drv, lap.qs)
        candidate = (lap.time, lap.sesT if lap.sesT is not None else _NEVER)
        if key not in bests or candidate < bests[key]:
            bests[key] = candidate
    return bests


def _order(drivers, segment: str, bests) -> list[str]:
    earlier = SEGMENTS[: SEGMENTS.index(segment)][::-1]    # latest earlier segment first

    def key(code: str):
        best = bests.get((code, segment))
        if best is not None:
            return (0, best, ())
        fallback = tuple(
            (0, bests[(code, s)]) if (code, s) in bests else (1, ()) for s in earlier
        )
        return (1, (), fallback, code)

    return sorted(drivers, key=lambda c: (key(c), c))


def _reached(drivers: list[str], bests, advance: dict[str, int]) -> dict[str, set[str]]:
    """Who reached each segment under the fixed cutoffs (REQ-ADV-1)."""
    reached = {SEGMENTS[0]: set(drivers)}
    for prev, seg in zip(SEGMENTS, SEGMENTS[1:]):
        reached[seg] = set(_order(reached[prev], prev, bests)[: advance[seg]])
    return reached


def _segment_results(drivers, bests, reached) -> dict[str, dict[str, SegmentResult]]:
    """Time, rank, gap and status per driver per segment (REQ-SEG-1..4)."""
    results = {code: {} for code in drivers}
    for seg in SEGMENTS:
        timed = sorted((bests[(c, seg)], c) for c in drivers if (c, seg) in bests)
        fastest = timed[0][0][0] if timed else None
        ranks = {code: i for i, (_, code) in enumerate(timed, start=1)}
        for code in drivers:
            if code in ranks:
                time = bests[(code, seg)][0]
                results[code][seg] = SegmentResult(time, ranks[code], time - fastest, TIMED)
            else:
                status = NO_TIME if code in reached[seg] else NOT_REACHED
                results[code][seg] = SegmentResult(None, None, None, status)
    return results


def _placement_note(code: str, seg: str, untimed: list[str], bests) -> str | None:
    """REQ-CLS-8: explain a place given without a time in the deciding segment."""
    note = f"Reached {seg} but set no time; placed behind {seg} runners"
    if len(untimed) > 1:
        earlier = SEGMENTS[: SEGMENTS.index(seg)][::-1]
        decided_by = next((s for s in earlier if (code, s) in bests), None)
        if decided_by:
            note += f"; ordered by {decided_by} time"
    return note


def classify(laps: list[Lap], advance: dict[str, int] = ADVANCE) -> list[DriverResult]:
    """Every driver in the data, in classification order; NC drivers last (REQ-CLS-*)."""
    drivers = sorted({lap.drv for lap in laps})
    teams: dict[str, str | None] = {}
    for lap in laps:
        if teams.get(lap.drv) is None:
            teams[lap.drv] = lap.team

    bests = segment_bests(laps)
    reached = _reached(drivers, bests, advance)
    segments = _segment_results(drivers, bests, reached)
    furthest = {c: max((s for s in SEGMENTS if c in reached[s]), key=SEGMENTS.index)
                for c in drivers}
    has_lap = {c for (c, _) in bests}

    ordered: list[DriverResult] = []
    for seg in reversed(SEGMENTS):                              # REQ-CLS-1
        group = [c for c in drivers if furthest[c] == seg and c in has_lap]
        untimed = [c for c in group if (c, seg) not in bests]
        for code in _order(group, seg, bests):
            note = _placement_note(code, seg, untimed, bests) if code in untimed else None
            ordered.append(DriverResult(code, teams[code], len(ordered) + 1, note,
                                        seg, segments[code]))    # REQ-CLS-7

    for code in drivers:                                         # REQ-CLS-6
        if code not in has_lap:
            ordered.append(DriverResult(code, teams[code], None, NC_NOTE,
                                        furthest[code], segments[code]))
    return ordered

"""Valid laps, segment bests, who reached each segment, and the final classification.

Implements REQ-LAP-*, REQ-SEG-*, REQ-ADV-1/2 and REQ-CLS-* from specs/driver-lookup.md.

The whole order comes from one comparison, ``_order(drivers, segment)``:
  1. drivers with a valid time in ``segment`` first, by (time, when it was set)   REQ-CLS-2/5
  2. then drivers without one, by their times in earlier segments, latest first   REQ-CLS-3/4
  3. driver code as the final, deterministic tie-break                             REQ-RT-3
The same function decides who advances (applied to one segment) and the final result
(applied to each group of drivers who got equally far).
"""

from __future__ import annotations

from .models import (NO_TIME, NOT_REACHED, SEGMENTS, TIMED, DriverResult, Lap,
                     SegmentResult)

# Drivers advancing into each segment: 2026 regulations, 22-car grid (REQ-ADV-2).
ADVANCE = {"Q2": 16, "Q3": 10}

NC_NOTE = "No valid lap set"

RED_FLAG = "5"   # track-status code; `status` lists every code seen during the lap


def is_valid(lap: Lap) -> bool:
    """A timed lap that isn't deleted, an out/in-lap, red-flagged or FastF1-generated (REQ-LAP-1).

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


def _segment_results(drivers, bests, reached, has_lap) -> dict[str, dict[str, SegmentResult]]:
    """Time, rank, gap and status per driver per segment (REQ-SEG-1..4).

    Ranked: everyone with a time in the segment, then everyone who reached it without one
    (except NC drivers), in the same order the classification uses (REQ-SEG-2).
    """
    results = {code: {} for code in drivers}
    for seg in SEGMENTS:
        ranked = [c for c in drivers
                  if (c, seg) in bests or (c in reached[seg] and c in has_lap)]
        ranks = {code: i for i, code in enumerate(_order(ranked, seg, bests), start=1)}
        times = [bests[(c, seg)][0] for c in drivers if (c, seg) in bests]
        fastest = min(times) if times else None
        for code in drivers:
            rank = ranks.get(code)
            if (code, seg) in bests:
                time = bests[(code, seg)][0]
                results[code][seg] = SegmentResult(time, rank, time - fastest, TIMED)
            else:
                status = NO_TIME if code in reached[seg] else NOT_REACHED
                results[code][seg] = SegmentResult(None, rank, None, status)
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
    has_lap = {c for (c, _) in bests}
    segments = _segment_results(drivers, bests, reached, has_lap)
    furthest = {c: max((s for s in SEGMENTS if c in reached[s]), key=SEGMENTS.index)
                for c in drivers}

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

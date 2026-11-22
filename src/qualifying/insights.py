"""Teammate head-to-head, the MVP insight (REQ-INS-2).

Teammates drive the same car, so the gap between them is the cleanest measure of the
driver's own performance; position and segment times mix driver and car.
"""

from __future__ import annotations

from .format import format_delta
from .models import SEGMENTS, DriverResult


def _label(result: DriverResult) -> str:
    return f"P{result.position}" if result.position is not None else "NC"


def teammate_lines(results: list[DriverResult], code: str) -> list[str]:
    """One line per teammate. Deltas are driver minus teammate: negative = driver faster."""
    me = next(r for r in results if r.code == code)
    mates = sorted(
        (r for r in results if me.team is not None and r.team == me.team and r.code != code),
        key=lambda r: r.code,
    )
    if not mates:
        return ["Teammate: not in this dataset"]

    lines = []
    for mate in mates:
        head = f"Teammate {mate.code} ({_label(mate)}): "
        deltas = [
            (seg, me.segments[seg].time - mate.segments[seg].time)
            for seg in SEGMENTS
            if me.segments[seg].time is not None and mate.segments[seg].time is not None
        ]
        if not deltas:
            lines.append(head + "no comparable segment")
            continue
        faster = sum(1 for _, d in deltas if round(d * 1000) < 0)   # equal to the ms isn't faster
        parts = ", ".join(f"{seg} {format_delta(d)}" for seg, d in deltas)
        lines.append(f"{head}{parts} (faster in {faster} of {len(deltas)})")
    return lines

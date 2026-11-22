"""Command-line interface: argument handling, interactive prompt, text output.

The only module that does I/O. Everything it shows comes from the pure functions in
classification.py and insights.py, so a future UI or JSON output (REQ-OUT-2) can reuse them.

Exit codes (REQ-OUT-4): 0 success, 1 data file problem, 2 usage error or unknown driver.
The interactive prompt (REQ-DRV-4) never exits with 2: it explains and asks again.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .classification import classify
from .format import format_delta, format_laptime
from .insights import teammate_lines
from .load import DataError, load_laps
from .models import SEGMENTS, DriverResult

DEFAULT_DATA = Path("data") / "session_laptimes.json"
PROMPT = "Driver code (e.g. HUL, or q to quit): "
QUIT = {"q", "quit"}
FORMAT_ERROR = "Driver code must be three letters, e.g. RUS"
CODE_PATTERN = re.compile(r"[A-Z]{3}")


class InputError(Exception):
    """A driver code that can't be looked up; the message is shown to the user."""


def find_driver(results: list[DriverResult], raw: str) -> DriverResult:
    """Normalise and validate a code (REQ-DRV-1/2/3)."""
    code = raw.strip().upper()
    if not CODE_PATTERN.fullmatch(code):
        raise InputError(FORMAT_ERROR)
    for result in results:
        if result.code == code:
            return result
    available = ", ".join(sorted(r.code for r in results))
    raise InputError(f"Driver {code} not found in this dataset. Available: {available}")


def render_report(result: DriverResult, results: list[DriverResult]) -> str:
    """The text report (REQ-OUT-1)."""
    classified = sum(1 for r in results if r.position is not None)
    lines = [f"{result.code} · {result.team or 'Unknown team'}"]
    if result.position is not None:
        lines.append(f"Classified P{result.position} of {classified}")
    else:
        lines.append("Not classified (NC)")
    if result.note:
        lines.append(result.note)

    lines += ["", f"{'Segment':<8} {'Best lap':<10} {'Rank':<5} Gap"]
    for seg in SEGMENTS:
        s = result.segments[seg]
        if s.time is not None:
            lines.append(f"{seg:<8} {format_laptime(s.time):<10} {s.rank:<5} {format_delta(s.gap)}")
        else:
            lines.append(f"{seg:<8} {format_laptime(None):<10} {'':<5} {'':<7} {s.status}")

    lines += ["", "Insights"]
    lines += [f"- {line}" for line in teammate_lines(results, result.code)]
    return "\n".join(lines)


def render_list(results: list[DriverResult]) -> str:
    """Every driver code with team, sorted by code (REQ-OUT-3)."""
    return "\n".join(f"{r.code}  {r.team or 'Unknown team'}"
                     for r in sorted(results, key=lambda r: r.code))


def interactive(results: list[DriverResult]) -> int:
    """Ask for codes until the user quits (REQ-DRV-4). Always returns 0."""
    while True:
        try:
            raw = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not raw.strip():
            continue
        if raw.strip().lower() in QUIT:
            return 0
        try:
            result = find_driver(results, raw)
        except InputError as exc:
            print(exc)
            continue
        print(render_report(result, results))
        print()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quali",
        description="Show a driver's best lap per qualifying segment, final position "
                    "and teammate comparison.",
    )
    parser.add_argument("code", nargs="?",
                        help="three-letter driver code, e.g. HUL; omit to be asked")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA,
                        help=f"lap-times JSON file (default: {DEFAULT_DATA})")
    parser.add_argument("--list", action="store_true", help="list driver codes and teams")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    try:
        loaded = load_laps(args.data)                                   # REQ-IN-6
    except DataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if loaded.malformed:                                                # REQ-IN-7
        print(f"Warning: ignored or treated as missing {loaded.malformed} malformed values",
              file=sys.stderr)

    results = classify(loaded.laps)
    if args.list:
        print(render_list(results))
        return 0
    if args.code is None:
        return interactive(results)
    try:
        result = find_driver(results, args.code)
    except InputError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(render_report(result, results))
    return 0

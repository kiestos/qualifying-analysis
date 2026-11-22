"""Shared fixtures for the driver lookup tests.

Tests are named after the spec requirement they check (specs/driver-lookup.md),
e.g. ``test_req_cls_3_...`` checks REQ-CLS-3.

Interfaces the tests rely on (the implementation must provide these):

- ``qualifying.load.load_laps(path) -> LoadResult`` with ``.laps`` (list of laps) and
  ``.malformed`` (int, REQ-IN-7); raises ``qualifying.load.DataError`` for REQ-IN-6.
  Laps are ``qualifying.models.Lap``; a lap has ``drv``, ``team``, ``lap``, ``qs``, ``time``, ``s1``-``s3``, ``sesT``, ``pin``,
  ``pout``, ``deleted`` (from ``del``), ``status`` and ``ff1g``; missing values are ``None``.
- ``qualifying.laps.is_valid(lap) -> bool`` (REQ-LAP-1).
- ``qualifying.classification.ADVANCE`` and
  ``classify(laps, advance=ADVANCE) -> list[DriverResult]`` in classification order, where a
  ``DriverResult`` (``qualifying.models``) has ``code``, ``team``, ``position`` (int or None), ``note`` (str or None),
  ``furthest`` ("Q1"/"Q2"/"Q3") and ``segments`` (dict "Q1".."Q3" -> ``SegmentResult`` with
  ``time``, ``rank``, ``gap``, ``status`` in {"timed", "no time set", "did not take part"}).
- ``qualifying.insights.teammate_lines(results, code) -> list[str]`` (REQ-INS-2).
- ``qualifying.format.format_laptime`` / ``format_delta`` (REQ-FMT-1/2).
- ``qualifying.cli.main(argv) -> int`` (exit code); reads ``sys.stdin`` via ``input()``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REAL_DATA = ROOT / "data" / "session_laptimes.json"

# Every field the loader requires (REQ-IN-5), plus `delR` so REQ-LAP-2 can be tested.
FIELDS = ["drv", "team", "lap", "qs", "time", "s1", "s2", "s3", "sesT",
          "pin", "pout", "del", "delR", "status", "ff1G"]


def lap(drv: str, qs: str, time, team: str | None = None, **overrides) -> dict:
    """One synthetic lap row. Defaults describe a clean, valid push lap.

    ``time=None`` means no lap time. ``lap`` and ``sesT`` are filled in by
    ``write_dataset`` unless given here.
    """
    row = {
        "drv": drv,
        "team": team or f"Team {drv}",
        "qs": qs,
        "time": time,
        "s1": None, "s2": None, "s3": None,
        "pin": None, "pout": None,
        "del": False, "delR": None,
        "status": "1",
        "ff1G": False,
    }
    row.update(overrides)
    return row


def write_dataset(directory: Path, rows: list[dict], name: str = "laps.json") -> Path:
    """Write rows as the columnar JSON format of the real file (REQ-IN-3).

    Missing values are written as the string "None", like the real file (REQ-IN-4).
    Lap numbers count up per driver; ``sesT`` counts up across the file in row order,
    so earlier rows were set earlier in the session.
    """
    counters: dict[str, int] = {}
    columns: dict[str, list] = {f: [] for f in FIELDS}
    for i, row in enumerate(rows):
        counters[row["drv"]] = counters.get(row["drv"], 0) + 1
        full = {"lap": counters[row["drv"]], "sesT": 1000.0 + 100.0 * i, **row}
        for f in FIELDS:
            value = full.get(f)
            columns[f].append("None" if value is None else value)
    path = directory / name
    path.write_text(json.dumps(columns))
    return path


@pytest.fixture
def make_dataset(tmp_path):
    """Write synthetic rows to a temp file and return its path."""
    return lambda rows, name="laps.json": write_dataset(tmp_path, rows, name)


@pytest.fixture
def load_rows(make_dataset):
    """Write synthetic rows and load them through the real loader."""
    from qualifying.load import load_laps

    return lambda rows: load_laps(make_dataset(rows)).laps


@pytest.fixture(scope="session")
def real_laps():
    from qualifying.load import load_laps

    return load_laps(REAL_DATA).laps


@pytest.fixture(scope="session")
def real_results(real_laps):
    from qualifying.classification import classify

    return classify(real_laps)


@pytest.fixture(scope="session")
def by_code(real_results):
    return {r.code: r for r in real_results}


@pytest.fixture
def run_cli(capsys, monkeypatch):
    """Run the CLI in-process. Returns (exit_code, stdout, stderr).

    ``stdin`` is fed to ``input()`` for the interactive prompt.
    """
    import io
    import sys

    from qualifying.cli import main

    def run(*argv: str, stdin: str = ""):
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
        code = main(list(argv))
        out, err = capsys.readouterr()
        return code, out, err

    return run


def rows_of(text: str) -> dict[str, list[str]]:
    """Map each segment row of the text report ("Q1 ...") to its whitespace-split tokens.

    Lets tests check the content of a row without depending on exact column spacing.
    """
    found = {}
    for line in text.splitlines():
        tokens = line.split()
        if tokens and tokens[0] in ("Q1", "Q2", "Q3"):
            found[tokens[0]] = tokens
    return found

"""Load the columnar lap-times JSON into ``Lap`` objects (REQ-IN-*).

This module is the only place that knows the upstream file's quirks: field lists instead
of rows, the string "None" for missing values, booleans that may arrive as strings.
It translates them into the domain model (models.py); nothing downstream imports it
except the CLI.

Two kinds of problem are handled differently:
- the file as a whole is unusable (REQ-IN-6) -> ``DataError``; the CLI exits with code 1
- individual values are bad (REQ-IN-7) -> treated as missing or the lap is skipped, and
  counted in ``LoadResult.malformed`` so the CLI can warn without stopping
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import SEGMENTS, Lap

REQUIRED_FIELDS = (
    "drv", "team", "lap", "qs", "time", "s1", "s2", "s3",
    "sesT", "pin", "pout", "del", "status", "ff1G",
)


class DataError(Exception):
    """The data file can't be used at all (REQ-IN-6)."""


@dataclass(frozen=True)
class LoadResult:
    laps: list[Lap]
    malformed: int


def _is_missing(value: Any) -> bool:
    return value is None or value == "None"


class _RowParser:
    """Converts raw values, counting the ones that are present but unusable."""

    def __init__(self) -> None:
        self.malformed = 0

    def _bad(self) -> None:
        self.malformed += 1

    def number(self, value: Any, positive: bool = False) -> float | None:
        if _is_missing(value):
            return None
        if isinstance(value, bool):          # bool is an int subclass; never a valid time
            self._bad()
            return None
        if isinstance(value, (int, float)):
            result = float(value)
        elif isinstance(value, str):
            try:
                result = float(value.strip())
            except ValueError:
                self._bad()
                return None
        else:
            self._bad()
            return None
        if not math.isfinite(result) or (positive and result <= 0):
            self._bad()
            return None
        return result

    def integer(self, value: Any) -> int | None:
        result = self.number(value)
        if result is None:
            return None
        if not result.is_integer():
            self._bad()
            return None
        return int(result)

    def boolean(self, value: Any) -> bool | None:
        if _is_missing(value):
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "false"):
            return value.strip().lower() == "true"
        self._bad()
        return None

    def text(self, value: Any) -> str | None:
        if _is_missing(value):
            return None
        text = str(value).strip()
        return text or None

    def lap(self, raw: dict[str, list], i: int) -> Lap | None:
        """Build lap ``i``, or return None (counted) if it can't be attributed."""
        drv = self.text(raw["drv"][i])
        qs = self.text(raw["qs"][i])
        if drv is None or qs not in SEGMENTS:
            self._bad()
            return None
        return Lap(
            drv=drv.upper(),
            team=self.text(raw["team"][i]),
            lap=self.integer(raw["lap"][i]),
            qs=qs,
            time=self.number(raw["time"][i], positive=True),
            s1=self.number(raw["s1"][i], positive=True),
            s2=self.number(raw["s2"][i], positive=True),
            s3=self.number(raw["s3"][i], positive=True),
            sesT=self.number(raw["sesT"][i]),
            pin=self.number(raw["pin"][i]),
            pout=self.number(raw["pout"][i]),
            deleted=self.boolean(raw["del"][i]),
            status=self.text(raw["status"][i]) or "",
            ff1g=self.boolean(raw["ff1G"][i]),
        )


def load_laps(path: str | Path) -> LoadResult:
    """Read and validate the file at ``path``. Raises ``DataError`` if it's unusable."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DataError(f"Data file not found: {path}") from None
    except OSError as exc:
        raise DataError(f"Cannot read data file {path}: {exc.strerror}") from None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DataError(f"Data file is not valid JSON: {path} ({exc})") from None

    if not isinstance(raw, dict):
        raise DataError("Data file must be a JSON object with one list per field")
    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        raise DataError(f"Data file is missing required field(s): {', '.join(missing)}")
    not_lists = [f for f in REQUIRED_FIELDS if not isinstance(raw[f], list)]
    if not_lists:
        raise DataError(f"Field(s) must be lists: {', '.join(not_lists)}")
    lengths = {f: len(raw[f]) for f in REQUIRED_FIELDS}
    if len(set(lengths.values())) > 1:
        detail = ", ".join(f"{f}={n}" for f, n in lengths.items())
        raise DataError(f"Field lists have different lengths ({detail})")

    parser = _RowParser()
    rows = (parser.lap(raw, i) for i in range(lengths["drv"]))
    laps = [lap for lap in rows if lap is not None]
    return LoadResult(laps=laps, malformed=parser.malformed)

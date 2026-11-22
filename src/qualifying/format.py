"""Time formatting (REQ-FMT-1, REQ-FMT-2).

All formatting goes through whole milliseconds, so floating-point noise such as
0.9019999999 can never surface as a wrong last digit.
"""

from __future__ import annotations

import math

MISSING = "—"


def _to_ms(seconds: float) -> int:
    return round(seconds * 1000)


def _m_ss_sss(ms: int) -> str:
    minutes, rest = divmod(ms, 60_000)
    secs, millis = divmod(rest, 1000)
    return f"{minutes}:{secs:02d}.{millis:03d}"


def format_laptime(seconds: float | None) -> str:
    """Lap time as m:ss.sss, e.g. 78.518 -> '1:18.518'. Missing -> '—'."""
    if seconds is None or math.isnan(seconds):
        return MISSING
    return _m_ss_sss(_to_ms(seconds))


def format_delta(seconds: float) -> str:
    """Signed difference: '+0.293', '-0.613'; 60 s or more uses m:ss.sss ('+1:02.410').

    Anything that rounds to zero is '+0.000', never '-0.000'.
    """
    ms = _to_ms(seconds)
    sign = "-" if ms < 0 else "+"
    ms = abs(ms)
    if ms >= 60_000:
        return sign + _m_ss_sss(ms)
    return f"{sign}{ms // 1000}.{ms % 1000:03d}"

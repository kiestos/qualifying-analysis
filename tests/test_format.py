"""REQ-FMT-1/2: m:ss.sss lap times and signed deltas."""

import math

import pytest

from qualifying.format import format_delta, format_laptime


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (78.518, "1:18.518"),
        (65.12, "1:05.120"),     # seconds padded to two digits
        (78.5179, "1:18.518"),   # rounded to the nearest millisecond
        (59.9996, "1:00.000"),   # rounding carries into the minute
        (9.5, "0:09.500"),
    ],
)
def test_req_fmt_1_laptime_is_m_ss_sss(seconds, expected):
    assert format_laptime(seconds) == expected


@pytest.mark.parametrize("missing", [None, math.nan])
def test_req_fmt_1_missing_laptime_is_dash(missing):
    assert format_laptime(missing) == "—"


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0.293, "+0.293"),
        (-0.613, "-0.613"),
        (0.0, "+0.000"),
        (-0.0004, "+0.000"),       # rounds to zero ms: no "-0.000"
        (62.41, "+1:02.410"),      # 60 s or more uses m:ss.sss
        (-62.41, "-1:02.410"),
    ],
)
def test_req_fmt_2_delta_is_signed(seconds, expected):
    assert format_delta(seconds) == expected

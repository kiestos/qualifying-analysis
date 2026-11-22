"""REQ-SEG-*: segment bests, ranks, gaps and why a time is missing."""

import pytest

from conftest import lap
from qualifying.classification import classify


def test_req_seg_1_best_is_fastest_valid_lap(by_code):
    rus = by_code["RUS"].segments
    assert rus["Q1"].time == pytest.approx(79.507)
    assert rus["Q2"].time == pytest.approx(78.934)
    assert rus["Q3"].time == pytest.approx(78.518)


def test_req_seg_1_deleted_fastest_lap_is_ignored(load_rows):
    results = classify(load_rows([
        lap("AAA", "Q1", 79.0, **{"del": True}),
        lap("AAA", "Q1", 80.0),
    ]))
    assert results[0].segments["Q1"].time == pytest.approx(80.0)


def test_req_seg_2_and_3_rank_and_gap(by_code):
    # Spec example: LIN — Q1 8th +0.902, Q2 8th +1.037, Q3 9th +2.729.
    lin = by_code["LIN"].segments
    assert (lin["Q1"].rank, lin["Q2"].rank, lin["Q3"].rank) == (8, 8, 9)
    assert lin["Q1"].gap == pytest.approx(0.902, abs=1e-6)
    assert lin["Q2"].gap == pytest.approx(1.037, abs=1e-6)
    assert lin["Q3"].gap == pytest.approx(2.729, abs=1e-6)


def test_req_seg_3_fastest_driver_gap_is_zero(by_code):
    assert by_code["RUS"].segments["Q3"].gap == 0


def test_req_seg_2_reached_without_time_ranked_behind_timed(by_code):
    # BOR reached Q3 but set no time: ranked 10th, behind the 9 timed Q3 drivers; no gap.
    assert by_code["BOR"].segments["Q3"].rank == 10
    assert by_code["BOR"].segments["Q3"].gap is None


def test_req_seg_2_no_rank_if_not_reached_or_nc(by_code):
    assert by_code["ALO"].segments["Q2"].rank is None     # did not take part
    assert by_code["ALO"].segments["Q3"].rank is None
    assert by_code["VER"].segments["Q1"].rank is None     # NC: not placed anywhere


def test_req_seg_2_several_without_time_ranked_like_classification(load_rows):
    # AAA and BBB reach Q3 with no time; BBB was faster in Q2, so BBB is ranked ahead.
    results = {r.code: r for r in classify(load_rows([
        lap("AAA", "Q2", 79.9), lap("BBB", "Q2", 79.8), lap("CCC", "Q2", 80.0),
        lap("CCC", "Q3", 79.5),
    ]))}
    assert [results[c].segments["Q3"].rank for c in ("CCC", "BBB", "AAA")] == [1, 2, 3]


@pytest.mark.parametrize(
    "code, segment, status",
    [
        ("BOR", "Q3", "no time set"),        # reached Q3, no valid lap
        ("VER", "Q1", "no time set"),        # only an out-lap and a red-flagged lap
        ("ALO", "Q2", "did not take part"),
        ("ALO", "Q3", "did not take part"),
        ("RUS", "Q3", "timed"),
    ],
)
def test_req_seg_4_why_a_time_is_missing(by_code, code, segment, status):
    assert by_code[code].segments[segment].status == status

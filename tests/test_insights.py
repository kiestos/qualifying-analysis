"""REQ-INS-2: teammate head-to-head (the MVP insight)."""

import pytest

from conftest import lap
from qualifying.classification import classify
from qualifying.insights import teammate_lines


@pytest.mark.parametrize(
    "code, expected",
    [
        ("RUS", "Teammate ANT (P2): Q1 -0.613, Q2 -0.501, Q3 -0.293 (faster in 3 of 3)"),
        ("BOR", "Teammate HUL (P11): Q1 -0.529, Q2 -0.082 (faster in 2 of 2)"),
        ("LEC", "Teammate HAM (P7): Q1 +0.415, Q2 -0.564, Q3 -0.151 (faster in 2 of 3)"),
        ("VER", "Teammate HAD (P3): no comparable segment"),
        ("HAD", "Teammate VER (NC): no comparable segment"),
        ("ALO", "Teammate: not in this dataset"),
    ],
)
def test_req_ins_2_spec_examples(real_results, code, expected):
    assert teammate_lines(real_results, code) == [expected]


def test_req_ins_2_sign_negative_means_driver_faster(real_results):
    # The same pair from the other side flips every sign.
    (hul,) = teammate_lines(real_results, "HUL")
    assert hul == "Teammate BOR (P10): Q1 +0.529, Q2 +0.082 (faster in 0 of 2)"


def test_req_ins_2_more_than_one_teammate_sorted_by_code(load_rows):
    results = classify(load_rows([
        lap("AAA", "Q1", 80.0, team="X"),
        lap("CCC", "Q1", 80.5, team="X"),
        lap("BBB", "Q1", 79.5, team="X"),
    ]))
    assert teammate_lines(results, "AAA") == [
        "Teammate BBB (P1): Q1 +0.500 (faster in 0 of 1)",
        "Teammate CCC (P3): Q1 -0.500 (faster in 1 of 1)",
    ]

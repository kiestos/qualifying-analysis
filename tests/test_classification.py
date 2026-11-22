"""REQ-ADV-* and REQ-CLS-*: who reached each segment and the final classification."""

from conftest import lap
from qualifying.classification import ADVANCE, classify

# Spec §5: expected classification for the real file.
EXPECTED = [
    "RUS", "ANT", "HAD", "LEC", "PIA", "NOR", "HAM", "LAW", "LIN",   # Q3 times
    "BOR",                                                          # reached Q3, no time
    "HUL", "BEA", "OCO", "GAS", "ALB", "COL",                       # out in Q2
    "ALO", "PER", "BOT",                                            # out in Q1
]


def test_acceptance_table_matches_spec(real_results):
    classified = [(r.position, r.code) for r in real_results if r.position is not None]
    assert classified == list(enumerate(EXPECTED, start=1))
    assert [r.code for r in real_results if r.position is None] == ["VER"]


# --- REQ-ADV: reaching segments --------------------------------------------------------------

def test_req_adv_2_fixed_cutoffs():
    assert ADVANCE == {"Q2": 16, "Q3": 10}


def test_req_adv_1_bor_reached_q3_without_q3_laps(by_code, real_laps):
    assert not any(l.drv == "BOR" and l.qs == "Q3" for l in real_laps)
    assert by_code["BOR"].furthest == "Q3"


def test_req_adv_1_furthest_segment_counts(real_results):
    furthest = [r.furthest for r in real_results]
    assert furthest.count("Q3") == 10
    assert furthest.count("Q2") == 6
    assert furthest.count("Q1") == 4      # ALO, PER, BOT and VER


def test_req_adv_1_cutoffs_apply_to_the_previous_segment_order(load_rows):
    # With advance = 2 into Q2 and 1 into Q3: C is too slow for Q2 despite having Q2 laps.
    laps = load_rows([
        lap("AAA", "Q1", 80.0), lap("BBB", "Q1", 80.5), lap("CCC", "Q1", 81.0),
        lap("AAA", "Q2", 79.5), lap("BBB", "Q2", 79.0), lap("CCC", "Q2", 78.0),
    ])
    results = {r.code: r for r in classify(laps, advance={"Q2": 2, "Q3": 1})}
    assert results["CCC"].furthest == "Q1"
    assert results["BBB"].furthest == "Q3"
    assert results["AAA"].furthest == "Q2"


# --- REQ-CLS ---------------------------------------------------------------------------------

def test_req_cls_1_furthest_segment_first(by_code):
    # LIN's Q3 lap (1:21.247) is slower than HUL's Q2 best (1:20.303), but LIN reached Q3.
    assert by_code["LIN"].position < by_code["HUL"].position


def test_req_cls_1_later_segment_beats_faster_time(load_rows):
    # AAA reaches Q3 and sets a slow 1:22.000; BBB is out in Q2 with a faster 1:19.500.
    laps = load_rows([
        lap("AAA", "Q1", 80.0), lap("BBB", "Q1", 80.5), lap("CCC", "Q1", 81.0),
        lap("AAA", "Q2", 79.0), lap("BBB", "Q2", 79.5),
        lap("AAA", "Q3", 82.0),
    ])
    results = classify(laps, advance={"Q2": 2, "Q3": 1})
    assert [r.code for r in results] == ["AAA", "BBB", "CCC"]


def test_req_cls_2_timed_drivers_ordered_by_time(real_results):
    assert [r.code for r in real_results[:9]] == EXPECTED[:9]


def test_req_cls_3_single_no_time_driver_goes_behind_timed(by_code):
    assert by_code["BOR"].position == 10


def test_req_cls_3_previous_segment_time_not_used(load_rows):
    # Only CCC has no Q3 time. CCC was fastest in Q2, yet still goes behind every Q3 time.
    laps = load_rows([
        lap("AAA", "Q2", 80.0), lap("BBB", "Q2", 80.5), lap("CCC", "Q2", 79.0),
        lap("AAA", "Q3", 79.9), lap("BBB", "Q3", 80.2),
    ])
    assert [r.code for r in classify(laps)] == ["AAA", "BBB", "CCC"]


def test_req_cls_4_several_no_time_drivers_ordered_by_previous_segment(load_rows):
    # Spec example: A and B reach Q3 with no Q3 time; Q2 A 1:19.900, B 1:19.800 → B ahead.
    laps = load_rows([
        lap("AAA", "Q2", 79.900), lap("BBB", "Q2", 79.800), lap("CCC", "Q2", 80.0),
        lap("CCC", "Q3", 79.5),
    ])
    assert [r.code for r in classify(laps)] == ["CCC", "BBB", "AAA"]


def test_req_cls_4_falls_back_another_segment(load_rows):
    # AAA and BBB have no Q2 or Q3 time, so their Q1 times decide.
    laps = load_rows([
        lap("AAA", "Q1", 81.0), lap("BBB", "Q1", 80.0), lap("CCC", "Q1", 82.0),
        lap("CCC", "Q2", 80.0), lap("CCC", "Q3", 79.0),
    ])
    assert [r.code for r in classify(laps)] == ["CCC", "BBB", "AAA"]


def test_req_cls_5_equal_times_earlier_lap_wins(load_rows):
    # BBB's lap comes first in the file, so it has the lower sesT.
    laps = load_rows([lap("BBB", "Q1", 80.0), lap("AAA", "Q1", 80.0)])
    assert [r.code for r in classify(laps)] == ["BBB", "AAA"]


def test_req_cls_5_full_tie_falls_back_to_code(load_rows):
    # Same time, set at the same session time: driver code decides.
    laps = load_rows([lap("BBB", "Q1", 80.0, sesT=1000.0), lap("AAA", "Q1", 80.0, sesT=1000.0)])
    assert [r.code for r in classify(laps)] == ["AAA", "BBB"]


def test_req_cls_6_no_valid_lap_is_nc(by_code):
    ver = by_code["VER"]
    assert ver.position is None
    assert ver.note == "No valid lap set"


def test_req_cls_6_nc_listed_last_sorted_by_code(load_rows):
    laps = load_rows([
        lap("ZZZ", "Q1", None), lap("AAA", "Q1", 80.0, **{"del": True}), lap("MMM", "Q1", 81.0),
    ])
    results = classify(laps)
    assert [(r.code, r.position) for r in results] == [("MMM", 1), ("AAA", None), ("ZZZ", None)]


def test_req_cls_7_positions_have_no_gaps(real_results):
    positions = [r.position for r in real_results if r.position is not None]
    assert positions == list(range(1, 20))


def test_req_cls_8_placement_notes(by_code, load_rows):
    assert by_code["BOR"].note == "Reached Q3 but set no time; placed behind Q3 runners"
    assert by_code["RUS"].note is None

    laps = load_rows([
        lap("AAA", "Q2", 79.9), lap("BBB", "Q2", 79.8), lap("CCC", "Q2", 80.0),
        lap("CCC", "Q3", 79.5),
    ])
    notes = {r.code: r.note for r in classify(laps)}
    assert notes["AAA"].endswith("; ordered by Q2 time")
    assert notes["BBB"].startswith("Reached Q3 but set no time")


def test_req_rt_3_classification_is_deterministic(real_laps, real_results):
    again = classify(real_laps)
    assert [(r.code, r.position) for r in again] == [(r.code, r.position) for r in real_results]

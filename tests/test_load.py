"""REQ-IN-*: loading the columnar JSON file, missing values and malformed data."""

import json

import pytest

from conftest import REAL_DATA, lap
from qualifying.load import DataError, load_laps


def test_req_in_3_real_file_loads_one_lap_per_row():
    result = load_laps(REAL_DATA)
    assert len(result.laps) == 355


def test_req_in_4_none_strings_are_missing(real_laps):
    # VER lap 2 was stopped by the red flag: the file has time "None".
    ver2 = next(l for l in real_laps if l.drv == "VER" and l.lap == 2)
    assert ver2.time is None


def test_req_in_7_real_file_has_no_malformed_values():
    assert load_laps(REAL_DATA).malformed == 0


def test_req_in_4_json_null_is_missing_and_not_counted(make_dataset):
    path = make_dataset([lap("AAA", "Q1", 80.0)])
    data = json.loads(path.read_text())
    data["time"] = [None]                       # JSON null instead of "None"
    path.write_text(json.dumps(data))
    result = load_laps(path)
    assert result.laps[0].time is None
    assert result.malformed == 0


# --- REQ-IN-6: problems with the file as a whole -------------------------------------------

def test_req_in_6_missing_file(tmp_path):
    with pytest.raises(DataError):
        load_laps(tmp_path / "nope.json")


def test_req_in_6_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    with pytest.raises(DataError):
        load_laps(path)


def test_req_in_6_top_level_must_be_object(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(DataError):
        load_laps(path)


def test_req_in_6_missing_required_field_is_named(make_dataset):
    path = make_dataset([lap("AAA", "Q1", 80.0)])
    data = json.loads(path.read_text())
    del data["qs"]
    path.write_text(json.dumps(data))
    with pytest.raises(DataError, match="qs"):
        load_laps(path)


def test_req_in_6_field_must_be_a_list(make_dataset):
    path = make_dataset([lap("AAA", "Q1", 80.0)])
    data = json.loads(path.read_text())
    data["time"] = 80.0
    path.write_text(json.dumps(data))
    with pytest.raises(DataError, match="time"):
        load_laps(path)


def test_req_in_6_lists_must_be_equal_length(make_dataset):
    path = make_dataset([lap("AAA", "Q1", 80.0), lap("BBB", "Q1", 81.0)])
    data = json.loads(path.read_text())
    data["time"] = data["time"][:1]
    path.write_text(json.dumps(data))
    with pytest.raises(DataError):
        load_laps(path)


# --- REQ-IN-7: bad individual values ---------------------------------------------------------

def test_req_in_7_unparseable_time_is_missing_and_counted(make_dataset):
    result = load_laps(make_dataset([lap("AAA", "Q1", "abc"), lap("AAA", "Q1", 80.0)]))
    assert result.laps[0].time is None
    assert result.laps[1].time == 80.0
    assert result.malformed == 1


def test_req_in_7_numeric_string_time_is_accepted(make_dataset):
    result = load_laps(make_dataset([lap("AAA", "Q1", "80.5")]))
    assert result.laps[0].time == 80.5
    assert result.malformed == 0


@pytest.mark.parametrize("bad", [0, -5.0])
def test_req_in_7_non_positive_time_is_missing(make_dataset, bad):
    result = load_laps(make_dataset([lap("AAA", "Q1", bad)]))
    assert result.laps[0].time is None
    assert result.malformed == 1


def test_req_in_7_boolean_strings_are_read(make_dataset):
    result = load_laps(make_dataset([lap("AAA", "Q1", 80.0, **{"del": "True", "ff1G": "False"})]))
    assert result.laps[0].deleted is True
    assert result.laps[0].ff1g is False
    assert result.malformed == 0


def test_req_in_7_unknown_segment_lap_is_ignored(make_dataset):
    result = load_laps(make_dataset([lap("AAA", "Q4", 80.0), lap("AAA", "Q1", 81.0)]))
    assert [l.qs for l in result.laps] == ["Q1"]
    assert result.malformed == 1


@pytest.mark.parametrize("bad_drv", ["", None])
def test_req_in_7_lap_without_driver_is_ignored(make_dataset, bad_drv):
    result = load_laps(make_dataset([lap("AAA", "Q1", 80.0), lap(bad_drv, "Q1", 81.0)]))
    assert [l.drv for l in result.laps] == ["AAA"]
    assert result.malformed == 1

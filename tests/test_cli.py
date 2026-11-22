"""REQ-DRV-*, REQ-OUT-*, REQ-RT-*: the command-line interface end to end."""

import ast
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import REAL_DATA, ROOT, lap, rows_of

DATA = ["--data", str(REAL_DATA)]


# --- REQ-OUT-1: text report ------------------------------------------------------------------

def test_req_out_1_report_for_pole_sitter(run_cli):
    code, out, err = run_cli("RUS", *DATA)
    assert code == 0
    assert "RUS · Mercedes" in out
    assert "Classified P1 of 19" in out
    rows = rows_of(out)
    assert rows["Q1"][:4] == ["Q1", "1:19.507", "1", "+0.000"]
    assert rows["Q2"][:4] == ["Q2", "1:18.934", "1", "+0.000"]
    assert rows["Q3"][:4] == ["Q3", "1:18.518", "1", "+0.000"]
    assert "Insights" in out
    assert "- Teammate ANT (P2): Q1 -0.613, Q2 -0.501, Q3 -0.293 (faster in 3 of 3)" in out
    assert err == ""


def test_req_out_1_report_shows_note_and_missing_segment(run_cli):
    code, out, _ = run_cli("BOR", *DATA)
    assert code == 0
    assert "Classified P10 of 19" in out
    assert "Reached Q3 but set no time; placed behind Q3 runners" in out
    rows = rows_of(out)
    assert rows["Q2"][:4] == ["Q2", "1:20.221", "10", "+1.287"]
    assert rows["Q3"] == ["Q3", "—", "no", "time", "set"]


def test_req_out_1_did_not_take_part(run_cli):
    _, out, _ = run_cli("ALO", *DATA)
    rows = rows_of(out)
    assert rows["Q2"] == ["Q2", "—", "did", "not", "take", "part"]
    assert "- Teammate: not in this dataset" in out


def test_req_out_1_unclassified_driver(run_cli):
    code, out, _ = run_cli("VER", *DATA)
    assert code == 0
    assert "Not classified (NC)" in out
    assert "No valid lap set" in out
    assert "Classified P" not in out


def test_req_out_3_list(run_cli):
    code, out, _ = run_cli("--list", *DATA)
    lines = out.strip().splitlines()
    assert code == 0
    assert len(lines) == 20
    assert lines[0] == "ALB  Williams"
    assert "VER  Red Bull Racing" in lines
    assert [l.split()[0] for l in lines] == sorted(l.split()[0] for l in lines)


def test_req_out_2_json_is_not_in_the_mvp(run_cli):
    # An unknown option is a usage error, whether main() returns 2 or argparse exits with 2.
    try:
        code, _, _ = run_cli("RUS", "--json", *DATA)
    except SystemExit as exc:
        code = exc.code
    assert code == 2


# --- REQ-DRV: driver code on the command line ------------------------------------------------

def test_req_drv_1_code_is_normalised(run_cli):
    code, out, _ = run_cli("  rus ", *DATA)
    assert code == 0
    assert "RUS · Mercedes" in out


@pytest.mark.parametrize("bad", ["12", "RUSS", "R5S", "ru"])
def test_req_drv_2_bad_format(run_cli, bad):
    code, out, err = run_cli(bad, *DATA)
    assert code == 2
    assert err.strip() == "Driver code must be three letters, e.g. RUS"
    assert out == ""


@pytest.mark.parametrize("unknown", ["XYZ", "STR", "SAI"])
def test_req_drv_3_unknown_driver(run_cli, unknown):
    code, _, err = run_cli(unknown, *DATA)
    assert code == 2
    assert err.startswith(f"Driver {unknown} not found in this dataset. Available: ALB, ALO, ANT")


# --- REQ-DRV-4: interactive prompt -----------------------------------------------------------

def test_req_drv_4_prompt_reasks_then_reports_then_quits(run_cli):
    code, out, err = run_cli(*DATA, stdin="XYZ\n\nRUSS\nhul\nq\n")
    assert code == 0
    assert out.count("Driver code (e.g. HUL, or q to quit): ") == 5
    assert "Driver XYZ not found in this dataset. Available: ALB" in out
    assert "Driver code must be three letters, e.g. RUS" in out
    assert "HUL · Audi" in out
    assert err == ""


def test_req_drv_4_asks_again_after_a_report(run_cli):
    code, out, _ = run_cli(*DATA, stdin="rus\nbor\nQUIT\n")
    assert code == 0
    assert "RUS · Mercedes" in out and "BOR · Audi" in out


def test_req_drv_4_end_of_input_exits_cleanly(run_cli):
    code, out, err = run_cli(*DATA, stdin="hul\n")      # no "q": input simply ends
    assert code == 0
    assert "HUL · Audi" in out
    assert "Traceback" not in out + err


def test_req_drv_4_ctrl_c_exits_cleanly(run_cli, monkeypatch):
    def interrupted(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupted)
    code, out, err = run_cli(*DATA)
    assert code == 0
    assert "Traceback" not in out + err


def test_req_drv_4_data_problem_exits_before_prompting(run_cli, tmp_path):
    code, out, err = run_cli("--data", str(tmp_path / "missing.json"), stdin="hul\n")
    assert code == 1
    assert "Driver code" not in out


# --- REQ-IN via the CLI: file problems, default path, warnings -------------------------------

def test_req_in_6_bad_file_exits_1_with_one_line(run_cli, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    code, out, err = run_cli("RUS", "--data", str(path))
    assert code == 1
    assert out == ""
    assert len(err.strip().splitlines()) == 1


def test_req_in_1_default_path_is_relative_to_cwd(run_cli, monkeypatch, tmp_path):
    (tmp_path / "data").mkdir()
    shutil.copy(REAL_DATA, tmp_path / "data" / "session_laptimes.json")
    monkeypatch.chdir(tmp_path)
    code, out, _ = run_cli("RUS")
    assert code == 0
    assert "Classified P1 of 19" in out


def test_req_in_2_data_option_overrides_default(run_cli, make_dataset):
    path = make_dataset([lap("AAA", "Q1", 80.0, team="Solo")])
    code, out, _ = run_cli("AAA", "--data", str(path))
    assert code == 0
    assert "AAA · Solo" in out


def test_req_in_7_warning_on_stderr_and_report_still_printed(run_cli, make_dataset):
    path = make_dataset([lap("AAA", "Q1", "abc"), lap("AAA", "Q1", 80.0)])
    code, out, err = run_cli("AAA", "--data", str(path))
    assert code == 0
    assert "1:20.000" in out
    assert err.strip() == "Warning: ignored or treated as missing 1 malformed values"


# --- REQ-OUT-4 / REQ-RT ------------------------------------------------------------------------

def test_req_rt_3_output_is_deterministic(run_cli):
    assert run_cli("LEC", *DATA) == run_cli("LEC", *DATA)


def test_req_rt_1_runtime_imports_only_the_standard_library():
    src = ROOT / "src" / "qualifying"
    imported = set()
    for path in src.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add(node.module.split(".")[0])
    third_party = imported - set(sys.stdlib_module_names) - {"qualifying"}
    assert third_party == set()


def test_req_rt_1_no_runtime_dependencies_declared():
    tomllib = pytest.importorskip("tomllib")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project.get("dependencies", []) == []
    assert project["requires-python"] == ">=3.10"


def test_req_rt_2_python_dash_m_without_uv():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run([sys.executable, "-m", "qualifying", "RUS"],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "Classified P1 of 19" in proc.stdout


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_req_rt_2_uv_run_quali():
    proc = subprocess.run(["uv", "run", "quali", "RUS"],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert "Classified P1 of 19" in proc.stdout

# Spec: Driver qualifying lookup

| | |
|---|---|
| Status | **Draft — for review** |
| Data | `data/session_laptimes.json` (2026 Australian GP Qualifying) |
| Background | `docs/eda_findings.md`, `README.md` (Decisions, Assumptions) |

Each requirement has an ID (`REQ-…`). Tests are named after the requirement they check
(e.g. `test_req_cls_2_…`). To change behaviour, change this spec first, then the tests, then the code.

"Must" is required; "should" is preferred but not tested.

---

## 1. Purpose and scope

The user provides a three-letter driver code. The tool shows:
1. the driver's **best valid lap time in Q1, Q2 and Q3**
2. the driver's **final classified qualifying position**, derived from the dataset only
3. **insights** that put those numbers in context

**In scope:** one session file, a command-line interface, text output (JSON output is *Later*, §1.1).

**Out of scope:** other sessions or events, official results, weather (the per-lap weather
fields are unreliable, see EDA §3.1), telemetry, a graphical UI.

### 1.1 Release scope

| Release | Requirements |
|---|---|
| **MVP** | Everything in §3 and §4 **except** the items marked *Later*. That means one insight: **REQ-INS-2** (teammate head-to-head) |
| **Later** | REQ-INS-1 gap to pole and neighbours · REQ-INS-3 cutoff margins · REQ-INS-4 theoretical best · REQ-INS-5 red flags · REQ-INS-6 data caveats · REQ-ADV-3 consistency check (it only feeds caveats) · REQ-OUT-2 JSON output (`--json`) and REQ-FMT-3 raw values in JSON |

*Later* requirements stay fully specified so they can be built without reopening decisions. Tests for
them aren't written until they're scheduled. The MVP still reports BOR's and VER's situations
through the classification note (REQ-CLS-8) and the NC reason (REQ-CLS-6), not through caveats.

## 2. Glossary

| Term | Meaning |
|---|---|
| Segment | Q1, Q2 or Q3, taken from the `qs` field of each lap. Often called "sessions" elsewhere (including the original request); this project always says *segment* |
| Session | The whole of qualifying, Q1 to Q3. `sesT` and "session best" refer to this |
| Valid lap | A lap that counts as a timed attempt (REQ-LAP-1) |
| Segment best | A driver's fastest valid lap within one segment |
| Reached | The driver qualified for that segment under the fixed cutoffs (REQ-ADV-1), whether or not they set a time in it |
| Cutoff | How many drivers advance from a segment: 16 from Q1, 10 from Q2 (REQ-ADV-2) |
| Classified | Given a numeric position; otherwise **NC** (not classified) |
| Deciding time | The time that determines a driver's place: their best in the furthest segment they reached |

---

## 3. Requirements

### 3.1 Runtime

**REQ-RT-1 — No third-party runtime dependencies.** The tool must run with the Python standard
library only, on **Python ≥ 3.10**, so a reviewer doesn't need a very recent interpreter. pytest is a
development dependency. EDA tooling is in the `eda` group and may need a newer Python (numpy needs
≥ 3.12); that must not raise the tool's own minimum.

**REQ-RT-2 — Commands.** From the project root, both of these must run the tool:
- `uv run quali <CODE>`
- `python -m qualifying <CODE>`, with no uv and nothing installed (`src/` on the path, e.g.
  `PYTHONPATH=src`). The README states the exact command.

**REQ-RT-3 — Deterministic.** The same input must always give the same output.

### 3.2 Loading data

**REQ-IN-1 — Default file.** With no `--data` option, the tool reads `data/session_laptimes.json`
relative to the current working directory.

**REQ-IN-2 — Override.** `--data PATH` reads the given file instead.

**REQ-IN-3 — Columnar format.** The file is a JSON object whose values are equal-length lists,
one per field. Row *i* is the *i*-th element of every list.

**REQ-IN-4 — Missing values.** The string `"None"` (and JSON `null`) must be treated as missing.

**REQ-IN-5 — Required fields.** The loader needs at least: `drv`, `team`, `lap`, `qs`, `time`,
`s1`, `s2`, `s3`, `sesT`, `pin`, `pout`, `del`, `status`, `ff1G`.

**REQ-IN-6 — Malformed file.** If the file is missing, isn't valid JSON, isn't a JSON object at the
top level, lacks a required field, has a field that isn't a list, or has lists of different lengths,
the tool must print one line to stderr naming the problem and exit with code **1**.

**REQ-IN-7 — Malformed values.** Inside a well-formed file, bad individual values must not crash the
tool or stop the report. Each one is handled as follows:

| Value | Handling |
|---|---|
| A time (`time`, `s1`–`s3`, `sesT`, `pin`, `pout`) that isn't a number or numeric string, e.g. `"abc"` | Treated as missing |
| `time` of zero or less | Treated as missing |
| `del` / `ff1G` given as `"True"` / `"False"` strings | Read as the boolean; any other non-boolean value is treated as missing |
| `qs` not one of `Q1`, `Q2`, `Q3` | Lap ignored |
| `drv` missing or empty | Lap ignored |

The tool then prints **one** warning line to stderr with the count, e.g.
`Warning: ignored or treated as missing 3 malformed values`, and continues. This doesn't change the
exit code. Values that are legitimately missing (`"None"`, `null`, REQ-IN-4) aren't counted.

> *Example:* the real file produces no warning.
>
> *Example (synthetic):* one lap with `time` `"abc"` → that lap isn't valid, the report is printed,
> and stderr has a warning with count 1.

### 3.3 Driver code input

**REQ-DRV-1 — Normalisation.** The code must be stripped of surrounding whitespace and uppercased
(`" rus "` → `RUS`).

**REQ-DRV-2 — Format.** After normalisation the code must match `^[A-Z]{3}$`. Otherwise the tool
must print `Driver code must be three letters, e.g. RUS` to stderr and exit with code **2**.

**REQ-DRV-3 — Unknown driver.** A well-formed code that isn't in the data must print
`Driver XYZ not found in this dataset. Available: ALB, ALO, …` (codes sorted) to stderr and exit with
code **2**. This covers STR and SAI, who are absent from this file (EDA §2).

**REQ-DRV-4 — Interactive prompt.** *(MVP)* If no code is given on the command line, the tool
loads the data once, then asks `Driver code (e.g. HUL, or q to quit): `. In this mode, **input
problems never end the program or set an error exit code.** It always explains and asks again:

| Input | Response |
|---|---|
| Valid, known code | Print the report (REQ-OUT-1), then ask for another code |
| Bad format, e.g. `12`, `RUSS` | Print the REQ-DRV-2 message to stdout, ask again |
| Unknown code, e.g. `XYZ`, `STR` | Print the REQ-DRV-3 message (with available codes) to stdout, ask again |
| Empty line | Ask again, no message |
| `q` or `quit` (any case) | Exit with code 0 |
| End of input (Ctrl-D) or Ctrl-C | Print a newline, exit with code 0, no traceback |

Data-file problems (REQ-IN-6) are found before the first prompt, so they still exit with code 1:
there is nothing useful to ask for.

Passing a code on the command line (`quali HUL`) still prints one report and exits, following
REQ-DRV-2/3 and REQ-OUT-4. That keeps the tool scriptable and easy to test.

> *Example:* `XYZ` → `Driver XYZ not found in this dataset. Available: ALB, ALO, …` → prompt again
> → `hul` → HUL's report → prompt again → `q` → exit 0.

### 3.4 Valid laps

**REQ-LAP-1 — Definition.** A lap is valid if **all** of these hold:
- `time` is present
- `del` is not true
- `pout` is missing (not an out-lap)
- `pin` is missing (not an in-lap)
- `status` does not contain `5` (not interrupted by a red flag)
- `ff1G` is not true (not generated by FastF1)

There is no 107% filter.

> *Example:* VER lap 1 has `time` 102.025 but is an out-lap → not valid. VER has **no** valid laps.
>
> *Example (synthetic):* a driver's fastest lap in Q2 has `del = true` → it's ignored, and the next
> fastest valid lap is their Q2 best.

**REQ-LAP-2 — Deletion source.** Lap deletion must be read only from `del`. The lap number in `delR`
must not be used (it's off by one, EDA §3.4).

### 3.5 Segment bests

**REQ-SEG-1 — Segment best.** For each driver and segment, the segment best is the minimum `time`
among their valid laps with that `qs`. If there are none, the segment best is *missing*.

**REQ-SEG-2 — Segment rank.** Within each segment, drivers with a segment best are ranked 1…n by
time (ties per REQ-CLS-5). Drivers without one have no rank in that segment.

**REQ-SEG-3 — Gap to segment fastest.** For a driver with a segment best: their time minus the
fastest segment best in that segment (0 for the fastest driver).

> *Example:* LIN — Q1 1:20.409 (8th, +0.902), Q2 1:19.971 (8th, +1.037), Q3 1:21.247 (9th, +2.729).

**REQ-SEG-4 — Why a time is missing.** When a driver has no segment best, the report must say why:
- `no time set`: they reached the segment (REQ-ADV-1) but have no valid lap in it (BOR in Q3, VER in Q1)
- `did not take part`: they didn't reach the segment (ALO in Q2 and Q3)

### 3.6 Reaching segments

**REQ-ADV-1 — Who reached each segment.**
- Every driver in the file reached **Q1**.
- The top **16** of the Q1 order (REQ-CLS rules applied to Q1 alone) reached **Q2**.
- The top **10** of the Q2 order (REQ-CLS rules applied to Q2 alone, among those who reached Q2)
  reached **Q3**.

This applies whether or not the driver has laps labelled with that segment.

> *Example:* BOR is 10th in Q2 (1:20.221) → **reached Q3**, even though the file has no Q3 laps
> for him.

**REQ-ADV-2 — Fixed cutoffs.** The cutoffs are one configuration constant,
`ADVANCE = {"Q2": 16, "Q3": 10}` (2026 regulations, 22-car grid), not literals spread through the
code.

**REQ-ADV-3 — Consistency check.** *(Later)* The tool compares REQ-ADV-1 with the `qs` labels. If they
disagree, REQ-ADV-1 still decides, and the affected driver gets a data caveat (REQ-INS-6):
- reached a segment but has no laps labelled with it (BOR in Q3)
- has laps labelled with a segment they didn't reach

### 3.7 Classification

The classification orders every driver in the file.

**REQ-CLS-1 — Furthest segment first.** Drivers who reached Q3 come before drivers whose furthest
segment was Q2, who come before those whose furthest was Q1.

**REQ-CLS-2 — Timed drivers first, by time.** Within the same furthest segment, drivers with a
segment best there come first, ordered by that time (fastest first).

> *Example:* P1–P9 are the Q3 times: RUS, ANT, HAD, LEC, PIA, NOR, HAM, LAW, LIN.

**REQ-CLS-3 — A single driver without a time.** If exactly one driver reached a segment and set no
time in it, they're placed directly behind that segment's timed drivers. Their previous segment's
time isn't used.

> *Example:* BOR reached Q3 with no Q3 time → **P10**, directly behind LIN (P9), ahead of every
> driver whose furthest segment was Q2.

**REQ-CLS-4 — Several drivers without a time.** If two or more drivers reached the same segment and
set no time in it, they're placed behind that segment's timed drivers and ordered among themselves by
their best time in the previous segment. If they're still tied or also have no time there, go back
one more segment.

> *Example (synthetic):* A and B both reach Q3 with no Q3 time; Q2 bests A 1:19.900, B 1:19.800
> → B ahead of A.

**REQ-CLS-5 — Equal times.** When two drivers have the same deciding time, the one who set it
first (lower `sesT` on that lap) is ahead. If they're still equal, or there are no times left to
compare, driver code decides alphabetically, so the order is always deterministic (REQ-RT-3).

**REQ-CLS-6 — Unclassified.** A driver with **no valid lap in any segment** is **NC** (not
classified), with the reason `No valid lap set`. NC drivers are listed after all classified drivers,
sorted by code.

> *Example:* VER → NC.

**REQ-CLS-7 — Numbering.** Classified drivers are numbered 1…n with no gaps. NC drivers take no
number. The total shown is the number of classified drivers ("P10 of 19").

**REQ-CLS-8 — Placement note.** A driver placed by REQ-CLS-3 or REQ-CLS-4 must carry a note, e.g.
`Reached Q3 but set no time; placed behind Q3 runners`, or for REQ-CLS-4
`…; ordered by Q2 time`.

### 3.8 Time format

**REQ-FMT-1 — Lap times.** Every lap or summed-sector time shown to the user is **`m:ss.sss`**.
Minutes aren't zero-padded; seconds are two digits; always three decimals.
Rounding is to the nearest millisecond, using integer milliseconds (`round(seconds × 1000)`).

| Input (s) | Output |
|---|---|
| 78.518 | `1:18.518` |
| 65.12 | `1:05.120` |
| 78.5179 | `1:18.518` |
| 59.9996 | `1:00.000` |
| missing | `—` |

**REQ-FMT-2 — Deltas.** Differences are signed, with three decimals: `+0.293`, `-0.613`, `+0.000`.
At 60 s or more in magnitude they use the `m:ss.sss` form: `+1:02.410`.

**REQ-FMT-3 — JSON keeps raw values.** *(Later, with REQ-OUT-2)* JSON output carries times as seconds (number) **and** the
formatted string (`"time": 78.518, "display": "1:18.518"`).

### 3.9 Output

**REQ-OUT-1 — Text report** (default). Layout:

```
RUS · Mercedes
Classified P1 of 19

Segment  Best lap   Rank  Gap
Q1       1:19.507   1     +0.000
Q2       1:18.934   1     +0.000
Q3       1:18.518   1     +0.000

Insights
- Teammate ANT (P2): Q1 -0.613, Q2 -0.501, Q3 -0.293 (faster in 3 of 3)
```

A driver with missing segments (MVP):

```
BOR · Audi
Classified P10 of 19
Reached Q3 but set no time; placed behind Q3 runners

Segment  Best lap   Rank  Gap
Q1       1:20.495   10    +0.988
Q2       1:20.221   10    +1.287
Q3       —                        no time set

Insights
- Teammate HUL (P11): Q1 -0.529, Q2 -0.082 (faster in 2 of 2)
```

That's the MVP output. *Later* insights add lines in REQ-INS order, for example:

```
- Gap to pole: pole
- Car behind: ANT -0.293 (Q3)
- Cutoff margins: Q1 safe by 2.462, Q2 safe by 1.369
- Theoretical best 1:18.518 — 0.000 left on the table; weakest sector: none (all session-best)
- Red flags: run interrupted in Q1 (lap 4) and Q3 (lap 16)
```

Missing segment bests show `—` in the time column, blanks for rank and gap, and the REQ-SEG-4 reason
(`no time set` or `did not take part`) at the end of the row. Insights that don't
apply are omitted (REQ-INS). If none apply, the `Insights` heading is omitted too. A classification
note (REQ-CLS-8) or NC reason (REQ-CLS-6) goes on the line under the position. For an NC driver the
position line reads `Not classified (NC)`. Column alignment uses plain spaces; no colour codes.

**REQ-OUT-2 — JSON.** *(Later)* In the MVP, `--json` isn't accepted: argparse rejects it as an
unknown option (exit 2). When built, `--json` prints one JSON object to stdout instead:

```json
{
  "code": "BOR", "team": "Audi",
  "position": 10, "classified_count": 19,
  "note": "Reached Q3 but set no time; placed behind Q3 runners",
  "segments": {
    "Q1": {"time": 80.495, "display": "1:20.495", "rank": 10, "gap": 0.988},
    "Q2": {"time": 80.221, "display": "1:20.221", "rank": 10, "gap": 1.287},
    "Q3": null
  },
  "insights": [{"id": "INS-2", "title": "Teammate HUL (P11)", "detail": "Q1 -0.529, Q2 -0.082 (faster in 2 of 2)"}],
  "caveats": []
}
```

For an NC driver, `position` is `null` and `note` is `No valid lap set`. The `caveats` key is always
present so the shape stays stable; it's empty until REQ-INS-6 (*Later*) is built.

**REQ-OUT-3 — List.** `--list` prints every driver code with team, one per line, sorted by code,
as `CODE  Team` (two spaces), and exits 0. It needs no driver code.

**REQ-OUT-4 — Exit codes.** 0 success · 1 data file problem · 2 usage error or unknown driver.
Code 2 only applies when the code is given on the command line. The interactive prompt
(REQ-DRV-4) never exits with 2.

### 3.10 Insights

Each insight is computed independently. An insight that doesn't apply to the driver is omitted, not
shown as an error. Weather-based insights are excluded (EDA §3.1).

**REQ-INS-1 — Gap to pole and to neighbours.** *(Later)*
- *Gap to pole:* the driver's fastest valid lap of the session minus the P1 driver's deciding time.
  Shown as `pole` for P1. Omitted for NC drivers.
- *Car ahead / car behind:* the classified drivers directly ahead and behind. A gap is shown only
  when **both drivers set a valid time in the same deciding segment**, i.e. the furthest segment each
  reached is the same and both have a time in it. The gap is labelled with that segment. Otherwise
  that line is omitted, because times from different segments aren't comparable.
- Deltas use the sign convention in REQ-INS-2.

> *Examples:*
> - LIN (P9) — car ahead LAW +1.253 (Q3); car behind BOR omitted (BOR has no Q3 time).
> - BOR (P10) — gap to pole +1.703; both neighbour lines omitted (no Q3 time; HUL's deciding segment is Q2).
> - HUL (P11) — car ahead BOR omitted (different deciding segment); car behind BEA -0.008 (Q2).

**REQ-INS-2 — Teammate head-to-head.** *(MVP — the one extra insight)*

*Why this insight:* teammates drive the same car, so the gap between them is the cleanest measure of
the **driver's** performance. The position and segment times mix driver and car.

- **Teammate:** the other driver(s) in the data with the same `team`. If there is more than one,
  one line per teammate, sorted by code.
- **Line:** `Teammate <CODE> (<position or NC>): <segment> <delta>, …` for each segment in which
  **both** set a valid time, in segment order, followed by `(faster in x of y)`.
- **Sign convention** (used by every head-to-head delta in this spec): the driver's time minus the
  other driver's time, so **negative means the driver was faster**.
- **No shared timed segment:** `Teammate <CODE> (<position>): no comparable segment`.
- **No teammate in the data:** `Teammate: not in this dataset`. In the MVP this is shown, not
  omitted, so every driver gets an insight line. It's also the caveat REQ-INS-6 lists for later.

> *Examples:*
> - RUS → `Teammate ANT (P2): Q1 -0.613, Q2 -0.501, Q3 -0.293 (faster in 3 of 3)`
> - BOR → `Teammate HUL (P11): Q1 -0.529, Q2 -0.082 (faster in 2 of 2)`
> - LEC → `Teammate HAM (P7): Q1 +0.415, Q2 -0.564, Q3 -0.151 (faster in 2 of 3)`
> - VER → `Teammate HAD (P3): no comparable segment`
> - ALO → `Teammate: not in this dataset`

**REQ-INS-3 — Cutoff margins.** *(Later)* For each elimination segment (Q1, Q2) in which the driver set a
valid time, using the cutoff *k* (REQ-ADV-2: 16 for Q1, 10 for Q2) and that segment's order:
- *Advanced:* margin = time of the first eliminated driver (position *k*+1) minus the driver's
  time → `safe by x`.
- *Eliminated:* deficit = driver's time minus the last advancing driver's time (position *k*) →
  `out by x`.

Omitted for a segment where nobody was eliminated, or where the first eliminated or last advancing
driver has no time.

> *Examples:* BOR Q2 safe by 0.082 (HUL, 11th, 1:20.303). HUL Q2 out by 0.082 (BOR, 10th,
> 1:20.221). ALO Q1 out by 0.722 (BEA, 16th, 1:21.247).

**REQ-INS-4 — Theoretical best and weakest sector.** *(Later)* Using the driver's valid laps across all
segments:
- theoretical best = min `s1` + min `s2` + min `s3`
- time left on the table = fastest valid lap − theoretical best (never negative)
- weakest sector = the sector with the largest gap between the driver's best and the session-best
  sector (session-best from all valid laps). If all three gaps are 0, report `none`.

> *Example:* LIN — theoretical best 1:19.753, 0.218 left; weakest sector 3 (+0.682).

**REQ-INS-5 — Red-flag impact.** *(Later)* List the driver's laps whose `status` contains `5`, as segment
and lap number. Omitted if there are none.

> *Example:* RUS — Q1 (lap 4), Q3 (lap 16).

**REQ-INS-6 — Data caveats** *(Later)* (shown under a separate heading, and as `caveats` in JSON once REQ-OUT-2 exists):
- NC → `No valid lap in the data` (VER)
- only driver of their team in the data → `Teammate not in this dataset` (ALO, ALB)
- REQ-ADV-3, reached but no laps → `Reached Q3 but has no Q3 laps in the data; may be missing` (BOR)
- REQ-ADV-3, laps but not reached → `Has Q3 laps but was not in the Q2 top 10`

---

## 4. Deliverables

**REQ-DOC-1 — Technical write-up.** `docs/WRITEUP.md` must cover, briefly:
1. How to build, run and test (both REQ-RT-2 commands, and `uv run pytest`)
2. Overall approach, architecture and key design choices
3. Assumptions and trade-offs, and why (valid-lap rule, fixed cutoffs, no-time placement, NC, weather excluded)
4. Why the teammate comparison was chosen and what it shows (REQ-INS-2)
5. Testing approach (REQ-TEST-1)
6. Future improvements (the *Later* items in §1.1)
7. How AI tools were used and how they influenced the solution. This section is written by or
   confirmed by the author.

**REQ-TEST-1 — Test suite.** A small pytest suite that shows a deliberate approach rather than
coverage. It must include:
- at least one test per MVP requirement, named after it (`test_req_cls_3_…`)
- the full acceptance table in §5, checked against the real file
- small synthetic data for rules the real file doesn't exercise: deleted fastest lap, tie on equal
  times, several drivers with no time (REQ-CLS-4), malformed values (REQ-IN-7)
- error paths: missing file, invalid JSON, unequal lists, bad code format, unknown code, exit codes
- the interactive prompt driven by scripted input (e.g. `XYZ`, empty line, `hul`, `q`): each bad
  input is explained and re-asked, the report appears, and the exit code is 0
- `format_laptime` / `format_delta` edge cases (REQ-FMT-1/2)

**REQ-DOC-2 — Repository hygiene.** The data's license and attribution (`data/LICENSE`,
`data/NOTICE.md`) stay in the repo. The exercise brief (`brief.md`) isn't committed.

---

## 5. Acceptance: expected classification for this file

| P | Code | Deciding time | Note |
|---|---|---|---|
| 1 | RUS | Q3 1:18.518 | |
| 2 | ANT | Q3 1:18.811 | |
| 3 | HAD | Q3 1:19.303 | |
| 4 | LEC | Q3 1:19.327 | |
| 5 | PIA | Q3 1:19.380 | |
| 6 | NOR | Q3 1:19.475 | |
| 7 | HAM | Q3 1:19.478 | |
| 8 | LAW | Q3 1:19.994 | |
| 9 | LIN | Q3 1:21.247 | |
| 10 | BOR | — (Q3, no time) | Reached Q3 as 10th in Q2, set no time (REQ-CLS-3) |
| 11 | HUL | Q2 1:20.303 | |
| 12 | BEA | Q2 1:20.311 | |
| 13 | OCO | Q2 1:20.491 | |
| 14 | GAS | Q2 1:20.501 | |
| 15 | ALB | Q2 1:20.941 | |
| 16 | COL | Q2 1:21.270 | |
| 17 | ALO | Q1 1:21.969 | |
| 18 | PER | Q1 1:22.605 | |
| 19 | BOT | Q1 1:23.244 | |
| NC | VER | — | No valid lap set (REQ-CLS-6) |

## 6. Open questions

1. ~~Fixed cutoffs vs. `qs` labels~~ — **Resolved:** fixed cutoffs, 16 and 10 (REQ-ADV-1,
   REQ-ADV-2), so BOR counts as a Q3 driver with no time. `qs` disagreements become caveats
   (REQ-ADV-3).
2. ~~Neighbour gaps across segments~~ — **Resolved:** only within the same deciding segment (REQ-INS-1).
3. ~~Segment vs session~~ — **Resolved:** Q1–Q3 are *segments*; *session* means the whole of
   qualifying (Glossary).

# EDA findings — `data/session_laptimes.json`

Reference write-up of the exploratory analysis, to build on when starting a project with this data.
The full, re-runnable analysis is `notebooks/eda_session_laptimes.ipynb`
(`uv run --group eda jupyter nbconvert --to notebook --execute --inplace notebooks/eda_session_laptimes.ipynb`).
The EDA tools (pandas, numpy, matplotlib, notebook tooling) live in the `eda` dependency group;
the project runtime has no third-party dependencies.

_Written 2026-11-22._

## 1. The dataset

| | |
|---|---|
| Source | Tracing Insights 2026 repo, *Australian Grand Prix / Qualifying*, redistributed unmodified (Apache-2.0, see `data/NOTICE.md`, `data/LICENSE`) |
| Session | 2026 Australian GP Qualifying, started 2026-03-07 05:00 UTC |
| Shape | 355 laps × 43 fields |
| Grain | one row per driver per lap |
| Field docs | `data/DATA_REFERENCE.md` → *LAP TIMES DATA* |

**Format.** The JSON is *columnar*: a dict of 43 equal-length lists. Missing values are the **string**
`"None"`, not JSON `null`, so numeric columns load as `object` until converted.

### Loading recipe

```python
import json, numpy as np, pandas as pd

raw = json.load(open("data/session_laptimes.json"))
df = pd.DataFrame(raw).replace("None", np.nan)

num_cols = ["time", "s1", "s2", "s3", "sesT", "lST", "s1T", "s2T", "s3T", "pin", "pout",
            "vi1", "vi2", "vfl", "vst", "pos", "wT", "wAT", "wH", "wP", "wTT", "wWD", "wWS"]
df[num_cols] = df[num_cols].apply(pd.to_numeric)
for c in ["pb", "del", "fresh", "ff1G", "iacc", "wR"]:
    df[c] = df[c].astype("boolean")   # nullable: pb and del have gaps
df["lSD"] = pd.to_datetime(df["lSD"])
df = df.sort_values(["drv", "lap"]).reset_index(drop=True)
```

All times are **seconds**; `sesT`, `lST`, `s*T`, `pin`, `pout`, `wT` are seconds since session start.

### Field groups

| Group | Fields | Notes |
|---|---|---|
| Identity | `drv`, `dNum`, `team`, `lap`, `qs` | `qs` ∈ Q1/Q2/Q3 (171 / 121 / 63 laps) |
| Timing | `time`, `s1`–`s3`, `sesT`, `lST`, `lSD`, `s1T`–`s3T` | `time` null on 109 laps; `s3` null on 92 |
| Speed traps | `vi1`, `vi2`, `vfl`, `vst` (km/h) | `vfl` null on 95 laps |
| Tyres | `compound`, `life`, `fresh`, `stint` | 339 SOFT, 16 MEDIUM |
| Mini-sectors | `ms1`, `ms2`, `ms3` | digit strings (9 / 5 / 10 chars), colour codes per reference |
| Status / quality | `status`, `pb`, `del`, `delR`, `iacc`, `ff1G`, `pos` | `pos` 100% null (expected in qualifying) |
| Pits | `pin`, `pout` | set only on in-laps / out-laps |
| Weather | `wT`, `wAT`, `wH`, `wP`, `wR`, `wTT`, `wWD`, `wWS` | **unusable as joined**, see §3.1 |

`status` is the *sequence* of track-status codes seen during the lap: values are `1`, `12`, `125`, `152`.
Any lap containing `5` was hit by a red flag.

## 2. Coverage

- **20 drivers, 11 teams.** The 2026 grid is 22 cars; **Stroll (Aston Martin) and Sainz (Williams)
  have no rows at all.**
- **Verstappen has 2 laps**: an out-lap and a lap aborted by the Q1 red flag. He has no timed push lap.
- **Bortoleto** was 10th in Q2 (80.221) but has **no Q3 laps**. His last row is a pit-in during Q2.
  Either he didn't run in Q3 or the data is missing; check against official results before relying on it.
- Laps per driver range from 2 (VER) to 26 (PIA); stints from 1 to 8.

## 3. Data-quality issues and how to handle them

| # | Issue | Evidence | Handling |
|---|---|---|---|
| 3.1 | **Per-lap weather is matched by lap number, not time** | every driver's lap *N* has identical `wT` (max 1 distinct value per lap number); gap between `wT` and lap start is median 110 s, max 4,695 s | Ignore `w*` columns. Re-join `weather.json` from the same upstream session with `pd.merge_asof` on `lST`. |
| 3.2 | **`time` is populated on out-laps** | VER's minimum `time` is 102.025, which is an out-lap | Never take raw `min(time)`. Filter to push laps (§4). |
| 3.3 | Out-lap `time` ≠ `sesT − lST` | 35 laps differ, all out-laps, by up to 22.3 s | Use `sesT − lST` for elapsed time on out-laps; don't use their `time` for pace. |
| 3.4 | **`delR` lap number is off by one** | all 3 deleted laps: the reason text names `lap + 1` | Trust `del` and `lap`; don't parse lap numbers out of `delR`. |
| 3.5 | Sector values copied from previous lap | VER lap 2 `s1` = 41.429, BOR lap 14 `s3` = 34.531 (both in/red-flag laps) | Harmless if you only use push laps; otherwise drop sector values equal to the previous lap's. |
| 3.6 | FastF1-generated laps | LEC lap 24, PIA lap 26 (`ff1G`): null `pb`, `del`, `lSD` | Exclude, or treat as untimed. |
| 3.7 | `qs` boundaries overlap | Q2 laps end at 4,458 s; first Q3 lap starts at 4,305 s | Use `qs` as given; don't derive segments from time windows. |
| 3.8 | `iacc` false on 54% of laps | false on out / in / cool-down laps | Expected; not a reason to drop push laps by itself. |

Checks that passed:
- `s1 + s2 + s3 == time` on every fully-timed lap (floating-point error only).
- `pb` marks each driver's fastest non-deleted lap correctly for all 19 drivers with a timed lap.

## 4. Lap classification

Rules applied in order (the red-flag rule must come first, since those laps usually end in the pits):

| Type | Rule | Laps |
|---|---|---|
| `red_flag` | `status` contains `5` | 28 |
| `out` | `pout` set | 95 |
| `in` | `pin` set | 65 |
| `push` | timed, not deleted, `time < 1.07 × session best` | 102 |
| `other` | everything else (prep, cool-down, aborted) | 65 |

The **102 push laps** are the analysis set for anything pace-related.

## 5. What happened in the session

### Timeline

| Segment | First lap start | Last lap end | Fastest push lap |
|---|---|---|---|
| Q1 | 764 s (12.7 min) | 2,963 s | 79.507 (RUS) |
| Q2 | 2,754 s (45.9 min) | 4,458 s | 78.934 (RUS) |
| Q3 | 4,305 s (71.8 min) | 5,660 s | 78.518 (RUS) |

**Two red flags:**
- **Q1, ~23 min in:** 19 laps aborted, one for every car on track. Verstappen's lap 2 stops after three
  mini-sectors (`ms1 = 134777777`); he pits at 1,677 s and never comes back out. That's consistent with
  him causing the stoppage, but the data has no cause field.
- **Q3, ~75 min in:** during the first runs, so all 9 cars that set Q3 times lost their first attempt.
  Effectively Q3 was a single-run shootout after the restart.

### Classification (best push lap per segment)

| P | Driver | Team | Q1 | Q2 | Q3 | Gap to pole |
|---|---|---|---|---|---|---|
| 1 | RUS | Mercedes | 79.507 | 78.934 | **78.518** | — |
| 2 | ANT | Mercedes | 80.120 | 79.435 | 78.811 | +0.293 |
| 3 | HAD | Red Bull Racing | 80.023 | 79.653 | 79.303 | +0.785 |
| 4 | LEC | Ferrari | 80.226 | 79.357 | 79.327 | +0.809 |
| 5 | PIA | McLaren | 79.664 | 79.525 | 79.380 | +0.862 |
| 6 | NOR | McLaren | 80.010 | 79.882 | 79.475 | +0.957 |
| 7 | HAM | Ferrari | 79.811 | 79.921 | 79.478 | +0.960 |
| 8 | LAW | Racing Bulls | 80.491 | 80.144 | 79.994 | +1.476 |
| 9 | LIN | Racing Bulls | 80.409 | 79.971 | 81.247 | +1.453 |
| 10 | BOR | Audi | 80.495 | 80.221 | — (no laps) | +1.703 |
| 11 | HUL | Audi | 81.024 | 80.303 | | +1.785 |
| 12 | BEA | Haas F1 Team | 81.247 | 80.311 | | +1.793 |
| 13 | OCO | Haas F1 Team | 80.759 | 80.491 | | +1.973 |
| 14 | GAS | Alpine | 81.138 | 80.501 | | +1.983 |
| 15 | ALB | Williams | 81.051 | 80.941 | | +2.423 |
| 16 | COL | Alpine | 81.200 | 81.270 | | +2.682 |
| 17 | ALO | Aston Martin | 81.969 | | | +3.451 |
| 18 | PER | Cadillac | 82.605 | | | +4.087 |
| 19 | BOT | Cadillac | 83.244 | | | +4.726 |
| — | VER | Red Bull Racing | no time | | | |

"Gap to pole" uses each driver's best push lap of the whole session. That's why LIN's gap (Q2 lap)
is smaller than LAW's even though LAW was ahead in Q3. The P column is a reconstruction from this
file, not the official result.

### Pace observations

- **Russell's pole lap had all three session-best sectors** (27.498 / 17.284 / 33.736), so his
  theoretical best equals his actual lap.
- **Time left on the table** (best lap − sum of best sectors): LIN 0.218, COL 0.216, PIA 0.118, BOT 0.119;
  RUS, ANT, HAM, ALO and PER 0.000.
- **Lindblad's Q3 lap (81.247) was 1.28 s slower than his Q2 lap**, although his best sector 2 (17.312, on a Q2 lap)
  was the second-best of any driver, behind only Russell.
- **Top speed (`vst`, team max):** Racing Bulls 315, Audi 311, Ferrari 309, Cadillac 307, Red Bull 305,
  Alpine 302, Haas 300, McLaren 297, Mercedes 297, Aston Martin 292, Williams 288 km/h.
  Mercedes took the front row with joint-8th top speed, so their advantage came from the corners.
- **Track evolution:** fastest lap fell ~0.57 s Q1→Q2 and ~0.42 s Q2→Q3. This mixes track improvement
  with a smaller, faster field, so it isn't a clean grip measure.

### Tyres

- Mediums were used only by **Hamilton (9 laps) and Leclerc (7 laps) in early Q1**; everything else was soft.
- Mean push-lap time, used vs. new soft: Q1 80.22 vs 81.30, Q2 80.10 vs 80.41, Q3 79.88 vs 79.50.
  The used-tyre advantage in Q1/Q2 is confounded by run timing and fuel, so don't read it as a tyre effect.

### Weather (from the per-lap fields, values only)

Air 20.3–20.6 °C, humidity 60–66%, pressure ~1013.5 mbar, no rain. Track temperature fell from about
37.7 to 31.3 °C over the session. Because of §3.1 these values aren't attached to the right laps,
but the ranges are fine for describing the session as a whole.

## 6. Starting points for a project

Things this data supports well:
- **Driver/team pace comparison** on push laps: gaps, sector deltas, theoretical best.
- **Session reconstruction**: run plans, stint lengths, red-flag impact, who improved between runs.
- **Mini-sector analysis** using `ms1`–`ms3` colour codes (green/purple/yellow per mini-sector).
- **Speed-trap vs lap-time trade-offs** (straight-line speed vs. cornering).

Things that need more data first:
- Anything weather-related: fetch `weather.json` for this session and re-join on time.
- Cross-event or season trends: this file is one session. The upstream repo has the same layout per
  event/session, so the loading recipe above should generalise.
- Telemetry-level work (braking, throttle): needs the per-lap `{lap}_tel.json` files.
- Official classification and the two missing drivers (STR, SAI): verify against an external results source.

Suggested first engineering steps:
1. Move the loading recipe and lap classification (§1, §4) into a small module (e.g. `src/qualifying/load.py`)
   so notebooks and scripts share one implementation.
2. Add tests for the data-quality checks in §3 so new sessions are validated on load.
3. Add `.venv/` to `.gitignore` before the first commit.

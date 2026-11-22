# Decisions
CLI vs Streamlit vs Web App: CLI first (`uv run quali RUS`), on a core library a UI can reuse later
Learned lots of the EDA, so can keep it simple
Not bringing in additional deps for ease of running: the runtime is standard library only (no pandas, no `rich`)
EDA tools (pandas, numpy, matplotlib, notebook tooling) are in the `eda` dependency group: `uv sync --group eda` or `uv run --group eda ...`
pytest is in the `dev` group
Use minutes:seconds.milliseconds


# Assumptions
A driver who reached a segment but set no time in it is classified behind everyone who set a time in that segment (e.g. BOR, no Q3 time → P10).
Only if multiple drivers set no time in the same segment are they ordered among themselves by their previous segment's time.
A driver with no valid time in any segment is unclassified (VER), as the data has no earlier session to fall back on.
No access to other datasets


# Future
UI

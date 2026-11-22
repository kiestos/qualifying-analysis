# Qualifying analysis

Console tool for the 2026 Australian GP qualifying lap-times data: a driver's best valid lap in
Q1, Q2 and Q3, final classified position, and a teammate head-to-head.

## Run

Python 3.10+, no third-party dependencies. The commands below use
[uv](https://docs.astral.sh/uv/); without it, use the plain Python command.

```bash
uv run quali HUL                          # one driver
uv run quali                              # interactive; q to quit
uv run quali --list                       # driver codes

PYTHONPATH=src python -m qualifying HUL   # without uv (macOS / Linux)
```

Windows PowerShell without uv: `$env:PYTHONPATH = "src"; python -m qualifying HUL`

## Test

```bash
uv run pytest
```

## Documents

- `docs/WRITEUP.md`: approach, architecture, assumptions, testing, AI use
- `specs/driver-lookup.md`: the specification
- `docs/eda_findings.md`, `notebooks/`: exploratory analysis
- `data/NOTICE.md`, `data/LICENSE`: data attribution (Tracing Insights, Apache-2.0)

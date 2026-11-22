"""Driver qualifying lookup for the Tracing Insights lap-times file.

Spec: specs/driver-lookup.md.

- models.py          domain model (Lap, SegmentResult, DriverResult); no dependencies
- load.py            raw JSON -> list[Lap]; the only module that knows the file format
- classification.py  valid-lap rule, segment bests, reaching segments, final order
- insights.py        teammate head-to-head
- format.py          m:ss.sss and signed deltas
- cli.py             arguments, prompt and text output; the only module doing I/O

Data flow: load -> valid laps -> classification -> insights -> cli.
"""

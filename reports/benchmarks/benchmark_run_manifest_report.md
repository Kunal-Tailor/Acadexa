# Acadexa Benchmark Report

Run ID: `bench_20260930_042934`
Generated: 2026-09-30T04:29:34.393708+00:00

## Environment

- python_version: 3.11.9
- platform: Windows-10-10.0.26200-SP0
- cpu_count: 20
- pandas_version: 3.0.1
- pyspark_version: 4.2.0
- pymongo_version: 4.17.0
- pyarrow_version: 25.0.1
- numpy_version: 1.26.4
- workload: feature_table_join
- engine: pandas
- input_path: data/raw/lms_events

## Feature-table join (`feature_table_join`)

Join per-domain academic summaries at student × course × semester grain with a join-focused metric subset (marks totals, attendance counts, coursework counts, LMS event totals). Per-engine scope is practical, not identical: pandas/Spark join four domains including LMS weekly aggregates, while MongoDB joins the three operational collections it holds (LMS weekly aggregates live outside MongoDB by architecture). Scopes are recorded per result.

Output grain: `student_id × course_id × semester_id`

| Engine | Duration (s) | Input rows | Output rows | Peak memory | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| pandas | 0.29649129998870194 | 38452 | 864 | 3.349 MB | SUCCESS |

## Notes

- Measured results from the local project environment; no technology conclusions are drawn.
- Each engine includes its own read path: pandas/Spark read Parquet datasets, MongoDB aggregates its serving collections.
- Feature-table join scopes differ by engine holdings: pandas/Spark join four domains including LMS weekly aggregates, MongoDB joins the three operational collections.
- Memory figures are Python-allocator peaks where measured; JVM execution memory is not captured (driver memory recorded).

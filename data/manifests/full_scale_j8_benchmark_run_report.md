# Acadexa Benchmark Report

Run ID: `bench_20261001_154957`
Generated: 2026-10-01T16:03:54.734425+00:00

## Environment

- python_version: 3.11.9
- platform: Windows-10-10.0.26300-SP0
- cpu_count: 20
- pandas_version: 3.0.1
- pyspark_version: 4.2.0
- pymongo_version: 4.17.0
- pyarrow_version: 25.0.1
- numpy_version: 1.26.4
- scale: full
- lms_input_path: D:\College\Secondary\Projects\acadexa\data\fullscale\raw\lms_events
- cleaned_base_path: D:\College\Secondary\Projects\acadexa\data\fullscale\cleaned

## Feature-table join (`feature_table_join`)

Join per-domain academic summaries at student × course × semester grain with a join-focused metric subset (marks totals, attendance counts, coursework counts, LMS event totals). Per-engine scope is practical, not identical: pandas/Spark join four domains including LMS weekly aggregates, while MongoDB joins the three operational collections it holds (LMS weekly aggregates live outside MongoDB by architecture). Scopes are recorded per result.

Output grain: `student_id × course_id × semester_id`

| Engine | Duration (s) | Input rows | Output rows | Peak memory | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| pandas | 1.4558247000022675 | 0 | 0 | n/a | FAILED: FileNotFoundError: Domain dataset not found: D:\College\Secondary\Projects\acadexa\data\fullscale\cleaned\lms_weekly_engagement |
| mongodb | 5.08541420000256 | 0 | 0 | n/a | FAILED: ServerSelectionTimeoutError: localhost:27017: [WinError 10061] No connection could be made because the target machine actively refused it (configured timeouts: socketTimeoutMS: 5000.0ms, connectTimeoutMS: 5000.0ms), Timeout: 5.0s, Topology Description: <TopologyDescription id: 6abe8464d0c2cffe146d5fec, topology_type: Unknown, servers: [<ServerDescription ('localhost', 27017) server_type: Unknown, rtt: None, error=AutoReconnect('localhost:27017: [WinError 10061] No connection could be made because the target machine actively refused it (configured timeouts: socketTimeoutMS: 5000.0ms, connectTimeoutMS: 5000.0ms)')>]> |
| pyspark | 1.4223172000019986 | 0 | 0 | n/a | FAILED: AnalysisException: [PATH_NOT_FOUND] Path does not exist: file:/D:/College/Secondary/Projects/acadexa/data/fullscale/cleaned/lms_weekly_engagement. SQLSTATE: 42K03 |

## Weekly LMS engagement aggregation (`weekly_lms_engagement`)

Aggregate event-level LMS data into weekly student-course engagement summaries: total events, positive-only durations, distinct active days, approved activity-category roll-ups and per-type breakdowns (same task as Spark J2).

Output grain: `student_id × course_id × school × semester_id × week_start × week_number`

| Engine | Duration (s) | Input rows | Output rows | Peak memory | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| pandas | 643.3580986000015 | 0 | 0 | n/a | FAILED: MemoryError:  |
| mongodb | 5.163671700000123 | 0 | 0 | n/a | FAILED: ServerSelectionTimeoutError: localhost:27017: [WinError 10061] No connection could be made because the target machine actively refused it (configured timeouts: socketTimeoutMS: 5000.0ms, connectTimeoutMS: 5000.0ms), Timeout: 5.0s, Topology Description: <TopologyDescription id: 6abe83c6d0c2cffe146d5feb, topology_type: Unknown, servers: [<ServerDescription ('localhost', 27017) server_type: Unknown, rtt: None, error=AutoReconnect('localhost:27017: [WinError 10061] No connection could be made because the target machine actively refused it (configured timeouts: socketTimeoutMS: 5000.0ms, connectTimeoutMS: 5000.0ms)')>]> |
| pyspark | 151.11664720000044 | 74757153 | 4682117 | n/a | SUCCESS |

## Notes

- Measured results from the local project environment; no technology conclusions are drawn.
- Each engine includes its own read path: pandas/Spark read Parquet datasets, MongoDB aggregates its serving collections.
- Feature-table join scopes differ by engine holdings: pandas/Spark join four domains including LMS weekly aggregates, MongoDB joins the three operational collections.
- Memory figures are Python-allocator peaks where measured; JVM execution memory is not captured (driver memory recorded).

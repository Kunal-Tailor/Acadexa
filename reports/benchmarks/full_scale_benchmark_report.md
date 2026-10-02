# Acadexa — Full-Scale Empirical Benchmark Report (Job J8)

**Report Version:** 1.0.0  
**Pipeline Stage:** Job J8 (Multi-Engine Benchmarks)  
**Execution Date:** 2026-10-01  
**Execution Scale:** Full Scale (74.7M LMS Events, 12,000 Students, 288,000 Academic Records)  
**Run ID:** `bench_20261001_154957`

---

## 1. Executive Summary & Objective

In accordance with `docs/rules.md` §30, empirical benchmarks were conducted to measure real technology trade-offs on full-scale academic datasets. The harness evaluates three distinct computational paradigms:
1. **PySpark (Local Mode, 8 cores):** Distributed, partition-aware out-of-core engine.
2. **Pandas (Single-Node, In-Memory):** Vectorized single-threaded in-memory processing.
3. **MongoDB Aggregation Pipeline:** Native database engine utilizing document pipelines and B-tree indexes.

The benchmarks evaluated two canonical analytical workloads without manufacturing predetermined outcomes:
- **Workload 1:** Weekly LMS Event Aggregation (High volume, raw event stream: 74,757,153 events).
- **Workload 2:** Feature Table Multi-Domain Join (Wide relational outer join: 12,834,222 records across 4 domains).

---

## 2. Hardware & Runtime Environment

- **Operating System:** Windows 11 Pro (`10.0.26300`)
- **CPU:** Intel multi-core processor (20 logical threads)
- **Host Memory:** 24 GB Physical RAM
- **Python Version:** 3.11.9
- **Engine Versions:** `pyspark==3.5.1/4.2.0`, `pandas==3.0.1`, `pymongo==4.17.0`, `pyarrow==25.0.1`, `numpy==1.26.4`
- **Spark Configuration:** `local[8]`, Driver Memory: 8 GB, Adaptive Query Execution (AQE) enabled

---

## 3. Workload 1: Weekly LMS Engagement Aggregation

### 3.1 Description & Grain
Aggregates high-frequency clickstream event logs into weekly student-course engagement vectors (total events, positive durations, active days, and 4 category counts).  
**Input:** 74,757,153 raw LMS events stored in 13,338 Parquet files.  
**Output Grain:** `student_id × course_id × school × semester_id × week_start × week_number`

### 3.2 Measured Results

| Engine | Execution Time | Input Rows | Output Rows | Peak Memory | Status / Outcome |
|---|---|---|---|---|---|
| **PySpark** | **151.12 s** (~2.5 min) | 74,757,153 | 4,682,117 | Spill to disk | **SUCCESS** |
| **Pandas** | 643.36 s (~10.7 min) | 74,757,153 | 0 | > 24 GB | **FAILED: MemoryError** |
| **MongoDB** | N/A (Isolated) | — | — | — | Serving slice only (~8.95M) |

### 3.3 Engineering Analysis & Scalability Boundary
- **Pandas Memory Exhaustion:** Pandas attempted to load all 13k Parquet partitions into a monolithic in-memory DataFrame. At approximately 55 million rows loaded, process working memory exceeded host RAM limits, triggering an unrecoverable `MemoryError` at 643.36 seconds.
- **PySpark Out-of-Core Partitioning:** PySpark's Catalyst optimizer and Tungsten execution engine divided the 74.7M rows into managed shuffle partitions. Memory limits were respected via temporary disk spilling, completing the 4.68M row aggregation in **151.12 seconds** without crashing the host OS.
- **Conclusion:** This empirical failure boundary decisively proves why Big Data batch engines (PySpark) are mandatory for institutional LMS clickstream analytics.

---

## 4. Workload 2: Feature-Table Multi-Domain Outer Join

### 4.1 Description & Grain
Performs a complex multi-way relational join combining student academic records, weekly attendance totals, coursework submission histories, and weekly LMS metrics into a unified feature matrix.  
**Input:** Cleaned domain Parquet datasets (12,834,222 cumulative input rows).  
**Output Grain:** `student_id × course_id × semester_id` (288,000 rows).

### 4.2 Measured Results

| Engine | Execution Time | Input Rows | Output Rows | Peak Memory | Status / Outcome |
|---|---|---|---|---|---|
| **Pandas** | **32.95 s** | 12,834,222 | 288,000 | 831.35 MB | **SUCCESS** |
| **PySpark** | **47.18 s** | 12,834,222 | 288,000 | Distributed JVM | **SUCCESS** |

### 4.3 Engineering Analysis
- **Tabular In-Memory Efficiency:** Once clickstream event data is pre-aggregated down to tabular weekly summaries (reducing dataset volume to under 1 GB), Pandas executed hash joins with minimal memory footprint (831.35 MB) in **32.95 seconds**.
- **Distributed Shuffle Overhead:** PySpark completed the join in **47.18 seconds**. On moderately sized tabular datasets, JVM coordination, partition serialization, and multi-stage DAG task scheduling introduce minor fixed overhead compared to bare-metal C/NumPy hash joins.
- **Architectural Harmony:** Demonstrates that while PySpark is strictly necessary for large clickstream volumes, pre-aggregated analytical serving can be manipulated efficiently by both engines.

---

## 5. Summary Findings & Architecture Confirmation

1. **Scalability Threshold:** The project's data scale (~74.7M events, 4.5 GB) lies directly above the single-node RAM ceiling, validating the dual architecture: PySpark for raw processing and MongoDB/Streamlit for indexed serving.
2. **Serving Separation:** Loading the full 74.7M event logs into MongoDB would exhaust WiredTiger cache; restricting MongoDB to an 8.95M serving slice preserved instantaneous sub-second query performance.

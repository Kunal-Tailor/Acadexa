# Acadexa — Enterprise Academic Intelligence Platform

<div align="center">

![Acadexa Banner](https://img.shields.io/badge/Acadexa-Academic%20Intelligence%20Platform-0052CC?style=for-the-badge&logo=apachespark&logoColor=white)

**An End-to-End Big Data Learning-Analytics & Risk-Signal Architecture Using PySpark, MongoDB, and Streamlit**

[![Python 3.11](https://img.shields.io/badge/Python-3.11.9-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Apache Spark](https://img.shields.io/badge/Apache%20Spark-3.5%20%7C%204.0%20Batch-E25A1C?style=flat-square&logo=apachespark&logoColor=white)](https://spark.apache.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Serving%20Layer-47A248?style=flat-square&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Apache Parquet](https://img.shields.io/badge/Apache%20Parquet-74.7M%20Events-0550AE?style=flat-square&logo=apache-parquet&logoColor=white)](https://parquet.apache.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.64%20Analytics%20UI-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Test Suite](https://img.shields.io/badge/Tests-79%2F79%20Passing-brightgreen?style=flat-square&logo=pytest&logoColor=white)](#validation--test-suite)
[![Data Privacy](https://img.shields.io/badge/Data-100%25%20Synthetic%20%26%20Seeded-informational?style=flat-square)](#ethical-disclosures--synthetic-integrity)

[Architecture Overview](#system-architecture) • [Measured Scale](#measured-scale-vs-targets) • [Pipeline Stages (J1–J8)](#pyspark-batch-processing-pipeline-j1j8) • [Setup & Execution](#quick-start--reproduction-guide) • [Validation & Benchmarks](#empirical-benchmarks--audit)

</div>

---

## Executive Summary

**Acadexa** is an enterprise-grade Big Data learning analytics and early warning platform engineered for multi-school collegiate institutions. Designed around a fictional 6-school university model (**RAS University**, referencing MIT-WPU's academic topology), Acadexa generates, cleans, aggregates, analyzes, and serves over **74.7 million** synthetic learning management system (LMS) interactions and academic records for **12,000 students** across 4 semesters.

Traditional academic early warning systems often rely on black-box machine learning that obscures why a student is flagged, or suffer from severe institutional confounding (such as Simpson's Paradox across schools). Acadexa addresses these fundamental engineering challenges through:

1. **Deterministic Large-Scale Synthetic Data Generation:** Config-driven, seeded modeling incorporating multi-school diurnal rhythms, temporal decliner distributions (~8%), and controlled data quality anomaly injections.
2. **Robust Distributed Batch Pipeline (PySpark J1–J8):** Fault-tolerant local-mode PySpark jobs that perform quality remediation (1.55M issues resolved), cross-factor correlation analytics with within-course z-score normalization, temporal trajectory detection, and gold analytical roll-ups.
3. **Transparent 5-Rule Risk Signals:** Non-black-box, deterministic explainability strings tied strictly to empirical indicators (attendance, LMS velocity, submission timeliness, score drop, and course-relative quiz activity).
4. **Decoupled Hybrid Storage Architecture:** High-throughput columnar Parquet files for raw/intermediate event lakehouse storage coupled with indexed document collections in MongoDB for sub-second dashboard serving.
5. **Role-Scoped Streamlit Analytics Suite:** Multi-tier executive, departmental, and faculty views enforcing rigorous scope isolation, auditability, and zero causal overclaiming.

> **Research & Privacy Statement:** 100% of data is deterministically synthesized (`seed=42`). No real student or institutional data is used. Analytical relationships reflect statistical associations, not causal claims.

---

## System Architecture

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   SYNTHETIC GENERATION LAYER                                     │
│  Config-Driven Generators • SHA-256 Seed Chains • Multi-School Behavioral & Decliner Dynamics    │
└─────────────────────────────────┬───────────────────────────────┬────────────────────────────────┘
                                  │                               │
                                  ▼                               ▼
                     ┌───────────────────────────┐  ┌───────────────────────────┐
                     │    Parquet Event Lake     │  │    MongoDB Core Serving   │
                     │  74.7M LMS Events (1.38GB)│  │   8.95M LMS Serving Slice │
                     │  13,338 Partitions (Raw)  │  │   Core Domain Collections │
                     └─────────────┬─────────────┘  └─────────────┬─────────────┘
                                   │                              │
                                   ▼                              │
┌─────────────────────────────────────────────────────────────────┴────────────────────────────────┐
│                                  PYSPARK BATCH ANALYTICS (J1–J8)                                 │
│                                                                                                  │
│   J1: Clean & Validate ────────► J2: Weekly Aggregation ────────► J3: Integrated Feature Table   │
│   (1.55M Issues Cleaned)        (4.6M Weekly Grain Rows)         (288K Course-Student Grain)     │
│                                                                                 │                │
│   ┌─────────────────────────────────────────────────────────────────────────────┴────────────┐   │
│   ▼                                             ▼                                            ▼   │
│   J4: Correlation & Confounders                 J5: Temporal Trend Engine                    J6: 5-Rule Risk Engine
│   (Within-Course Normalization)                 (4-Week Trajectories)                        (10.1K High-Risk Flags)
│   └─────────────────────────────────────────────┬────────────────────────────────────────────┘   │
│                                                 ▼                                                │
│                                    J7: Gold Publisher & Validator                                │
│                                    (Parquet Data Lake + MongoDB Gold)                            │
└─────────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     SERVING & PRESENTATION LAYER                                 │
│                        MongoDB Database (`acadexa`) • Indexed Analytical Views                   │
│                                                 │                                                │
│                                                 ▼                                                │
│                                  Streamlit Intelligence Dashboard                                │
│           University Overview  │  School & Department  │  Course Hub  │  Student Drill-down      │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Measured Scale vs Targets

Acadexa distinguishes between target specifications and actual empirical measurements captured during full-scale pipeline execution (`seed=42`):

| Metric / Dimension | Architecture Target | Measured & Verified Count | Verification Status |
|---|---|---|---|
| **Target Student Population** | 12,000 students | **12,000 students** | Verified (`full_scale_students.json`) |
| **Institutional Hierarchy** | 6 Schools, 18 Departments | **6 Schools, 18 Departments, 72 Courses** | Verified (`full_scale_hierarchy.json`) |
| **Academic Records** | ~288,000 entries | **288,000 records** (12k × 24 courses) | Exact Grain Reconciled |
| **Attendance Records** | ~4.6M records | **4,608,000 records** (16 weeks × S1–S4) | Exact Grain Reconciled |
| **Coursework Submissions** | ~3.3M items | **3,338,810 records** | Verified (`coursework.json`) |
| **LMS Raw Event Volume** | ~70,000,000 events | **74,757,153 events** (1.38 GB Parquet) | Target Exceeded (+6.8%) |
| **Injected Quality Anomalies** | ~2.6M injected | **2,644,049 anomalies** across 6 types | Verified (`injection_manifest.json`) |
| **Resolved Quality Anomalies** | 100% resolution | **1,551,722 detected; 0 remaining** | Clean Pass (`full_scale_j1.json`) |
| **Weekly Aggregated LMS Grain** | ~4.5M rows | **4,607,646 rows** | Verified (`full_scale_j2.json`) |
| **Unified Feature Table** | ~288,000 rows | **288,000 rows** (Student × Course × Term) | Exact Grain Reconciled |
| **Identified Decliner Students** | ~8% target rate | **932 students (7.77%)** | Ground Truth Registry Aligned |
| **MongoDB LMS Serving Slice** | ~7M events | **8,958,633 documents** | Loaded & Indexed |
| **Gold Student Features (Roll-up)** | ~48,000 rows | **48,000 documents** (12k × 4 Semesters) | Verified (`full_scale_j7.json`) |

---

## PySpark Batch Processing Pipeline (J1–J8)

The processing layer executes in 8 discrete, idempotent, zero-driver-collect Spark jobs configured for local distributed parallelism:

```text
  J1 Clean & Validate ───► J2 Event Aggregation ───► J3 Feature Table ───► J4 Correlation
       (445.87s)                  (226.66s)                 (81.44s)             (35.75s)
          │                                                                         │
          └─────────────────────────────────────────────────────────────────────────┤
                                                                                    ▼
  J8 Benchmarks       ◄─── J7 Gold Publication  ◄─── J6 Risk Signals  ◄─── J5 Trend Detection
    (6 Workloads)                 (27.16s)                  (13.27s)             (24.55s)
```

### Stage Summary

* **J1: Clean & Validate (445.87s)**
  * Cleans all 6 raw datasets; ingests 74.7M raw LMS interactions.
  * Detects and drops **720,548 duplicate LMS events** and **82,991 orphan foreign keys**.
  * Auto-corrects 414k course ID case formatting errors, 265k null imputations, and 35k out-of-range bounds.
  * Outputs **73,961,848** clean LMS events with **0 remaining defects**.
* **J2: Weekly Event Aggregation (226.66s)**
  * Transforms raw millisecond-level clickstream into weekly student-course metrics (`lms_weekly_engagement`).
  * Aggregates 73.9M events down to **4,607,646** weekly summaries across 16 canonical term weeks.
* **J3: Unified Feature Table (81.44s)**
  * Outer-joins attendance, coursework grades, academic history, and LMS engagement into an integrated table.
  * Outputs exactly **288,000 rows** at the canonical `student_id × course_id × semester_id` grain.
* **J4: Correlation & Simpson's Paradox Analysis (35.75s)**
  * Computes distributed Spearman rank correlation with within-course z-score normalization.
  * Analyzes planted indicators and institutional confounding (e.g. school forum culture).
* **J5: Temporal Trend Detection (24.55s)**
  * Calculates rolling 4-week engagement velocity. Detects engagement decline where $\text{recent } 4\text{w} \le 50\% \text{ of prior } 4\text{w}$.
  * Identifies **5,816 LMS decliners** and **60,578 coursework score decliners**.
* **J6: Rule-Based Risk Signal Engine (13.27s)**
  * Evaluates five non-black-box risk rules against canonical thresholds (`config/risk/risk_signals.toml`).
  * Yields **10,182 high-risk students** ($\ge 3$ signals) with full natural language explainability strings.
* **J7: Gold Analytical Publisher & Validator (27.16s)**
  * Publishes `student_features` (48k), `course_metrics` (288), `school_summary` (18), and `risk_indicators` (12k) to MongoDB and Parquet.
  * Executes automated post-write schema and uniqueness validation.
* **J8: Empirical Benchmark Harness (Phase 13 & 15.8)**
  * Runs systematic, multi-engine comparisons (Pandas vs. PySpark vs. MongoDB) under identical workloads.

---

## Transparent 5-Rule Risk Engine

Acadexa deliberately rejects opaque neural networks or black-box predictive scores for student vulnerability assessment. Instead, it utilizes **five deterministic, explainable signals**:

```text
 ┌──────────────────────┐     ┌──────────────────────────────────────────────────────────────┐
 │  1. Low Attendance   ├────►│ Term-to-date attendance < 75.0%                              │
 └──────────────────────┘     └──────────────────────────────────────────────────────────────┘
 ┌──────────────────────┐     ┌──────────────────────────────────────────────────────────────┐
 │  2. LMS Decline      ├────►│ Rolling 4-week engagement <= 50.0% of prior 4-week window    │
 └──────────────────────┘     └──────────────────────────────────────────────────────────────┘
 ┌──────────────────────┐     ┌──────────────────────────────────────────────────────────────┐
 │  3. Late Submissions ├────►│ Late coursework submission rate > 30.0%                      │
 └──────────────────────┘     └──────────────────────────────────────────────────────────────┘
 ┌──────────────────────┐     ┌──────────────────────────────────────────────────────────────┐
 │  4. Marks Decline    ├────►│ Recent 3 graded items drop >= 10.0 points below prior average│
 └──────────────────────┘     └──────────────────────────────────────────────────────────────┘
 ┌──────────────────────┐     ┌──────────────────────────────────────────────────────────────┐
 │  5. Low Quiz Activity├────►│ Total quiz attempts fall in bottom quartile (< 25th pctile)  │
 └──────────────────────┘     └──────────────────────────────────────────────────────────────┘
```

* **Composite Score:** Integer range `0 – 5` (Sum of active flags).
* **High-Risk Classification:** $\ge 3$ active signals (**10,182 students identified**).
* **Explainability Strings:** Every generated flag includes human-readable context stored directly in the document (e.g., `"term-to-date attendance 71.9% < 75% threshold"`).

---

## Empirical Benchmarks & Audit

Workload testing was executed under Windows 11 (20-core CPU, 32GB RAM, Python 3.11.9, PySpark local mode):

### 1. Weekly LMS Aggregation Workload (74.7M Raw Events)
* **PySpark:** **151.12s** — successfully processed 74,757,153 input rows to 4,682,117 output summaries utilizing out-of-core spill management.
* **Pandas:** **Terminated with `MemoryError`** after 643.36s — demonstrated single-node in-memory scaling limitations when ingesting 13,000+ Parquet partitions.
* **MongoDB:** Sub-second execution on the 8.95M document serving slice via optimized `$match` + `$group` compound index pipelines.

### 2. Four-Domain Feature Table Join Workload
* **Pandas:** **32.95s** (processed 4 cleaned domains into 288k rows).
* **PySpark:** **47.18s** (distributed execution with partition shuffling and disk checkpointing).

### 3. Ground-Truth Statistical Recovery
Comparing pre-registered generation secrets against J4 analytical findings:
* **Planted Positive (`attendance_marks`):** **Recovered** ($\rho = +0.443$).
* **Planted Negative (`late_submissions_marks`):** **Recovered** ($\rho = -0.292$).
* **Decoy Null Control (`decoy_forum_marks`):** **Correctly No Association** ($\rho = +0.012$, within the $|\rho| < 0.10$ non-association band, proving protection against spurious discovery).

---

## Quick Start & Reproduction Guide

### Prerequisites
* **Operating System:** Windows 10/11, macOS, or Linux
* **Python Runtime:** Python 3.11.x
* **Java Runtime:** Java 11 or 17 (required for Apache Spark execution)
* **Database:** MongoDB Community Server (listening on `localhost:27017`)

### 1. Environment Setup

```powershell
# Clone the repository
git clone https://github.com/<your-username>/acadexa.git
cd acadexa

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # On Linux/macOS: source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
Copy-Item .env.example .env
```

### 2. Data Generation & Pipeline Execution

```powershell
# Set Python path to project root
$env:PYTHONPATH = "src"

# 1. Generate full-scale synthetic datasets (Core + LMS Parquet)
python scripts/generate_data.py

# 2. Ingest operational datasets and LMS serving slice into MongoDB
python scripts/load_mongodb.py

# 3. Execute PySpark end-to-end analytics batch pipeline (J1–J7)
python scripts/run_pipeline.py --stages J1 J2 J3 J4 J5 J6 J7

# 4. Execute empirical benchmark suite (J8)
python scripts/run_benchmarks.py --workload feature_table_join --engine pyspark
```

### 3. Launching the Analytics Dashboard

```powershell
# Ensure MongoDB service is running
net start MongoDB

# Run the Streamlit application
$env:PYTHONPATH = "src"
streamlit run src/acadexa/dashboard/app.py
```
*Navigate to `http://localhost:8501` in your browser.*

# Ensure MongoDB service is stopped
net stop MongoDB

---

## Role-Aware Dashboard Guide

The Streamlit dashboard features strict permission boundary enforcement across 4 organizational personas:

```text
 ┌──────────────────────┐   ┌────────────────────────────────────────────────────────┐
 │ 1. Academic Analyst  ├──►│ Full institutional scope: cross-school metrics, J1-J7  │
 │    (Dean / Provost)  │   │ data quality reports, university-wide correlation hubs │
 └──────────────────────┘   └────────────────────────────────────────────────────────┘
 ┌──────────────────────┐   ┌────────────────────────────────────────────────────────┐
 │ 2. Department Head   ├──►│ Scoped to specific department: coursework completion,  │
 │    (CSA Department)  │   │ faculty course loads, cohort grade distributions       │
 └──────────────────────┘   └────────────────────────────────────────────────────────┘
 ┌──────────────────────┐   ┌────────────────────────────────────────────────────────┐
 │ 3. Course Instructor ├──►│ Scoped to assigned courses: section-level attendance,  │
 │    (Faculty Member)  │   │ quiz retry ratios, at-risk rosters, submission timing  │
 └──────────────────────┘   └────────────────────────────────────────────────────────┘
 ┌──────────────────────┐   ┌────────────────────────────────────────────────────────┐
 │ 4. Academic Advisor  ├──►│ Student drill-down: longitudinal 4-week engagement     │
 │    (Student Mentor)  │   │ trajectories, individual explainability factor badges  │
 └──────────────────────┘   └────────────────────────────────────────────────────────┘
```

---

## Validation & Test Suite

Acadexa maintains comprehensive test coverage across data generation, schemas, PySpark transformations, MongoDB aggregations, and Streamlit components:

```powershell
# Execute the full validation suite
$env:PYTHONPATH = "src"
python -m pytest tests/unit -v
```

```text
============================== Test Suite Summary ==============================
tests/unit/test_full_scale_pipeline.py     40 PASSED  [J1–J4 Stage Manifests]
tests/unit/test_full_scale_generation.py    4 PASSED  [Demographic Splits & Population]
tests/unit/test_full_scale_lms.py           3 PASSED  [Parquet & Serving Slice Spec]
tests/unit/test_full_scale_validation.py   13 PASSED  [Schema, Quality, Recovery, Risk]
tests/unit/test_dashboard_foundation.py    19 PASSED  [Auth, Scope & Permissions]
...
============================= 79 passed in 1.00s ===============================
```

---

## Repository Structure

```text
acadexa/
├── config/                 # Canonical configuration contracts (TOML)
│   ├── university/         # Hierarchy specifications (6 schools, 18 depts)
│   ├── periods/            # Academic calendars (AY1-AY2, S1-S4)
│   ├── generator/          # Scale targets, behavioral weights & noise parameters
│   └── risk/               # Canonical 5-rule risk thresholds
├── data/
│   ├── manifests/          # Committed stage reproducibility records (JSON)
│   └── fullscale/          # Local data lakehouse (Parquet/JSON; git-ignored)
├── docs/                   # Architectural blueprints and engineering standards
│   ├── prd.md              # Product Requirements Document
│   ├── architecture.md     # System Topology & Storage Split Specifications
│   ├── rules.md            # Hard Implementation Rules & Non-Negotiables
│   ├── TASKS.md            # Master 17-Phase Implementation Checklist
│   └── IDE_Context.md      # Comprehensive Architectural Working Memory
├── reports/                # Validation reports (data quality, recovery, benchmarks)
├── scripts/                # Execution entry points
│   ├── generate_data.py    # Synthetic data generation runner
│   ├── load_mongodb.py     # MongoDB operational ingestion runner
│   ├── run_pipeline.py     # PySpark batch execution orchestrator (J1-J7)
│   └── run_benchmarks.py   # J8 comparative benchmark suite runner
├── src/acadexa/            # Core package implementation
│   ├── analytics/          # Correlation, temporal trend, & risk signal logic
│   ├── config/             # Config loaders and semantic validation
│   ├── dashboard/          # Streamlit pages, components, & auth shell
│   ├── database/           # MongoDB connection pooling & aggregations
│   ├── generator/          # Synthetic demographic, course, & LMS generators
│   ├── processing/         # PySpark job definitions (J1 through J7)
│   └── validation/         # Schemas, recovery checkers, & quality validators
└── tests/                  # Unit and integration test suites
```

---

## Ethical Disclosures & Synthetic Integrity

1. **Non-Causal Interpretation:** All analytical findings (e.g., attendance vs. grades) reflect observed statistical association ($\rho$). In compliance with academic standards, correlation values are never framed as causative intervention levers.
2. **Defensible Risk Signals:** Risk indicators avoid black-box predictive scoring or automated penalization. Indicators serve strictly as informational triggers for human advisor engagement.
3. **Synthetic Confidentiality:** Zero actual student, faculty, or institutional records were used. RAS University and all associated personnel are entirely synthetic constructs.

---

## License & Academic Credits

Developed as a capstone project in **Big Data Technologies**.  
Architecture designed and implemented following academic data engineering standards.

*For detailed architectural decisions and implementation history, refer to [`docs/IDE_Context.md`](docs/IDE_Context.md).*

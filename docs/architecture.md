# Acadexa — System Architecture

**Document:** `docs/architecture.md`  
**Project:** Acadexa  
**Institution model:** RAS University  
**Architecture type:** Local Big Data batch analytics platform  
**Status:** Working baseline  
**Primary references:** `data.md` and `docs/prd.md`

---

## 1. Architecture Overview

Acadexa is a local, batch-oriented academic intelligence platform that integrates synthetic university data, processes large event datasets with PySpark, stores operational and analytical results in MongoDB, and exposes the processed results through a Streamlit dashboard.

The architecture is deliberately designed around the project's academic Big Data requirements and the available local compute budget.

At a high level:

```text
                  ┌───────────────────────────────┐
                  │     Synthetic Data Generator  │
                  │                               │
                  │ Config + Seed + Ground Truth  │
                  │ + Data Quality Injection       │
                  └──────────────┬────────────────┘
                                 │
                ┌────────────────┴─────────────────┐
                │                                  │
                │                                  │
                ▼                                  ▼
       ┌─────────────────┐               ┌──────────────────┐
       │  Raw Parquet    │               │    MongoDB       │
       │  Landing Zone   │               │ Operational Store│
       │                 │               │                  │
       │ Full LMS events │               │ Core collections │
       │ ~70M target     │               │ + LMS slice      │
       └────────┬────────┘               └────────┬─────────┘
                │                                 │
                │                                 │
                └──────────────┬──────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      PySpark        │
                    │     Local Mode      │
                    │                     │
                    │ Clean / Join /      │
                    │ Aggregate / Analyze │
                    │ Feature Engineer    │
                    └──────────┬──────────┘
                               │
                         Gold datasets
                               │
                               ▼
                    ┌─────────────────────┐
                    │      MongoDB        │
                    │   Gold Collections  │
                    │                     │
                    │ student_features    │
                    │ course_metrics      │
                    │ school_summary      │
                    │ risk_indicators     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     Streamlit       │
                    │      Dashboard      │
                    │                     │
                    │ Dummy Login         │
                    │ Role-aware Views    │
                    │ Drill-down          │
                    └─────────────────────┘
```

The architecture has no Kafka or Spark Structured Streaming layer.

---

## 2. Architectural Principles

### 2.1 Batch-first

Acadexa is a batch analytics system.

Data is generated, landed, processed, published, and then consumed by the dashboard.

The architecture must not describe batch event generation as live streaming.

### 2.2 Separation of concerns

The system separates:

- data generation,
- raw data storage,
- operational storage,
- large-scale processing,
- analytical publishing,
- dashboard presentation.

A component should not silently absorb responsibilities belonging to another layer.

### 2.3 MongoDB as serving and operational storage

MongoDB is the primary serving database for:

- operational collections,
- selected LMS events,
- Spark-produced gold collections,
- dashboard queries,
- drill-down operations.

### 2.4 Parquet as raw event landing

The complete LMS event dataset is stored in Parquet.

This avoids attempting to load all ~70M target LMS events into MongoDB and keeps the large raw event workload suitable for batch processing.

### 2.5 Spark for large-scale processing

PySpark performs the heavier data-processing operations:

- cleaning,
- deduplication,
- joins,
- feature engineering,
- correlation,
- trend detection,
- risk-signal calculation,
- publication of gold datasets.

### 2.6 Dashboard as a consumer

Streamlit consumes processed information from MongoDB.

The dashboard should not become the primary analytics engine.

### 2.7 Reproducibility

The generator uses a seed and configuration so that the same project configuration can reproduce equivalent synthetic data.

### 2.8 Ground-truth validation

Because the project controls the synthetic data, known relationships and injected data-quality problems are recorded and used to validate the processing pipeline.

---

## 3. Logical Architecture

Acadexa can be divided into six logical layers:

```text
┌────────────────────────────────────────────────────────────┐
│ 1. Presentation Layer                                      │
│    Streamlit dashboard + dummy login + role-aware views    │
├────────────────────────────────────────────────────────────┤
│ 2. Serving / Operational Layer                             │
│    MongoDB core + gold collections + LMS event slice      │
├────────────────────────────────────────────────────────────┤
│ 3. Analytics Layer                                         │
│    PySpark local-mode batch jobs                           │
├────────────────────────────────────────────────────────────┤
│ 4. Raw Data Layer                                          │
│    Parquet LMS event landing                              │
├────────────────────────────────────────────────────────────┤
│ 5. Synthetic Data Layer                                    │
│    Generator + configuration + seed + ground truth        │
├────────────────────────────────────────────────────────────┤
│ 6. Validation / Metadata Layer                             │
│    Injection manifest + quality reports + benchmarks      │
└────────────────────────────────────────────────────────────┘
```

These are logical boundaries rather than separate servers.

The entire system is intended to run on a local development machine.

---

## 4. Physical / Runtime Architecture

The project is designed for a single developer workstation/laptop.

```text
Developer Laptop
│
├── Python environment
│   ├── Synthetic generator
│   ├── PySpark
│   ├── Streamlit
│   └── Supporting libraries
│
├── MongoDB
│   ├── Core collections
│   ├── LMS time-series slice
│   └── Gold collections
│
├── Local filesystem
│   └── Parquet raw event data
│
└── Streamlit process
    └── Reads MongoDB
```

PySpark operates in local mode.

The project does not require:

- a Spark cluster,
- Kafka cluster,
- cloud data warehouse,
- cloud object storage,
- distributed Kubernetes deployment.

---

## 5. Component Architecture

### 5.1 Synthetic Data Generator

The generator creates all project data.

Responsibilities:

- create university hierarchy,
- create students,
- create courses,
- generate academic records,
- generate weekly attendance,
- generate coursework,
- generate LMS events,
- inject controlled data-quality problems,
- record injection counts,
- record planted relationships,
- write data to the appropriate destinations.

Inputs:

```text
Configuration
Seed
Behavior parameters
School profiles
Course difficulty parameters
Injection configuration
```

Outputs:

```text
Core MongoDB datasets
Raw Parquet LMS events
Ground-truth registry
Injection manifest
```

The generator is a first-class component because the dataset itself is part of the experimental design.

---

## 6. Configuration Architecture

Configuration should be centralized.

The configuration should contain, as appropriate:

- university metadata,
- school definitions,
- department definitions,
- program definitions,
- course catalogue,
- student-distribution parameters,
- school behavior profiles,
- course difficulty parameters,
- academic calendar,
- generator seed,
- target volumes,
- data-quality injection rates,
- MongoDB connection configuration,
- dummy-user definitions,
- dashboard configuration,
- risk-signal thresholds.

The implementation should avoid embedding these values across unrelated Python files.

A configuration-driven design allows a seventh school or different generation parameters to be introduced without rewriting the processing pipeline.

---

## 7. Data Architecture

### 7.1 University hierarchy

The logical hierarchy is:

```text
RAS University
    │
    ├── School
    │      │
    │      └── Department
    │              │
    │              └── Program
    │                      │
    │                      └── Course
    │                              │
    │                              └── Student enrollment
```

The same hierarchy drives:

- generated data,
- MongoDB lookups,
- Spark joins,
- dashboard filters,
- role-oriented views.

---

## 8. Core MongoDB Collections

The core collections are:

```text
students
courses
academic_records
attendance
coursework
```

### 8.1 `students`

**Grain:** one document per student.

Purpose:

- student identity within the synthetic university,
- school/department/program mapping,
- batch and semester metadata.

Example conceptual structure:

```json
{
  "student_id": "STU010482",
  "school": "Computer Engineering & Technology",
  "department": "Computer Science and Applications",
  "program": "B.Tech CSE (AI & DS)",
  "batch": 2024,
  "semester": 3
}
```

### 8.2 `courses`

**Grain:** one document per course.

Purpose:

- course catalogue,
- academic hierarchy,
- course difficulty,
- course metadata.

### 8.3 `academic_records`

**Grain:** student × course × semester.

Purpose:

- internal marks,
- midterm marks,
- endterm marks,
- final grade,
- term-level academic summary.

### 8.4 `attendance`

**Grain:** student × course × week.

Purpose:

- classes conducted,
- classes attended,
- weekly attendance analysis.

Attendance percentage is derived.

### 8.5 `coursework`

**Grain:** student × coursework item.

Assignments and quizzes are represented in the same collection using an item type.

---

## 9. LMS Event Architecture

The LMS dataset is intentionally treated differently from the smaller academic collections.

### Full dataset

The complete generated LMS event set is written to Parquet.

Target scale:

```text
~70 million events
```

### MongoDB slice

Only the defined operational slice is stored in MongoDB.

The project specification defines the initial slice as:

```text
Latest semester
+
Computer Engineering & Technology
+
Business
```

The estimated slice is approximately:

```text
~7 million events
```

This design prevents MongoDB from being unnecessarily burdened with the entire event history while retaining a useful event set for operational and dashboard drill-downs.

---

## 10. MongoDB Time-Series Design

The `lms_events` collection should use MongoDB time-series capabilities.

Conceptually:

```text
timeField = timestamp
metaField = meta
```

The event structure contains:

```json
{
  "timestamp": "2025-09-17T10:15:00",
  "meta": {
    "student_id": "STU010482",
    "course_id": "CSE301",
    "school": "CET"
  },
  "activity_type": "VIDEO_VIEW",
  "resource_id": "R118",
  "duration_sec": 1080,
  "session_id": "SES3320041"
}
```

Time-series configuration should be selected based on the actual event-generation pattern and documented once finalized.

---

## 11. Spark Architecture

PySpark runs locally and consumes:

1. raw Parquet LMS events,
2. MongoDB core collections,
3. other required project inputs.

The Spark pipeline is divided into explicit jobs.

```text
J1  Clean + Validate
        ↓
J2  Event Aggregation
        ↓
J3  Feature Table
        ↓
J4  Correlation
        ↓
J5  Trend Detection
        ↓
J6  Risk Signals
        ↓
J7  Publish Gold Data
        ↓
J8  Benchmark
```

Jobs should remain independently testable wherever practical.

---

## 12. Spark Job Responsibilities

### J1 — Clean and Validate

Responsibilities:

- deduplicate events,
- parse timestamps,
- normalize identifiers,
- normalize course IDs,
- detect orphan records,
- correct/drop invalid values according to documented rules,
- generate a quality report.

Output:

```text
Cleaned datasets
+
Data-quality report
```

### J2 — Event Aggregation

Responsibilities:

- aggregate LMS events,
- calculate weekly engagement,
- produce student-course temporal summaries.

Output:

```text
Weekly engagement dataset
```

### J3 — Feature Table

Responsibilities:

Join:

```text
Attendance
+
Coursework
+
Academic records
+
LMS engagement
```

to create a student-course-semester analytical feature table.

### J4 — Correlation

Responsibilities:

- calculate within-course z-scores,
- calculate Spearman correlations,
- optionally calculate Pearson correlations,
- report results overall and by school.

### J5 — Trend Detection

Responsibilities:

- calculate rolling four-week engagement windows,
- identify engagement decline,
- examine graded-item score trends,
- identify decline start periods.

### J6 — Risk Signals

Responsibilities:

Apply the five documented rules:

```text
Low attendance
LMS decline
Late submissions
Marks decline
Low quiz activity
```

Output:

```text
student_id
+
signal count
+
individual signal flags
```

This is a rule-based indicator, not an ML prediction.

### J7 — Publish

Responsibilities:

Write Spark-produced analytical outputs into MongoDB gold collections.

### J8 — Benchmark

Responsibilities:

Measure selected workloads across:

- pandas,
- MongoDB aggregation,
- Spark.

The benchmark must record measured results rather than predetermined conclusions.

---

## 13. Gold Data Architecture

Spark produces four primary analytical collections.

### `student_features`

Per student per semester:

- attendance summary,
- engagement counts,
- late-submission rate,
- score trend,
- relevant analytical features.

### `course_metrics`

Per course per semester:

- mean performance,
- attendance,
- engagement,
- difficulty-adjusted scores.

### `school_summary`

Roll-ups at:

- school,
- department.

### `risk_indicators`

Per student/week or relevant analytical period:

- individual signal flags,
- total signal count,
- signal descriptions where required.

The dashboard consumes these gold collections rather than recomputing the complete analytics layer.

---

## 14. End-to-End Data Flow

### Stage 1 — Generate

```text
Config + Seed
     ↓
Synthetic Generator
```

The generator produces:

- students,
- courses,
- academic records,
- attendance,
- coursework,
- LMS events,
- ground-truth metadata,
- injection manifest.

### Stage 2 — Land

```text
LMS events ───────────────→ Parquet
Core datasets ────────────→ MongoDB
LMS operational slice ────→ MongoDB
```

### Stage 3 — Process

```text
Parquet + MongoDB
       ↓
     PySpark
       ↓
Cleaned / transformed analytical datasets
```

### Stage 4 — Analyze

```text
Cleaned data
    ↓
Aggregations
    ↓
Features
    ↓
Correlations
    ↓
Trends
    ↓
Risk signals
```

### Stage 5 — Publish

```text
Spark Gold Outputs
       ↓
    MongoDB
```

### Stage 6 — Serve

```text
MongoDB
   ↓
Streamlit
   ↓
University / School / Department / Faculty / Analyst views
```

---

## 15. Dashboard Architecture

The dashboard is a read-oriented presentation layer.

```text
Dummy Login
    ↓
Role Resolution
    ↓
Scope / Navigation
    ↓
MongoDB Queries
    ↓
Dashboard Components
```

The dashboard should retrieve:

- precomputed KPIs,
- gold analytical results,
- appropriate MongoDB operational data,
- selected LMS event data.

Heavy joins and large-scale transformations should not be performed inside Streamlit request/render paths.

---

## 16. Dashboard Drill-Down Architecture

The primary navigation path is:

```text
University
   ↓
School
   ↓
Department
   ↓
Program
   ↓
Course
   ↓
Student
```

Each level should narrow the data scope rather than independently reconstructing the complete analytical dataset.

Conceptually:

```text
University KPI
      │
      ├── School comparison
      │       │
      │       └── Department
      │              │
      │              └── Program
      │                     │
      │                     └── Course
      │                            │
      │                            └── Student
```

---

## 17. Role-Aware Architecture

The dummy authentication system should conceptually resolve:

```text
User
 ↓
Role
 ↓
Allowed scope
 ↓
Available dashboard capabilities
```

Roles:

```text
University Admin
School / Department Admin
Faculty
Academic Analyst
```

Role-aware behavior should be implemented centrally rather than through scattered page-specific checks.

The project does not require production-grade identity management.

---

## 18. Data Quality Architecture

Data quality is treated as an explicit pipeline.

```text
Synthetic Generator
       │
       ├── Injected issues
       │
       ▼
Injection Manifest
       │
       ▼
Spark Cleaning
       │
       ├── Detected issues
       │
       ▼
Quality Report
       │
       ▼
Dashboard / Report
```

The quality layer must allow the project team to answer:

- What was intentionally injected?
- What did the cleaning pipeline detect?
- What was corrected?
- What was dropped?
- What remained?

---

## 19. Ground-Truth Architecture

The synthetic generator creates controlled relationships.

```text
Generator
   │
   ├── Data
   │
   └── Ground-truth Registry
             │
             ▼
       Spark Analytics
             │
             ▼
       Recovery Test
             │
             ▼
       Comparison Table
```

The recovery test is important because the project is not attempting to discover unknown facts about real students.

It tests whether the analytical pipeline can recover known relationships from generated data while avoiding unsupported causal claims.

---

## 20. Benchmark Architecture

Benchmarking is separated from the main dashboard pipeline.

```text
                 ┌───────────────┐
                 │ Same workload │
                 └───────┬───────┘
                         │
          ┌──────────────┼───────────────┐
          ▼              ▼               ▼
       pandas         MongoDB          Spark
          │              │               │
          └──────────────┼───────────────┘
                         ▼
                  Benchmark Results
```

The benchmark should use comparable workloads and record:

- execution time,
- memory where practical,
- dataset size,
- environment,
- workload description.

Results should be treated as measurements from the local project environment.

---

## 21. MongoDB Responsibilities

MongoDB is responsible for:

### Operational storage

- students,
- courses,
- academic records,
- attendance,
- coursework,
- selected LMS events.

### Serving

- dashboard queries,
- drill-down queries,
- indexed lookups.

### Aggregation

MongoDB should demonstrate relevant operators such as:

```text
$match
$group
$project
$sort
$lookup
$unwind
$setWindowFields
$facet
```

### Indexing

The project should demonstrate and measure indexes relevant to its query patterns, including concepts around:

```text
student_id + course_id + timestamp
course_id + semester_id
school + department
```

The exact final index definitions should be verified against implemented query workloads.

---

## 22. Spark–MongoDB Boundary

The architectural boundary is:

```text
MongoDB
    │
    │ Core data
    ▼
  Spark
    │
    │ Gold analytical data
    ▼
MongoDB
    │
    ▼
Dashboard
```

MongoDB handles:

- operational storage,
- indexed access,
- smaller aggregations,
- serving.

Spark handles:

- large batch processing,
- heavy joins,
- feature engineering,
- cross-factor analytics,
- temporal processing.

This separation is important to demonstrate why both technologies exist in the architecture.

---

## 23. Data Volume and Resource Architecture

Target estimates:

| Resource / Dataset | Initial estimate |
|---|---:|
| LMS events | ~70M |
| Raw Parquet | ~2–3 GB |
| MongoDB core collections | ~2–3 GB |
| MongoDB LMS slice | ~7M events |
| Spark driver memory | ~6–8 GB |
| Mongo cache | ~2–3 GB |
| Streamlit + headroom | ~1 GB |

These are engineering estimates and must be measured after implementation.

The system should be designed so that the full 70M-event dataset is processed in a memory-conscious manner.

The generator should write event data in chunks rather than creating the entire dataset as one in-memory pandas object.

---

## 24. Memory-Safety Principles

The following architectural rules apply:

1. Do not load all LMS events into pandas simultaneously.
2. Generate/write LMS events in chunks.
3. Prefer Parquet for large raw event storage.
4. Process large event workloads with Spark.
5. Keep only the defined LMS slice in MongoDB.
6. Avoid unnecessary copies of large Spark DataFrames.
7. Materialize intermediate datasets only when justified.
8. Monitor driver memory during full-scale processing.
9. Measure actual disk and memory consumption rather than relying exclusively on estimates.

---

## 25. Error and Failure Boundaries

The architecture should fail visibly rather than silently producing misleading analytics.

Examples:

### Generator failure

```text
Invalid configuration
        ↓
Stop generation
        ↓
Report configuration error
```

### Data-quality failure

```text
Invalid records
        ↓
Quality detection
        ↓
Apply documented cleaning rule
        ↓
Record outcome
```

### Spark failure

```text
Job failure
   ↓
Identify job
   ↓
Log error
   ↓
Do not publish incomplete gold output
```

### MongoDB failure

```text
Database unavailable
   ↓
Dashboard shows controlled error state
   ↓
Do not fabricate KPI values
```

---

## 26. Observability and Auditability

The project should retain enough metadata to understand how an analytical result was produced.

Important artifacts include:

- generator seed,
- configuration snapshot,
- ground-truth registry,
- injection manifest,
- data-quality report,
- Spark job outputs,
- benchmark measurements,
- processing logs,
- generated dataset metadata.

The goal is reproducibility and academic auditability rather than production observability infrastructure.

---

## 27. Deployment Model

### Development

```text
Local laptop
├── MongoDB
├── Python environment
├── PySpark
├── Parquet files
└── Streamlit
```

### Academic demonstration

The same architecture can be demonstrated locally.

A future deployment may separate these services, but deployment infrastructure is not part of the current core scope.

---

## 28. Security Boundary

Because the dataset is fully synthetic:

- no real student PII is required,
- no real institutional credentials are required,
- no real identity provider is required.

Nevertheless:

- MongoDB credentials should not be committed,
- configuration should support environment variables for secrets,
- connection strings should not be hard-coded,
- `.env` files containing secrets must remain outside version control.

The dummy dashboard login is for demonstration and must not be represented as production security.

---

## 29. Architecture Decision Summary

| Decision | Architecture choice |
|---|---|
| Institution | RAS University |
| Data | Fully synthetic |
| Data generation | Seeded/config-driven |
| Raw event format | Parquet |
| Operational database | MongoDB |
| LMS storage | Full Parquet + defined MongoDB slice |
| Big Data processing | PySpark local mode |
| Dashboard | Streamlit |
| Authentication | Dummy login |
| Analytics | Batch |
| Streaming | Out of scope |
| Kafka | Out of scope |
| ML risk prediction | Out of scope |
| Risk indicator | Five-rule signal count |
| Analytical outputs | MongoDB gold collections |
| Target students | 12,000 |
| Target LMS events | ~70M |
| Target period | 2 academic years |
| First milestone | One-school, one-semester vertical slice |

---

## 30. Architecture Boundaries

The following boundaries must remain intact unless explicitly changed in project documentation.

### Generator

Owns:

```text
Synthetic data creation
Ground truth
Injection manifest
```

Does not own:

```text
Dashboard analytics
```

### Parquet

Owns:

```text
Large raw LMS event landing
```

Does not replace:

```text
MongoDB serving layer
```

### MongoDB

Owns:

```text
Operational storage
Serving
Indexes
Small/medium aggregations
Gold collections
```

Does not replace:

```text
Large Spark batch analytics
```

### Spark

Owns:

```text
Large-scale processing
Cleaning
Joins
Feature engineering
Analytics
Risk signals
Publishing
```

Does not own:

```text
Dashboard presentation
```

### Streamlit

Owns:

```text
Authentication experience
Navigation
Visualization
Drill-down
User-facing analytical presentation
```

Does not own:

```text
Core large-scale data processing
```

---

## 31. Architectural Invariants

The following are considered architectural invariants:

1. The project uses synthetic data only.
2. The university is modeled as RAS University.
3. The system remains batch-oriented.
4. Kafka and Structured Streaming remain outside core scope.
5. PySpark remains the main large-scale processing engine.
6. MongoDB remains the operational and serving database.
7. Full LMS events remain in Parquet rather than being loaded entirely into MongoDB.
8. Streamlit remains the dashboard layer.
9. Risk scoring remains rule-based.
10. The five risk signals do not constitute failure prediction.
11. Heavy processing remains outside the dashboard layer.
12. The first milestone remains a one-school, one-semester vertical slice.
13. Target scale is 12,000 students over two academic years with approximately 70M LMS events, subject to measured final volume.
14. Analytical claims from synthetic data must not be presented as findings about real students.
15. Correlation must not be presented as causation.

---

## 32. Architecture Evolution

Any future architecture change should answer:

1. What problem does the change solve?
2. Which existing boundary does it affect?
3. Does it alter the PRD?
4. Does it alter the data contract?
5. Does it affect the benchmark?
6. Does it affect the dashboard?
7. Does it introduce a new dependency?
8. Does it exceed the local resource budget?
9. Does it change the project's academic Big Data demonstration objective?

If a change materially affects these areas, update the relevant documentation before implementing it.

---

## 33. Relationship to Other Project Documents

```text
data.md
   │
   ▼
prd.md
   │
   ├──────────────┐
   ▼              ▼
architecture.md  features.md
   │              │
   ├──► tech_stack.md
   ├──► folder_structure.md
   ├──► design.md
   ├──► rules.md
   └──► tasks.md

memory.md
   └── Persistent implementation context derived from the above
```

`architecture.md` describes **how Acadexa is structured**.

It must not become a substitute for:

- `prd.md` — product requirements,
- `features.md` — feature definitions,
- `tech_stack.md` — technology inventory,
- `rules.md` — coding/implementation rules,
- `design.md` — UI/UX direction,
- `tasks.md` — execution tracking,
- `memory.md` — persistent IDE-agent context.

---

## 34. Canonical Architecture Statement

> Acadexa is a local, batch-oriented Big Data academic-intelligence platform in which a seeded synthetic-data generator produces a multi-school university dataset; large LMS event data lands in Parquet while operational and analytical data is served through MongoDB; PySpark performs cleaning, large joins, feature engineering, correlation and trend analysis in local mode; Spark publishes analytical gold collections back to MongoDB; and a Streamlit application provides dummy-authenticated, role-aware hierarchical dashboards over the processed data.

---

## 35. Approved Implementation Findings & Architectural Refinements

During the full-scale execution (Phases 14–16), several empirical findings materialized that validated and refined the architectural specifications:

### 35.1 Big Data Dimensionality Reduction (Raw vs. Gold Scale Dynamics)
- **High-Volume Raw Interaction Footprint:** The raw ingestion and cleaning layers process **74,757,153 discrete clickstream LMS events** (~1.38 GB Parquet raw, ~1.4 GB cleaned), **4,608,000 weekly attendance check-ins**, and **3,338,810 coursework submissions**, resulting in a cumulative raw/staging footprint of **~4.5 GB**.
- **PySpark Analytical Aggregation:** The PySpark batch pipeline (J1–J7) systematically distills this high-frequency interaction data into course- and student-level analytical aggregates.
- **Serving Layer Cardinality:** The Gold serving layer holds **48,000 student-semester rows** ($12,000 \text{ students} \times 4 \text{ terms}$), **12,000 risk profiles**, **288 course metrics**, and **18 school summaries**.
- **Impact:** Achieves a **99.93% reduction in row cardinality** and compresses data to under 20 MB Parquet (~25 MB indexed in MongoDB). This decoupling enables MongoDB to execute all dashboard queries in **under 5 milliseconds**, completely eliminating real-time aggregation latencies on user requests.

### 35.2 Empirical Engine Scalability & In-Memory Limits (PySpark vs. Pandas)
- **Workload Verification:** The J8 benchmark executed weekly LMS event aggregation across 13,338 Parquet files holding 74.7M events.
- **Finding:** Single-node in-memory processing via **Pandas exhausted system RAM (24 GB) and terminated with `MemoryError`** after 643.36s.
- **Architectural Validation:** **PySpark completed the exact aggregation in 151.12s**, leveraging partitioned DAG scheduling and disk spilling. This empirically proved the non-viability of in-memory single-node libraries for raw clickstream analytics and justified the distributed PySpark engine.

### 35.3 Operational LMS Serving Slice in MongoDB
- **Isolation Principle:** Full raw event logs (74.7M events) remain exclusively in partitioned Parquet files.
- **Serving Slice Selection:** To provide live event inspection in the dashboard without overwhelming MongoDB's WiredTiger cache, a deterministic operational slice comprising **Semester 4 across CET and SOM schools (8,958,633 documents)** is loaded into `acadexa.lms_events`.
- **Resource Footprint:** WiredTiger RAM usage is capped at ~1.8 GB, maintaining instantaneous retrieval on indexed compound keys `(student_id, course_id, timestamp)`.

### 35.4 PySpark Windows Runtime Adaptations
- **Classloader Singleton Handling:** PySpark initializes a single Py4J JVM per process. Cached Ivy driver JARs for MongoDB (`mongo-spark-connector`) are proactively injected into `spark.jars` during session initialization to prevent dynamic classloader attachment failures in multi-stage runs.
- **Hadoop Home Dummy Fallback:** Local Windows execution utilizes an automated dummy `HADOOP_HOME` / `winutils.exe` configuration fallback to suppress native IO initialization warnings.
- **JVM Shutdown Hook Lock:** On Windows, Py4J's `ShutdownHookManager` can encounter file-locking exceptions when attempting to delete temporary Ivy JARs on exit. The pipeline verifies completion status via structured manifests rather than process exit codes.

### 35.5 Streamlit Authenticated Navigation Enforcement
- **Multi-Page Shell Isolation:** To prevent users from bypassing Acadexa's role-based access control (RBAC) via Streamlit's default page selector, custom CSS injection (`[data-testid='stSidebarNav'] {display: none;}`) suppresses default sidebar navigation, routing all interactions exclusively through the authenticated `src/acadexa/dashboard/layout.py` navigation shell.

### 35.6 Within-Course Normalization Safeguards
- **Zero-Variance Protection:** During course-level Z-score computations $(x - \mu) / \sigma$, single-student enrollments or identical student scores produce $\sigma = 0$. The pipeline implements `F.when(col("stddev") > 0, (col("score") - col("mean")) / col("stddev")).otherwise(0.0)` to guarantee numerical stability across all academic catalogs.


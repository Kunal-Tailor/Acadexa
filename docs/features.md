# Acadexa — Feature Specification

**Document:** `docs/features.md`  
**Project:** Acadexa  
**Institution model:** RAS University  
**Status:** Working baseline  
**Primary references:** `data.md`, `docs/prd.md`, `docs/architecture.md`, `docs/tech_stack.md`

---

# 1. Purpose

This document defines the functional features of Acadexa.

It translates the product requirements and architecture into concrete capabilities that the implementation must provide.

Each feature is described in terms of:

- purpose,
- users,
- behavior,
- inputs,
- outputs,
- dependencies,
- boundaries,
- completion expectations.

This document is a **feature contract**, not an implementation tutorial.

Implementation details belong primarily in:

- `architecture.md`,
- `tech_stack.md`,
- `rules.md`,
- `folder_structure.md`.

---

# 2. Product Feature Map

Acadexa is divided into the following feature groups:

```text
Acadexa
│
├── A. Authentication & Access
│   ├── Dummy Login
│   ├── Role Resolution
│   └── Scope-aware Navigation
│
├── B. Synthetic Data Platform
│   ├── University Generation
│   ├── Academic Data Generation
│   ├── LMS Event Generation
│   ├── Ground Truth Registry
│   └── Data Quality Injection
│
├── C. Data Management
│   ├── MongoDB Collections
│   ├── Parquet Landing
│   ├── Indexing
│   └── Time-Series LMS Storage
│
├── D. Big Data Processing
│   ├── Cleaning
│   ├── Event Aggregation
│   ├── Feature Engineering
│   ├── Correlation
│   ├── Trend Detection
│   ├── Risk Signals
│   └── Gold Data Publishing
│
├── E. Academic Intelligence Dashboard
│   ├── University Overview
│   ├── School Overview
│   ├── Department Overview
│   ├── Program Drill-down
│   ├── Course Analytics
│   └── Student Analytics
│
├── F. Analytical Views
│   ├── Cross-factor Analysis
│   ├── Trend Analysis
│   ├── Risk Indicators
│   ├── Recovery Test
│   └── Benchmarking
│
└── G. Data Quality
    ├── Injection Manifest
    ├── Detection Results
    └── Quality Dashboard
```

---

# 3. Feature Classification

Features are classified as:

### Core

Required for the final project.

### Supporting

Required to make a core feature operational or demonstrable.

### MVP

Required for the first one-school, one-semester vertical slice.

### Future

Not required for the current project and explicitly outside the core implementation.

---

# 4. Feature Group A — Authentication & Access

## F-A01 — Dummy Login

**Priority:** Core  
**MVP:** Yes

### Purpose

Provide a demonstrational login experience before users enter the Acadexa dashboard.

### Users

All dashboard users.

### Required behavior

The application should present a login interface that allows a configured dummy user to authenticate.

The login system is demonstrational.

It does not require:

- OAuth,
- enterprise SSO,
- real user registration,
- production password management,
- external identity providers.

### Inputs

- username or configured user identifier,
- dummy authentication credential.

### Outputs

A successful login should establish:

```text
authenticated user
+
role
+
allowed scope
```

### Configuration

Dummy users should be defined centrally rather than hard-coded across dashboard pages.

---

## F-A02 — Role Resolution

**Priority:** Core  
**MVP:** Yes

### Purpose

Determine what dashboard experience the logged-in dummy user receives.

### Supported roles

```text
University Admin
School / Department Admin
Faculty
Academic Analyst
```

### Output

A normalized application-level user context:

```text
user
role
scope
```

### Boundary

Role resolution must not be duplicated independently in every dashboard page.

---

## F-A03 — Scope-aware Navigation

**Priority:** Core  
**MVP:** Yes

### Purpose

Present dashboard navigation appropriate to the user's role and configured scope.

### Example

```text
University Admin
    → University
    → Schools
    → Departments
    → Analysis
    → Data Quality

School / Department Admin
    → Assigned School/Department
    → Courses
    → Students
    → Analysis

Faculty
    → Assigned Courses
    → Students
    → Attendance
    → Coursework
    → LMS Activity
    → Risk Signals

Academic Analyst
    → Analytical Views
    → Correlations
    → Trends
    → Recovery Test
    → Benchmarks
```

This is a demonstrational access model, not production authorization.

---

# 5. Feature Group B — Synthetic Data Platform

## F-B01 — Configurable University Generator

**Priority:** Core  
**MVP:** Yes

### Purpose

Generate the RAS University academic hierarchy.

### Target structure

```text
University
  └── School
        └── Department
              └── Program
                    └── Course
                          └── Student
```

### Target scale

- 6 schools,
- ~18 departments,
- ~40 programs,
- ~250 courses,
- 12,000 students.

### Requirement

The hierarchy must be configuration-driven.

Adding a school should not require rewriting core generator logic.

---

## F-B02 — Seeded Student Generation

**Priority:** Core  
**MVP:** Yes

### Purpose

Generate reproducible synthetic students.

### Student attributes

At minimum, generated students should support the project's defined hierarchy and academic context.

The generator may internally model:

- ability,
- diligence,
- engagement.

These hidden traits influence generated behavior.

### Requirement

The generator must use a reproducible seed.

---

## F-B03 — Course Generation

**Priority:** Core  
**MVP:** Yes

### Purpose

Generate the course catalogue.

### Course behavior

Each course should have a configurable difficulty factor.

Difficulty should influence generated academic behavior in a controlled manner.

---

## F-B04 — Academic Record Generation

**Priority:** Core  
**MVP:** Yes

### Purpose

Generate student-course-semester academic summaries.

### Data includes

- internal marks,
- midterm marks,
- endterm marks,
- final grade.

### Grain

```text
student × course × semester
```

---

## F-B05 — Attendance Generation

**Priority:** Core  
**MVP:** Yes

### Purpose

Generate weekly attendance observations.

### Grain

```text
student × course × week
```

### Data includes

- classes conducted,
- classes attended.

### Derived metric

Attendance percentage is calculated from the raw counts.

---

## F-B06 — Coursework Generation

**Priority:** Core  
**MVP:** Yes

### Purpose

Generate assignment and quiz activity.

### Supported item types

```text
ASSIGNMENT
QUIZ
```

### Relevant attributes

- item ID,
- assigned date,
- due date,
- submission timestamp,
- score,
- maximum score,
- attempts,
- status.

---

## F-B07 — LMS Event Generation

**Priority:** Core  
**MVP:** Yes, vertical-slice scale

### Purpose

Generate timestamped LMS activity.

### Event types

```text
LOGIN
LOGOUT
VIDEO_VIEW
VIDEO_COMPLETE
PDF_VIEW
RESOURCE_DOWNLOAD
QUIZ_ATTEMPT
ASSIGNMENT_VIEW
ASSIGNMENT_SUBMISSION
COURSE_PAGE_VIEW
FORUM_POST
```

### Target

Approximately:

```text
70 million events
```

over two academic years.

The final generated event count must be measured rather than assumed.

---

## F-B08 — Temporal Behavior Simulation

**Priority:** Core  
**MVP:** Partial

### Purpose

Make generated LMS data suitable for temporal analytics.

The generator should model:

- weekly rhythms,
- semester rhythms,
- fewer weekend events,
- activity spikes before deadlines/exams,
- mid-semester dips,
- engagement decline for a defined subset of students.

The generator should produce enough temporal structure for the trend-detection feature to have something meaningful to analyze.

---

## F-B09 — Planted Relationships

**Priority:** Core  
**MVP:** Yes

### Purpose

Create known analytical relationships that can later be recovered by the analytics pipeline.

Planned relationships:

| Relationship | Intended behavior |
|---|---|
| Attendance → marks | Moderate positive |
| LMS engagement → marks | Moderate positive, school-dependent |
| Late submissions → marks | Negative |
| Course difficulty | Confounding factor |
| Decoy relationship | No intentionally planted relationship |

### Requirement

The generator must store a ground-truth registry.

---

## F-B10 — Data Quality Injection

**Priority:** Core  
**MVP:** Yes

### Purpose

Deliberately introduce controlled data-quality problems.

Target categories include:

- duplicate LMS events,
- nulls in selected non-key fields,
- timestamp format inconsistencies,
- course ID casing/whitespace problems,
- orphan records,
- out-of-range values.

### Requirement

The generator must record exact injected counts in an injection manifest.

---

# 6. Feature Group C — Data Management

## F-C01 — MongoDB Core Storage

**Priority:** Core  
**MVP:** Yes

### Collections

```text
students
courses
academic_records
attendance
coursework
```

### Purpose

Provide operational storage and serving access for the core academic datasets.

---

## F-C02 — Raw Parquet Landing

**Priority:** Core  
**MVP:** Yes

### Purpose

Store the complete LMS event dataset in Parquet.

### Requirement

The generator must write data in chunks rather than attempting to hold the full event dataset in memory.

---

## F-C03 — MongoDB LMS Event Slice

**Priority:** Core

### Purpose

Provide a practical event dataset for MongoDB queries and dashboard drill-down.

### Initial slice

```text
Latest semester
+
Computer Engineering & Technology
+
Business
```

Target estimate:

```text
~7 million events
```

Actual count must be measured.

---

## F-C04 — MongoDB Time-Series Collection

**Priority:** Core

### Purpose

Demonstrate MongoDB's time-series data capabilities.

### Configuration concept

```text
timeField = timestamp
metaField = meta
```

---

## F-C05 — MongoDB CRUD

**Priority:** Core  
**MVP:** Supporting

### Required demonstrations

- insert,
- query,
- update,
- delete.

CRUD should be demonstrated against appropriate student/course or operational records.

---

## F-C06 — MongoDB Indexing

**Priority:** Core

### Purpose

Demonstrate query optimization through indexes.

Relevant query dimensions include:

```text
student_id
course_id
semester_id
timestamp
school
department
```

Before/after timing should be measured where practical.

---

## F-C07 — MongoDB Aggregation

**Priority:** Core

### Required concepts

The project should demonstrate appropriate use of:

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

The operators should be used in meaningful workloads rather than inserted only for demonstration.

---

# 7. Feature Group D — Big Data Processing

## F-D01 — Data Cleaning and Validation

**Priority:** Core  
**MVP:** Yes

### Purpose

Convert intentionally imperfect raw data into validated analytical data.

### Responsibilities

- deduplication,
- timestamp parsing,
- ID normalization,
- course ID normalization,
- orphan detection,
- range validation,
- handling configured nulls,
- quality-report generation.

### Output

```text
cleaned data
+
quality report
```

---

## F-D02 — Weekly LMS Engagement Aggregation

**Priority:** Core  
**MVP:** Yes

### Purpose

Convert event-level LMS data into weekly student-course engagement summaries.

### Input

Raw LMS events.

### Output

Conceptually:

```text
student
course
week
event_count
activity breakdown
```

This output supports trend analysis and feature engineering.

---

## F-D03 — Student Feature Table

**Priority:** Core  
**MVP:** Yes

### Purpose

Integrate the academic domains into a student-course-semester analytical feature set.

### Inputs

```text
attendance
coursework
academic_records
LMS engagement
```

### Output

Student-level analytical features such as:

- attendance mean,
- engagement counts,
- late-submission rate,
- score trends,
- relevant signal inputs.

---

## F-D04 — Cross-factor Correlation

**Priority:** Core  
**MVP:** Yes, reduced scope

### Purpose

Analyze relationships between academic factors.

### Required relationships

- attendance ↔ performance,
- LMS engagement ↔ performance,
- assignment lateness ↔ performance,
- quiz attempts ↔ performance,
- attendance + engagement ↔ performance.

### Processing

Values should be normalized within course where required.

### Correlation

Spearman is the default.

Pearson may be shown alongside it.

### Reporting

Results should be available:

- overall,
- by school.

### Interpretation rule

Results are reported as associations.

They must not be presented as causal relationships.

---

## F-D05 — Trend and Decline Detection

**Priority:** Core  
**MVP:** Yes, reduced scope

### Purpose

Identify meaningful changes in engagement and academic performance over time.

### Inputs

- weekly engagement,
- graded-item scores.

### Required behavior

Use rolling four-week windows for engagement comparison.

The output should identify:

```text
decline flag
+
approximate decline start week
```

---

## F-D06 — Rule-based Risk Indicator

**Priority:** Core  
**MVP:** Yes

### Purpose

Combine observable signals into a simple student-level indicator.

### Five signals

1. Low attendance.
2. LMS decline.
3. Late submissions.
4. Marks decline.
5. Low quiz activity.

### Scoring

Each signal contributes one point.

Maximum:

```text
5
```

Example:

```text
3 / 5 signals
```

### Critical boundary

This feature:

- is not machine learning,
- does not predict failure,
- does not produce a probability,
- does not make academic decisions.

It is a count of observed signals.

---

## F-D07 — Gold Data Publishing

**Priority:** Core  
**MVP:** Yes

### Purpose

Publish processed analytical datasets to MongoDB for dashboard consumption.

### Gold collections

```text
student_features
course_metrics
school_summary
risk_indicators
```

---

# 8. Feature Group E — Dashboard

## F-E01 — University Overview

**Priority:** Core  
**MVP:** Yes

### Displays

- total students,
- total courses,
- average attendance,
- average performance,
- average engagement,
- total LMS events,
- school comparison.

All KPIs must come from generated/processed data.

---

## F-E02 — School Overview

**Priority:** Core

### Displays

- performance trends,
- attendance trends,
- engagement trends,
- course comparisons.

---

## F-E03 — Department Overview

**Priority:** Core

### Displays

Department-level views derived from the university hierarchy.

The view should support comparison and drill-down.

---

## F-E04 — Program Drill-down

**Priority:** Core

### Purpose

Allow users to navigate from department to program.

### Hierarchy

```text
School
 ↓
Department
 ↓
Program
```

---

## F-E05 — Course Analytics

**Priority:** Core  
**MVP:** Yes

### Displays

- average performance,
- attendance,
- engagement,
- coursework completion,
- difficulty-adjusted performance.

---

## F-E06 — Student Analytics

**Priority:** Core  
**MVP:** Yes

### Displays

- semester performance,
- attendance by course,
- coursework,
- LMS activity,
- trend lines,
- risk signals.

---

## F-E07 — Analytical Dashboard

**Priority:** Core

### Displays

- correlation matrix,
- cross-factor analysis,
- trend analysis,
- planted-relationship recovery table.

---

## F-E08 — Data Quality Dashboard

**Priority:** Core

### Displays

- injected issues,
- detected issues,
- quality summaries,
- cleaning outcomes.

---

## F-E09 — Benchmark Dashboard

**Priority:** Core

### Displays

Benchmark measurements across:

```text
pandas
MongoDB
Spark
```

Where relevant.

The dashboard must display measured results and environment/context rather than claiming a universal technology winner.

---

# 9. Feature Group F — Validation and Benchmarking

## F-F01 — Ground-truth Recovery Test

**Priority:** Core  
**MVP:** Supporting

### Purpose

Determine whether the analytical pipeline can recover relationships intentionally planted into the synthetic data.

### Process

```text
Known planted relationship
        ↓
Generated data
        ↓
Spark analytics
        ↓
Observed result
        ↓
Comparison
```

### Required comparison

The report/dashboard should distinguish:

- planted relationships,
- recovered relationships,
- decoy relationships.

---

## F-F02 — Data Quality Recovery Test

**Priority:** Core

### Purpose

Compare the injection manifest with the cleaning pipeline's detected problems.

### Process

```text
Injected
   ↓
Detected
   ↓
Corrected / Removed
```

The system should make this comparison measurable.

---

## F-F03 — Performance Benchmark

**Priority:** Core

### Purpose

Compare appropriate workloads across:

```text
pandas
MongoDB aggregation
Spark
```

### Required benchmark areas

1. Weekly engagement on the MongoDB slice.
2. Same task on the full event dataset where applicable.
3. Full feature-table join.

### Measurements

- execution time,
- peak memory where practical.

---

# 10. Feature Group G — Data Explainability

## F-G01 — KPI Traceability

**Priority:** Core

Every major dashboard KPI should have a traceable source.

Conceptually:

```text
Dashboard KPI
    ↓
Gold / MongoDB data
    ↓
Spark or MongoDB computation
    ↓
Source dataset
```

Hard-coded KPI values are not allowed.

---

## F-G02 — Risk Signal Explainability

**Priority:** Core

A displayed risk indicator should identify the signals that contributed to its score.

Example:

```text
3 / 5 signals

✓ Low attendance
✓ LMS decline
✓ Late submissions
```

The interface should make it clear that these are observed signals.

---

## F-G03 — Correlation Interpretation

**Priority:** Core

Correlation results must be labeled as association.

The interface/documentation must not imply:

```text
correlation = causation
```

---

# 11. Feature Group H — Configuration

## F-H01 — Configuration-driven University

**Priority:** Core

Schools, departments, programs, courses and behavioral parameters should be configurable.

---

## F-H02 — Configuration-driven Data Scale

**Priority:** Supporting

The generator should support configuration of target dataset size and related generation parameters.

---

## F-H03 — Configuration-driven Risk Thresholds

**Priority:** Supporting

Risk thresholds should be centralized and tunable.

Examples:

```text
attendance threshold
LMS decline threshold
late submission threshold
marks decline threshold
quiz activity threshold
```

Changing a threshold should not require editing the core risk-engine algorithm.

---

# 12. Feature Group I — Reproducibility

## F-I01 — Seeded Generation

**Priority:** Core

A fixed seed and configuration should produce reproducible synthetic data.

---

## F-I02 — Generation Metadata

**Priority:** Core

Each generation run should retain relevant metadata such as:

- seed,
- configuration,
- generation timestamp,
- target volumes,
- actual generated counts.

---

## F-I03 — Processing Metadata

**Priority:** Supporting

Where practical, record:

- processing job,
- input dataset,
- output dataset,
- processing status,
- execution timing.

---

# 13. Feature Dependencies

The main dependency chain is:

```text
F-B01 University Generator
        ↓
F-B02 Student Generation
        ↓
F-B03 Course Generation
        ↓
F-B04 Academic Records
F-B05 Attendance
F-B06 Coursework
F-B07 LMS Events
        ↓
F-B09 Ground Truth
F-B10 Quality Injection
        ↓
F-C01 MongoDB
F-C02 Parquet
        ↓
F-D01 Cleaning
        ↓
F-D02 Engagement Aggregation
        ↓
F-D03 Feature Table
        ↓
 ┌──────┼────────┬───────────┐
 ▼      ▼        ▼           ▼
D04    D05      D06         F-F03
Corr   Trend    Risk        Benchmark
 │      │        │
 └──────┴────────┘
        ↓
F-D07 Gold Data
        ↓
F-E Dashboard Features
        ↓
Streamlit
```

---

# 14. MVP Feature Set

The MVP is not the complete six-school/four-semester dataset.

The MVP is the **one-school, one-semester vertical slice**.

It must include:

```text
✓ Synthetic university subset
✓ Students
✓ Courses
✓ Academic records
✓ Attendance
✓ Coursework
✓ LMS events
✓ Seeded generation
✓ Basic ground truth
✓ Basic quality injection
✓ MongoDB storage
✓ Parquet event storage
✓ Spark cleaning
✓ Weekly engagement
✓ Feature table
✓ Basic correlation
✓ Basic trend detection
✓ Five-rule risk indicator
✓ Gold collections
✓ Streamlit dashboard
✓ Dummy login
```

The purpose of the MVP is to prove the complete pipeline before scaling.

---

# 15. Full Project Feature Set

After the vertical slice is stable, scale to:

```text
6 schools
~18 departments
~40 programs
~250 courses
12,000 students
4 semesters
~70M LMS events
```

Then complete:

```text
Full cross-factor analytics
Full trend detection
Full risk indicators
Full recovery test
Full data-quality comparison
Benchmark suite
Complete dashboard
```

---

# 16. Feature Priorities

| Priority | Meaning |
|---|---|
| P0 | Required for system to function |
| P1 | Required for core project demonstration |
| P2 | Supporting/quality feature |
| P3 | Future enhancement |

### P0

- Synthetic generation
- MongoDB
- Parquet
- Spark pipeline
- Gold data
- Dashboard foundation

### P1

- Dummy login
- Role-aware navigation
- Correlation
- Trend detection
- Risk signals
- Data-quality analysis
- Recovery test
- Benchmarking

### P2

- Detailed metadata
- Advanced query optimization
- Additional dashboard refinements
- Extended validation

### P3

- Kafka
- Structured Streaming
- ML prediction
- Real institutional data
- Production authentication
- Cloud/distributed deployment
- Additional schools beyond the target six

---

# 17. Feature Completion Criteria

A feature is considered implemented only when:

1. Its required behavior exists.
2. It uses the appropriate architectural layer.
3. It does not violate the project boundaries.
4. It works with the project's synthetic data model.
5. Its output can be validated.
6. Relevant tests or verification exist where practical.
7. Documentation is updated if behavior differs from the documented specification.

A feature is not considered complete merely because a UI element exists.

---

# 18. Feature Boundaries

## The dashboard must not

- fabricate values,
- hard-code KPI data,
- run the full Spark pipeline on every page render,
- imply risk scores are predictions,
- imply correlation proves causation.

## The generator must not

- depend on real student data,
- require external institutional systems,
- create an unreproducible dataset,
- hold the entire LMS dataset in memory.

## Spark must not

- become the dashboard UI,
- silently change data semantics,
- publish incomplete gold data after a failed job.

## MongoDB must not

- become a dumping ground for all 70M LMS events,
- replace Spark for the project's full-scale analytical workload.

---

# 19. Feature-to-Technology Mapping

| Feature | Primary technology |
|---|---|
| Dummy login | Streamlit + Python |
| Role resolution | Python + Streamlit |
| University generation | Python + NumPy |
| Large event generation | Python + NumPy + Polars/PyArrow as required |
| Raw event storage | Parquet |
| Operational storage | MongoDB |
| LMS time-series | MongoDB Time-Series |
| CRUD | MongoDB |
| Indexing | MongoDB |
| Small/medium aggregation | MongoDB |
| Cleaning | PySpark |
| Large joins | PySpark |
| Event aggregation | PySpark |
| Feature engineering | PySpark |
| Correlation | PySpark |
| Trend detection | PySpark |
| Risk signals | PySpark |
| Gold publishing | PySpark + MongoDB |
| Dashboard | Streamlit |
| Charts | Streamlit/native or selected visualization library |
| Benchmarking | Python + pandas/MongoDB/PySpark |
| Documentation | Markdown |

---

# 20. Feature-to-User Mapping

| Feature | University Admin | School/Dept Admin | Faculty | Academic Analyst |
|---|:---:|:---:|:---:|:---:|
| Dummy Login | ✓ | ✓ | ✓ | ✓ |
| University Overview | ✓ | — | — | ✓ |
| School Overview | ✓ | ✓ | — | ✓ |
| Department Overview | ✓ | ✓ | — | ✓ |
| Course Analytics | ✓ | ✓ | ✓ | ✓ |
| Student Analytics | ✓ | Scoped | Scoped | ✓ |
| Attendance | ✓ | ✓ | ✓ | ✓ |
| Coursework | ✓ | ✓ | ✓ | ✓ |
| LMS Activity | ✓ | ✓ | ✓ | ✓ |
| Risk Signals | ✓ | ✓ | ✓ | ✓ |
| Correlation | ✓ | ✓ | — | ✓ |
| Trend Analysis | ✓ | ✓ | ✓ | ✓ |
| Recovery Test | — | — | — | ✓ |
| Data Quality | ✓ | ✓ | — | ✓ |
| Benchmarks | — | — | — | ✓ |

`Scoped` means access is conceptually limited to the user's configured school, department, or course context.

---

# 21. Future Feature Boundary

The following are intentionally not current features:

### Live Streaming

Would require:

```text
Kafka
+
Structured Streaming
```

Not part of the current project.

### ML-based Prediction

Could introduce:

- classification,
- probability scores,
- predictive risk models.

Not part of the current core.

### Real Student Data

Would require substantial privacy, governance and security considerations.

Not required and explicitly excluded.

### Production Authentication

Would require:

- real identity provider,
- secure password handling,
- session/security infrastructure,
- proper authorization.

Not part of the academic core.

---

# 22. Feature Evolution Rules

Before adding a new feature, answer:

1. What user problem does it solve?
2. Which persona uses it?
3. Is it core, supporting, or future?
4. Which data does it require?
5. Which architecture layer owns it?
6. Which technology implements it?
7. Does it change the PRD?
8. Does it change the architecture?
9. Does it increase resource requirements?
10. Can it be validated?

If the feature changes a documented project boundary, update the relevant documentation before implementation.

---

# 23. Canonical Feature Statement

> Acadexa provides a role-aware academic intelligence dashboard over a reproducible synthetic university dataset. It generates and integrates attendance, academic, coursework and LMS data; processes large event workloads using PySpark; stores operational and analytical results in MongoDB and raw events in Parquet; performs cross-factor, temporal and rule-based signal analysis; validates results against known synthetic ground truth; and exposes the resulting insights through hierarchical Streamlit views.

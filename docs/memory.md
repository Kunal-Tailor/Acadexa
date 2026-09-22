# Acadexa — Project Memory

**Document:** `docs/memory.md`  
**Project:** Acadexa  
**Institution:** RAS University  
**Purpose:** Persistent context for developers and IDE coding agents  
**Status:** Canonical working context

---

# 1. What Is Acadexa?

**Acadexa** is an integrated university academic intelligence system designed as a final-year Big Data Technologies project.

Its purpose is to demonstrate a scalable, reproducible Big Data analytics pipeline that integrates:

```text
Attendance
+
Marks
+
Coursework
+
LMS activity
```

and produces:

```text
Cross-factor analysis
+
Trend detection
+
Rule-based risk signals
+
Course/course-school/student summaries
+
Data-quality analysis
+
Performance benchmarks
```

The system is not intended to be a production university ERP or a machine-learning prediction platform.

---

# 2. Institution Context

The university represented by the project is:

> **RAS University**

It is modeled on the structure of MIT-WPU for academic hierarchy and scale.

The system represents a multi-school university.

The hierarchy is:

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

The current design targets:

```text
6 schools
~18 departments
~40 programs
~250 courses
~12,000 active students
2 academic years
4 semesters
~70M LMS events
```

These are target engineering values. Actual counts and resource usage must be measured after generation and processing.

---

# 3. Primary Users

Acadexa has four primary user personas:

1. **University Admin**
2. **School / Department Admin**
3. **Faculty**
4. **Academic Analyst**

The application contains a **dummy login** that resolves a user's role and analytical scope.

This is a demonstration authentication system, not production IAM.

---

# 4. Core Objective

The primary objective is:

> **Demonstrate a scalable Big Data analytics pipeline using synthetic academic and LMS data.**

The project should demonstrate why multiple technologies are used together:

```text
Synthetic generator
        ↓
Parquet + MongoDB
        ↓
PySpark
        ↓
Gold analytical collections
        ↓
Streamlit
```

The project should demonstrate Big Data concepts through an actual working pipeline rather than through isolated technology demos.

---

# 5. Data Policy

Acadexa uses **synthetic data only**.

Real student or institutional data is never required.

The synthetic generator must be:

- reproducible,
- seeded,
- configuration-driven,
- internally consistent,
- capable of controlled data-quality injection.

The project must clearly disclose that analytical results are based on synthetic data.

---

# 6. Synthetic Behavioral Model

The generator uses latent synthetic characteristics such as:

```text
Ability
Diligence
Engagement
```

It also models:

```text
Course difficulty
Weekly rhythms
Semester rhythms
Student behavior variation
```

Approximately 8% of students are intended to behave as **decliners** for trend-analysis validation.

The generator intentionally plants relationships that analytics should be able to recover.

---

# 7. Planted Relationships

The synthetic data is designed to contain relationships such as:

```text
Attendance ↔ Marks
LMS Engagement ↔ Marks
Late Submission ↔ Marks
```

Course difficulty acts as a confounding factor.

A decoy relationship is also included so the recovery analysis can demonstrate that not every pair of variables should appear strongly related.

These relationships are synthetic ground truth.

They must not be described as discoveries about real students.

---

# 8. Analytical Interpretation Rule

Acadexa measures **association**, not causation.

Use:

```text
associated with
correlated with
observed relationship
```

Avoid:

```text
causes
caused
impact of X on Y
```

unless a future methodology explicitly supports causal inference.

The default correlation method is:

```text
Spearman
```

with Pearson optionally available.

Where specified, cross-factor analysis uses within-course normalization to reduce course-difficulty distortion.

---

# 9. Risk Indicator

The risk indicator is strictly rule-based.

It contains exactly five documented signals:

### Signal 1 — Attendance

Attendance below:

```text
75%
```

### Signal 2 — LMS decline

Current four-week LMS engagement is:

```text
<= 50%
```

of the previous four-week period.

### Signal 3 — Late submissions

More than:

```text
30%
```

of assignments are late.

### Signal 4 — Marks decline

The average of the latest three graded items is:

```text
>= 10 points
```

below the earlier comparison average.

### Signal 5 — Quiz activity

Quiz attempts fall in the:

```text
bottom quartile
```

Each triggered rule contributes one point.

Therefore:

```text
Risk signal count = 0–5
```

This is an **observed signal count**, not a probability.

It is not:

- failure prediction,
- an ML model,
- a grade decision,
- a disciplinary decision,
- an institutional decision engine.

---

# 10. Target Data Model

Core MongoDB collections:

```text
students
courses
academic_records
attendance
coursework
lms_events
```

Gold/serving collections:

```text
student_features
course_metrics
school_summary
risk_indicators
```

Target approximate volumes:

```text
students           ~12,000
academic_records   ~290,000
attendance         ~5–6M
coursework         ~3.5M
LMS events         ~70M
```

The exact counts are targets/estimates and must be measured after generation.

---

# 11. LMS Storage Strategy

The full LMS event dataset is intentionally large.

The architecture therefore uses:

```text
Full LMS events
→ Parquet

Defined LMS serving slice
→ MongoDB
```

The complete ~70M-event LMS dataset should not be loaded into MongoDB simply for convenience.

---

# 12. Data Quality Model

The generator intentionally injects controlled quality issues.

Approximate target rates include:

```text
Duplicate LMS events        ~1%
Nulls                       ~1–2%
Timestamp inconsistencies   ~1%
Course ID formatting        ~0.5%
Orphan records              ~0.1%
Out-of-range values         ~0.1%
```

Key fields are not intentionally nulled.

Every injection run should have an injection manifest.

The pipeline should distinguish:

```text
Injected
Detected
Corrected
Dropped
Remaining
```

---

# 13. Big Data Dimensions

Acadexa demonstrates the five Vs as:

### Volume

Approximately:

```text
~70M LMS events
+
millions of other academic records
```

### Velocity

Batch timestamped events.

There is no live streaming requirement.

### Variety

The system includes:

```text
Structured records
Time-series events
JSON-like MongoDB documents
Parquet datasets
```

### Veracity

Controlled synthetic data-quality problems.

### Value

The system converts integrated academic data into:

```text
Cross-factor analysis
Trend signals
Risk indicators
Dashboards
Performance measurements
```

---

# 14. Architecture

Canonical architecture:

```text
Synthetic Data Generator
        │
        ├──────────────→ Raw Parquet
        │
        └──────────────→ MongoDB Core + LMS Slice
                                │
                                ↓
                         PySpark Local
                                │
                ┌───────────────┼───────────────┐
                ↓               ↓               ↓
             Features      Analytics       Risk Signals
                │               │               │
                └───────────────┼───────────────┘
                                ↓
                         Gold Collections
                                ↓
                            MongoDB
                                ↓
                           Streamlit
```

---

# 15. Spark Pipeline

The planned Spark jobs are:

```text
J1 — Clean and Validate
J2 — Event Aggregation
J3 — Feature Table
J4 — Correlation
J5 — Trend Detection
J6 — Risk Signals
J7 — Publish
J8 — Benchmark
```

Spark runs in **local mode**.

The project is designed around a laptop with:

```text
24 GB RAM
RTX 4060 8 GB
```

Approximately:

```text
10–12 GB
```

is the intended project resource budget.

The actual resource profile must be measured rather than assumed.

---

# 16. Technology Stack

Core technologies:

```text
Python
NumPy
Parquet
MongoDB
MongoDB Time-Series where appropriate
MongoDB Aggregation
PySpark
MongoDB Spark integration
Streamlit
Python visualization libraries
Git / GitHub
Markdown
```

Optional/supporting tools may be used only when they fit the documented architecture.

---

# 17. Explicitly Out of Scope

The current core project does **not** include:

```text
Kafka
Spark Structured Streaming
Live streaming
Machine-learning prediction
Failure prediction
Real institutional data
Cloud deployment
Production IAM
Full LMS ingestion into MongoDB
More than six schools
Question-level quiz analytics
```

Do not introduce these silently.

---

# 18. Dashboard Structure

Primary dashboard areas:

```text
Overview
Schools
Courses
Students
Analysis
Data Quality
```

Typical navigation:

```text
University
→ School
→ Department
→ Program
→ Course
→ Student
```

The dashboard should use gold/serving data rather than repeatedly executing expensive raw-data processing.

---

# 19. Main Dashboard Views

## University Overview

Shows:

- active students,
- average marks,
- attendance,
- LMS engagement,
- school-level variation,
- trends,
- risk-signal summaries.

## School / Department

Shows:

- population,
- performance,
- attendance,
- LMS engagement,
- coursework,
- trends,
- risk distribution.

## Course

Shows:

- enrollment,
- marks,
- attendance,
- coursework,
- LMS engagement,
- trends,
- associations.

## Student

Shows an integrated view:

```text
Academic performance
+
Attendance
+
Coursework
+
LMS engagement
+
Trends
+
Risk signals
```

## Analysis

Shows:

```text
Correlations
Trend analysis
Engagement analysis
Recovery testing
Methodology
```

## Data Quality

Shows:

```text
Records processed
Issues injected
Issues detected
Issues corrected
Issues dropped
Remaining issues
```

---

# 20. First Milestone

The most important implementation milestone is:

> **One school, one semester, end-to-end vertical slice.**

It must include:

```text
Synthetic generation
↓
MongoDB / Parquet
↓
PySpark
↓
Gold data
↓
Streamlit
```

The MVP should use actual generated data rather than permanent UI mock data.

Only after this vertical slice works should the project scale toward the full target.

---

# 21. Scaling Strategy

Recommended progression:

```text
One school / one semester
        ↓
Full hierarchy
        ↓
Multiple semesters
        ↓
Two academic years
        ↓
12,000 students
        ↓
~70M LMS events
```

At every scale increase, measure:

- runtime,
- memory,
- disk usage,
- MongoDB size,
- Spark behavior,
- output counts.

---

# 22. Benchmarking

The project compares suitable workloads across:

```text
Pandas
MongoDB aggregation
PySpark
```

Example workload:

```text
Weekly LMS engagement aggregation
```

Other applicable workloads may include:

```text
Full feature-table join
```

Record:

```text
Wall-clock time
Peak memory where practical
Dataset size
Environment
Workload description
```

Benchmarking must report measured results rather than predetermined conclusions.

---

# 23. Ground-Truth Recovery

The project contains a synthetic recovery test.

The purpose is to determine whether analytics recover relationships intentionally planted by the generator.

The process is:

```text
Generator ground truth
        ↓
Synthetic data
        ↓
Spark analytics
        ↓
Observed relationship
        ↓
Recovery comparison
```

The recovery test should also include the decoy relationship.

Ground truth must not be changed after observing analytical results.

---

# 24. Resource Constraints

The project is intended to run locally.

Important constraints:

```text
24 GB system RAM
~10–12 GB intended project usage
```

Therefore:

- generate large data in chunks,
- avoid loading 70M events into pandas,
- avoid full `collect()` in Spark,
- avoid unnecessary Spark caching,
- avoid unnecessary data duplication,
- keep MongoDB LMS data to the defined slice,
- measure memory usage.

---

# 25. Repository Context

Canonical repository:

```text
acadexa/
```

Important locations:

```text
docs/
config/
src/acadexa/
scripts/
tests/
data/
reports/
logs/
notebooks/
```

Source code belongs under:

```text
src/acadexa/
```

Entry-point scripts belong under:

```text
scripts/
```

Generated large data should not be committed to Git.

---

# 26. Important Documentation Files

The project documentation hierarchy is:

```text
prd.md
    ↓
architecture.md
    ↓
tech_stack.md
    ↓
features.md
    ↓
rules.md
    ↓
design.md
    ↓
tasks.md
    ↓
memory.md
```

Use them as follows:

### `prd.md`

What the product must accomplish.

### `architecture.md`

How the system is structured.

### `tech_stack.md`

Which technologies are used and why.

### `features.md`

What features the system provides.

### `rules.md`

How implementation must behave.

### `design.md`

How the user experience should work.

### `tasks.md`

What needs to be implemented and in what sequence.

### `memory.md`

Compact persistent project context.

---

# 27. IDE Agent Guidance

Before making a major implementation decision, an IDE agent should understand:

```text
Acadexa = Big Data academic intelligence
RAS University = synthetic university
Synthetic data only
MongoDB + Parquet
PySpark local
Streamlit
Five-rule risk signals
No ML prediction
No streaming
One-school/one-semester MVP first
```

If a request conflicts with these principles, the agent should identify the conflict instead of silently changing the architecture.

---

# 28. Terminology

Use these terms consistently.

### Student

A synthetic university student.

### Academic Record

A student's course/semester academic result record.

### LMS Event

A timestamped synthetic interaction with the learning-management environment.

### Engagement

A measurable collection of LMS activity features.

### Risk Signal

One of five observed rule-based conditions.

### Risk Signal Count

The number of triggered risk rules from 0 to 5.

### Gold Collection

Processed analytical data prepared for serving/dashboard use.

### Decliner

A synthetic student whose generated behavior intentionally contains a declining trend.

### Ground Truth

Relationships and characteristics intentionally planted during synthetic data generation.

### Recovery

The extent to which analytics identify planted ground-truth relationships.

---

# 29. Interpretation Boundaries

Acadexa results must always be interpreted within the project context.

A high risk-signal count means:

```text
More predefined observed signals are currently triggered.
```

It does not mean:

```text
The student will fail.
```

A positive correlation means:

```text
The variables show an observed statistical association.
```

It does not mean:

```text
One variable causes the other.
```

A benchmark result means:

```text
This workload was measured under this environment.
```

It does not mean:

```text
This technology is universally faster.
```

A synthetic pattern means:

```text
The generator intentionally created or produced this pattern.
```

It does not mean:

```text
The pattern exists in real university students.
```

---

# 30. Current Project State

Documentation foundation currently established:

```text
✓ prd.md
✓ architecture.md
✓ tech_stack.md
✓ features.md
✓ folder_structure.md
✓ rules.md
✓ design.md
✓ tasks.md
✓ memory.md
```

The documentation set is therefore complete at the baseline level.

The next work is implementation rather than additional requirements discovery unless a genuine design conflict appears.

---

# 31. Immediate Next Actions

The recommended implementation order is:

```text
1. README.md
2. .gitignore
3. .env.example
4. Python package skeleton
5. Configuration files
6. Schema contract
7. One-school/one-semester generator
8. Data validation
9. MongoDB loader
10. Parquet generation
11. Spark J1
12. Spark J2
13. Spark J3
14. Spark J4–J6
15. Spark J7
16. MVP dashboard
17. End-to-end validation
18. Recovery test
19. Benchmark framework
20. Full-scale generation
21. Full-scale processing
22. Final benchmark
23. Report/demo/viva preparation
```

---

# 32. Non-Negotiable Project Facts

Remember these facts when working on Acadexa:

```text
Project:
Acadexa

University:
RAS University

Data:
100% synthetic

Students:
~12,000 target

Time:
2 academic years / 4 semesters

LMS:
~70M target events

Storage:
MongoDB + Parquet

Processing:
PySpark local mode

Dashboard:
Streamlit

Authentication:
Dummy login

Users:
University Admin
School/Department Admin
Faculty
Academic Analyst

Risk:
Exactly five rule-based signals

ML prediction:
Not part of core project

Streaming:
Not part of core project

MVP:
One school + one semester end-to-end

Primary objective:
Demonstrate a scalable Big Data analytics pipeline
```

---

# 33. Final Context Statement

> **Acadexa is a synthetic-data-only Big Data learning-analytics platform for RAS University. Its central engineering goal is to demonstrate how MongoDB, Parquet and PySpark can work together to process large-scale academic and LMS data and produce explainable cross-factor analytics, temporal trends and five-rule risk signals through a role-aware Streamlit dashboard. The project must first prove the complete architecture on a one-school/one-semester vertical slice before scaling toward approximately 12,000 students, two academic years and 70M LMS events.**

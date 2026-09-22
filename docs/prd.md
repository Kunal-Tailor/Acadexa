# Acadexa — Product Requirements Document (PRD)

**Document:** `docs/prd.md`  
**Project:** Acadexa  
**Institution model:** RAS University (fictional, modeled on MIT-WPU)  
**Project domain:** Big Data Technologies / University Academic Intelligence  
**Status:** Working baseline  
**Source of truth:** `data.md`, plus decisions confirmed during project scoping

---

## 1. Product Overview

Acadexa is an **Integrated University Academic Intelligence System** designed as a Big Data learning-analytics platform for a multi-school university.

The system integrates fragmented academic data—attendance, marks, coursework, and LMS activity—and processes it across multiple levels of the university hierarchy to produce:

- cross-factor academic insights,
- temporal and trend analysis,
- course and school comparisons,
- student-level engagement signals,
- rule-based risk indicators,
- data-quality reporting, and
- interactive analytical dashboards.

The project is primarily intended to **demonstrate a scalable Big Data analytics pipeline**, rather than function as a production university ERP, LMS, or student-information system.

Acadexa will use **fully synthetic, seeded, reproducible data**. Real student data or real institutional data will never be required.

---

## 2. Product Vision

The vision of Acadexa is to demonstrate how fragmented university academic data can be integrated into a unified analytical system and processed at meaningful Big Data scale.

The platform should make it possible to move from:

> fragmented academic records

to:

> integrated data → scalable processing → analytical signals → explainable dashboard insights.

The system should demonstrate the practical roles of:

- MongoDB as an operational and serving database,
- Parquet as the raw event landing format,
- PySpark as the batch Big Data processing engine, and
- Streamlit as the analytical presentation layer.

The project must remain grounded in measurable data processing and reproducible analytics rather than unsupported claims about real students.

---

## 3. Problem Statement

A university typically produces attendance records, marks, assignment and quiz results, and LMS activity in separate systems.

When these sources are isolated, it becomes difficult to answer cross-factor questions such as:

- How does attendance relate to marks?
- Does the relationship differ between schools?
- Does LMS engagement move with academic performance?
- Do drops in LMS activity and late submissions appear before marks decline?
- Which courses show consistently weak performance after accounting for course difficulty?
- Which students show meaningful changes in engagement during a semester?

Acadexa addresses this problem by integrating these data domains and applying scalable batch analytics across them.

---

## 4. Product Goals

### 4.1 Primary goal

Demonstrate a scalable, reproducible Big Data analytics pipeline for university academic data.

### 4.2 Secondary goals

1. Model a realistic multi-school university structure.
2. Generate a large, controlled synthetic academic dataset.
3. Store operational and analytical data appropriately.
4. Demonstrate MongoDB data modeling, CRUD, indexing, aggregation, and time-series capabilities.
5. Demonstrate PySpark-based cleaning, deduplication, joins, feature engineering, correlation analysis, trend detection, and rule-based signal generation.
6. Produce analytical gold datasets for dashboard consumption.
7. Provide an interactive Streamlit dashboard with hierarchical drill-down.
8. Benchmark selected workloads across pandas, MongoDB aggregation, and Spark.
9. Validate analytical behavior against known relationships deliberately planted in the synthetic data.
10. Demonstrate data-quality detection against known injected problems.

---

## 5. Non-Goals

The following are explicitly outside the core product scope:

- Live production university deployment.
- Real institutional or real student data.
- Kafka.
- Apache Spark Structured Streaming.
- Live event streaming.
- ML-based academic prediction.
- Failure prediction.
- Automated academic decisions.
- Question-level quiz analytics.
- More than six schools in the target dataset.
- Replacing a university ERP, SIS, LMS, or examination system.

Streaming and ML may be discussed as future extensions, but neither is part of the core implementation.

---

## 6. Target Institution Model

Acadexa models a fictional institution named **RAS University**, using MIT-WPU as the structural reference for its university/school/department/program organization.

The hierarchy is:

```text
University
  └── School
        └── Department
              └── Program
                    └── Course
                          └── Student
```

The target implementation contains:

- 6 schools,
- approximately 18 departments,
- approximately 40 programs,
- approximately 250 courses,
- 12,000 active students,
- 2 academic years,
- 4 semesters.

The exact catalogue and distribution should remain configuration-driven so the system can be extended without rewriting core application logic.

---

## 7. Target Scale

The target demonstration scale is:

| Dimension | Target |
|---|---:|
| Active students | 12,000 |
| Academic years | 2 |
| Semesters | 4 |
| Schools | 6 |
| Departments | ~18 |
| Programs | ~40 |
| Courses | ~250 |
| LMS events | ~70 million |
| Other academic records | ~9 million |

The LMS-event and storage figures are **engineering estimates**, not guaranteed final measurements.

Actual generated volume, disk usage, runtime, and memory consumption must be measured after the generator and pipeline are implemented.

The project must not present estimates as measured results.

---

## 8. Product Users and Personas

Acadexa will include a **dummy authentication/login experience** for demonstrating role-oriented access to the dashboard.

Authentication is demonstrational only. It is not intended to provide production-grade identity management.

### 8.1 University Admin

**Purpose:** University-wide oversight.

Expected dashboard capabilities:

- university-level KPIs,
- school comparisons,
- overall attendance,
- overall academic performance,
- LMS engagement overview,
- total event volume,
- cross-school trends,
- data-quality overview,
- access to analytical summaries.

### 8.2 School / Department Admin

**Purpose:** Monitor a specific school or department.

Expected capabilities:

- school/department performance,
- attendance trends,
- engagement trends,
- course comparisons,
- academic trends,
- student-level drill-down within authorized scope,
- risk-signal summaries,
- data-quality information relevant to their scope.

### 8.3 Faculty

**Purpose:** Inspect course and student-level academic information.

Expected capabilities:

- course performance,
- attendance,
- coursework completion,
- LMS activity,
- student trends,
- rule-based risk signals,
- course-level analytical information.

### 8.4 Academic Analyst

**Purpose:** Explore integrated data and analytical findings.

Expected capabilities:

- cross-factor correlation analysis,
- trend analysis,
- school/course comparisons,
- planted-relationship recovery results,
- data-quality analysis,
- benchmark results,
- deeper analytical drill-downs.

---

## 9. Authentication and Access Model

The dashboard must include a **dummy login**.

The authentication layer exists to demonstrate role-aware navigation and access behavior.

It does not need to implement:

- real password storage,
- OAuth,
- enterprise identity providers,
- production authorization infrastructure,
- real user provisioning.

The application should still maintain a clear conceptual separation between:

1. authentication,
2. role,
3. university scope,
4. dashboard capabilities.

The dummy accounts and role mappings should be defined in configuration rather than scattered through application code.

---

## 10. Core Data Domains

Acadexa integrates the following academic data domains:

### 10.1 Students

Student identity and academic hierarchy information.

### 10.2 Courses

Course catalogue and course metadata.

### 10.3 Academic Records

Student-course-semester academic summaries including marks and final grade.

### 10.4 Attendance

Weekly student-course attendance records.

Attendance percentage is derived from classes conducted and classes attended rather than stored as the primary raw field.

### 10.5 Coursework

Assignments and quizzes represented through a unified coursework collection.

### 10.6 LMS Events

Timestamped learning-management-system events such as:

- login,
- logout,
- video views,
- video completion,
- PDF views,
- resource downloads,
- quiz attempts,
- assignment views,
- assignment submissions,
- course-page views,
- forum posts.

The full LMS event dataset is stored in Parquet for batch processing. Only the defined operational slice is loaded into MongoDB.

---

## 11. Storage Requirements

Acadexa uses two primary storage mechanisms.

### MongoDB

MongoDB acts as the:

- operational store,
- serving layer,
- dashboard data source,
- location for core collections,
- location for Spark-produced gold collections.

MongoDB must demonstrate:

- CRUD,
- indexed queries,
- aggregation pipelines,
- time-series collections,
- appropriate document modeling,
- drill-down queries.

### Parquet

Parquet acts as the raw event landing format.

The large LMS-event dataset must be generated and written in chunks rather than accumulated as one giant in-memory pandas dataset.

Data should be partitioned appropriately for batch processing.

---

## 12. Processing Requirements

PySpark runs in **local mode on the development laptop**.

Spark is responsible for computationally heavier operations including:

- data cleaning,
- deduplication,
- timestamp normalization,
- identifier normalization,
- orphan detection,
- range validation,
- large joins,
- feature engineering,
- cross-factor analytics,
- correlation analysis,
- temporal trend analysis,
- risk-signal calculation,
- publishing gold collections.

The dashboard must not perform the heavy analytical computation itself.

---

## 13. Synthetic Data Requirements

Synthetic data generation is a **core product component**, not merely a setup utility.

The generator must be:

- seeded,
- reproducible,
- configuration-driven,
- documented,
- capable of producing the target scale,
- capable of injecting controlled data-quality problems,
- capable of recording the exact injected problems.

### 13.1 Simulated student traits

Students may be modeled using hidden traits such as:

- ability,
- diligence,
- engagement.

These traits influence generated academic behavior together with course difficulty, school profiles, and controlled noise.

### 13.2 Planted relationships

The generator must maintain a ground-truth registry describing intentionally planted relationships.

The intended relationships include:

- attendance ↔ marks: moderate positive relationship,
- LMS engagement ↔ marks: moderate positive relationship with school-dependent strength,
- late submissions ↔ marks: negative relationship,
- course difficulty as a confounding factor,
- at least one decoy relationship without a planted relationship.

The system must not claim that these synthetic relationships are discoveries about real students.

---

## 14. Data Quality Requirements

The synthetic generator should inject light, controlled data-quality problems.

Examples include:

- duplicate LMS events,
- nulls in selected non-key fields,
- timestamp format inconsistencies,
- course-ID casing/whitespace problems,
- orphan records,
- out-of-range values.

Key identifiers must not be nulled.

The generator must save an **injection manifest** containing exact injected counts.

The cleaning pipeline must produce a quality report that allows:

```text
Injected problems
        ↓
Detected problems
        ↓
Cleaned output
```

to be compared.

---

## 15. Analytics Requirements

### 15.1 Cross-factor analysis

Acadexa must analyze relationships between:

- attendance and performance,
- LMS engagement and performance,
- assignment lateness and performance,
- quiz attempts and performance,
- combined attendance and engagement.

Where required, values should be normalized within course before correlation to reduce the impact of course difficulty.

Spearman correlation is the default correlation measure, with Pearson optionally shown alongside it.

Correlation must always be presented as **observed association, not causation**.

### 15.2 Trend and decline detection

The system must examine:

- weekly student-course engagement,
- rolling four-week engagement windows,
- graded-item score trends.

The output should identify whether a decline signal exists and when it began.

### 15.3 Rule-based risk indicator

The risk indicator is **not an ML model**.

It consists of five independently observable signals:

| Signal | Rule |
|---|---|
| Low attendance | Term-to-date attendance below 75% |
| LMS decline | Last 4 weeks ≤ 50% of previous 4 weeks |
| Late submissions | More than 30% of assignments late |
| Marks decline | Last 3 graded items average ≥10 points below earlier average |
| Low quiz activity | Quiz attempts in bottom quartile of student's course |

Each signal contributes one point.

Example:

```text
3 / 5 signals
attendance low
LMS declining
late submissions
```

The result is a **signal count**, not a prediction of failure.

The system must never represent this score as:

- a predicted failure probability,
- an ML prediction,
- a diagnosis,
- an automated academic decision.

---

## 16. Dashboard Requirements

The dashboard will be implemented using **Streamlit**.

The primary drill-down hierarchy is:

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

### Required dashboard areas

#### University

- total students,
- total courses,
- average attendance,
- average performance,
- average engagement,
- total LMS events,
- school comparison.

#### School / Department

- performance trends,
- attendance trends,
- engagement trends,
- course comparisons.

#### Course

- average performance,
- attendance,
- engagement,
- coursework completion,
- difficulty-adjusted performance.

#### Student

- semester performance,
- attendance by course,
- coursework,
- LMS activity,
- trend lines,
- rule-based risk signals.

#### Analysis

- correlation matrix,
- planted-relationship recovery table.

#### Data Quality

- injected vs detected problems,
- cleaning results,
- quality summaries.

All displayed KPI values must be derived from actual generated/processed data rather than hard-coded demonstration numbers.

---

## 17. Benchmarking Requirements

A core project objective is to demonstrate **why and where Big Data processing tools fit**.

The project must benchmark selected workloads across:

- pandas,
- MongoDB aggregation,
- PySpark.

At minimum, the benchmark should cover:

1. weekly engagement per student-course on the MongoDB LMS slice,
2. the same task on the full LMS event dataset where applicable,
3. the full feature-table join.

Measurements should include:

- wall-clock execution time,
- peak memory where practical.

If pandas performs adequately for a workload, that result must be reported rather than hidden.

The benchmark is an empirical project finding, not a predetermined claim that Spark will always be faster.

---

## 18. Big Data Characteristics

Acadexa demonstrates the Big Data 5 Vs as follows:

| V | Project interpretation |
|---|---|
| Volume | Approximately 70M LMS events plus other academic records |
| Velocity | Batch-generated timestamped event volume and windowed temporal analytics; no live streaming claim |
| Variety | Structured records, JSON-like documents, time-series events and Parquet data |
| Veracity | Deliberately injected quality problems and cleaning validation |
| Value | Cross-factor analysis, trends, risk signals and dashboard insights |

The project must not describe its batch event generation as live streaming.

---

## 19. MVP Definition

The first implementation milestone is a **vertical slice**:

> One school + one semester + complete end-to-end pipeline.

The MVP vertical slice should demonstrate:

```text
Generate
   ↓
Store
   ↓
Clean
   ↓
Process
   ↓
Aggregate
   ↓
Publish
   ↓
Dashboard
```

Only after the vertical slice works should the system scale toward:

- six schools,
- four semesters,
- 12,000 students,
- the full synthetic event volume.

This approach reduces implementation risk while preserving the final target architecture.

---

## 20. Functional Requirements

### FR-01 — Synthetic Data Generation

The system shall generate seeded, reproducible synthetic university data.

### FR-02 — Configurable University Model

The system shall define schools, departments, programs, courses, students and behavior parameters through configuration.

### FR-03 — Multi-domain Integration

The system shall integrate attendance, academic records, coursework and LMS events.

### FR-04 — MongoDB Storage

The system shall store defined operational and analytical collections in MongoDB.

### FR-05 — Parquet Landing

The system shall store the full raw LMS event dataset in Parquet.

### FR-06 — Data Cleaning

The system shall identify and clean configured data-quality issues.

### FR-07 — Ground-truth Validation

The system shall compare analytical results against planted relationships.

### FR-08 — Spark Analytics

The system shall execute large-scale cleaning, joins and analytical transformations using PySpark.

### FR-09 — Gold Data

The system shall publish processed analytical collections to MongoDB.

### FR-10 — Risk Signals

The system shall calculate the five defined rule-based signals.

### FR-11 — Dashboard

The system shall provide hierarchical Streamlit dashboard views.

### FR-12 — Dummy Authentication

The system shall provide a demonstrational login and role-oriented dashboard experience.

### FR-13 — Benchmarking

The system shall measure selected workloads across pandas, MongoDB and Spark.

### FR-14 — Data Quality Dashboard

The system shall expose injected-versus-detected quality results.

---

## 21. Non-Functional Requirements

### Reproducibility

The same generator seed and configuration should produce equivalent synthetic datasets.

### Explainability

Analytics and risk signals must be understandable from their underlying rules or calculations.

### Resource Awareness

The system must be designed around a local laptop compute budget rather than assuming a distributed production cluster.

### Modularity

Generator, storage, processing, dashboard and configuration concerns should remain separated.

### Configurability

University hierarchy and behavioral parameters should be configurable without rewriting core processing logic.

### Performance

Large-volume workloads must use appropriate batch processing and should not unnecessarily load the entire dataset into memory.

### Data Integrity

Key identifiers must remain valid, and data-quality corrections must be traceable.

### Maintainability

Project structure, naming conventions, coding rules and architecture boundaries will be documented separately in the repository documentation.

---

## 22. Constraints

The project operates under the following known constraints:

- 2-person team.
- Local PySpark execution.
- Approximately 10–12 GB intended project compute usage on a 24 GB RAM laptop.
- RTX 4060 GPU is not a core requirement for the Big Data pipeline.
- No Kafka.
- No Structured Streaming.
- No real student data.
- No ML in the core risk indicator.
- Large LMS event data must not be naively loaded into MongoDB in full.
- The dashboard reads MongoDB rather than performing the heavy Spark computation itself.

---

## 23. Success Criteria

Acadexa will be considered successful when it can demonstrate an end-to-end reproducible pipeline that:

1. Generates the defined synthetic university dataset.
2. Produces the target data domains and relationships.
3. Loads the required MongoDB collections.
4. Produces raw LMS events in Parquet.
5. Cleans and validates deliberately injected quality issues.
6. Executes the defined Spark analytical jobs.
7. Produces gold analytical collections.
8. Recovers the deliberately planted analytical relationships to a documented degree.
9. Avoids incorrectly identifying the decoy relationship as planted/meaningful merely because it exists in sampled data.
10. Produces the five rule-based risk signals.
11. Displays analytical results through Streamlit.
12. Provides dummy role-based dashboard access.
13. Provides benchmark measurements.
14. Demonstrates the intended Big Data concepts clearly enough to support the academic project and viva.

Success must be reported using measured results where measurements are available. Estimated figures must remain explicitly identified as estimates.

---

## 24. Expected Product Outputs

The completed project should contain:

- synthetic data generator,
- generator configuration,
- ground-truth registry,
- injection manifest,
- raw Parquet dataset,
- MongoDB core collections,
- MongoDB LMS time-series slice,
- Spark processing jobs,
- gold analytical collections,
- MongoDB indexes and aggregation pipelines,
- correlation analysis,
- trend detection,
- rule-based risk indicators,
- Streamlit dashboard,
- dummy login,
- benchmark results,
- data-quality report,
- recovery-test results,
- technical documentation,
- academic report and viva material.

---

## 25. Future Scope

The following may be considered after the core project is complete:

- Kafka,
- Spark Structured Streaming,
- real-time analytics,
- ML-based risk modeling,
- additional schools,
- real institutional integrations,
- richer quiz-level analytics,
- production-grade authentication,
- deployment to distributed infrastructure.

These are explicitly **future scope**, not requirements for the core implementation.

---

## 26. Product Boundary

Acadexa should be understood as:

> **A reproducible Big Data academic-intelligence demonstration platform.**

It is not:

> a production university ERP, LMS, student information system, or predictive academic decision engine.

This boundary must be preserved throughout implementation, documentation, dashboard copy, presentations and demonstrations.

---

## 27. Source-of-Truth Hierarchy

When project documentation or implementation decisions conflict, use the following order:

1. Explicitly confirmed project decisions by the project owner.
2. Current `data.md` project specification.
3. `docs/prd.md`.
4. Other project documentation derived from the PRD.
5. Implementation assumptions.

Any change to a locked requirement should be explicitly discussed and reflected in the relevant documentation before being treated as a new project requirement.

---

## 28. Related Documentation

The PRD is the product-level source for the following documents:

```text
docs/
├── prd.md              # What the product must be
├── architecture.md     # How the system is structured
├── tech_stack.md       # What technologies are used
├── features.md         # What capabilities are implemented
├── folder_structure.md # Where implementation artifacts live
├── rules.md             # How implementation should be performed
├── design.md            # How the dashboard should look and behave
├── tasks.md             # What is being built and current progress
└── memory.md            # Persistent project context for IDE agents
```

Each document should reference this PRD rather than redefining product scope independently.

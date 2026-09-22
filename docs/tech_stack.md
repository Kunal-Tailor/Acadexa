# Acadexa — Technology Stack

**Document:** `docs/tech_stack.md`  
**Project:** Acadexa  
**Institution model:** RAS University  
**Status:** Working baseline  
**Primary references:** `data.md`, `docs/prd.md`, `docs/architecture.md`

---

## 1. Purpose

This document defines the technologies used by Acadexa, the responsibility of each technology, the architectural layer in which it belongs, and the technologies that are explicitly outside the core project scope.

The purpose is to prevent technology drift during implementation and to give IDE agents a clear reference for technology selection.

The stack is intentionally designed for:

- a local laptop environment,
- a two-person academic project,
- Big Data batch processing,
- approximately 10–12 GB intended project compute usage on a 24 GB RAM machine,
- reproducible synthetic data,
- MongoDB-based serving,
- PySpark-based analytics,
- Streamlit-based presentation.

---

# 2. Stack at a Glance

```text
Language
└── Python

Data Generation
├── NumPy
├── Polars and/or PyArrow
└── Python configuration

Raw Storage
└── Apache Parquet

Operational / Serving Database
└── MongoDB

Big Data Processing
└── Apache Spark / PySpark

Dashboard
└── Streamlit

Visualization
└── Streamlit-compatible visualization libraries

Environment / Configuration
├── Python virtual environment
├── .env / environment variables for secrets
└── Git / GitHub

Documentation
└── Markdown
```

The exact package versions should be pinned during implementation after the environment is created and tested.

---

# 3. Technology Principles

## 3.1 Use a technology only where it has a defined responsibility

Every major dependency should have a clear reason to exist.

Avoid adding libraries merely because they are popular or convenient.

## 3.2 Prefer the simplest compatible tool

If a requirement can be implemented using the existing stack, do not introduce another framework without a documented reason.

## 3.3 Preserve the Big Data demonstration

The project should demonstrate meaningful use of:

- MongoDB,
- Parquet,
- PySpark,
- large-scale batch processing.

A smaller library should not replace Spark merely because the task happens to be easier in pandas.

At the same time, the project should not use Spark where a MongoDB aggregation or simple Python operation is deliberately part of the architecture.

## 3.4 Local-first

The stack must remain executable on the development laptop.

No cloud infrastructure is required for the core project.

## 3.5 Reproducible

Dependencies and environment configuration should be documented and, where practical, pinned.

---

# 4. Python

### Role

Python is the primary implementation language.

### Used for

- synthetic data generation,
- configuration handling,
- MongoDB interaction,
- PySpark jobs,
- analytical utilities,
- benchmark orchestration,
- Streamlit dashboard,
- validation utilities,
- project scripts.

### Policy

Python code should follow the project's rules defined in `rules.md`.

The project should use one consistent Python environment rather than multiple unrelated installations for the same repository.

---

# 5. NumPy

### Role

Numerical generation and efficient numerical operations.

### Used for

Potential generator operations such as:

- seeded random generation,
- numerical distributions,
- student trait generation,
- course difficulty generation,
- noise generation,
- event-rate simulation.

### Important constraint

NumPy is a supporting component.

It is not the project's primary Big Data processing engine.

The full LMS event dataset should not be accumulated into one enormous NumPy structure before being written to disk.

Generation should be chunked.

---

# 6. Polars

### Role

Optional high-performance data-generation support.

Polars may be used for:

- constructing generated chunks,
- transforming generated records,
- efficient local tabular preparation,
- writing data to Parquet.

### Scope

Polars is primarily useful in the **synthetic-data generation layer**.

It does not replace PySpark for the project's large-scale analytics layer.

If the final implementation determines that NumPy + PyArrow is simpler and sufficient for generation, Polars does not need to remain a mandatory dependency.

The final dependency list should contain only the tools actually used.

---

# 7. PyArrow

### Role

Parquet interoperability and efficient columnar data handling.

### Used for

- writing generated LMS events to Parquet,
- reading or validating Parquet where appropriate,
- supporting data interchange between Python tooling and the Parquet format.

PyArrow is a supporting storage/data-format technology rather than the primary analytics engine.

---

# 8. Apache Parquet

### Role

Raw event landing format.

### Primary use

The complete LMS event dataset is stored in Parquet.

Target scale:

```text
~70 million LMS events
```

### Why Parquet

Parquet provides:

- columnar storage,
- efficient analytical reads,
- compression,
- compatibility with Spark,
- partitioning support,
- suitability for large event datasets.

### Architecture rule

The full LMS event dataset should remain in Parquet rather than being loaded entirely into MongoDB.

---

# 9. MongoDB

### Role

Operational database and serving layer.

MongoDB is one of the project's two major data technologies alongside Spark.

### Primary responsibilities

MongoDB stores:

```text
students
courses
academic_records
attendance
coursework
lms_events slice
student_features
course_metrics
school_summary
risk_indicators
```

### MongoDB is used for

- CRUD,
- indexed lookups,
- operational queries,
- dashboard serving,
- selected aggregations,
- time-series LMS storage,
- serving Spark-produced gold data.

---

# 10. MongoDB Time-Series

The `lms_events` MongoDB collection should use MongoDB time-series functionality.

Conceptually:

```text
timeField = timestamp
metaField = meta
```

The event data contains:

```text
timestamp
meta
activity_type
resource_id
duration_sec
session_id
```

The final time-series configuration should be verified against the actual event-generation pattern.

---

# 11. MongoDB Aggregation Framework

MongoDB aggregation is part of the required technical demonstration.

The project should demonstrate relevant operations including:

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

These operations should be used for appropriate workloads rather than inserted artificially into the project.

MongoDB aggregation is particularly appropriate for:

- smaller/medium analytical queries,
- dashboard drill-downs,
- operational summaries,
- indexed data exploration.

Large multi-source batch analytics remain a Spark responsibility.

---

# 12. MongoDB Indexing

Indexes should be designed around actual query patterns.

The project specification identifies index concepts including:

```text
{student_id, course_id, timestamp}
{course_id, semester_id}
{school, department}
```

The final implementation should verify exact index definitions and field ordering against actual dashboard and benchmark workloads.

Index performance should be measured where practical using before/after comparisons.

---

# 13. Apache Spark

### Role

Primary large-scale batch processing engine.

### Runtime

PySpark in **local mode**.

### Spark responsibilities

Spark handles:

- cleaning,
- deduplication,
- identifier normalization,
- timestamp processing,
- orphan detection,
- large joins,
- feature engineering,
- cross-factor analytics,
- correlation analysis,
- temporal analysis,
- trend detection,
- rule-based risk signals,
- gold-data publication,
- selected benchmarks.

Spark is the primary technology used to demonstrate Big Data processing.

---

# 14. PySpark

PySpark is the Python interface used to implement Spark jobs.

The planned job structure is:

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

### Spark DataFrames

Spark DataFrames should be the default abstraction for structured transformations.

Prefer DataFrame APIs and Spark SQL functions over unnecessary Python-side row processing.

### Spark SQL

Spark SQL/window functionality may be used for:

- aggregations,
- rolling windows,
- ranking,
- temporal calculations,
- analytical transformations.

---

# 15. Spark–MongoDB Integration

Spark needs to consume selected MongoDB data and publish analytical results back to MongoDB.

The project may use an appropriate MongoDB Spark Connector version compatible with the selected Spark/MongoDB environment.

The connector version must be pinned after the development environment is finalized.

### Responsibilities

```text
MongoDB
   ↓
Spark
   ↓
Analytical processing
   ↓
MongoDB gold collections
```

The dashboard does not need to communicate directly with Spark for every request.

---

# 16. Streamlit

### Role

Primary dashboard and presentation framework.

### Used for

- dummy login,
- role-aware navigation,
- KPI dashboards,
- filters,
- drill-down views,
- charts,
- analytical tables,
- data-quality views,
- benchmark result presentation,
- correlation/recovery analysis.

### Dashboard hierarchy

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

### Architecture rule

Streamlit is a presentation/serving consumer.

It must not become the replacement for the Spark analytics pipeline.

---

# 17. Visualization Libraries

Visualization libraries should remain lightweight and compatible with Streamlit.

The final implementation may use Streamlit's native charting capabilities and/or a visualization library where the required chart cannot be represented adequately using native functionality.

Possible categories include:

- line charts,
- bar charts,
- scatter plots,
- heatmaps,
- trend charts,
- correlation matrices,
- KPI cards,
- analytical tables.

Only libraries that are actually needed should be retained in the final dependency file.

---

# 18. Configuration

Configuration should be separated from application logic.

Possible configuration formats:

```text
YAML
JSON
TOML
Python configuration
environment variables
```

The final choice should be made once the repository structure is implemented.

Configuration should cover, where applicable:

- university hierarchy,
- generator seed,
- target volumes,
- school behavior,
- course difficulty,
- injection rates,
- academic calendar,
- risk thresholds,
- MongoDB connection,
- dummy users,
- dashboard settings.

---

# 19. Environment Variables

Environment variables should be used for secrets and environment-specific configuration.

Examples:

```text
MONGODB_URI
MONGODB_DATABASE
ACADexa_ENV
```

The exact variable names should be standardized before implementation.

Sensitive values must never be committed to GitHub.

A `.env.example` file may document required variables without containing real secrets.

---

# 20. Git and GitHub

### Role

Version control and project collaboration.

GitHub hosts:

- source code,
- documentation,
- configuration templates,
- tests,
- project history,
- issue/task tracking.

Large generated datasets should not automatically be committed to the repository.

The repository should distinguish between:

```text
source/configuration
```

and:

```text
generated data/artifacts
```

---

# 21. Markdown

Markdown is the project's documentation format.

The `docs/` directory contains the project reference documentation:

```text
docs/
├── prd.md
├── architecture.md
├── rules.md
├── design.md
├── tasks.md
├── memory.md
├── folder_structure.md
├── tech_stack.md
└── features.md
```

These documents collectively provide context for human developers and IDE agents.

---

# 22. Testing Stack

Testing should use Python-compatible testing tools.

A lightweight unit-testing framework should be selected during implementation.

Tests should cover at least:

- generator determinism,
- schema validation,
- data-quality injection,
- cleaning behavior,
- risk-signal rules,
- feature calculations,
- critical MongoDB queries,
- dashboard helper logic where applicable.

The exact testing library should be finalized when the code structure is created.

Do not add a large testing framework solely for appearance.

---

# 23. Logging

Python's standard logging facilities should be preferred initially.

Logging should provide enough information to identify:

- generator execution,
- seed/configuration,
- record counts,
- Spark job start/end,
- processing failures,
- quality checks,
- publication status,
- benchmark execution.

Avoid excessive logging of individual LMS events.

Large event-level debug logging can itself become a performance problem.

---

# 24. Dependency Management

The project should maintain a single explicit dependency definition.

Possible implementation:

```text
requirements.txt
```

or an equivalent Python project configuration such as:

```text
pyproject.toml
```

The final repository should avoid maintaining multiple conflicting dependency lists.

Versions should be pinned or constrained sufficiently to make the environment reproducible.

---

# 25. Technologies Explicitly Out of Core Scope

The following technologies are not part of the core Acadexa implementation.

## Kafka

**Status:** Out of scope.

Reason:

The project is batch-oriented and does not implement live event streaming.

## Spark Structured Streaming

**Status:** Out of scope.

Reason:

The project does not implement a live streaming pipeline.

## ML frameworks

**Status:** Not required for the core project.

The risk indicator is explicitly rule-based.

ML may be considered future scope.

## Cloud infrastructure

**Status:** Not required.

The project is designed for local execution.

## Real institutional databases

**Status:** Out of scope.

The project uses synthetic data only.

## Production identity providers

**Status:** Out of scope.

The dashboard uses dummy authentication.

## Full LMS ingestion into MongoDB

**Status:** Out of scope.

The full event dataset remains in Parquet; only the defined LMS slice is stored in MongoDB.

---

# 26. Technology Responsibility Matrix

| Technology | Layer | Primary responsibility | Core? |
|---|---|---|---|
| Python | Application | Main implementation language | Yes |
| NumPy | Generation | Numerical/random generation | Yes/Supporting |
| Polars | Generation | Optional efficient local tabular generation | Optional |
| PyArrow | Data format | Parquet interoperability | Yes/Supporting |
| Parquet | Raw storage | Full LMS event landing | Yes |
| MongoDB | Storage/Serving | Operational + analytical serving | Yes |
| MongoDB Time-Series | Storage | LMS event slice | Yes |
| MongoDB Aggregation | Analytics/Serving | Smaller/medium aggregations | Yes |
| MongoDB indexes | Serving | Query optimization | Yes |
| Apache Spark | Processing | Big Data batch engine | Yes |
| PySpark | Processing | Python implementation of Spark jobs | Yes |
| MongoDB Spark Connector | Integration | Spark ↔ MongoDB data movement | Yes |
| Streamlit | Presentation | Dashboard | Yes |
| Visualization library | Presentation | Charts where required | Optional |
| Git | Version control | Source history | Yes |
| GitHub | Collaboration | Repository/issue management | Yes |
| Markdown | Documentation | Project documentation | Yes |
| Python logging | Observability | Runtime logs | Yes |
| Testing framework | Quality | Automated tests | Yes |
| Kafka | Streaming | Live events | No |
| Structured Streaming | Streaming | Live processing | No |
| ML frameworks | Prediction | ML risk prediction | No |
| Cloud infrastructure | Deployment | Distributed deployment | No |
| Production IAM | Security | Real authentication | No |

---

# 27. Technology Selection Rules

When introducing a new dependency, the developer/IDE agent should answer:

1. What requirement does it satisfy?
2. Can the existing stack satisfy the requirement?
3. Which architectural layer owns it?
4. Does it increase memory or runtime requirements?
5. Does it conflict with the local-first constraint?
6. Does it duplicate an existing library?
7. Does it change the documented architecture?
8. Does it need to be added to the dependency manifest?
9. Does it require an update to `architecture.md`, `features.md`, or `rules.md`?

If a new technology materially changes the architecture, it must not be introduced silently.

---

# 28. Version Policy

The project should record the versions actually used for:

- Python,
- PySpark/Spark,
- MongoDB,
- MongoDB Spark Connector,
- Streamlit,
- NumPy,
- PyArrow,
- Polars if retained,
- major visualization/testing dependencies.

Version values in this document should be updated after environment setup.

Do not invent version numbers before compatibility has been verified.

---

# 29. Local Resource Policy

The stack must remain practical on the available machine.

Target project budget:

```text
24 GB system RAM
↓
~10–12 GB intended project usage
```

Therefore:

- avoid unnecessary local services,
- avoid duplicate data copies,
- avoid loading all events into memory,
- use Parquet for raw event storage,
- use Spark for large event processing,
- limit MongoDB's LMS event slice,
- monitor Spark driver memory,
- avoid heavyweight dependencies unless justified.

---

# 30. GPU Policy

A GPU is not required by the core Acadexa architecture.

The project is a Big Data analytics system rather than a deep-learning workload.

The system should not introduce GPU-specific dependencies unless a future approved feature actually requires them.

---

# 31. Data Generation Technology Boundary

The generator may use:

```text
Python
+
NumPy
+
Polars and/or PyArrow
```

but generated data must ultimately follow the project's defined storage architecture.

Conceptually:

```text
Python generator
      ↓
Chunk
      ↓
Parquet / MongoDB
      ↓
Spark processing
```

The generator should not use pandas as a mandatory intermediate representation for the complete ~70M-event dataset.

---

# 32. Analytics Technology Boundary

Use:

### MongoDB

For:

- CRUD,
- indexed lookups,
- selected aggregations,
- dashboard drill-down,
- time-series slice.

### Spark

For:

- large joins,
- cleaning,
- feature engineering,
- large-scale event aggregation,
- correlation,
- temporal windows,
- risk signals,
- full-dataset processing.

### Python

For:

- orchestration,
- utility functions,
- configuration,
- validation,
- benchmark coordination.

Do not move heavy Spark workloads into ordinary Python loops.

---

# 33. Dashboard Technology Boundary

Streamlit should:

- query MongoDB,
- render analytical results,
- provide navigation,
- apply user-facing filters,
- display charts/tables,
- show risk signals,
- show data-quality and analytical results.

Streamlit should not:

- read the complete 70M-event Parquet dataset for every page load,
- execute the complete Spark pipeline interactively,
- recreate all analytical joins,
- calculate large-scale metrics that should already exist in gold collections.

---

# 34. Recommended Dependency Categories

The final environment should conceptually contain:

```text
Core
├── Python
├── PySpark
├── pymongo / MongoDB client
├── Streamlit
├── NumPy
└── PyArrow

Generation
└── Polars (only if retained)

Integration
└── MongoDB Spark Connector

Quality
└── Testing dependency

Development
├── Formatting/linting tools if selected
└── Environment tooling if selected
```

The final `requirements.txt` or `pyproject.toml` should contain only packages actually required by the implementation.

---

# 35. Stack-to-Architecture Mapping

```text
                ACADExA
                   │
       ┌───────────┴───────────┐
       │                       │
   Generation              Presentation
       │                       │
 Python / NumPy          Streamlit
 Polars / PyArrow             │
       │                       │
       ▼                       ▼
   Parquet                 MongoDB
       │                       ▲
       │                       │
       ▼                       │
    PySpark ───────────────────┘
       │
       ▼
 Gold analytical collections
```

MongoDB also receives the core generated collections and the defined LMS operational slice.

---

# 36. Stack Invariants

The following are technology-level invariants unless explicitly changed:

1. Python remains the primary language.
2. PySpark remains the main large-scale batch-processing technology.
3. MongoDB remains the primary operational/serving database.
4. Parquet remains the raw landing format for the complete LMS event dataset.
5. Streamlit remains the dashboard framework.
6. Kafka is not required for the core implementation.
7. Structured Streaming is not required for the core implementation.
8. The risk indicator remains rule-based.
9. Real institutional data is not required.
10. The system remains local-first.
11. Heavy analytics should not be moved into Streamlit.
12. The complete LMS dataset should not be loaded into MongoDB merely for convenience.
13. New dependencies require a documented reason.

---

# 37. Final Stack Statement

> Acadexa uses Python as its primary development language; NumPy and optionally Polars/PyArrow for reproducible synthetic-data generation; Apache Parquet as the raw LMS event landing format; MongoDB for operational, time-series and analytical serving; Apache Spark/PySpark in local mode for large-scale batch processing; MongoDB Spark integration for data exchange; and Streamlit for the role-aware analytical dashboard. The core stack intentionally excludes Kafka, Structured Streaming, ML-based risk prediction, production identity infrastructure, and cloud deployment.

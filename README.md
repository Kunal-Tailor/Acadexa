# Acadexa

### An Integrated University Academic Intelligence System Using MongoDB and PySpark

Acadexa is a **Big Data learning-analytics platform** designed for a multi-school university environment. It integrates synthetic academic and LMS data to demonstrate how **MongoDB, Parquet, and PySpark** can work together to process large-scale educational data and produce meaningful analytical insights.

The project is being developed as a final-year Big Data Technologies project and is designed around **RAS University**, a synthetic university modeled on the academic structure of MIT-WPU.

---

## Overview

Acadexa brings together multiple academic factors that are normally analyzed separately:

- Student academic performance
- Attendance
- Coursework and submissions
- Quiz activity
- LMS engagement
- Temporal trends
- Data-quality information

These datasets are processed through a batch Big Data pipeline to generate:

- Cross-factor associations
- Student and course features
- Engagement trends
- Rule-based risk indicators
- School and university summaries
- Data-quality reports
- Technology benchmarks

The final results are exposed through a **Streamlit dashboard** with role-aware views.

> **Important:** Acadexa uses fully synthetic data. It does not require or use real student or institutional data.

---

## Project Objective

The primary objective is to demonstrate a **scalable, reproducible Big Data analytics pipeline** rather than build a conventional student-management application.

The core pipeline is:

```text
Synthetic Data Generator
        │
        ├──────────────→ Parquet
        │
        └──────────────→ MongoDB
                              │
                              ▼
                         PySpark Local
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
            Features      Analytics      Risk Signals
               │              │              │
               └──────────────┼──────────────┘
                              ▼
                       Gold Collections
                              │
                              ▼
                          MongoDB
                              │
                              ▼
                         Streamlit
```

---

## Target Scale

Acadexa is designed toward the following target dataset:

| Component | Target |
|---|---:|
| Schools | 6 |
| Departments | ~18 |
| Programs | ~40 |
| Courses | ~250 |
| Students | ~12,000 |
| Academic period | 2 years / 4 semesters |
| LMS events | ~70 million |

These values are **engineering targets**, not claimed measured results. Actual generated volume, disk usage, execution time, and memory consumption will be recorded after the pipeline is executed.

---

## Core Analytics

Acadexa focuses on three main analytical areas.

### 1. Cross-Factor Analysis

The system examines relationships between factors such as:

```text
Attendance ↔ Marks
LMS Engagement ↔ Marks
Late Submissions ↔ Marks
```

The default correlation method is **Spearman correlation**, with within-course normalization used where specified.

These are interpreted as **associations, not causal relationships**.

---

### 2. Trend Detection

The system identifies changes in student behavior over time.

A key LMS comparison is:

```text
Current 4-week engagement
        vs
Previous 4-week engagement
```

The synthetic generator also creates a controlled population of approximately 8% "decliners" so that trend detection can be evaluated against known synthetic behavior.

---

### 3. Rule-Based Risk Signals

Acadexa uses five predefined signals:

1. Attendance below 75%
2. LMS engagement at or below 50% of the previous four-week period
3. More than 30% of assignments submitted late
4. Latest three graded items averaging at least 10 points below the earlier comparison average
5. Quiz attempts in the bottom quartile

Each triggered condition contributes one point:

```text
Risk Signal Count = 0–5
```

This is an **observed signal count**, not a failure prediction or machine-learning model.

---

## Big Data Approach

Acadexa demonstrates the five Vs of Big Data:

### Volume

Approximately 70M LMS events plus millions of other academic records.

### Velocity

Timestamped batch-generated LMS activity. The current project does **not** use live streaming.

### Variety

The project works with:

- Structured academic records
- Time-series LMS events
- MongoDB documents
- Parquet datasets

### Veracity

Controlled synthetic data-quality issues are injected, including:

- Duplicates
- Selected nulls
- Timestamp inconsistencies
- Course-ID formatting problems
- Orphan records
- Out-of-range values

### Value

The processed data produces:

- Cross-factor analytics
- Trends
- Risk signals
- Academic summaries
- Data-quality insights
- Dashboard views
- Technology benchmarks

---

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application and data generation |
| NumPy | Synthetic-data generation |
| Parquet | Large raw LMS event storage |
| MongoDB | Operational and analytical serving layer |
| MongoDB Time-Series | Appropriate LMS event storage |
| MongoDB Aggregation | Database-side analytics |
| PySpark | Large-scale batch processing |
| MongoDB Spark Integration | Spark ↔ MongoDB integration |
| Streamlit | Dashboard |
| Python visualization libraries | Charts and analytical views |
| Git / GitHub | Version control |
| Markdown | Project documentation |

The project is designed to run locally using **PySpark local mode**.

---

## Data Architecture

### Core MongoDB Collections

```text
students
courses
academic_records
attendance
coursework
lms_events
```

### Gold / Serving Collections

```text
student_features
course_metrics
school_summary
risk_indicators
```

The full LMS dataset is stored in Parquet. Only the defined LMS serving slice is placed in MongoDB to keep the local architecture resource-conscious.

---

## Spark Processing Pipeline

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

The pipeline is designed to move from raw data to dashboard-ready analytical collections.

---

## Dashboard

Acadexa provides a Streamlit dashboard with a hierarchical analytical experience:

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

Planned dashboard areas:

- **Overview**
- **Schools**
- **Courses**
- **Students**
- **Analysis**
- **Data Quality**

### User Roles

The dashboard supports four demonstration personas:

- University Admin
- School / Department Admin
- Faculty
- Academic Analyst

A dummy login is included for role-aware access.

---

## Synthetic Data & Ground Truth

The synthetic generator intentionally creates controlled relationships between academic variables.

It models synthetic characteristics such as:

```text
Ability
Diligence
Engagement
Course Difficulty
```

The project also maintains a **ground-truth registry** describing planted relationships.

This enables a recovery experiment:

```text
Planted relationship
        ↓
Synthetic dataset
        ↓
PySpark analytics
        ↓
Observed relationship
        ↓
Recovery comparison
```

The purpose is to demonstrate whether the analytical pipeline can recover relationships that were intentionally embedded in the generated data.

---

## Data Quality

Acadexa intentionally injects a small amount of controlled data-quality noise.

The pipeline measures:

```text
Injected
Detected
Corrected
Dropped
Remaining
```

This demonstrates the **Veracity** dimension of the project and makes the cleaning pipeline measurable rather than purely theoretical.

---

## Benchmarking

The project includes a benchmarking component comparing suitable workloads across:

```text
Pandas
MongoDB Aggregation
PySpark
```

Example workload:

```text
Weekly LMS engagement aggregation
```

Other applicable workloads may include large feature-table joins.

Benchmarks record measured information such as:

- Dataset size
- Wall-clock execution time
- Peak memory where practical
- Environment
- Workload description

The goal is to demonstrate where different technologies fit rather than produce a predetermined winner.

---

## MVP Strategy

Acadexa is intentionally being developed using a **vertical-slice-first approach**.

### MVP

The first milestone is:

```text
One School
+
One Semester
+
Synthetic Data
+
MongoDB
+
Parquet
+
PySpark
+
Gold Collections
+
Streamlit
```

Only after the complete pipeline works end-to-end will it be scaled toward the full target dataset.

This reduces the risk of discovering integration or schema problems only after generating millions of records.

---

## Repository Structure

```text
acadexa/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── requirements.txt
│
├── docs/
│   ├── prd.md
│   ├── architecture.md
│   ├── rules.md
│   ├── design.md
│   ├── tasks.md
│   ├── memory.md
│   ├── folder_structure.md
│   ├── tech_stack.md
│   └── features.md
│
├── config/
│   ├── university/
│   ├── generator/
│   ├── dashboard/
│   └── risk/
│
├── src/
│   └── acadexa/
│       ├── config/
│       ├── generator/
│       ├── database/
│       ├── processing/
│       ├── analytics/
│       ├── dashboard/
│       ├── validation/
│       ├── benchmarks/
│       └── utils/
│
├── scripts/
│   ├── generate_data.py
│   ├── load_mongodb.py
│   ├── run_pipeline.py
│   ├── publish_gold.py
│   └── run_benchmarks.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── data/
│   └── fixtures/
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── generated/
│   ├── manifests/
│   └── samples/
│
├── reports/
│   ├── quality/
│   ├── benchmarks/
│   ├── recovery/
│   └── exports/
│
├── logs/
│
└── notebooks/
    └── exploratory/
```

Large generated datasets should not be committed to Git.

---

## Local Development

### Prerequisites

The project is intended to run locally with:

- Python
- MongoDB
- Java runtime compatible with the selected PySpark version
- PySpark
- Streamlit
- Git

The exact dependency versions will be maintained in the project's dependency configuration.

---

### 1. Clone the repository

```bash
git clone <repository-url>
cd acadexa
```

### 2. Create a virtual environment

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy:

```text
.env.example
```

to:

```text
.env
```

and configure the local MongoDB connection.

Do not commit `.env`.

---

## Intended Execution Flow

Once implementation is complete, the normal project flow will resemble:

```bash
# Generate synthetic data
python scripts/generate_data.py

# Load MongoDB
python scripts/load_mongodb.py

# Run Spark processing
python scripts/run_pipeline.py

# Publish/refresh gold collections
python scripts/publish_gold.py

# Run benchmarks
python scripts/run_benchmarks.py

# Start dashboard
streamlit run src/acadexa/dashboard/app.py
```

The exact commands may evolve during implementation.

---

## Project Constraints

The following are intentionally outside the current core scope:

- Kafka
- Spark Structured Streaming
- Live streaming
- Machine-learning prediction
- Failure prediction
- Real institutional/student data
- Production IAM
- Cloud deployment
- Full LMS dataset in MongoDB
- More than six schools
- Question-level quiz analytics

These may be considered future extensions but should not be introduced into the core implementation without an explicit project decision.

---

## Resource Constraints

Acadexa is designed around local development resources of approximately:

```text
24 GB system RAM
RTX 4060 8 GB
~10–12 GB intended project resource usage
```

The implementation therefore emphasizes:

- Chunked data generation
- Parquet for large raw event storage
- Limited MongoDB LMS serving data
- Spark local mode
- Memory-conscious transformations
- Avoidance of large `collect()` operations
- Measured rather than assumed performance

---

## Documentation

The `docs/` directory contains the project's detailed source of truth:

| Document | Purpose |
|---|---|
| `prd.md` | Product requirements |
| `architecture.md` | System architecture |
| `tech_stack.md` | Technology decisions |
| `features.md` | Feature specification |
| `rules.md` | Coding and implementation rules |
| `design.md` | UI/UX direction |
| `tasks.md` | Implementation roadmap |
| `memory.md` | Persistent project context |
| `folder_structure.md` | Repository organization |

When implementing a significant change, consult the relevant documentation before changing the architecture or scope.

---

## Academic Disclaimer

Acadexa uses **fully synthetic data** for educational and demonstration purposes.

The generated students, academic records, LMS activity, relationships, trends and risk signals do not represent real students, real institutional outcomes, or real university data.

Analytical relationships are interpreted as associations and should not be treated as causal conclusions.

---

## Project Status

**Current stage:** Documentation and implementation foundation

### Completed documentation

- [x] Product requirements
- [x] Architecture
- [x] Technology stack
- [x] Feature specification
- [x] Repository structure
- [x] Coding rules
- [x] UI/UX design
- [x] Implementation roadmap
- [x] Project memory

### Next implementation milestone

> **Build and validate the one-school, one-semester end-to-end vertical slice.**

---

## License

This project is developed as an academic project.

Add the final project license here once the team decides which license, if any, should be applied to the repository.

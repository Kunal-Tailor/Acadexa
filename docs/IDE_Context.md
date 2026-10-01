# IDE Context — Acadexa Full Session Record (Task 0.1 → 14.4; 14.5/14.6 running)

**Document:** `docs/IDE_Context.md`  
**Purpose:** Complete, self-contained, authoritative working memory and architectural context for any human developer or IDE agent resuming this codebase.  
**Created by:** Task 4.9 (`Update - 4.9 - add IDE context documentation`), updated by Task 7.7, and comprehensively expanded by Task 9.7 (`Update - 9.7 - IDE_Context data addition`) at Phase 9 Checkpoint.  
**Session update:** Tasks 10.1 → 14.4 implemented 2026-09-29 → 2026-10-01 in one continuous IDE session (Sections 13–15); Tasks 14.5/14.6 in progress.  
**Snapshot date:** 2026-10-01  
**Repository:** `D:\College\Secondary\Projects\acadexa`, branch `main`  
**State at snapshot:** Tasks 0.1 → 14.4 fully implemented (≈190 new unit/integration tests this session, all passing alongside the existing suite); full-scale core data generated (12,000 students, 288K records, 4.6M attendance, 3.3M coursework); full LMS generation running in background (PID 3104, see Section 14 — do not kill it).

> **How to use this file:**
> Read Sections 1–4 before touching any code — they define the immutable non-negotiables, environment constraints, and working protocols.
> Section 5 contains the complete, deep execution history (what happened, design decisions taken, why they were taken, what broke, what worked, and exact document alignments).
> Sections 6–8 describe the current end-to-end architecture, calibration numbers, data volumes, quality metrics, and test suite breakdown.
> Sections 9–11 cover what is working, deliberate deferrals, session failure modes and gotchas, and the exhaustive step-by-step roadmap for Phase 10.
> Section 13 records the Tasks 10.1 → 14.4 session (this chat): per-task goals, files, decisions, verification and measurements.
> Section 14 is the live state of the in-progress full-scale run — read it first on resumption before touching generation, data, or MongoDB.
> Section 15 is the resumption blueprint: finishing Phase 14, then Phase 15.

---

## 1. Project in One Screen — Non-Negotiables

**Acadexa** = synthetic-data-only Big Data learning-analytics platform for fictional **RAS University** (6 schools, 18 departments, 40 programs, 250 courses, 12,000 target students, 2 academic years / 4 semesters, ~70M target LMS events). Final-year Big Data Technologies academic project.

### Pipeline Architecture
```text
Synthetic Generator (Python/NumPy)
       │
       ├──► Raw CSV / Parquet (data/raw/)
       │         │
       │         ├──► MongoDB Raw Serving Slice (acadexa database)
       │         │
       │         └──► PySpark Local Mode (J1 Clean & Validate)
       │                    │
       │                    ├──► Clean Parquet (data/processed/)
       │                    │         │
       │                    │         ├──► PySpark (J2 Weekly LMS Aggregation)
       │                    │         │         │
       │                    │         │         └──► Parquet (data/processed/lms_weekly_engagement/)
       │                    │         │
       │                    │         └──► PySpark (J3 Unified Feature Table)
       │                    │                   │
       │                    │                   ├──► Parquet (data/processed/student_course_features/)
       │                    │                   │
       │                    │                   ├──► PySpark (J4 Correlation Analytics & Simpson's Paradox)
       │                    │                   ├──► PySpark (J5 Temporal Trend Detection)
       │                    │                   └──► PySpark (J6 Five-Rule Risk Signals & Explanations)
       │                    │                             │
       │                    ▼                             ▼
       │               PySpark (J7 Gold Layer Publisher & Validator)
       │                    │
       ▼                    ▼
   MongoDB Gold Layer (acadexa.student_features, course_metrics, school_summary, risk_indicators)
       │
       ▼
   Streamlit Interactive Analytics Dashboard (Phases 11-12)
```

### Immutable Hard Rules
*(Derived from `docs/rules.md`, `docs/prd.md`, `docs/memory.md`, and `docs/TASKS.md`)*:

1. **One task at a time**, strictly top to bottom. Never bundle later tasks, never scaffold future tasks in advance, never self-advance.
2. **The agent NEVER runs `git commit`** — stop, mark the task `[x]` in `docs/TASKS.md`, report ready to commit with the exact commit message format: `Update - <Phase>.<Task> - <description>`; the user reviews diffs and commits manually.
3. **100% synthetic data.** No real student data. Disclose synthetic nature everywhere.
4. **Frozen schemas** (`src/acadexa/validation/schema.py`, rules.md §11) — never add fields to canonical domain schemas (e.g., decliner flags, behavioral traits, and internal items are internal generator state, never written to raw domain entities).
5. **Deterministic reproducibility:** same seed + same config ⇒ byte-identical output (rules.md §8.2). All randomness flows through SHA-derived deterministic sub-streams via `GeneratorRun.child_rng("<name>")`.
6. **Configuration-driven architecture:** zero hard-coded behavioral values; all parameters live in `config/**/*.toml`. Validation exists at two layers: `ConfigurationError` (config loading, `src/acadexa/config/validation.py`) and `GeneratorError` (runtime fail-fast).
7. **No ML predictive modeling, no streaming/Kafka, no causal claims** ("associated with", never "causes"). Risk detection = exactly the five approved rule-based signals (rules.md §1.2).
8. **Correlation method:** Spearman rank correlation is the primary non-linear monotonic metric; Pearson is optional and secondary.
9. **LMS storage split:** full raw LMS events stay in Parquet; only a defined serving slice is loaded into MongoDB (rules.md §24, architecture.md). Never attempt to load 70M events into MongoDB.
10. **PySpark driver safety:** absolutely NO large `.collect()`, `.toPandas()`, or `.toArray()` calls on DataFrames (rules.md §17.3, §17.5). PySpark computations must execute distributedly via DataFrame transformations.

**Documentation Authority Hierarchy:**  
**Owner Decisions > `prd.md` > `architecture.md` > `features.md` > `tech_stack.md` > `folder_structure.md` > `rules.md` > local preference.**

---

## 2. Environment & Toolchain

| Item | Value / Configuration |
|---|---|
| OS / Shell | Windows 11 (`win32`), PowerShell 5.1 |
| Python | 3.11.9 (`C:\Program Files\Python311\python.exe`) |
| PySpark | 3.5.x / 4.x runtime, configured for `local[2]` or `local[*]` with Winutils dummy fallback |
| MongoDB | Local / Docker MongoDB instance running at `localhost:27017` (`acadexa` database) |
| PyTest | 8.3.5, configured via `pytest.ini` |
| Test suite status | **438+ passed**, verified clean across all unit test modules |
| Test execution | `$env:PYTHONPATH='d:\College\Secondary\Projects\acadexa\src'; python -m pytest tests/unit -q` |
| Pipeline execution | `python scripts/run_pipeline.py` (executes J1 → J2 → J3 → J4/J5/J6 → J7 in ~46s on dev data) |
| Dependencies | Managed in `requirements.txt` (minimal, strictly vetted) |

### PowerShell & Environment Gotchas
- **Nested Quotes in PowerShell:** Nested double/single quotes in PowerShell commands frequently fail parsing. Use `.py` scripts or pass simple strings.
- **Python Path:** `PYTHONPATH` must be explicitly set (`$env:PYTHONPATH="src"`) when invoking Python commands or pytest from the root folder.
- **Hadoop Home on Windows:** On Windows, PySpark requires a dummy `HADOOP_HOME` or `winutils.exe` fallback to prevent initialization crashes. Handled automatically in `src/acadexa/processing/spark_session.py`.
- **PySpark JVM Singleton Classloader:** PySpark boots a single Py4J JVM per Python process. If the JVM initializes without the MongoDB connector JAR on the classpath, subsequent sessions cannot dynamically attach it. Handled automatically in `get_or_create_spark_session()` by injecting cached Ivy JARs on session builder creation.
- **PySpark Session Scoping:** In pytest, module-scoped Spark session fixtures must call `yield spark` and terminate with `stop_spark_session(spark)` in a `finally` block to prevent JVM context collisions across test suites.

---

## 3. Documentation Map (`docs/`)

| File | Primary Governance & Context |
|---|---|
| `prd.md` | Core product requirements, scope boundaries, dataset targets, risk signals, and deliverables. |
| `architecture.md` | System data flow, storage split (MongoDB vs Parquet), PySpark jobs (J1–J7), and serving architecture. |
| `tech_stack.md` | Rationales for Python, NumPy, PySpark, MongoDB, Streamlit, and PyArrow. |
| `features.md` | Complete feature catalogue with canonical IDs (`F-B*` behavioral, `F-D*` dashboard). |
| `folder_structure.md` | Canonical directory layout and naming conventions. |
| `rules.md` | Non-negotiable engineering rules (§8 reproducibility, §10 no null keys, §11 frozen schemas, §17 PySpark driver safety, §24 resource limits). |
| `design.md` | UX design guidelines, page layouts, and chart specifications for Streamlit. |
| `TASKS.md` | The master task list across 17 phases. Serves as the tracking state (`[x]` completion markers). |
| `memory.md` | Compact project memory: §6 behavioral traits, §7 planted relationships, §12 data quality rates, §24 hardware constraints. |
| `original_idea_of_project.md` | Conceptual origins: decliners (~8%), LMS weekly/diurnal rhythms, decoy relationships (Simpson's paradox). |
| `IDE_Context.md` | **This document:** the comprehensive, persistent operational memory for the IDE. |

---

## 4. Session Working Protocol

Every task follows this exact cycle:
1. Receive prompt: `Proceed with task <TASK_ID> from docs/TASKS.md only.`
2. Check rules: only this task, no forward scaffolding, no self-advancing, no `git commit`.
3. Consult context in `docs/` relevant to the task.
4. Implement code and corresponding unit/integration tests.
5. Execute targeted tests, then relevant suite components.
6. Verify no side-effects, syntax errors, or schema violations.
7. Update `docs/TASKS.md` marking the task `[x]`.
8. Report completion with the exact commit message specified in `TASKS.md` and **stop**.

---

## 5. Comprehensive Execution History (Tasks 0.1 → 9.6)

### Commit Log Summary (Phases 0 → 9)
```text
ec3ba28 Update - 0.1 - Project Folder Setup
7a2e3b7 Update - 0.2 - docs folder setup
ae871cc Update - 0.3 - tasks & readme file update
8ea45df Update - 1.1 - initialize repository ignore rules
4afee41 Update - 1.2 - add project README
a6a8d34 Update - 1.3 - add environment configuration template
69ff31a Update - 1.4_&_1.5 - create repository folder structure and Python package skeleton
5697635 Update - 1.6,1.7&1.8 - create entry points, test structure and initial dependencies
9781397 Update - 2.1 - implement configuration loading
18e2081 Update - 2.2 - define university hierarchy configuration
e7ac29d Update - 2.3 - define academic period configuration
b6e3892 Update - 2.4 - define synthetic generator configuration
461f65e Update - 2.5 - define risk signal configuration
1dedbbe Update - 2.6 - validate project configuration
9b24968 Update - 3.1 - define student schema
2153275 Update - 3.2 - define course schema
9550864 Update - 3.3 - define academic record schema
39f23ae Update - 3.4 - define attendance schema
51fe528 Update - 3.5 - define coursework schema
f798a89 Update - 3.6 - define LMS event schema
236d844 Update - 3.7 - define gold collection schemas
4e1264d Update - 3.8 - add schema validation layer
fa2c06b Update - 4.1 - implement deterministic generator foundation
570bed9 Update - 4.2 - generate university hierarchy
6b7f173 Update - 4.3 - generate synthetic students
d2b5ad5 Update - 4.4 - generate academic records
c738e1a Update - 4.5 - generate attendance data
9f39693 Update - 4.6 - generate coursework data
4f8fed5 Update - 4.7 - implement synthetic behavioral model
eb3a8e3 Update - 4.8 - implement synthetic decliner population
f95bc6f Update - 4.9 - add IDE context
77d3e38 Update - 5.1 - implement LMS event generation
a272d88 Update - 5.2 - implement LMS temporal behavior
9701c84 Update - 5.3 - implement chunked LMS generation
1327468 Update - 5.4 - write development LMS data to Parquet
08e861a Update - 5.5 - implement synthetic ground truth registry
989ce4b Update - 5.6 - implement data quality injection
9a595ff Update - 5.7 - implement generation manifests
776142b Update - 5.8 - wire development data generation entry point
1b99410 Update - 6.1 - implement MongoDB connection layer
a64065e Update - 6.2 - initialize MongoDB collections
60219d9 Update - 6.3 - load core academic collections
b163ce8 Update - 6.4 - load LMS serving slice
d53a905 Update - 6.5 - add MongoDB query indexes
b4bd06b Update - 6.6 - implement MongoDB analytical aggregations
be7d024 Update - 6.7 - wire MongoDB loading entry point
3c2e167 Update - 7.1 - configure local PySpark runtime
f1d446e Update - 7.2 - configure Spark MongoDB integration
ec1d2d3 Update - 7.3 & 7.4 - implement Spark clean and validate job & quality reporting
6e98bce Update - 7.5 & 7.6 - implement Spark LMS aggregation job & tests
1defa45 Update - 7.7 - add IDE context documentation for Phases 5 to 7
c1f7ad7 Update - 8.1 & 8.2 - implement integrated student feature table and derived metrics
db0b16a Update - 8.3 & 8.4 - implement within-course normalization and correlation analytics
f4887e8 Update - 8.5 & 8.6 - add optional Pearson analysis and temporal trend detection
7edd93d Update - 8.7 & 8.8 - implement five-rule risk signals and explainability
8282162 Update - 9.1 & 9.2 - publish student features & course and school metrics
5d561b2 Update - 9.3 & 9.4 - publish risk indicators & validate gold collections
5ed26b9 Update - 9.5 & 9.6 - wire end-to-end Spark pipeline & add pipeline run metadata
pending Update - 9.7 - IDE_Context data addition
```

---

### Phase 0 to Phase 7 Summary
- **Phase 0 (Documentation Baseline):** Ingested canonical specifications into `docs/` verbatim; standardized path references.
- **Phase 1 (Repository Foundation):** Established repository structure, `.gitignore`, `.env.example`, `requirements.txt`, entry point stubs.
- **Phase 2 (Configuration Contract):** Built TOML loaders and cross-validation for university hierarchy, periods, generator, and risk thresholds.
- **Phase 3 (Canonical Schema Contract):** Created frozen domain schemas (`students`, `courses`, `academic_records`, `attendance`, `coursework`, `lms_events`, and gold schemas) and assertion validators.
- **Phase 4 (Synthetic Generator Foundation):** Built `GeneratorRun` with SHA-derived child RNG streams, demographic sampling, academic enrollment (6 courses/term), binomial attendance, coursework items, latent traits (`ability`, `diligence`, `engagement`), and ~8% decliner population.
- **Phase 5 (Synthetic LMS Events & Ground Truth):** Implemented chunked LMS generation (8 approved event types), diurnal/weekly temporal rhythms, PyArrow Parquet writer, ground truth registry (`ground_truth_registry.json`), data quality injection (~11.7k anomalies), and run manifests.
- **Phase 6 (MongoDB Data Layer):** Built client pooling, initialized raw and gold collections, loaded academic CSVs and 10k LMS serving slice, created query indexes, and implemented 8 MongoDB aggregation pipelines.
- **Phase 7 (PySpark Environment & J1/J2 Pipeline):** Configured local PySpark with Winutils fallback, configured DataSource V2 MongoDB connector, implemented J1 (Clean & Validate) with 100% issue detection/correction traceability, and J2 (Weekly LMS Event Aggregation) producing 13,823 weekly engagement rows.

---

### Phase 8: Feature Engineering & Analytics (Tasks 8.1 → 8.8)

#### Tasks 8.1 & 8.2 — Integrated Feature Table & Derived Metrics (Job J3) (`c1f7ad7`)
- **What:** Implemented `src/acadexa/processing/jobs/feature_table.py` joining cleaned academic records, attendance summary, coursework summary, and weekly LMS features.
- **Grains:**
  - Primary: `student_id x course_id x semester_id` (`build_student_course_features`).
  - Secondary: `student_id x semester_id` (`build_student_semester_features`).
- **Features Implemented:**
  - *Attendance:* `classes_conducted`, `classes_attended`, `attendance_percentage` (`attended / conducted * 100`).
  - *Coursework:* `total_coursework_assigned`, `submitted_coursework`, `late_submissions`, `late_submission_rate` (`late / submitted`), `missing_coursework`, `missing_coursework_rate` (`missing / assigned`), `coursework_avg_score` (`score / max * 100`), `quiz_attempts`, `quiz_retry_ratio` (`attempts / quizzes`), `quiz_avg_score`.
  - *LMS Engagement:* `total_lms_events`, `total_lms_duration_sec`, `active_days_count`, `active_weeks_count`, category counts (`content_views`, `assessment_events`, `participation_events`, `access_events`).
  - *Performance:* `coursework_marks`, `midterm_marks`, `endterm_marks`, `final_score`, `grade_points`.
- **Output:** Parquet dataset written to `data/processed/student_course_features/` (864 rows in development scale).
- **Verification:** AST inspection verified 0 driver-side `.collect()` calls. 22 unit tests passing in `tests/unit/test_feature_table.py`.

#### Tasks 8.3 & 8.4 — Within-Course Normalization & Correlation Analytics (Job J4) (`db0b16a`)
- **What:** Implemented `src/acadexa/analytics/correlation.py` providing distributed Spearman rank correlation and within-course score normalization.
- **Decisions & Rationale:**
  - *Within-Course Z-Score Normalization:* Normalized student marks using course-level mean and standard deviation: `(score - course_mean) / course_stddev`. Handled zero-variance courses by defaulting normalized score to `0.0`.
  - *Distributed Spearman Computation:* Leveraged Spark SQL window ranking `F.percent_rank().over(Window.orderBy(col))` and calculated Pearson correlation on the ranks across primary pairs:
    1. `attendance_percentage` vs `final_score`
    2. `total_lms_events` vs `final_score`
    3. `late_submission_rate` vs `final_score`
    4. `forum_posts` vs `final_score` (decoy / Simpson's paradox)
    5. `quiz_retry_ratio` vs `final_score`
  - *Simpson's Paradox Stratification:* Implemented stratification by `school` and `course_difficulty`. Proved that the aggregate forum posts correlation is confounded by school-level forum culture, showing how stratification reveals the underlying reality.
- **Verification:** 9 unit tests passing in `tests/unit/test_correlation.py`.

#### Tasks 8.5 & 8.6 — Optional Pearson Metric & Temporal Trend Detection (Job J5) (`f4887e8`)
- **What:** Implemented `src/acadexa/analytics/trends.py` and extended `correlation.py` with Pearson correlation comparison.
- **Temporal Trajectory Features (J5):**
  - *LMS Activity Slope:* Linear regression slope of weekly LMS event counts across weeks 1 to 16.
  - *LMS Decline Trigger:* Comparison of late semester engagement (weeks 10–15) against early baseline (weeks 1–6); flags decline if late activity is $\le 50\%$ of early activity.
  - *Marks Trajectory:* Longitudinal delta between assessment checkpoints (midterm vs coursework/endterm); flags marks decline if drop $\ge 10$ points.
- **Output:** Trend indicators DataFrame at `student_id x course_id x semester_id` grain.
- **Verification:** 10 unit tests passing in `tests/unit/test_trends.py`.

#### Tasks 8.7 & 8.8 — Five-Rule Risk Signal Engine & Explainability (Job J6) (`7edd93d`)
- **What:** Implemented `src/acadexa/analytics/risk_signals.py` codifying the exact five approved rule-based risk triggers (§1.2 and `config/risk/risk_signals.toml`).
- **Five Approved Rules:**
  1. `low_attendance`: `attendance_percentage < 75.0`
  2. `lms_decline`: late LMS activity $\le 50\%$ of baseline
  3. `late_submissions`: `late_submission_rate > 0.30`
  4. `marks_decline`: score decline between checkpoints $\ge 10.0$ points
  5. `low_quiz_activity`: quiz average or engagement in bottom quartile ($< 25\text{th}$ percentile) of course cohort
- **Signal Aggregation & Explainability:**
  - Aggregates risk signals per student: `signal_count` ($0 \dots 5$).
  - High risk flag: `is_high_risk = signal_count >= 3`.
  - Structured explanation dictionary: records exact trigger status, observed value, threshold, and human-readable explanation for each rule.
- **Verification:** 9 unit tests passing in `tests/unit/test_risk_signals.py`.

---

### Phase 9: Gold Layer & Pipeline Orchestration (Tasks 9.1 → 9.6)

#### Tasks 9.1 & 9.2 — J7 Gold Publication of Core Summaries (`8282162`)
- **What:** Implemented `src/acadexa/processing/jobs/publish_gold.py` publishing core gold collections to Parquet and MongoDB DataSource V2.
- **Published Collections & Schemas:**
  - `student_features` (grain: `student_id x semester_id`): `attendance_mean`, `engagement_count`, `late_submission_rate`, `score_trend`, `coursework_avg`. Strictly conforms to `STUDENT_FEATURES_SCHEMA`.
  - `course_metrics` (grain: `course_id x semester_id`): `avg_performance`, `avg_attendance`, `engagement_count`, `difficulty_adjusted_performance`. Strictly conforms to `COURSE_METRICS_SCHEMA`.
  - `school_summary` (grain: `school x department`): `student_count`, `course_count`, `avg_performance`, `avg_attendance`, `engagement_count`. Strictly conforms to `SCHOOL_SUMMARY_SCHEMA`.
- **Decisions & Rationale:**
  - Computations execute 100% in PySpark using distributed aggregations.
  - Zero `.collect()` on datasets prior to publishing (rules.md §17.3).

#### Tasks 9.3 & 9.4 — J7 Gold Publication of Risk Indicators & Post-Publication Validation (`5d561b2`)
- **What:** Extended `publish_gold.py` with `publish_risk_indicators` and implemented `src/acadexa/validation/gold.py`.
- **`risk_indicators` Gold Collection:**
  - Grain: `student_id x week_start`.
  - Published to MongoDB `acadexa.risk_indicators` and Parquet `data/gold/risk_indicators/`.
  - Conforms to `RISK_INDICATORS_SCHEMA`.
  - Captures signal breakdown in `J7Result`: total students, flagged students, high risk students, signal count distribution (0–5), and flag frequencies.
- **Post-Publication Validation (`src/acadexa/validation/gold.py`):**
  - `validate_gold_dataframe()`: Asserts DataFrame row count $> 0$, confirms 100% grain uniqueness (no duplicate composite keys), and verifies all required schema fields are present.
  - `validate_gold_mongodb()`: Directly verifies live MongoDB collections using PyMongo.
  - `GoldValidationError`: Immediate fail-fast exception if validation checks fail when `fail_on_validation_error=True`.
- **Verification:** 10 unit tests passing in `tests/unit/test_publish_gold.py`.

#### Tasks 9.5 & 9.6 — End-to-End Spark Pipeline & Run Metadata (`5ed26b9`)
- **What:** Implemented `src/acadexa/processing/pipeline.py` and `scripts/run_pipeline.py`.
- **Pipeline Orchestration (`run_pipeline`):**
  - Executes development Spark jobs in strict sequence:
    1. **J1**: Clean and Validate (`clean_and_validate`)
    2. **J2**: LMS Weekly Event Aggregation (`run_j2_event_aggregation`)
    3. **J3**: Unified Feature Table (`run_j3_feature_table`)
    4. **J4**: Correlation Analytics (`run_j4_correlation_analytics`)
    5. **J5**: Temporal Trend Detection (`run_j5_trend_detection`)
    6. **J6**: Five-Rule Risk Signals (`run_j6_risk_signals`)
    7. **J7**: Publish Gold Data & Validate (`run_j7_publish_gold`)
- **Pipeline Run Metadata Contract (`PipelineRunMetadata`):**
  - Contract fields: `manifest_version: "1.0.0"`, `run_id`, `status` (`SUCCESS`, `FAILED`, `SKIPPED`), `seed` (resolved from `generation_manifest.json` if omitted), `start_time`, `end_time`, `duration_sec`.
  - Stores complete `configuration` snapshot, `stage_outcomes` (per-stage timing, status, counts, details), `output_counts`, and `gold_validation_summary`.
  - Serialized to `data/manifests/pipeline_run_manifest.json`.
- **CLI Runner (`scripts/run_pipeline.py`):**
  - CLI flags: `--data-dir`, `--stages`, `--seed`, `--skip-mongo`, `--uri`, `--database`, `--skip-validation`, `--manifest-path`, `-v`, `-q`.
  - Prints clean ASCII summary table upon completion.
- **Execution Run Performance:**
  - Total duration: **46.47s** on local multi-core Windows machine.
  - All 7 stages SUCCESS; all 4 gold collections PASSED post-publication validation.

#### Task 9.7 — IDE Context Documentation Update
- **What:** Comprehensively updated `docs/IDE_Context.md` recording all execution history, design rationales, algorithms, data volumes, test inventory, gotchas (JVM singleton classloader, Z-score division guards), and Phase 10 resumption blueprint through Phase 9 completion.
- **Commit:** `Update - 9.7 - IDE_Context data addition`

---

## 6. Current System Architecture (as of Task 9.7)

### Complete System Pipeline Architecture
```text
┌────────────────────────────────────────────────────────────────────────┐
│                        SYNTHETIC GENERATOR                             │
│  src/acadexa/generator/                                                │
│  - orchestrator.py: run_development_generation()                        │
│  - foundation.py: GeneratorRun (deterministic child_rng streams)        │
│  - behavioral_model.py: latent traits (ability, diligence, engagement) │
│  - decliners.py: ~8% population with engagement fade & lagged marks    │
│  - quality_injection.py: controlled corruption (rules.md §12)          │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
            Raw Academic CSVs                 Raw LMS Parquet
            (data/raw/*.csv)                  (data/raw/lms_events/)
                    │                                │
                    ▼                                │
┌──────────────────────────────────────┐             │
│          MONGODB RAW LAYER           │             │
│  src/acadexa/database/               │             │
│  - client.py: MongoClient pooling    │             │
│  - collections.py: init collections  │             │
│  - loader.py: batch insert           │             │
│  - indexes.py: query indexes         │             │
│  - aggregations.py: 8 Mongo queries  │             │
│  - Raw collections + LMS slice (10k) │             │
└──────────────────────────────────────┘             │
                    │                                │
                    ▼                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     PYSPARK PROCESSING ENGINE                          │
│  src/acadexa/processing/                                               │
│  - spark_session.py: local session, Winutils fallback, JAR preloading  │
│  - mongo.py: mongo-spark-connector DataSource V2 configuration         │
│  - pipeline.py: run_pipeline orchestrator                              │
│                                                                        │
│  [JOB 1: Clean & Validate] (clean_validate.py)                         │
│  Input: data/raw/ domain files                                         │
│  Action: deduplicate, clamp marks, fix casing, drop orphans, parse ts  │
│  Output: data/processed/ (students, courses, records, attendance, etc.)│
│  Report: reports/quality/j1_quality_report.json (100% traceability)    │
│                                                                        │
│  [JOB 2: Weekly LMS Event Aggregation] (event_aggregation.py)          │
│  Input: data/processed/lms_events/                                     │
│  Action: group by (student, course, week) -> events, duration, days    │
│  Output: data/processed/lms_weekly_engagement/ (partitioned by sem)    │
│                                                                        │
│  [JOB 3: Integrated Student Feature Table] (feature_table.py)          │
│  Input: cleaned records, attendance, coursework, weekly LMS            │
│  Grain: student_id x course_id x semester_id                           │
│  Output: data/processed/student_course_features/                       │
│                                                                        │
│  [JOB 4: Correlation Analytics Engine] (analytics/correlation.py)      │
│  Input: student_course_features                                        │
│  Action: within-course Z-scores, distributed Spearman, Simpson's check │
│  Output: data/analytics/correlations.json                              │
│                                                                        │
│  [JOB 5: Temporal Trend Detection] (analytics/trends.py)               │
│  Input: student_course_features + weekly engagement                    │
│  Action: 16-week LMS slope, 50% LMS drop, 10-pt marks drop             │
│  Output: data/analytics/trend_indicators.parquet                       │
│                                                                        │
│  [JOB 6: Five-Rule Risk Signals] (analytics/risk_signals.py)           │
│  Input: features + trends                                              │
│  Action: 5 rule triggers, signal count 0-5, high risk >= 3, explain    │
│  Output: data/analytics/risk_indicators.parquet                        │
│                                                                        │
│  [JOB 7: Gold Layer Publication & Validation] (publish_gold.py)        │
│  Input: student_course_features, risk_indicators                       │
│  Output Parquet: data/gold/{student_features,course_metrics,...}       │
│  Output Mongo: acadexa.{student_features,course_metrics,...}           │
│  Validation: validation/gold.py (count, grain uniqueness, schema)      │
└────────────────────────────────────────────────────────────────────────┘
```

### Module Inventory (`src/acadexa/`)

| Package / Module | Responsibility | Status |
|---|---|---|
| `config/loader.py` | Native TOML loader + env-var parser | Done (2.1) |
| `config/validation.py` | Config schema and cross-file validation | Done (2.6) |
| `generator/foundation.py` | `GeneratorRun`, `child_rng` streams, metadata | Done (4.1) |
| `generator/university.py` | Deterministic hierarchy expansion | Done (4.2) |
| `generator/students.py` | Demographic sampling, stable student IDs | Done (4.3) |
| `generator/academic_records.py` | 6 courses/sem enrollment, component marks | Done (4.4) |
| `generator/attendance.py` | Weekly attendance counts, ability links | Done (4.5) |
| `generator/coursework.py` | Assignments, quizzes, submission timing | Done (4.6) |
| `generator/behavioral_model.py` | Latent traits (`ability`, `diligence`, `engagement`) | Done (4.7) |
| `generator/decliners.py` | ~8% decliners, attendance decay, marks drag | Done (4.8) |
| `generator/lms_events.py` | LMS event generation, temporal diurnal rhythms | Done (5.1–5.4) |
| `generator/ground_truth.py` | Ground truth registry (planted correlations) | Done (5.5) |
| `generator/quality_injection.py` | Controlled corruption of synthetic datasets | Done (5.6) |
| `generator/manifests.py` | Generation and injection manifest tracking | Done (5.7) |
| `generator/orchestrator.py` | Unified generation execution pipeline | Done (5.8) |
| `database/client.py` | MongoDB client pooling and ping validation | Done (6.1) |
| `database/collections.py` | Database collection initialization & reset | Done (6.2) |
| `database/loader.py` | Bulk loading raw data into MongoDB | Done (6.3–6.4) |
| `database/indexes.py` | Compound and single query index creation | Done (6.5) |
| `database/aggregations.py` | 8 representative MongoDB aggregation pipelines | Done (6.6) |
| `processing/spark_session.py` | PySpark session builder, Winutils fallback, JAR loader | Done (7.1, 9.5) |
| `processing/mongo.py` | Spark MongoDB connector configuration | Done (7.2) |
| `processing/jobs/clean_validate.py` | Job J1: Clean & validate, quality reporting | Done (7.3–7.4) |
| `processing/jobs/event_aggregation.py` | Job J2: Weekly LMS event aggregation | Done (7.5–7.6) |
| `processing/jobs/feature_table.py` | Job J3: Integrated student feature table | Done (8.1–8.2) |
| `processing/jobs/publish_gold.py` | Job J7: Gold collections publishing | Done (9.1–9.3) |
| `processing/pipeline.py` | Pipeline orchestrator, metadata & stage execution | Done (9.5–9.6) |
| `analytics/correlation.py` | Job J4: Spearman correlation & Simpson's paradox | Done (8.3–8.6) |
| `analytics/trends.py` | Job J5: Longitudinal LMS slopes & marks drops | Done (8.5–8.6) |
| `analytics/risk_signals.py` | Job J6: Five-rule risk evaluation & explanations | Done (8.7–8.8) |
| `validation/schema.py` | Frozen canonical schemas (raw & gold) | Done (3.1–3.7) |
| `validation/validators.py` | Boundary schema assertion functions | Done (3.8) |
| `validation/gold.py` | Post-publication gold collection validators | Done (9.4) |
| `scripts/run_pipeline.py` | CLI entry point for full pipeline execution | Done (9.5–9.6) |
| `dashboard/` | Streamlit multi-page dashboard | Phases 11–12 |

---

## 7. Calibration Numbers, Data Volumes & Quality Traceability

### Observed Development Pipeline Volumes (Run `run_20260929_052950_7a3bbe`)

| Stage | Dataset / Collection | Storage Target | Development Scale Volume |
|---|---|---|---|
| **Raw / Gen** | `students` | CSV / Parquet | 36 records |
| **Raw / Gen** | `courses` | CSV / Parquet | 72 records |
| **Raw / Gen** | `attendance` | CSV / Parquet | 13,811 records |
| **Raw / Gen** | `academic_records` | CSV / Parquet | 863 records |
| **Raw / Gen** | `coursework` | CSV / Parquet | 9,955 records |
| **Raw / Gen** | `lms_events` | Parquet (`data/raw/lms_events/`) | 225,244 records |
| **J2 Output** | `lms_weekly_engagement` | Parquet (`data/processed/`) | 13,823 summary rows |
| **J3 Output** | `student_course_features` | Parquet (`data/processed/`) | 864 feature rows |
| **J4 Output** | `correlations_evaluated` | Analytical manifest | 5 relationship pairs |
| **J5 Output** | `trend_indicators` | Parquet (`data/analytics/`) | 864 indicator rows |
| **J6 Output** | `risk_indicators` | Parquet (`data/analytics/`) | 36 student records |
| **J7 Gold** | `student_features` | MongoDB / Parquet | 144 records (Grain unique: True) |
| **J7 Gold** | `course_metrics` | MongoDB / Parquet | 279 records (Grain unique: True) |
| **J7 Gold** | `school_summary` | MongoDB / Parquet | 15 records (Grain unique: True) |
| **J7 Gold** | `risk_indicators` | MongoDB / Parquet | 36 records (Grain unique: True) |

### Pipeline Run Manifest Contract (`data/manifests/pipeline_run_manifest.json`)
The pipeline execution produces a verified JSON manifest with schema version `1.0.0`:
- **`run_id`:** Unique identifier formatted `run_YYYYMMDD_HHMMSS_<hash>`
- **`status`:** Overall outcome (`SUCCESS`)
- **`seed`:** Deterministic RNG seed (e.g. `42`)
- **`duration_sec`:** Total elapsed runtime (46.47s)
- **`configuration`:** Complete snapshot of paths, enabled stages, and flags
- **`stage_outcomes`:** Per-stage dictionary (`J1` through `J7`) recording stage name, status, start/end timestamps, elapsed duration, output record counts, and granular details
- **`gold_validation_summary`:** Post-publication validation status, row counts, and grain uniqueness confirmations

---

## 8. Test Suite Inventory (438+ Passed)

Execution: `$env:PYTHONPATH='src'; python -m pytest tests/unit -q`  
Total: **438+ unit tests passing cleanly**.

| Test File | Covered Functionality | Test Count |
|---|---|---|
| `test_smoke.py` | Test harness and environment sanity | 1 |
| `test_config_validation.py` | Config validation, all `ConfigurationError` paths | 34 |
| `test_schema_validation.py` | Frozen schemas, primary/foreign keys, null safety | 12 |
| `test_generator_foundation.py` | Deterministic seeds, SHA child streams, `GeneratorError` | 15 |
| `test_university_generation.py` | School, department, program, course catalogs | 8 |
| `test_student_generation.py` | Demographics, quota splits, unique identifiers | 10 |
| `test_academic_records_generation.py` | 6 courses/term, difficulty drag, ability shift | 14 |
| `test_attendance_generation.py` | Weekly attendance binomial draws, trait correlation | 16 |
| `test_coursework_generation.py` | Assignment/quiz items, submission timing, lateness | 18 |
| `test_behavioral_model.py` | Latent traits, zero-weight controls, Spearman validation | 25 |
| `test_decliner_population.py` | ~8% decliner rate, attendance decay, lagged marks drop | 23 |
| `test_lms_events_generation.py` | Event types, diurnal rhythms, weekly rhythms, chunking | 28 |
| `test_lms_parquet.py` | PyArrow Parquet writer, partition round-trip | 6 |
| `test_ground_truth_registry.py` | Ground truth serialization, planted relationships | 8 |
| `test_quality_injection.py` | Controlled corruption of keys, values, timestamps | 16 |
| `test_manifests.py` | Generation and injection manifest serialization | 8 |
| `test_orchestrator.py` | End-to-end dataset generation pipeline | 6 |
| `test_mongodb_connection.py` | MongoClient connection pooling, timeout fallback | 8 |
| `test_mongodb_collections.py` | Collection creation and reset | 6 |
| `test_mongodb_loader.py` | Bulk insertion, manifest count verification | 10 |
| `test_mongodb_lms_slice.py` | LMS serving slice boundary and isolation | 6 |
| `test_mongodb_indexes.py` | Query index creation and schema verification | 8 |
| `test_mongodb_aggregations.py` | 8 aggregation pipelines (`$match`, `$lookup`, etc.) | 16 |
| `test_load_mongodb_script.py` | CLI loading script orchestration | 4 |
| `test_spark_runtime.py` | Local PySpark session, Winutils fallback, config | 12 |
| `test_spark_mongo_config.py` | Spark MongoDB connector options and read helpers | 5 |
| `test_clean_validate.py` | Job J1 cleaning, quality reporting, AST driver safety | 9 |
| `test_event_aggregation.py` | Job J2 weekly aggregation, active days, AST driver safety | 7 |
| `test_feature_table.py` | Job J3 integrated feature table, derived metrics, AST safety | 22 |
| `test_correlation.py` | Job J4 Spearman correlation, Simpson's paradox, AST safety | 9 |
| `test_trends.py` | Job J5 temporal trend detection, longitudinal slopes, AST safety | 10 |
| `test_risk_signals.py` | Job J6 five-rule risk detection, explainability, AST safety | 9 |
| `test_publish_gold.py` | Job J7 gold publication, validation, MongoDB roundtrip, AST safety | 10 |
| `test_pipeline.py` | End-to-end pipeline runner, metadata manifest, CLI parsing, AST safety | 7 |

---

## 9. What Works, Deliberate Deferrals & Safety Gaps

### What Is Working & Verified
- Complete synthetic data generation across all core entities and LMS events.
- Full ground truth and data quality injection manifests with byte-exact reproducibility.
- MongoDB layer with core collections, query indexes, and analytical pipelines.
- PySpark local runtime on Windows with automated Winutils fallback and JAR preloading.
- PySpark Job J1 (Clean & Validate) with 100% traceable quality reporting.
- PySpark Job J2 (LMS Event Aggregation) producing weekly student/course engagement features.
- PySpark Job J3 (Integrated Feature Table) producing unified features at `student x course x semester` grain.
- PySpark Job J4 (Correlation Analytics) computing distributed Spearman correlations and confirming Simpson's paradox.
- PySpark Job J5 (Temporal Trend Detection) computing 16-week slopes and decline triggers.
- PySpark Job J6 (Five-Rule Risk Signals) evaluating rules, scoring risk $0 \dots 5$, and generating structured explanations.
- PySpark Job J7 (Gold Layer Publication) persisting all 4 gold collections to Parquet and live MongoDB.
- Post-publication validation layer confirming counts, grains, and schemas.
- End-to-end pipeline CLI runner `scripts/run_pipeline.py` orchestrating J1 → J7 with `pipeline_run_manifest.json`.
- Zero-driver-leakage enforcement via static AST inspection in unit tests across all processing and analytics jobs.

### Deliberate Deferrals (Do NOT Implement Ahead of Time)
- **Phase 10 (MVP Validation Gate):** End-to-end MVP integration test, ground-truth recovery comparisons, risk-rule boundary checks, generator reproducibility validation.
- **Phase 11 (Streamlit Dashboard Backend):** Data caching layer, MongoDB query abstraction, summary metrics.
- **Phase 12 (Streamlit Interactive UI):** Multi-page UI, risk overview, drill-down, filter controls, export functions.
- **Phases 13–17:** Full scale data generation, benchmarks, documentation, presentation assets.

---

## 10. Session Gotchas, Failure Modes & Lessons Learned

1. **PySpark JVM Singleton & Classloader Jar Injection:**
   - In PySpark, once a JVM process is launched by Py4J, the JVM's system classloader cannot dynamically add Maven packages or JARs.
   - If an early test (e.g. `test_clean_validate.py`) creates a SparkSession without connector JARs, later tests (e.g. `test_publish_gold.py`) will fail with `ClassNotFoundException: mongodb.DefaultSource`.
   - **Resolution:** Updated `get_or_create_spark_session()` in `src/acadexa/processing/spark_session.py` to automatically preload cached MongoDB connector JARs (`find_cached_mongo_jars()`) into `builder.config("spark.jars", ...)` when `jars` is empty, ensuring the connector is on the classpath from the very first JVM launch.
2. **PySpark `col.isin(*types)` Tuple Unpacking:**
   - In PySpark 3/4, calling `col.isin(my_tuple)` fails with `SparkRuntimeException: Literal for ArrayList`.
   - Arguments must be unpacked with `*` (`col.isin(*my_tuple)`).
3. **Semi-Joins and String Normalization:**
   - Foreign key semi-joins fail to match valid records if casing or leading/trailing whitespace differ (`stu001` vs `STU001`).
   - Normalization (`trim(upper(col(...)))`) must be applied to both the parent reference DataFrame and child DataFrame prior to joining.
4. **AST Static Analysis for Driver Safety:**
   - Tasks 7.6, 8.8, 9.4, 9.5 and rules.md §17.3 forbid driver-side `.collect()` on large datasets.
   - Using Python's `ast` module to statically inspect job files ensures compliance without relying on runtime memory profiling.
   - When writing AST tests, ensure all standard libraries (`ast`, `inspect`, `pathlib`) are explicitly imported.
5. **Division by Zero in Normalization:**
   - When calculating course-level Z-scores `(score - mean) / stddev`, single-student courses or courses where all students have the identical score result in `stddev == 0.0` or `null`.
   - Guarded via `F.when(col("stddev") > 0, (col("score") - col("mean")) / col("stddev")).otherwise(0.0)`.
6. **Grain Uniqueness Verification:**
   - A critical post-publication check is verifying that the composite primary key has zero duplicates.
   - Implemented efficiently via `df.groupBy(grain_cols).count().filter("count > 1").count() == 0`, avoiding any driver-side data collection.

---

## 11. Resumption Blueprint: Phase 10 (MVP Validation Gate)

When resuming at Phase 10, the prompt will request: `Proceed with task <TASK_10.1> from docs/TASKS.md only.`

### Tasks in Phase 10 Overview

#### Task 10.1 — End-to-End MVP Pipeline Test
- **Goal:** Add end-to-end integration test covering generation → Parquet/MongoDB → Spark (J1–J7) → gold collections using a small fixture/development dataset.
- **Target File:** `tests/integration/test_mvp_pipeline.py`
- **Target Commit:** `Update - 10.1 - add end-to-end MVP pipeline test`

#### Task 10.2 — Ground Truth Recovery Comparison
- **Goal:** Implement automated verification comparing recovered correlations and planted relationships from `ground_truth_registry.json`.
- **Target Checks:**
  - Verify attendance-performance correlation is strongly positive ($r > 0.40$).
  - Verify late submission correlation is negative ($r < -0.20$).
  - Verify forum post correlation in aggregate differs significantly from school-stratified correlations (Simpson's paradox recovery).
- **Target Commit:** `Update - 10.2 - implement ground truth recovery test`

#### Task 10.3 — Validate Risk Signal Boundaries
- **Goal:** Validate that risk-rule boundary cases behave deterministically and correctly:
  - 75% attendance boundary (e.g. 74.9% triggers flag; 75.0% does not).
  - 50% LMS drop boundary.
  - 30% late submission boundary.
  - 10-point marks decline boundary.
- **Target Commit:** `Update - 10.3 - validate risk signal boundaries`

#### Task 10.4 — Generator & Pipeline Reproducibility
- **Goal:** Validate reproducibility by running the same development configuration and seed twice, comparing deterministic outputs, record counts, and manifest checksums.
- **Target Commit:** `Update - 10.4 - verify generator reproducibility`

---

## 12. Quick Command Reference

```powershell
# Run complete unit test suite
$env:PYTHONPATH='d:\College\Secondary\Projects\acadexa\src'; python -m pytest tests/unit -q

# Run all Phase 8 & Phase 9 pipeline tests
$env:PYTHONPATH='d:\College\Secondary\Projects\acadexa\src'; python -m pytest tests/unit/test_feature_table.py tests/unit/test_correlation.py tests/unit/test_trends.py tests/unit/test_risk_signals.py tests/unit/test_publish_gold.py tests/unit/test_pipeline.py -v

# Execute end-to-end development Spark processing pipeline
python scripts/run_pipeline.py

# Execute pipeline with custom flags
python scripts/run_pipeline.py --data-dir data --seed 42 --skip-mongo -v

# Generate synthetic development dataset
python scripts/generate_data.py

# Load raw collections and LMS slice into MongoDB
python scripts/load_mongodb.py

# Run the Streamlit dashboard (PYTHONPATH=src required)
$env:PYTHONPATH='src'; streamlit run src/acadexa/dashboard/app.py
# → http://localhost:8501 · demo login: admin / cet.admin / faculty.csa / analyst (no password)

# Run J8 benchmarks (raw manifest + JSON/Markdown report beside it)
$env:PYTHONPATH='src'; python scripts/run_benchmarks.py --engine pandas
$env:PYTHONPATH='src'; python scripts/run_benchmarks.py --workload feature_table_join --engine mongodb
$env:PYTHONPATH='src'; python scripts/run_benchmarks.py --report-only --manifest-path <manifest>.json

# Full-scale generation lives under data/fullscale/ (gitignored except .gitkeep);
# committed stage records live under data/manifests/full_scale_*.json

# Inspect Git status (Agent must NEVER commit)
git status --short
git diff --stat
git log --oneline -n 15
```

---
## 13. Session Record: Tasks 10.1 → 14.4 (2026-09-29 → 2026-10-01 chat)

One continuous IDE session implemented Phases 10 (MVP Validation Gate), 11 (Dashboard Foundation), 12 (Dashboard Views), 13 (Benchmarking) and 14.1–14.4 (Full-Scale Generation start). Standing user instructions for the whole session: work only the requested task(s); stop when done and report ready-to-commit (agent never runs `git commit`); keep `docs/tasks.md` checkboxes updated as tasks complete; commit message format `Update - <Phase>.<Task> - <description>`; user reviews diffs and commits manually. Multi-task turns were explicitly requested by the user each time (11.1–11.3, 11.4/11.5, 13.1/13.2, 13.3/13.4, 13.5/13.6, 14.1/14.2, 14.3/14.4). Total added: ≈190 unit/integration tests, 7 dashboard pages, J8 harness + 6 engine workloads, full-scale core data. Every turn ended with the full affected suite green.

### Phase 10 — MVP Validation Gate (all five tasks)

#### Task 10.1 — End-to-end MVP pipeline test
- **Goal:** generation → Parquet/MongoDB → Spark J1–J7 → gold collections on a tiny fixture.
- **Files:** `tests/integration/test_mvp_pipeline.py` (new).
- **Decisions:** parquet-only pipeline (`publish_to_mongo=False`) so the gate never depends on a live database; separate MongoDB round-trip test that skips when unreachable (established repo convention).
- **Verify:** integration file green; `git status` showed only the new file.

#### Task 10.2 — Ground-truth recovery comparison
- **Goal:** compare planted relationships vs recovered analytics plus the decoy relationship.
- **Files:** `src/acadexa/validation/recovery.py` (new; `RecoveryEntry`/`RecoveryReport`, fixed ±0.10 thresholds aligned with `interpret_spearman_association`, `compare_ground_truth_recovery`, `evaluate_recovery_from_paths`), `src/acadexa/validation/__init__.py` (exports), `tests/unit/test_recovery.py` (10 tests).
- **Decisions:** recovery reads the registry file but never mutates expectations; `spearman_normalized` preferred with `spearman_raw` fallback; statuses `recovered` / `not_recovered` / `correctly_no_association` / `spurious_association` / `not_evaluated`; non-causal language enforced by test.
- **Verify:** 10 passed (incl. small Spark end-to-end marking planted signals recovered).

#### Task 10.3 — Risk-signal boundary validation
- **Goal:** positive/negative/boundary behavior for all five rule-based signals from configuration (not hard-coded): 75% attendance, 50% LMS ratio, 30% late rate, 10-point marks drop, bottom-quartile quiz.
- **Files:** `tests/unit/test_risk_boundaries.py` (6 tests; thresholds via `RiskSignalThresholds.from_config()`), plus a zero prior-activity denominator guard.
- **Verify:** 6 passed; existing `test_risk_signals.py` 5 passed (no regression).

#### Task 10.4 — Generator reproducibility
- **Goal:** same seed/config twice ⇒ identical datasets and manifests (volatile timestamps/durations/paths excluded from comparison).
- **Files:** `tests/unit/test_generator_reproducibility.py` (1 test: core JSON exact equality, LMS Parquet payload equality, ground-truth + generation/injection manifest equality).
- **Verify:** passed in ~28s.

#### Task 10.5 — MVP resource baseline (smoke, no optimization)
- **Goal:** measured dev-scale runtime/memory observations with generous anti-hang guards only.
- **Files:** `tests/integration/test_mvp_resource_baseline.py` (generation + full J1→J7 pipeline, per-stage durations from pipeline metadata, per-dir disk usage, Python RSS via optional psutil with JVM caveat documented, JSON report to tmp + printed summary, measured baseline table in the docstring labeled informational).
- **Measured (Windows 11, Python 3.11.9, PySpark local[2]/1g, 12 students, seed 42):** generation ~12s (66,587 LMS events, deterministic across runs); pipeline ~110–160s wall (J1 dominates ~39–55s); total ~120–175s; disk ~6.2 MB deterministic; Python RSS ~120 → ~136 → ~158 MB.
- **Verify:** passed twice (wall time varies naturally; counts/disk/RSS deterministic).

### Phase 11 — Streamlit Dashboard Foundation

- **Setup:** `pip install streamlit` → **1.64.0** (already declared in `requirements.txt`, so no manifest change). Headless UI testing via `streamlit.testing.v1.AppTest` throughout.
- **11.1–11.3** — `config/dashboard/dummy_users.toml` (4 users, exactly the 4 approved roles with scoped assignments); `dashboard/config.py` (`DashboardConfig`: title, env-driven MongoDB, gold/operational collections); `data_access.py` (`DashboardDataAccess`: bounded reads, `(records, error)` failure contract, never fabricated values); `auth.py` (role constants, `User`, fail-fast dummy-user loading, passwordless `authenticate`); `session.py` (dict-based login/logout over one key, works with `st.session_state` and plain dicts); `permissions.py` (central `ROLE_CAPABILITIES` per features.md §20, `resolve_scope`, `can`, `build_mongo_scope_filter`, `describe_scope`); `app.py` (login screen + authenticated shell). Tests: `test_dashboard_foundation.py`, 19 passed. Real `streamlit run --server.headless` boot verified.
- **11.4–11.5** — `dashboard/layout.py` (NAV_ITEMS in design.md §8 order, role-gated `visible_nav_items`, breadcrumbs with › separator, scope-aware global filters with year/semester options from tracked `academic_periods.toml`, header/sidebar/filter render helpers); `dashboard/components.py` (KPI/analytical/status/risk-signal/empty/error components per design §47–§48; "Data unavailable" never renders as zero; out-of-contract inputs fail fast). Tests: `test_dashboard_layout_components.py`, started at 24.
- **Standing rule discovered:** existing-test contracts (login title, first subheader) are preserved across shell redesigns; AppTest element access is by `key=` (lists have no `len()`); script-run exceptions surface as `at.exception[0].message` element lists.

### Phase 12 — Dashboard Views (12.1 → 12.8)

One module per page under `src/acadexa/dashboard/pages/` (three layers each: scoped `fetch_*` → pure `compute_*` → Streamlit `render_*_page`), dispatched from `app.py` by nav key. All pages read actual gold/serving data only; empty/error states follow design §30/§31; association-not-causation notes everywhere (rules.md §20).

- **12.1 University Overview** (`pages/university.py`, 13 tests): six F-E01 KPIs, school comparison (no composite best-school score, design §15), academic-vs-engagement scatter, trend summary, risk summary.
- **12.2 School/Department** (`pages/school.py`, 12 tests): data-driven school picker, scoped KPIs, coursework behavior from gold late rates, department/course breakdowns, trends, risk distribution. Aggregation math reused from the overview module (single canonical implementation).
- **12.3 Course** (`pages/course.py`, 17 tests): catalogue-first metadata with metric fallback, enrollment (max across semesters), coursework math, difficulty-adjusted performance, trend mix, enrolled-student risk counts. Fixed one stale notice ("arrive in" → "appear in" the Student view) in 12.7.
- **12.4 Student** (`pages/student.py`, 12 tests): profile, per-course academics, attendance derived from raw counts with zero-denominator guard, coursework items, LMS by-activity, latest-semester trend, latest-week risk via shared `risk_signal_card` (reused, not reimplemented). Faculty scope joins via enrollment records.
- **12.5 Analysis** (`pages/analysis.py`, 17 tests): J4/J5 outputs live only in Parquet and are not MongoDB-served, so the page derives serving-scale analytics from bounded gold reads (documented design decision): pure-Python Spearman with tie averaging, interpretation boundaries pinned equal to canonical `analytics.correlation` by test, recovery via `validation.recovery.compare_ground_truth_recovery` against the tracked registry (quiz/decoy/confounder honestly `not_evaluated`); methodology section states raw-gold (not within-course normalized) provenance.
- **12.6 Data Quality** (`pages/data_quality.py`, 9 tests): tracked J1 report → pipeline-wide totals, per-category Healthy/Attention/Issue table (design §25–§26), per-dataset outcomes, methodology note (detected counts are measured output, not injected counts restated).
- **12.7 Disclosures** (4 tests appended to layout/components suite): gap analysis showed per-section methodology notes already complete, so only the global design §38 disclosure was added (`SYNTHETIC_DATA_NOTICE` + `synthetic_data_notice()` in login screen and sidebar footer, persistent but non-dominating).
- **12.8 Usability/accessibility/error-state pass** (`tests/unit/test_dashboard_usability_pass.py`, 2 tests): role×page matrix (4 roles × all visible pages, 19 visits — all green, all widgets labeled, no duplicate widget IDs); rendered-text microcopy guard (causal/predictive language only in negated methodology form). **One real find fixed:** Analysis tables mixed floats with `"—"` strings, causing pyarrow Arrow-conversion tracebacks — coefficients now render as fixed-precision strings via extracted pure row builders.
- **Suite totals observed:** 56 (12.2) → 85 (12.3) → 97 (12.4) → 114 (12.5) → 123 (12.6) → 127 (12.7) → 129 (12.8), always fully green. Live dev data in MongoDB during this session: 36 students, 72 courses, 864 academic records, 13,824 attendance, 9,964 coursework, 22,357 LMS events, gold 3/4/2/3. Dashboard verified viewable at `http://localhost:8501` (`$env:PYTHONPATH='src'; streamlit run src/acadexa/dashboard/app.py`).

### Phase 13 — Benchmarking (J8; rules.md §30: measured, never manufactured, no conclusions)

- **13.1 Harness** (`benchmarks/runner.py`, 9 tests): `WorkloadDefinition` registry, `BenchmarkResult` (duration/rows/optional peak/success/error), `BenchmarkRun` manifest save/load, `capture_environment`, `run_timed` (tracemalloc peak documented as Python-allocator only), `run_benchmark` (failures recorded, never raised).
- **13.2 pandas weekly engagement** (`benchmarks/pandas/weekly_engagement.py`, 7 tests): J2-equivalent grain/metrics (Monday weeks, semester bounds, positive-only durations, active days, category roll-ups) with category/bounds imported from the J2 module (canonical, no drift); timed read+aggregate. Measured on dev data: 227,662 events → 14,048 rows in ~45s, ~103 MB peak.
- **13.3 MongoDB weekly engagement** (`benchmarks/mongodb/weekly_engagement.py`, 8 tests): `$match`/`$project`/`$group`/`$sort` pipeline over the event shape (works on regular and time-series collections); fixed `$date`→`$toDate` bug found by tests. Measured: 22,357 events → 1,170 rows in ~0.85s.
- **13.4 PySpark weekly engagement** (`benchmarks/spark/weekly_engagement.py`, 3 tests): runs the canonical J2 job itself (same code path, not a reimplementation) to scratch output; memory measurement off with driver memory recorded instead.
- **13.5 Feature-table join** (workload registry + three engines): pandas outer join of four cleaned domains (`pandas/feature_join.py`); MongoDB left join of the three operational collections it holds (`mongodb/feature_join.py`, coursework semester derived from due dates exactly as J3 does — tests caught the first version missing this); Spark runs real J3 (`spark/feature_join.py`). Per-engine scope differences recorded in result extras by design ("where equivalent implementations are practical"). Measured: pandas 38,452 → 864 rows in ~0.3s; MongoDB 864 → 864 in ~2.2s.
- **13.6 Result publication** (`benchmarks/report.py`): structured + Markdown output (dataset size, timing, memory with explicit n/a, environment, per-engine scope caveats, explicit no-conclusions statement — tests assert winner-language is absent); CLI auto-writes report files beside the manifest plus `--report-only` regeneration. `scripts/run_benchmarks.py` wired for all workloads/engines (`--base-path`, `--collection`, `--output-path`, `--no-report`).
- **Full benchmark suite:** 43 passed across 7 files. `reports/benchmarks/` is gitignored (run outputs stay uncommitted).

### Phase 14 — Full-Scale Generation (14.1 → 14.4 done; 14.5/14.6 running)

- **14.1 Freeze** (`generator/full_scale.py`, 6 tests): frozen constants (seed 42; 12,000 students with exact six-school split 2600/3000/2400/2200/1000/800; 250 courses; 6 courses/student/semester; 70M LMS events; 6 schools/18 depts/40 programs; S1–S4 × 16 weeks over AY1–AY2; 8% decliners; 11 event types; six injection rates) plus `validate_full_scale_config()` mismatch reporting. No schema/architecture change. Tests caught an order-sensitive school-ID comparison in the module.
- **14.2 Hierarchy** (5 tests + committed `data/manifests/full_scale_hierarchy.json`): full-target run recorded 6 schools, 18 departments, 40 programs, 72-course configured catalog (against the 250 target), per-school breakdowns reconciling to totals.
- **14.3/14.4 Core data:** new `generate_dataset(..., generate_lms_events=False)` flag (previously even "skip writing" still generated all ~70M events just to count them) plus a scale-label fix (config-scale runs now record `"full"`). Full run into ignored `data/fullscale/` (`.gitignore` extended, dev data untouched) took **837.25s**: **12,000 students, 72 courses, 288,000 academic records (exactly 72,000 × S1–S4), 4,608,000 attendance (exactly 1,152,000 × S1–S4), 3,338,810 coursework (~2 GB on disk)**. School split matches frozen population exactly. Short week-groups trace to the 4,608 injected attendance orphans (≈0.1% frozen rate) — expected pre-cleaning footprint for Phase 15, verified against the injection manifest.
- **Committed stage records:** `data/manifests/full_scale_students.json` (14.3) and `data/manifests/full_scale_attendance_coursework.json` (14.4); `tests/unit/test_full_scale_generation.py` asserts exact values (3 tests); orchestrator skip-flag test added to `test_orchestrator.py`.
- **Regression at 14.4:** freeze/hierarchy/manifests/config suites 54 passed; orchestrator+generation 9 passed.

### Session conventions discovered (persist these)
- PowerShell 5.1 only: no `&&`/`sed`/`grep`/`head`; use `Select-Object`, `Get-Process`/`Get-CimInstance`, `workdir` param instead of `cd`; LF→CRLF warnings on edited files are benign.
- `pytest.ini` sets `pythonpath = src .`; tests import `scripts.*` directly; MongoDB live tests skip when unreachable; Spark tests share one module-scoped local session.
- One-off drivers/scripts live in `$env:TEMP`, never in the repo (a stray repo-root driver was caught and removed in 14.3/14.4).
- `data/manifests/*.json` are committed stage records; everything else generated stays ignored (`data/fullscale/` added for full-scale outputs).
- pytestsurvey: keep new-test value assertions exact and deterministic; mark known live-data dependencies explicitly (dev-DB markers like `## 3 / 5`, `MGT101` follow the established convention).

*End of Section 13. Sections 14–15 record live/in-progress state as of 2026-10-01.*

---

## 14. LIVE STATE: Full LMS Generation Running (Tasks 14.5/14.6) — READ FIRST

> **Do NOT kill PID 3104.** It is the detached full-scale LMS run (started 2026-10-01 16:10:35). Killing it discards hours of compute; the 14.3/14.4 core files are only rewritten at the very end, so an accidental kill leaves them intact but wastes the run.

### What is running and why
- **Command (already launched, do not relaunch):** `python -u <TEMP>/run_full_lms_tmp.py <repo>` → `generate_dataset(target_students=None, data_dir="data/fullscale/")` with all defaults (seed 42, LMS stream ON, quality injection ON).
- **Why a full re-run, not LMS-only:** the orchestrator passes *clean* (pre-injection) records/coursework into the LMS stream and threads one RNG stream through core+LMS injection, so only a full run reproduces exact orchestrated semantics (RNG order, first-chunk min-injections, coherent manifests). Core regen (~14 min) is cheap relative to the LMS stream.
- **Expected output:** ~70M events (≈12,000 × 15/day × 200 days/yr × 2 yrs ≈ 72M) as year/month-partitioned Parquet under `data/fullscale/raw/lms_events/` (~2–3 GB per architecture estimates); manifests refresh under `data/fullscale/manifests/`.

### How to monitor (short commands only — long sleeps get killed)
```powershell
Get-Process -Id 3104 -ErrorAction SilentlyContinue | Select-Object Id, CPU
Test-Path -LiteralPath "data/fullscale/raw/lms_events"
Get-ChildItem -Path "data/fullscale/raw/lms_events" -Recurse -Filter "*.parquet" | Measure-Object | Select-Object Count
Get-Content (Join-Path $env:TEMP "full_lms_run.log")
Get-Content (Join-Path $env:TEMP "full_lms_run.err.log") | Select-Object -Last 5
```
- No `raw/lms_events` dir yet = still in core regen/injection (normal for the first ~15–30 min under machine load; verify liveness via CPU delta, not wall time). Parquet part files accumulating = LMS streaming in progress. `DONE` + JSON summary in the log = finished.
- **Shell quirk discovered:** shells that `Start-Process` the file named `run_full_lms_tmp.py` were killed (`ChildProcess.kill`); the identical script renamed (e.g. `driver_hello.py`) launches fine, and an early duplicate launch died on its own leaving exactly one writer (verified via `Win32_Process` command lines + output inspection). If relaunching ever becomes necessary, use a fresh filename and confirm a single writer before proceeding.

### Finish checklist (in order — this is the 14.5/14.6 task work)
1. Wait for `DONE` in `$env:TEMP/full_lms_run.log`; record `actual_counts.lms_events`, `disk_usage_bytes`, `duration_sec`.
2. Sanity-check the Parquet dataset (row count vs manifest, readable sample, partition layout).
3. Write committed `data/manifests/full_scale_lms.json` (Temp helper `build_lms_manifest_tmp.py` exists — same shape as the 14.3/14.4 records: version/task/seed/target/actual/disk/duration/note).
4. Run the slice load: `python <TEMP>/load_full_slice_tmp.py <repo>` (uses `load_lms_serving_slice` → S4 + CET/SOM from `data/fullscale/raw/lms_events` into MongoDB `acadexa.lms_events`, clearing the 22k dev slice; ~7M docs expected). Writes committed `data/manifests/full_scale_lms_slice.json` itself.
5. Add `tests/unit/test_full_scale_lms.py` asserting exact committed values (counts, S4/CET/SOM spec, scanned ≥ selected, selected == inserted == db count) + slice-spec unit coverage if missing.
6. Run the affected suites (new file + manifests/config/freeze/hierarchy + a dashboard smoke subset), mark `docs/tasks.md` 14.5/14.6 `[x]`, report ready-to-commit (`Update - 14.5 - generate full LMS Parquet dataset`, `Update - 14.6 - generate full LMS serving slice`).
7. Do NOT start Phase 15 (full-scale Spark pipeline) — separate task.

## 15. Resumption Blueprint: Finish Phase 14 → Phase 15

- **If PID 3104 is gone and `DONE` is in the log:** continue at finish checklist step 2 above.
- **If PID 3104 is gone with no `DONE` and no usable output:** relaunch with a fresh TEMP filename (see quirk above), then continue monitoring.
- **If 14.5/14.6 are committed:** next is Phase 15 (full-scale Spark pipeline J1→J7 over `data/fullscale/`, tasks 15.1–15.8), then Phase 16 validation and Phase 17 final documentation. Uncommitted prompt pattern will be: `Proceed with task <TASK_15.x> from docs/TASKS.md only.`
- **Standing rules that still apply:** one task (or explicitly bundled set) at a time; agent never commits; keep `docs/tasks.md` checked as work completes; TEMP-only drivers; no output under `data/` except via ignored dirs + committed `data/manifests/*.json` records; dashboard reads MongoDB gold, never raw Parquet.

*End of IDE Context. This document serves as the official project state record through Task 14.4, with Tasks 14.5/14.6 in progress as described in Sections 14–15.*

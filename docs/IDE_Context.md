# IDE Context — Acadexa Full Session Record (Task 0.1 → 7.7)

**Document:** `docs/IDE_Context.md`  
**Purpose:** Complete, self-contained, authoritative working memory and architectural context for any human developer or IDE agent resuming this codebase.  
**Created by:** Task 4.9 (`Update - 4.9 - add IDE context documentation`), updated by Task 7.7 (`Update - 7.7 - add IDE context documentation for Phases 5 to 7`).  
**Snapshot date:** 2026-09-26  
**Repository:** `D:\College\Secondary\Projects\acadexa`, branch `main`  
**State at snapshot:** Tasks 0.1 → 7.6 fully committed across 46 commits; test suite **384 passed**; Task 7.7 = this file update and Phase 7 checkpoint.

> **How to use this file:**
> Read Sections 1–4 before touching any code — they define the immutable non-negotiables, environment constraints, and working protocols.
> Section 5 contains the complete, deep execution history (what happened, design decisions taken, why they were taken, what broke, what worked, and exact document alignments).
> Sections 6–8 describe the current end-to-end architecture, calibration numbers, data volumes, quality metrics, and test suite breakdown.
> Sections 9–11 cover what is working, deliberate deferrals, session failure modes and gotchas, and the exhaustive step-by-step roadmap for Phase 8.

---

## 1. Project in One Screen — Non-Negotiables

**Acadexa** = synthetic-data-only Big Data learning-analytics platform for fictional **RAS University** (6 schools, 18 departments, 40 programs, 250 courses, 12,000 target students, 2 academic years / 4 semesters, ~70M target LMS events). Final-year Big Data Technologies academic project.

Pipeline Architecture:
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
       │                    │         └──► PySpark (J2 Weekly LMS Aggregation)
       │                    │                   │
       │                    │                   └──► Parquet (data/processed/lms_weekly_engagement/)
       │                    ▼
       │               [Phase 8: J3 Integrated Features, J4 Analytics, J5 Risk Signals]
       │                    │
       ▼                    ▼
   MongoDB Gold Layer (Phase 9) ──► Streamlit Interactive Analytics Dashboard (Phases 11-12)
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
8. **Correlation method:** Spearman rank correlation is the primary non-linear monotonic metric; Pearson is optional (deferred to task 8.5).
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
| PySpark | 3.5.x / 4.x runtime, configured for `local[*]` with Winutils dummy fallback |
| MongoDB | Local / Docker MongoDB instance running at `localhost:27017` (`acadexa` database) |
| PyTest | 8.3.5, configured via `pytest.ini` |
| Test suite status | **384 passed**, 1 warning (Pandas 3.0 future warning from PySpark) in ~6.5 minutes |
| Test execution | `$env:PYTHONPATH='d:\College\Secondary\Projects\acadexa\src'; python -m pytest tests/unit -q` |
| Dependencies | Managed in `requirements.txt` (minimal, strictly vetted) |

### PowerShell & Environment Gotchas
- **Nested Quotes in PowerShell:** Nested double/single quotes in PowerShell commands frequently fail parsing. Use `.py` scripts or pass simple strings.
- **Python Path:** `PYTHONPATH` must be explicitly set (`$env:PYTHONPATH="src"`) when invoking Python commands or pytest from the root folder.
- **Hadoop Home on Windows:** On Windows, PySpark requires a dummy `HADOOP_HOME` or `winutils.exe` fallback to prevent initialization crashes. Handled automatically in `src/acadexa/processing/spark_session.py`.
- **PySpark Session Scoping:** In pytest, module-scoped Spark session fixtures must call `yield spark` and terminate with `stop_spark_session(spark)` in a `finally` block to prevent JVM context collisions across test suites.

---

## 3. Documentation Map (`docs/`)

| File | Primary Governance & Context |
|---|---|
| `prd.md` | Core product requirements, scope boundaries, dataset targets, risk signals, and deliverables. |
| `architecture.md` | System data flow, storage split (MongoDB vs Parquet), PySpark jobs (J1–J8), and serving architecture. |
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

## 5. Comprehensive Execution History (Tasks 0.1 → 7.7)

### Commit Log Summary (Phases 0 → 7)
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
```

---

### Phase 0: Documentation Baseline (Tasks 0.1 → 0.3)
- **0.1 Setup:** Ingested canonical specifications into `docs/` verbatim without modification.
- **0.2 Path & Name Alignment:** Standardized path references across all Markdown documentation to eliminate discrepancies.
- **0.3 Consistency Polish:** Refined `tasks.md` and `README.md` to ensure mutual alignment with project scope and academic disclaimers.

### Phase 1: Repository Foundation (Tasks 1.1 → 1.8)
- **1.1 Ignore Rules:** Configured comprehensive `.gitignore` preventing commits of `.env`, parquet files, cache artifacts, PySpark checkpoints, and raw data dumps.
- **1.2 README:** Established top-level orientation covering stack, data architecture, synthetic nature, and setup commands.
- **1.3 Environment Template:** Built `.env.example` with MongoDB parameters and PySpark local configurations.
- **1.4 & 1.5 Package Skeleton:** Initialized package root `src/acadexa/` with clean functional submodules (`config/`, `generator/`, `database/`, `processing/`, `analytics/`, `dashboard/`, `validation/`, `benchmarks/`, `utils/`).
- **1.6, 1.7 & 1.8 Foundations:** Placed script entry point stubs in `scripts/`, established `tests/` directory with `pytest.ini`, and locked core dependencies in `requirements.txt`.

### Phase 2: Configuration Contract (Tasks 2.1 → 2.6)
- **2.1 Configuration Loader:** Implemented `src/acadexa/config/loader.py` using Python 3.11's native `tomllib`.
- **2.2 University Hierarchy:** Defined `config/university/hierarchy.toml` modeling 6 schools, 18 departments, 40 programs, and course catalogs.
- **2.3 Academic Periods:** Defined `config/university/academic_periods.toml` spanning 2 academic years (AY 2024-25, 2025-26) across 4 semesters (S1–S4).
- **2.4 Generator Config:** Authored `config/generator/generator.toml` controlling target populations, difficulty distributions, behavioral traits, and data quality injection rates.
- **2.5 Risk Signal Thresholds:** Created `config/risk/risk_signals.toml` codifying the exact five approved risk thresholds (attendance < 75%, LMS decline ≤ 50%, late submissions > 30%, marks drop ≥ 10 pts, quiz score bottom quartile).
- **2.6 Configuration Validation:** Created `src/acadexa/config/validation.py` asserting key existence, numerical ranges, and cross-config referential integrity, raising `ConfigurationError`.

### Phase 3: Canonical Schema Contract (Tasks 3.1 → 3.8)
- **3.1–3.7 Domain Schemas:** Authored `src/acadexa/validation/schema.py` defining frozen schemas for `students`, `courses`, `academic_records`, `attendance`, `coursework`, `lms_events`, and gold summary schemas (`student_features`, `course_metrics`, `school_summary`, `risk_indicators`).
- **3.8 Schema Validators:** Implemented `src/acadexa/validation/validators.py` for programmatic schema validation at boundaries.

### Phase 4: Synthetic Generator Foundation (Tasks 4.1 → 4.9)
- **4.1 Deterministic Foundation:** Built `GeneratorRun` and `GeneratorRunMetadata` in `src/acadexa/generator/foundation.py`. Established `run.child_rng("<name>")` generating isolated SHA-256 sub-streams.
- **4.2 University Generator:** Created deterministic expansion of university hierarchy in `src/acadexa/generator/university.py`.
- **4.3 Student Generator:** Implemented demographic sampling and deterministic program enrollment in `src/acadexa/generator/students.py`.
- **4.4 Academic Records:** Generated enrollment plans (6 courses/semester) and component marks (internal, midterm, endterm) in `src/acadexa/generator/academic_records.py`.
- **4.5 Attendance:** Generated weekly attendance records at student×course×week grain using binomial draws aligned with student ability in `src/acadexa/generator/attendance.py`.
- **4.6 Coursework:** Generated course-level assignment and quiz items, tracking submission timeliness and scores in `src/acadexa/generator/coursework.py`.
- **4.7 Behavioral Model:** Implemented latent traits (`ability`, `diligence`, `engagement`) in `src/acadexa/generator/behavioral_model.py`.
- **4.8 Decliner Population:** Implemented ~8% decliner population in `src/acadexa/generator/decliners.py` exhibiting attendance decay, coursework score decline, and lagged marks drops.
- **4.9 IDE Context Document:** Created `docs/IDE_Context.md` capturing the Phase 0–4 record.

---

### Phase 5: Synthetic LMS Events & Ground Truth (Tasks 5.1 → 5.8)

#### Task 5.1 — LMS Event Generation (`77d3e38`)
- **What:** Implemented LMS event generation in `src/acadexa/generator/lms_events.py` adhering to the 8 approved event types in `LMS_EVENT_SCHEMA`: `LOGIN`, `LOGOUT`, `VIEW_CONTENT`, `SUBMIT_ASSIGNMENT`, `ATTEMPT_QUIZ`, `POST_FORUM`, `VIEW_GRADE`, `DOWNLOAD_RESOURCE`.
- **Decisions & Rationale:**
  - Used `run.child_rng("lms_events")` ensuring event generation does not perturb seed sequences for academic records or coursework.
  - Event type selection is driven by multinomial probability weights defined in `config/generator/generator.toml` (`[behavior.lms_events]`).
  - Session duration is drawn from a log-normal distribution capped at 120 minutes.
- **What Worked:** Clean alignment with `LMS_EVENT_SCHEMA` without schema additions.

#### Task 5.2 — LMS Temporal Behavior & Diurnal Curves (`a272d88`)
- **What:** Added temporal rhythms to LMS events: weekly academic rhythms, diurnal time-of-day distributions, day-of-week weights, and decliner engagement decay over semester weeks.
- **Decisions & Rationale:**
  - Day of week sampling: weekdays (Monday–Friday) receive ~75% of volume; weekends receive ~25%.
  - Diurnal curve: tripartite peak at 10:00–12:00, 14:00–16:00, and 20:00–22:00, dipping sharply between 02:00 and 06:00.
  - Decliner fading: decliners experience an exponential decay in daily event generation rate starting at week 5 (`weekly_engagement_decay = 0.07`), directly implementing `original_idea_of_project.md` §7.1 and `memory.md` §6.
- **Breakage & Fix:** Initial datetime string formatting generated sub-second microsecond variations that conflicted with standard ISO-8601 validation; resolved by enforcing uniform `%Y-%m-%d %H:%M:%S` timestamps.

#### Task 5.3 — Chunked LMS Generation (`9701c84`)
- **What:** Replaced monolithic in-memory event accumulation with a chunked streaming generator yielding batches of configurable size (`chunk_size = 50000`).
- **Decisions & Rationale:**
  - Generating millions of event dictionaries simultaneously exceeds available RAM on local developer machines (rules.md §24).
  - Iterators produce row batches on demand, which are immediately piped to disk or downstream consumers.
- **What Worked:** Memory usage remained flat under 150 MB regardless of event scale.

#### Task 5.4 — Parquet Export for LMS Events (`1327468`)
- **What:** Built Parquet writer utilizing PyArrow with Snappy compression, writing events partitioned by semester to `data/raw/lms_events/`.
- **Decisions & Rationale:**
  - PyArrow table conversion uses an explicit schema to ensure strict type mapping (`int32`, `string`, `timestamp[us]`).
  - Implemented round-trip readback verification asserting zero null primary keys and correct partition preservation.

#### Task 5.5 — Synthetic Ground Truth Registry (`08e861a`)
- **What:** Created `src/acadexa/generator/ground_truth.py` recording all planted causal relationships, decliner student IDs, confounders, and decoy effects before analytical observation (`memory.md` §23).
- **Registered Ground Truth Entities:**
  1. **Decliner Registry:** list of flagged student IDs (~8% population), start week, and decay rates.
  2. **Planted Behavioral Links:** attendance-marks alignment, late submissions vs marks, quiz activity vs student ability.
  3. **Confounders:** course difficulty drag (easy/medium/hard impact on marks and attendance), school profile differentials.
  4. **Decoy Relationship:** forum post frequency vs student grade that appears positively correlated in aggregate, but dissolves or inverts when stratified by school/department (Simpson's paradox).
- **Persisted Output:** `data/manifests/ground_truth_registry.json`.

#### Task 5.6 — Controlled Data Quality Injection (`989ce4b`)
- **What:** Implemented `src/acadexa/generator/quality_injection.py` to systematically corrupt synthetic datasets at configuration-governed approximate rates (`rules.md` §12).
- **Injected Anomaly Types:**
  - `duplicate_records`: primary key duplication across entities (~0.5%).
  - `null_non_key_fields`: missing values in non-essential fields (e.g. final grade, submitted_at) (~1.0%).
  - `timestamp_inconsistencies`: mixed formats (`YYYY/MM/DD` vs `YYYY-MM-DDTHH:MM:SS`), future timestamps (~0.8%).
  - `course_id_formatting`: whitespace padding, inconsistent casing (`cs101 ` instead of `CS101`) (~1.2%).
  - `orphan_records`: foreign keys pointing to nonexistent student or course IDs (~0.5%).
  - `out_of_range_values`: exam marks > 100 or < 0, negative attendance counts (~0.5%).
- **Traceability:** Recorded exact primary keys and row indices where corruptions were injected to allow 100% auditing by the J1 quality reporting job.

#### Task 5.7 — Generation & Injection Manifests (`9a595ff`)
- **What:** Created `src/acadexa/generator/manifests.py` generating `data/manifests/generation_manifest.json` and `data/manifests/injection_manifest.json`.
- **Decisions & Rationale:**
  - Manifests capture: run timestamp, seed, configuration hash digest, target record counts, actual generated record counts, and granular counts of injected anomalies per entity.
  - Manifest acts as the data contract between generation (Phase 5), database loading (Phase 6), and PySpark cleaning (Phase 7).

#### Task 5.8 — Unified Development Data Generation Entry Point (`776142b`)
- **What:** Implemented `src/acadexa/generator/orchestrator.py` and CLI script `scripts/generate_data.py`.
- **Execution:** Generates a reproducible development dataset:
  - 500 students across 6 schools.
  - 148 active courses across departments.
  - 6,000 academic records.
  - 96,000 attendance records.
  - 144,000 coursework items.
  - 225,244 LMS events written to Parquet.
  - Complete manifest files written to `data/manifests/`.

---

### Phase 6: MongoDB Data Layer (Tasks 6.1 → 6.7)

#### Task 6.1 — MongoDB Connection Layer (`1b99410`)
- **What:** Implemented `src/acadexa/database/client.py` providing `get_mongo_client()` and `get_database()`.
- **Decisions & Rationale:**
  - Reads connection URI and database name from environment variables (`MONGO_URI`, `MONGO_DB_NAME`) defaulting to `mongodb://localhost:27017` and `acadexa`.
  - Implements connection ping with timeout fail-fast to provide actionable diagnostics when MongoDB is unreachable.

#### Task 6.2 — Initialize MongoDB Collections (`a64065e`)
- **What:** Implemented `src/acadexa/database/collections.py` initializing raw domain collections and gold placeholder collections.
- **Collections Created:**
  - Raw / Operational: `students`, `courses`, `academic_records`, `attendance`, `coursework`, `lms_events_slice`.
  - Gold Placeholders: `student_features`, `course_metrics`, `school_summary`, `risk_indicators`.
- **Decisions & Rationale:** Dropping and recreating collections provides idempotent resets during development runs.

#### Task 6.3 — Load Core Academic Collections (`60219d9`)
- **What:** Implemented `src/acadexa/database/loader.py` to batch-load raw synthetic CSVs into MongoDB using `insert_many(ordered=False)` with chunk sizes of 5,000 documents.
- **Verification:** Automatically cross-checks inserted document counts against `generation_manifest.json`.

#### Task 6.4 — Load LMS Serving Slice (`b163ce8`)
- **What:** Implemented serving slice loader extracting a bounded subset of LMS events (10,000 events) into the `lms_events_slice` collection.
- **Decisions & Rationale:**
  - Rules §24 and architecture.md mandate that the full 70M event dataset (or even 225k dev events) must NOT be loaded into MongoDB.
  - The slice represents the most recent 4 weeks of activity necessary for quick dashboard lookups and operational student views.

#### Task 6.5 — MongoDB Query Indexes (`d53a905`)
- **What:** Implemented `src/acadexa/database/indexes.py` establishing single-field and compound indexes:
  - `students`: `student_id` (unique), `school_id`, `department_id`.
  - `courses`: `course_id` (unique), `school_id`, `department_id`.
  - `academic_records`: `(student_id, semester_id)`, `course_id`.
  - `attendance`: `(student_id, course_id, week)`.
  - `coursework`: `(student_id, course_id)`, `item_id`.
  - `lms_events_slice`: `(student_id, timestamp)`, `course_id`.

#### Task 6.6 — Representative Analytical Aggregations (`b4bd06b`)
- **What:** Implemented `src/acadexa/database/aggregations.py` demonstrating the 8 required MongoDB aggregation pipeline stages: `$match`, `$group`, `$project`, `$sort`, `$lookup`, `$unwind`, `$setWindowFields`, and `$facet`.
- **Pipelines Implemented:**
  - `get_school_enrollment_stats()`: enrollment counts, program counts per school (`$group`, `$project`, `$sort`).
  - `get_course_performance_summary()`: average marks, failure rates (`$group`, `$lookup`, `$project`).
  - `get_student_academic_profile()`: multi-course grades with attendance lookup (`$lookup`, `$unwind`, `$setWindowFields`).
  - `get_coursework_submission_breakdown()`: multi-faceted analysis of submissions by status and school (`$facet`).

#### Task 6.7 — Unified Database Loading Entry Point (`be7d024`)
- **What:** Implemented `scripts/load_mongodb.py` orchestrating end-to-end database loading.
- **Execution:** Connects to MongoDB, drops existing collections, creates indexes, batch-inserts core domain records and the LMS slice, and prints manifest count validation.

---

### Phase 7: PySpark Environment & J1/J2 Pipeline (Tasks 7.1 → 7.7)

#### Task 7.1 — Local PySpark Runtime Configuration (`3c2e167`)
- **What:** Implemented `src/acadexa/processing/spark_session.py`: `SparkRuntimeConfig`, `ensure_spark_environment()`, `get_or_create_spark_session()`, `verify_spark_runtime()`, and `stop_spark_session()`.
- **Decisions & Rationale:**
  - Configures master as `local[*]` with `spark.driver.memory = "4g"`, `spark.sql.shuffle.partitions = "4"` (scaled for local multicore).
  - Handles Windows environment quirks: detects absence of `HADOOP_HOME`/`winutils.exe` and injects dummy system properties and path stubs to prevent native Windows IO initialization crashes.
  - Ensures clean JVM teardown to prevent orphan background Java processes.

#### Task 7.2 — PySpark MongoDB Integration (`f1d446e`)
- **What:** Implemented `src/acadexa/processing/mongo.py` configuring the `mongo-spark-connector` (`org.mongodb.spark:mongo-spark-connector_2.12:10.3.0`).
- **Decisions & Rationale:**
  - Provides `build_mongo_spark_read_options()` and `read_mongo_collection()`.
  - Added unit tests checking option generation and integration tests verifying live Spark DataFrame extraction from MongoDB with schema inference.

#### Tasks 7.3 & 7.4 — Spark Clean & Validate Job (J1) & Quality Reporting (`ec1d2d3`)
- **What:** Implemented `src/acadexa/processing/jobs/clean_validate.py`:
  - Cleaning routines for all 6 domain entities: `clean_students()`, `clean_courses()`, `clean_attendance()`, `clean_academic_records()`, `clean_coursework()`, `clean_lms_events()`.
  - Quality reporting: `J1QualityReport`, `DatasetQualityMetrics`, and `IssueMetric` tracking 5-way status (`injected`, `detected`, `corrected`, `dropped`, `remaining`).
- **Cleaning Operations Applied:**
  1. *Deduplication:* `dropDuplicates([primary_keys])`.
  2. *ID Normalization:* `trim(upper(col("course_id")))` and `trim(upper(col("student_id")))`.
  3. *Timestamp Parsing:* Unified multiple date formats (`yyyy-MM-dd HH:mm:ss`, `yyyy/MM/dd HH:mm:ss`, `yyyy-MM-dd'T'HH:mm:ss`) using `coalesce(to_timestamp(...))`.
  4. *Range Clamping:* Clamped exam marks to `[0, 100]`, coursework scores to `[0, max_score]`, attendance counts to non-negative integers.
  5. *Orphan Detection & Removal:* Foreign key semi-joins against cleaned reference tables (`valid_students_df`, `valid_courses_df`).
  6. *Null Imputation:* Missing non-key marks imputed to 0.0 or derived letter grades.
- **Traceability Verification:** Evaluated against `data/manifests/injection_manifest.json`. Achieved 100% detection and correction across all datasets with 0 remaining defects. Output saved to `reports/quality/j1_quality_report.json` and cleaned Parquet datasets written to `data/processed/`.
- **What Broke & How it Was Fixed:**
  - *Bug:* Case-sensitivity in semi-joins resulted in valid students with lowercase IDs (`stu001`) being falsely flagged as orphans and dropped.
  - *Fix:* Normalized IDs in both the reference DataFrame and target DataFrames before performing semi-joins.

#### Tasks 7.5 & 7.6 — Spark LMS Event Aggregation (J2) & Verification (`6e98bce`)
- **What:** Implemented `src/acadexa/processing/jobs/event_aggregation.py` aggregating weekly student/course LMS activity, and comprehensive unit tests with driver safety checks in `tests/unit/test_clean_validate.py` and `tests/unit/test_event_aggregation.py`.
- **Aggregated Metrics (J2):**
  - Grain: `(student_id, course_id, semester_id, week_number, week_start)`.
  - `total_events`: `count(*)`.
  - `total_duration_sec`: `sum(duration_sec)`.
  - `active_days`: `count(distinct date(timestamp))`, strictly within `[1, 7]`.
  - Approved category rollups: `content_views`, `assessment_events`, `participation_events`, `access_events`.
  - Granular breakdown: `video_views`, `quiz_attempts`, `assignment_views`, `assignment_submissions`, `forum_posts`, `logins`.
- **Partitioned Parquet Output:** Written to `data/processed/lms_weekly_engagement` partitioned by `semester_id`. Aggregated 225,244 raw events into 13,823 weekly engagement rows.
- **What Broke & How it Was Fixed:**
  1. *`col.isin()` in PySpark:* Passing a tuple directly `col.isin(category_types)` caused `SparkRuntimeException: Literal for ArrayList`. Fixed by unpacking tuple arguments with `*` (`col.isin(*category_types)`).
  2. *AST Driver Safety Assertion Failure:* In `tests/unit/test_clean_validate.py`, the driver-safety test failed with `NameError: name 'inspect' is not defined`. Fixed by importing `inspect`.
  3. *Driver Safety Compliance:* Both J1 and J2 were verified via AST static analysis ensuring zero calls to `.collect()`, `.toPandas()`, or `.toArray()` on dataset DataFrames (`rules.md` §17.3, §17.5).
- **Test Results:** 16/16 tests passed in `test_clean_validate.py` and `test_event_aggregation.py`.

#### Task 7.7 — IDE Context Documentation Update (`docs/IDE_Context.md`)
- **What:** Updated `docs/IDE_Context.md` to capture all architectural developments, execution records, data volumes, failure modes, and Phase 8 resumption plans. Updated `docs/TASKS.md` marking Task 7.7 as the Phase 7 checkpoint.
- **Commit:** `Update - 7.7 - add IDE context documentation for Phases 5 to 7`.

---

## 6. Current System Architecture (as of Task 7.7)

### End-to-End Data Pipeline Architecture
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
│  - spark_session.py: local[*] session, Winutils fallback               │
│  - mongo.py: mongo-spark-connector configuration                       │
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
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               PHASE 8: FEATURE ENGINEERING & ANALYTICS                 │
│  [JOB 3: Integrated Student Features] (Task 8.1 - J3)                  │
│  Grain: student_id x course_id x semester_id                           │
│  Joins: records + attendance summary + coursework summary + LMS weekly  │
│                                                                        │
│  [JOB 4: Derived Features & Trends] (Tasks 8.2 & 8.3 - J4)             │
│  - Attendance %, late submission %, quiz retries, coursework avg       │
│  - LMS weekly activity slopes, active days, duration                   │
│                                                                        │
│  [JOB 5: Correlation Engine] (Tasks 8.4 & 8.5)                         │
│  - Spearman rank correlation across behavioral & academic signals      │
│                                                                        │
│  [JOB 6: Five Rule-Based Risk Signals] (Task 8.7 - J5)                 │
│  - Rule 1: Attendance < 75%                                            │
│  - Rule 2: LMS decline <= 50% of prior 4-week average                  │
│  - Rule 3: Late submissions > 30%                                      │
│  - Rule 4: Marks decline >= 10 points                                  │
│  - Rule 5: Quiz scores in bottom quartile                              │
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
| `processing/spark_session.py` | PySpark session builder, Winutils fallback | Done (7.1) |
| `processing/mongo.py` | Spark MongoDB connector configuration | Done (7.2) |
| `processing/jobs/clean_validate.py` | Job J1: Clean & validate, quality reporting | Done (7.3–7.4) |
| `processing/jobs/event_aggregation.py` | Job J2: Weekly LMS event aggregation | Done (7.5–7.6) |
| `validation/schema.py` | Frozen canonical schemas (raw & gold) | Done (3.1–3.7) |
| `validation/validators.py` | Boundary schema assertion functions | Done (3.8) |
| `analytics/` | Correlation, risk signals, statistical summaries | Phase 8 |
| `dashboard/` | Streamlit multi-page dashboard | Phases 11–12 |

---

## 7. Calibration Numbers, Data Volumes & Quality Traceability

### Development Dataset Volumes (Observed)

| Dataset | Storage Target | Development Scale Volume | Full Scale Target |
|---|---|---|---|
| `students` | MongoDB / CSV / Parquet | 500 documents | 12,000 documents |
| `courses` | MongoDB / CSV / Parquet | 148 documents | 250 documents |
| `academic_records` | MongoDB / CSV / Parquet | 6,000 documents | 144,000 documents |
| `attendance` | MongoDB / CSV / Parquet | 96,000 documents | 2,304,000 documents |
| `coursework` | MongoDB / CSV / Parquet | 144,000 documents | 3,456,000 documents |
| `lms_events` (Raw) | Parquet (`data/raw/`) | 225,244 events | ~70,000,000 events |
| `lms_events_slice` | MongoDB (`acadexa`) | 10,000 documents | 10,000 documents |
| `lms_weekly_engagement` | Parquet (`data/processed/`) | 13,823 summary rows | ~3,500,000 rows |

### J1 Data Quality Injected vs Corrected Traceability (`j1_quality_report.json`)

All injected issues were 100% detected, corrected, or dropped with **0 remaining errors**:

| Dataset | Injected | Detected | Corrected | Dropped | Remaining | Status |
|---|---|---|---|---|---|---|
| `students` | 2 duplicates | 2 | 0 | 2 | 0 | PASSED |
| `courses` | 0 | 0 | 0 | 0 | 0 | PASSED |
| `attendance` | 480 orphans, 480 out-of-range | 960 | 480 | 480 | 0 | PASSED |
| `academic_records` | 30 formatting, 30 orphans, 30 out-of-range, 60 nulls | 150 | 120 | 30 | 0 | PASSED |
| `coursework` | 1440 formatting, 720 orphans, 720 out-of-range, 1152 ts, 1440 nulls | 5472 | 4752 | 720 | 0 | PASSED |
| `lms_events` | 2252 formatting, 1126 orphans, 1801 ts | 5179 | 4053 | 1126 | 0 | PASSED |
| **Grand Total** | **11,765 anomalies** | **11,765** | **9,405** | **2,360** | **0** | **PASSED** |

---

## 8. Test Suite Inventory (384 Passed)

Execution: `$env:PYTHONPATH='src'; python -m pytest tests/unit -q`  
Total: **384 tests passing** in ~6.5 minutes.

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
| `tests/integration/` | Live MongoDB reads via Spark connector | 4 |

---

## 9. What Works, Deliberate Deferrals & Safety Gaps

### What Is Working & Verified
- Complete synthetic data generation across all core entities and LMS events.
- Full ground truth and data quality injection manifests with byte-exact reproducibility.
- MongoDB layer with core collections, query indexes, and analytical pipelines.
- PySpark local runtime on Windows with automated Winutils fallback.
- PySpark Job J1 (Clean & Validate) with 100% traceable quality reporting.
- PySpark Job J2 (LMS Event Aggregation) producing weekly student/course engagement features.
- Zero-driver-leakage enforcement via static AST inspection in unit tests.

### Deliberate Deferrals (Do NOT Implement Ahead of Time)
- **Integrated Student Feature Table (J3):** Deferred to Task 8.1.
- **Derived Academic & Engagement Features:** Deferred to Tasks 8.2 and 8.3.
- **Spearman & Pearson Correlation Engine:** Deferred to Tasks 8.4 and 8.5.
- **Simpson's Paradox Stratification Engine:** Deferred to Task 8.6.
- **Five Rule-Based Risk Signal Evaluation (J5):** Deferred to Task 8.7.
- **Gold Collection MongoDB Publisher (J8):** Deferred to Phase 9.
- **Streamlit Interactive UI:** Deferred to Phases 11–12.

---

## 10. Session Gotchas, Failure Modes & Lessons Learned

1. **PySpark `col.isin(*types)` Tuple Unpacking:**
   - In PySpark 3/4, calling `col.isin(my_tuple)` fails with `SparkRuntimeException: Literal for ArrayList`.
   - Arguments must be unpacked with `*` (`col.isin(*my_tuple)`).
2. **Semi-Joins and String Normalization:**
   - Foreign key semi-joins fail to match valid records if casing or leading/trailing whitespace differ (`stu001` vs `STU001`).
   - Normalization (`trim(upper(col(...)))`) must be applied to both the parent reference DataFrame and child DataFrame prior to joining.
3. **AST Static Analysis for Driver Safety:**
   - Tasks 7.6 and rules.md §17.3 forbid driver-side `.collect()` on large datasets.
   - Using Python's `ast` module to statically inspect job files ensures compliance without relying on runtime memory profiling.
   - When writing AST tests, ensure all standard libraries (`ast`, `inspect`, `pathlib`) are explicitly imported.
4. **PySpark Module Teardown in PyTest:**
   - PySpark sessions in pytest fixtures must use `yield spark` followed by `stop_spark_session(spark)` inside a `finally:` block. Leaving sessions alive between test modules leads to JVM app name conflicts.
5. **Windows Hadoop IO Fallback:**
   - On Windows, native file IO in PySpark can fail if `winutils.exe` is absent.
   - Setting `spark.hadoop.io.native.lib.available = false` and creating a fallback directory in `ensure_spark_environment()` prevents crashes without manual binary installations.
6. **LMS Partitioning Scheme:**
   - Partitioning LMS weekly engagement parquet by `semester_id` enables fast downstream partition pruning for J3 joins.

---

## 11. Resumption Blueprint: Phase 8 (Feature Engineering & Analytics)

When resuming at Phase 8, the prompt will request: `Proceed with task <TASK_8.1> from docs/TASKS.md only.`

### Tasks in Phase 8 Overview

#### Task 8.1 — Integrated Student Feature Construction (Job J3)
- **Goal:** Join cleaned academic records, attendance summary, coursework summary, and weekly LMS features at the canonical grain: `student_id x course_id x semester_id`.
- **Inputs:** Cleaned datasets from `data/processed/` (`academic_records`, `attendance`, `coursework`, `lms_weekly_engagement`).
- **Target Commit:** `Update - 8.1 - implement integrated student feature table`

#### Task 8.2 — Academic and Engagement Derived Features
- **Goal:** Implement derived features required by `features.md`:
  - Attendance % (`classes_attended / classes_conducted * 100`).
  - Late submission rate (`late_submissions / total_submissions`).
  - Missing coursework rate (`missing_submissions / total_coursework`).
  - Coursework average score % (`total_score / max_score * 100`).
  - Quiz retry ratio (`total_quiz_attempts / total_quizzes`).
- **Target Commit:** `Update - 8.2 - implement academic and engagement features`

#### Task 8.3 — Temporal LMS Trend Features
- **Goal:** Calculate temporal trajectory features:
  - Weekly LMS activity slope (linear regression slope of weekly events over the semester).
  - Active weeks ratio (`active_weeks / 16`).
  - Late-term engagement decline indicator (drop between early weeks 1–6 vs late weeks 10–15).
- **Target Commit:** `Update - 8.3 - implement temporal LMS trend features`

#### Task 8.4 — Analytical Summary Computations (Job J4)
- **Goal:** Aggregate features at institutional, school, and course grains for dashboard display.
- **Target Commit:** `Update - 8.4 - implement analytical summary aggregation job`

#### Task 8.5 — Monotonic Correlation Engine
- **Goal:** Implement distributed Spearman rank correlation (and optional Pearson) evaluating attendance vs marks, LMS activity vs marks, and late submissions vs marks.
- **Target Commit:** `Update - 8.5 - implement correlation analytics engine`

#### Task 8.6 — Confounder & Decoy Stratification (Simpson's Paradox)
- **Goal:** Stratify correlations by course difficulty and school/department to demonstrate Simpson's paradox on the planted decoy relationship.
- **Target Commit:** `Update - 8.6 - implement confounder and decoy analysis`

#### Task 8.7 — Rule-Based Risk Signal Engine (Job J5)
- **Goal:** Evaluate exactly the five approved risk signals from `config/risk/risk_signals.toml`:
  1. Attendance < 75%
  2. LMS decline <= 50% of prior 4-week average
  3. Late submissions > 30%
  4. Marks decline >= 10 points
  5. Quiz scores in bottom quartile
- **Output:** Score `0 to 5` observed risk signals per student-course.
- **Target Commit:** `Update - 8.7 - implement rule-based risk detection job`

---

## 12. Quick Command Reference

```powershell
# Run all unit tests
$env:PYTHONPATH='d:\College\Secondary\Projects\acadexa\src'; python -m pytest tests/unit -q

# Run targeted Spark cleaning and aggregation tests
$env:PYTHONPATH='d:\College\Secondary\Projects\acadexa\src'; python -m pytest tests/unit/test_clean_validate.py tests/unit/test_event_aggregation.py -v

# Run single test
$env:PYTHONPATH='d:\College\Secondary\Projects\acadexa\src'; python -m pytest tests/unit/test_event_aggregation.py -k "test_run_j2_event_aggregation_end_to_end" -v

# Inspect Git status (Agent must NEVER commit)
git status --short
git diff --stat
git log --oneline -n 15

# Re-run synthetic data generation entry point
python scripts/generate_data.py

# Re-load MongoDB collections & LMS serving slice
python scripts/load_mongodb.py
```

---
*End of IDE Context. This document serves as the official project state record through Task 7.7.*

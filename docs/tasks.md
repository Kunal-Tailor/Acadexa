# TASKS.md — Acadexa Implementation Plan

## How to use this file

- Work **one task at a time**, top to bottom, phase by phase.
- Each task below is sized to be **one IDE execution + one reviewable commit**.
- Do not start a task until the previous task is committed and, where applicable, its validation check passes.
- Do not jump ahead to later tasks "while you're at it."
- Do not scaffold implementation for future tasks unless the current task explicitly requires it.
- When a task is complete, stop. Do not self-advance to the next task.
- The user reviews the diff and performs the Git commit manually.
- Check tasks as `[x]` only after the implementation has actually been reviewed/completed.
- If a task is discovered to be too large, split it into smaller tasks **before starting it** rather than bundling multiple commits.
- Generated large datasets must never be committed to Git.
- The MVP is a hard gate: **one school + one semester must work end-to-end before full-scale generation begins.**

### Task execution prompt

Use this pattern when asking an IDE agent to implement a task:

```text
Proceed with task <TASK_ID> from docs/TASKS.md only.

Rules still apply:
1. Only this task — nothing from later tasks, even if it seems convenient to bundle in.
2. When done, stop and tell me it's ready to commit. Do not run git commit yourself — I'll review the diff and commit it using the message format specified in TASKS.md.
3. Don't scaffold anything for future tasks in advance.
4. Don't self-advance to the next task after this one.
5. Use the docs/ directory to contextually understand the project requirements, architecture, rules, design and constraints.
```

### Commit message format

```text
Update - <Phase>.<Task> - <description>
```

Example:

```text
Update - 1.1 - Update - 0.1 - Project Folder Setup
```

---

# Phase 0 — Project Documentation Baseline

This phase establishes the documentation source of truth before implementation begins.

The detailed project documents already exist conceptually and should be present in the repository before implementation work starts.

- [x] 0.1 — Add the finalized `docs/` documentation set to the repository: `prd.md`, `architecture.md`, `tech_stack.md`, `features.md`, `rules.md`, `design.md`, `tasks.md`, `memory.md`, and `folder_structure.md`. Do not modify their content in this task.
  Commit: `Update - 0.1 - Project Folder Setup`

- [x] 0.2 — Review the documentation set for internal consistency only; fix only obvious path/name references required for the repository to match the documented structure. Do not introduce new architecture or features.
  Commit: `Update - 0.2 - docs folder setup`

- [x] 0.3 — Updated the tasks & readme files, for project betterment.
  Commit: `Update - 0.3 - tasks & readme file update`

**Checkpoint:** The repository contains the complete documentation source of truth. No application implementation has started yet.

---

# Phase 1 — Repository Foundation

## Goal

Create the actual repository skeleton without implementing application logic.

- [x] 1.1 — Initialize/verify Git repository and create the root `.gitignore` covering Python environments, IDE files, `.env`, logs, generated data, Parquet output, caches, Spark artifacts and other local/generated files defined by the project rules.
  Commit: `Update - 1.1 - initialize repository ignore rules`

- [x] 1.2 — Add the root `README.md` containing project overview, architecture summary, technology stack, target scale, setup outline, repository structure, scope boundaries and academic synthetic-data disclaimer. Keep detailed requirements in `docs/`.
  Commit: `Update - 1.2 - add project README`

- [x] 1.3 — Add `.env.example` with only safe configuration placeholders for MongoDB and local application settings. Do not add real credentials.
  Commit: `Update - 1.3 - add environment configuration template`

- [x] 1.4 — Create the complete repository folder structure from `docs/folder_structure.md`, using only required placeholder files such as `.gitkeep` or `__init__.py`. No business logic.
  Commit: `Update - 1.4 - create repository folder structure`

- [x] 1.5 — Create the Python package skeleton under `src/acadexa/` with package initialization files and empty module boundaries for config, generator, database, processing, analytics, dashboard, validation, benchmarks and utils. No implementation logic.
  Commit: `Update - 1.5 - create Python package skeleton`

- [x] 1.6 — Create the script entry-point placeholders under `scripts/`: `generate_data.py`, `load_mongodb.py`, `run_pipeline.py`, `publish_gold.py`, and `run_benchmarks.py`. Each should contain only a minimal executable entry point or TODO, not future implementation.
  Commit: `Update - 1.6 - create pipeline entry points`

- [x] 1.7 — Create the initial test structure under `tests/` and add a minimal test configuration so the test runner executes successfully with no application tests yet.
  Commit: `Update - 1.7 - initialize test structure`

- [x] 1.8 — Add the initial dependency configuration (`requirements.txt` or `pyproject.toml`) containing only the foundational runtime/development dependencies required at this stage. Do not add speculative libraries.
  Commit: `Update - 1.8 - add initial Python dependencies`

**Checkpoint:** Repository structure, documentation, environment template, Python package skeleton and test runner exist. No functional application logic exists.

---

# Phase 2 — Configuration Contract

## Goal

Build the configuration layer before data generation or database implementation depends on hard-coded values.

- [x] 2.1 — Implement configuration loading under `src/acadexa/config/` so application configuration can be read from project configuration files and environment variables without hard-coding secrets.
  Commit: `Update - 2.1 - implement configuration loading`

- [x] 2.2 — Create the RAS University hierarchy configuration: six schools, departments, programs and the initial course catalog structure. Keep hierarchy data configuration-driven rather than embedding it in generator logic.
  Commit: `Update - 2.2 - define university hierarchy configuration`

- [x] 2.3 — Create academic-period configuration for two academic years and four semesters, including identifiers and dates required by the generator.
  Commit: `Update - 2.3 - define academic period configuration`

- [x] 2.4 — Create generator configuration containing seed, target population, generation scale, behavioral parameters, course difficulty settings and data-quality injection rates.
  Commit: `Update - 2.4 - define synthetic generator configuration`

- [x] 2.5 — Create risk configuration containing the five approved thresholds/rules only: attendance, LMS decline, late submissions, marks decline and quiz bottom-quartile activity.
  Commit: `Update - 2.5 - define risk signal configuration`

- [x] 2.6 — Add configuration validation and tests for required fields, valid ranges and incompatible configuration values. Do not generate data yet.
  Commit: `Update - 2.6 - validate project configuration`

**Checkpoint:** All project-level values needed by generation, analytics and risk logic are configuration-driven.

---

# Phase 3 — Schema Contract

## Goal

Freeze the data contract before implementing the generator.

- [x] 3.1 — Define the canonical schema for `students`, including identifiers, hierarchy references and required student attributes.
  Commit: `Update - 3.1 - define student schema`

- [x] 3.2 — Define the canonical schema for `courses`, including hierarchy references, semester applicability and course-difficulty metadata.
  Commit: `Update - 3.2 - define course schema`

- [x] 3.3 — Define the canonical schema for `academic_records`, preserving the student × course × semester grain.
  Commit: `Update - 3.3 - define academic record schema`

- [x] 3.4 — Define the canonical schema for `attendance`, preserving the student × course × week grain and raw attended/conducted counts.
  Commit: `Update - 3.4 - define attendance schema`

- [x] 3.5 — Define the canonical schema for `coursework`, including assignments, quizzes, submission status/timing and student/course relationships.
  Commit: `Update - 3.5 - define coursework schema`

- [x] 3.6 — Define the canonical LMS event schema and allowed event types, timestamps, identifiers and course/student references.
  Commit: `Update - 3.6 - define LMS event schema`

- [x] 3.7 — Define the gold schemas for `student_features`, `course_metrics`, `school_summary` and `risk_indicators`.
  Commit: `Update - 3.7 - define gold collection schemas`

- [x] 3.8 — Add schema validation utilities/tests that verify required fields, data types, identifier formats and expected record grain using small fixtures.
  Commit: `Update - 3.8 - add schema validation layer`

**Checkpoint:** The generator, MongoDB layer, Spark jobs and dashboard can all reference a stable documented schema.

---

# Phase 4 — Synthetic Generator Foundation

## Goal

Build a reproducible generator before attempting the full dataset.

- [x] 4.1 — Implement deterministic seed handling and generator run metadata. Given the same seed/configuration, the generator must initialize reproducibly.
  Commit: `Update - 4.1 - implement deterministic generator foundation`

- [x] 4.2 — Implement generation of the university hierarchy from configuration: schools, departments, programs and courses.
  Commit: `Update - 4.2 - generate university hierarchy`

- [x] 4.3 — Implement synthetic student generation with stable IDs and valid hierarchy assignments.
  Commit: `Update - 4.3 - generate synthetic students`

- [x] 4.4 — Implement synthetic academic-record generation for student/course/semester combinations, including course difficulty and performance behavior.
  Commit: `Update - 4.4 - generate academic records`

- [x] 4.5 — Implement synthetic attendance generation using conducted/attended counts and weekly behavior.
  Commit: `Update - 4.5 - generate attendance data`

- [x] 4.6 — Implement synthetic coursework generation for assignments and quizzes, including submission timing, late submissions and attempts.
  Commit: `Update - 4.6 - generate coursework data`

- [x] 4.7 — Implement the synthetic behavioral model: ability, diligence, engagement, course difficulty and controlled student-level variation.
  Commit: `Update - 4.7 - implement synthetic behavioral model`

- [x] 4.8 — Implement the approximately 8% decliner population and make its behavior reproducible from the generator configuration.
  Commit: `Update - 4.8 - implement synthetic decliner population`

- [x] 4.9 — Create `docs/IDE_Context.md` containing the complete session context: every executed task from 0.1 to 4.8 with decisions and rationale, calibration data, environment conventions, working rules and the state of the project, so any developer or IDE agent can resume work without re-deriving context. Documentation only — no code changes.
  Commit: `Update - 4.9 - add IDE context documentation`

---

# Phase 5 — Synthetic LMS Generation & Ground Truth

## Goal

Build the large event generator and analytical ground truth without yet scaling to the full target.

- [x] 5.1 — Implement LMS event-type generation using only the approved event types and configuration-driven distributions.
  Commit: `Update - 5.1 - implement LMS event generation`

- [x] 5.2 — Implement timestamp generation with weekly and semester rhythms while preserving valid student/course/semester context.
  Commit: `Update - 5.2 - implement LMS temporal behavior`

- [x] 5.3 — Implement chunked LMS generation so large event volumes are written incrementally instead of accumulated in driver/Python memory.
  Commit: `Update - 5.3 - implement chunked LMS generation`

- [x] 5.4 — Implement Parquet output for LMS events with a small development-scale dataset only. Validate that it can be read back successfully.
  Commit: `Update - 5.4 - write development LMS data to Parquet`

- [x] 5.5 — Implement the ground-truth registry describing planted relationships, decliner behavior and the decoy relationship. Ground truth must be generated before analytical results are observed.
  Commit: `Update - 5.5 - implement synthetic ground truth registry`

- [x] 5.6 — Implement controlled data-quality injection for duplicates, selected nulls, timestamp inconsistencies, course-ID formatting, orphan records and out-of-range values using the approved approximate rates.
  Commit: `Update - 5.6 - implement data quality injection`

- [x] 5.7 — Implement the generation/injection manifest recording seed, configuration, target counts, actual counts and injected issue counts.
  Commit: `Update - 5.7 - implement generation manifests`

- [x] 5.8 — Implement `scripts/generate_data.py` as the single development-scale generator entry point and verify that a small dataset can be generated from a clean configuration.
  Commit: `Update - 5.8 - wire development data generation entry point`

**Checkpoint:** A reproducible small synthetic dataset exists, including all core entities, LMS events, planted relationships and controlled quality issues.

---

# Phase 6 — MongoDB Data Layer

## Goal

Make the generated development dataset queryable in MongoDB.

- [x] 6.1 — Implement MongoDB configuration/connection handling with credentials coming from environment configuration.
  Commit: `Update - 6.1 - implement MongoDB connection layer`

- [x] 6.2 — Implement database initialization for the core collections and gold collection placeholders. Do not populate gold data yet.
  Commit: `Update - 6.2 - initialize MongoDB collections`

- [x] 6.3 — Implement loading of `students`, `courses`, `academic_records`, `attendance` and `coursework` into MongoDB with validation of inserted counts.
  Commit: `Update - 6.3 - load core academic collections`

- [x] 6.4 — Implement loading of the defined development LMS serving slice into MongoDB. Keep the full LMS Parquet dataset outside MongoDB.
  Commit: `Update - 6.4 - load LMS serving slice`

- [x] 6.5 — Add indexes based on documented query patterns for student, course, semester, hierarchy and LMS access.
  Commit: `Update - 6.5 - add MongoDB query indexes`

- [x] 6.6 — Implement representative MongoDB aggregation demonstrations required by the project: `$match`, `$group`, `$project`, `$sort`, `$lookup`, `$unwind`, `$setWindowFields` and `$facet` where applicable.
  Commit: `Update - 6.6 - implement MongoDB analytical aggregations`

- [x] 6.7 — Implement `scripts/load_mongodb.py` as the reproducible development database-loading entry point and verify counts against generated manifests.
  Commit: `Update - 6.7 - wire MongoDB loading entry point`

**Checkpoint:** Development data is stored in the intended MongoDB/Parquet split and representative MongoDB operations work.

---

# Phase 7 — PySpark Environment & J1/J2

## Goal

Establish Spark processing and the first two pipeline jobs.

- [x] 7.1 — Configure PySpark local mode and verify Spark can start within the documented local environment.
  Commit: `Update - 7.1 - configure local PySpark runtime`

- [x] 7.2 — Configure the MongoDB Spark integration and verify a small development collection can be read into a Spark DataFrame.
  Commit: `Update - 7.2 - configure Spark MongoDB integration`

- [x] 7.3 — Implement J1 clean/validate for the development dataset: duplicates, null handling, ID normalization, timestamp issues, orphan detection and range validation.
  Commit: `Update - 7.3 - implement Spark clean and validate job`

- [x] 7.4 — Implement J1 quality reporting so injected/detected/corrected/dropped/remaining counts are measurable.
  Commit: `Update - 7.4 - add Spark data quality reporting`

- [x] 7.5 — Implement J2 event aggregation for weekly student/course LMS activity, active days and approved activity categories.
  Commit: `Update - 7.5 - implement Spark LMS aggregation job`

- [x] 7.6 — Add unit/integration tests for J1 and J2 using small fixtures; explicitly verify no large `collect()` or unnecessary driver-side iteration is introduced.
  Commit: `Update - 7.6 - test Spark cleaning and event aggregation`

- [x] 7.7 — Update `docs/IDE_Context.md` containing the complete session context: every executed task from 5.1 to 7.6 with decisions and rationale, data volumes, calibration data, failure modes and solutions, and instructions for Phase 8 resumption. Documentation only — no code changes.
  Commit: `Update - 7.7 - add IDE context documentation for Phases 5 to 7`

**Checkpoint:** Raw development data can be cleaned and transformed through the first Spark stages.

---

# Phase 8 — Feature Engineering & Analytics

## Goal

Build the analytical core from validated Spark outputs.

- [x] 8.1 — Implement J3 integrated student feature construction by joining academic records, attendance, coursework and LMS features at the documented grain.
  Commit: `Update - 8.1 - implement integrated student feature table`

- [x] 8.2 — Implement attendance, coursework, LMS and academic derived features required by the feature contract.
  Commit: `Update - 8.2 - implement academic and engagement features`

- [x] 8.3 — Implement within-course normalization required for cross-factor analysis.
  Commit: `Update - 8.3 - implement within-course normalization`

- [x] 8.4 — Implement J4 Spearman correlation analysis for the approved planted relationships and the decoy relationship.
  Commit: `Update - 8.4 - implement correlation analytics`

- [x] 8.5 — Add optional Pearson correlation output without replacing Spearman as the default method.
  Commit: `Update - 8.5 - add optional Pearson analysis`

- [x] 8.6 — Implement J5 four-week trend detection for LMS engagement and marks where applicable.
  Commit: `Update - 8.6 - implement temporal trend detection`

- [x] 8.7 — Implement J6 attendance, LMS decline, late-submission, marks-decline and quiz-activity risk signals exactly from configuration.
  Commit: `Update - 8.7 - implement five-rule risk signals`

- [x] 8.8 — Add explainability fields to risk outputs so each triggered signal can be traced to its underlying metric/value.
  Commit: `Update - 8.8 - add risk signal explanations`

**Checkpoint:** The development dataset produces integrated features, associations, trends and the five-rule signal count.

---

# Phase 9 — Gold Layer & Pipeline Orchestration

## Goal

Create the serving layer and one reproducible pipeline command.

- [x] 9.1 — Implement J7 publication of `student_features` to MongoDB.
  Commit: `Update - 9.1 - publish student features`

- [x] 9.2 — Implement J7 publication of `course_metrics` and `school_summary`.
  Commit: `Update - 9.2 - publish course and school metrics`

- [x] 9.3 — Implement publication of `risk_indicators` with signal breakdown and run metadata.
  Commit: `Update - 9.3 - publish risk indicators`

- [x] 9.4 — Add validation after publication to confirm counts, grain and required fields of all gold collections.
  Commit: `Update - 9.4 - validate gold collections`

- [x] 9.5 — Implement `scripts/run_pipeline.py` to execute the development Spark pipeline in the documented order: J1 → J2 → J3 → J4/J5/J6 → J7.
  Commit: `Update - 9.5 - wire end-to-end Spark pipeline`

- [x] 9.6 — Implement pipeline run metadata/logging so each run records configuration/seed, start/end status, stage outcomes and output counts.
  Commit: `Update - 9.6 - add pipeline run metadata`

- [x] 9.7 — Update IDE context documentation for Phases 8 and 9.
  Commit: `Update - 9.7 - IDE_Context data addition`

**Checkpoint:** The project can run from generated development data through gold MongoDB collections using one documented pipeline command.

---

# Phase 10 — MVP Validation Gate

## Goal

Prove the complete architecture before building the polished dashboard or generating the full dataset.

- [x] 10.1 — Add end-to-end integration test covering generation → Parquet/MongoDB → Spark → gold collections using a small fixture/development dataset.
  Commit: `Update - 10.1 - add end-to-end MVP pipeline test`

- [x] 10.2 — Implement ground-truth recovery comparison for planted relationships and the decoy relationship.
  Commit: `Update - 10.2 - implement ground truth recovery test`

- [ ] 10.3 — Validate that risk-rule boundary cases behave correctly, including 75% attendance, 50% LMS comparison, 30% late submissions and 10-point marks decline boundaries.
  Commit: `Update - 10.3 - validate risk signal boundaries`

- [ ] 10.4 — Validate reproducibility by running the same development configuration/seed twice and comparing deterministic outputs/manifest characteristics.
  Commit: `Update - 10.4 - verify generator reproducibility`

- [ ] 10.5 — Run a local resource/performance smoke test and document actual development-scale runtime and memory observations. Do not optimize prematurely.
  Commit: `Update - 10.5 - record MVP resource baseline`

**MVP CHECKPOINT:** Stop here and review the complete vertical slice.

The following must all work before Phase 11:

```text
Generator
→ Parquet/MongoDB
→ Spark
→ Gold collections
→ Ground-truth recovery
→ Risk signals
→ Validated outputs
```

Do not begin full-scale generation until this checkpoint passes.

---

# Phase 11 — Streamlit Dashboard Foundation

## Goal

Build the dashboard against real gold/serving data, not permanent mock values.

- [ ] 11.1 — Implement Streamlit application entry point and shared configuration/data-access layer. The app should start and display a basic authenticated shell.
  Commit: `Update - 11.1 - initialize Streamlit dashboard`

- [ ] 11.2 — Implement dummy login/session state with the four approved roles: University Admin, School/Department Admin, Faculty and Academic Analyst.
  Commit: `Update - 11.2 - implement dashboard dummy authentication`

- [ ] 11.3 — Implement centralized role/scope resolution so dashboard pages do not duplicate permission logic.
  Commit: `Update - 11.3 - implement role and scope control`

- [ ] 11.4 — Implement shared dashboard layout, navigation, page header, breadcrumbs and global academic filters.
  Commit: `Update - 11.4 - implement shared dashboard layout`

- [ ] 11.5 — Implement reusable KPI, analytical-card, status and risk-signal UI components following `docs/design.md`.
  Commit: `Update - 11.5 - implement shared dashboard components`

---

# Phase 12 — Dashboard Views

## Goal

Build each analytical view as one reviewable page-level task.

- [ ] 12.1 — Build the University Overview page using actual gold data: university KPIs, school comparison, academic/attendance/LMS overview, trend summary and risk summary.
  Commit: `Update - 12.1 - build university overview`

- [ ] 12.2 — Build School/Department views with scoped KPIs, course breakdown, trends and risk distribution.
  Commit: `Update - 12.2 - build school and department analytics`

- [ ] 12.3 — Build Course view with enrollment, marks, attendance, coursework, LMS engagement, trend and association information.
  Commit: `Update - 12.3 - build course analytics`

- [ ] 12.4 — Build Student view with integrated academic, attendance, coursework, LMS, trend and five-rule signal breakdown.
  Commit: `Update - 12.4 - build student intelligence view`

- [ ] 12.5 — Build Analysis view with correlation, trend analysis and methodology/explainability sections.
  Commit: `Update - 12.5 - build analytical analysis view`

- [ ] 12.6 — Build Data Quality view showing injected/detected/corrected/dropped/remaining issues from actual pipeline output.
  Commit: `Update - 12.6 - build data quality dashboard`

- [ ] 12.7 — Add the synthetic-data disclosure and non-causal/risk methodology notices to the appropriate dashboard locations.
  Commit: `Update - 12.7 - add analytical disclosure and methodology notices`

- [ ] 12.8 — Perform one cross-dashboard usability/accessibility/error-state pass without adding new features.
  Commit: `Update - 12.8 - dashboard usability and accessibility pass`

**Checkpoint:** The MVP dashboard operates on real generated/gold data and supports the documented roles and hierarchy.

---

# Phase 13 — Benchmarking

## Goal

Measure technology trade-offs using real workloads.

- [ ] 13.1 — Implement J8 benchmark harness with repeatable workload definitions, timing and run metadata.
  Commit: `Update - 13.1 - implement benchmark harness`

- [ ] 13.2 — Implement the weekly LMS engagement benchmark using pandas where the workload is feasible.
  Commit: `Update - 13.2 - benchmark pandas workload`

- [ ] 13.3 — Implement the equivalent MongoDB aggregation benchmark.
  Commit: `Update - 13.3 - benchmark MongoDB aggregation`

- [ ] 13.4 — Implement the equivalent PySpark benchmark.
  Commit: `Update - 13.4 - benchmark PySpark workload`

- [ ] 13.5 — Add the full feature-table join benchmark where equivalent implementations are practical.
  Commit: `Update - 13.5 - benchmark feature-table join`

- [ ] 13.6 — Generate benchmark output containing dataset size, execution time, memory observations where practical and environment information. Do not manufacture conclusions.
  Commit: `Update - 13.6 - publish benchmark results`

---

# Phase 14 — Full-Scale Generation

## Goal

Scale the validated architecture toward the documented target.

- [ ] 14.1 — Review and freeze the generator configuration for the full target run. Do not change schema or architecture in this task.
  Commit: `Update - 14.1 - freeze full-scale generator configuration`

- [ ] 14.2 — Run/implement full university hierarchy generation for the six-school target and record actual counts.
  Commit: `Update - 14.2 - generate full university hierarchy`

- [ ] 14.3 — Generate the full target student population and academic records across two academic years/four semesters using the validated generator.
  Commit: `Update - 14.3 - generate full academic dataset`

- [ ] 14.4 — Generate full attendance and coursework datasets and record actual counts/storage usage.
  Commit: `Update - 14.4 - generate full attendance and coursework data`

- [ ] 14.5 — Generate the full LMS event dataset in chunked Parquet form toward the ~70M target and record actual event count and disk usage.
  Commit: `Update - 14.5 - generate full LMS Parquet dataset`

- [ ] 14.6 — Generate the defined MongoDB LMS serving slice from the full dataset without loading all LMS events into MongoDB.
  Commit: `Update - 14.6 - generate full LMS serving slice`

- [ ] 14.7 — Record full-scale generation manifest containing actual counts, seed, configuration, disk usage and generation duration.
  Commit: `Update - 14.7 - record full-scale generation manifest`

**Checkpoint:** Full synthetic data exists and actual scale is documented.

---

# Phase 15 — Full-Scale Spark Pipeline

## Goal

Run the validated processing architecture at target scale.

- [ ] 15.1 — Run J1 on the full dataset and record cleaning/data-quality metrics.
  Commit: `Update - 15.1 - run full-scale data validation`

- [ ] 15.2 — Run J2 full-scale LMS aggregation and record runtime/memory observations.
  Commit: `Update - 15.2 - run full-scale LMS aggregation`

- [ ] 15.3 — Run J3 full-scale feature-table generation and validate output grain/counts.
  Commit: `Update - 15.3 - run full-scale feature engineering`

- [ ] 15.4 — Run J4 full-scale correlation analysis and store measured results.
  Commit: `Update - 15.4 - run full-scale correlation analytics`

- [ ] 15.5 — Run J5 full-scale trend detection and validate the synthetic decliner behavior.
  Commit: `Update - 15.5 - run full-scale trend detection`

- [ ] 15.6 — Run J6 full-scale five-rule risk signals and validate signal distributions.
  Commit: `Update - 15.6 - run full-scale risk analytics`

- [ ] 15.7 — Run J7 full-scale publication and validate all gold collections.
  Commit: `Update - 15.7 - publish full-scale gold layer`

- [ ] 15.8 — Run J8 against the documented benchmark workloads and record actual performance.
  Commit: `Update - 15.8 - run full-scale benchmarks`

**Checkpoint:** Full-scale processing succeeds within the local resource constraints or produces documented engineering findings where the target requires adjustment.

---

# Phase 16 — Full-Scale Validation & Hardening

## Goal

Verify correctness after scaling.

- [ ] 16.1 — Compare full-scale generated counts against the generation manifest and schema expectations.
  Commit: `Update - 16.1 - validate full-scale record counts`

- [ ] 16.2 — Validate full-scale data-quality detection against the injection manifest.
  Commit: `Update - 16.2 - validate full-scale data quality`

- [ ] 16.3 — Run full-scale ground-truth recovery and document recovered/non-recovered/decoy relationships.
  Commit: `Update - 16.3 - validate full-scale ground truth recovery`

- [ ] 16.4 — Validate full-scale risk signal calculations against independent small fixtures and selected sampled records.
  Commit: `Update - 16.4 - validate full-scale risk signals`

- [ ] 16.5 — Test dashboard behavior against full-scale gold collections, including role scope, filters, drill-down and error/empty states.
  Commit: `Update - 16.5 - validate dashboard at full scale`

- [ ] 16.6 — Perform a local resource audit covering Spark memory, MongoDB usage, Parquet size, pipeline runtime and dashboard responsiveness.
  Commit: `Update - 16.6 - record full-scale resource audit`

---

# Phase 17 — Final Documentation & Demonstration

## Goal

Turn the working implementation into a defensible academic project.

- [ ] 17.1 — Update `README.md` with actual setup commands, measured scale and current project status. Do not leave target values presented as measured values.
  Commit: `Update - 17.1 - finalize README with measured project status`

- [ ] 17.2 — Update `docs/tasks.md` statuses and ensure completed tasks match the actual Git history.
  Commit: `Update - 17.2 - finalize implementation task status`

- [ ] 17.3 — Update architecture/technology documentation with any approved implementation findings that materially changed the original design.
  Commit: `Update - 17.3 - document implementation findings`

- [ ] 17.4 — Produce quality, benchmark and recovery reports under `reports/`.
  Commit: `Update - 17.4 - add project validation reports`

- [ ] 17.5 — Prepare the final academic report content from the actual implementation: problem, architecture, data generation, MongoDB, Spark, analytics, dashboard, quality, benchmarks, recovery, limitations and future scope.
  Commit: `Update - 17.5 - prepare final project report materials`

- [ ] 17.6 — Prepare the final demonstration flow: login → overview → hierarchy drill-down → course → student → risk signals → analysis → data quality → benchmark/recovery evidence.
  Commit: `Update - 17.6 - prepare final demonstration flow`

- [ ] 17.7 — Perform final repository hygiene: remove accidental generated artifacts/secrets, verify `.gitignore`, verify documentation links/paths and confirm the repository can be understood from a clean clone.
  Commit: `Update - 17.7 - final repository hygiene`

**Final Checkpoint:** Acadexa is reproducible, documented, demonstrable and ready for academic submission.

---

# Execution Gates

## Gate 1 — Foundation

Required before Phase 2:

```text
Repository
+
README
+
docs
+
environment template
+
package/test skeleton
```

## Gate 2 — Data Contract

Required before Phase 4:

```text
Configuration
+
schemas
+
validation
```

## Gate 3 — Development Data

Required before Phase 6:

```text
Small reproducible dataset
+
ground truth
+
quality manifest
```

## Gate 4 — Analytical Pipeline

Required before Phase 11:

```text
MongoDB
+
Parquet
+
Spark J1–J7
+
gold collections
+
recovery
+
risk validation
```

## Gate 5 — MVP

Required before Phase 14:

```text
One school
+
one semester
+
end-to-end processing
+
working dashboard
+
validation
```

## Gate 6 — Full Scale

Required before finalization:

```text
Target-scale data
+
full Spark pipeline
+
actual benchmarks
+
full validation
```

---

# Things That Must Never Be Bundled

Do not combine these into a single task merely because they are technically related:

```text
Schema + generator
Generator + MongoDB loader
MongoDB + Spark
Spark + dashboard
Risk logic + ML
Dashboard + full-scale generation
Benchmark + optimization
```

Each boundary exists so that the resulting commit is understandable and reversible.

---

# Things to Keep in Mind During Implementation

## 1. Do not optimize before measuring

The target resource estimates are planning assumptions.

Measure the actual generator and Spark behavior before changing architecture.

## 2. Do not generate 70M events first

The first successful run should be small.

The full dataset is a later milestone.

## 3. Do not use permanent mock dashboard data

Temporary mocks are acceptable while a UI page is being assembled, but the MVP must read actual generated/gold data.

## 4. Do not turn risk signals into predictions

The output is:

```text
0–5 observed signals
```

not:

```text
probability of failure
```

## 5. Do not interpret correlation causally

Keep analytical language neutral and evidence-based.

## 6. Do not load the entire LMS dataset into MongoDB

The architecture intentionally separates:

```text
Full LMS → Parquet
Serving slice → MongoDB
```

## 7. Do not use large Spark `collect()` operations

The project is specifically intended to demonstrate scalable data processing.

## 8. Do not hard-code dashboard numbers

All KPI values must come from actual data.

## 9. Do not silently change the architecture

If a new requirement conflicts with the documented design, update the documentation/decision first.

## 10. Do not commit secrets or generated datasets

Keep:

```text
.env
large Parquet files
generated Mongo exports
logs
local caches
```

out of Git.

---

# Suggested First Five IDE Tasks

If starting implementation now, execute exactly these in order:

```text
1.0 / 0.1 — Add finalized docs/
1.1       — Initialize repository ignore rules
1.2       — Add project README
1.3       — Add environment configuration template
1.4       — Create repository folder structure
```

Then continue into:

```text
1.5 → Python package skeleton
1.6 → script entry points
1.7 → test structure
1.8 → dependencies
2.1 → configuration loader
2.2 → university hierarchy
...
```

Do not start the generator until the configuration and schema contract have been established.

---

# Current Starting Point

The documentation and planning work is complete.

The first implementation objective is **not**:

```text
Generate 70M LMS events
```

It is:

```text
Create a clean repository
        ↓
Freeze configuration
        ↓
Freeze schema
        ↓
Generate a tiny but complete dataset
        ↓
Prove the pipeline end-to-end
```

The first major technical milestone is therefore:

> **A one-school, one-semester vertical slice that travels from synthetic generation through MongoDB/Parquet, PySpark processing and gold collections, and is then displayed through Streamlit.**

Everything after that is scaling, validation and refinement of a pipeline that is already proven to work.

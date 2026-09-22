# Acadexa — Implementation Tasks & Progress

**Document:** `docs/tasks.md`  
**Project:** Acadexa  
**Institution:** RAS University  
**Status:** Initial implementation roadmap  
**Primary references:** `data.md`, `docs/prd.md`, `docs/architecture.md`, `docs/features.md`, `docs/rules.md`, `docs/design.md`, `docs/folder_structure.md`

---

# 1. Purpose

This document is the implementation roadmap for Acadexa.

It converts the approved requirements and architecture into:

- phases,
- tasks,
- dependencies,
- milestones,
- validation gates,
- team responsibilities,
- MVP criteria,
- full-scale criteria,
- documentation work.

This document is also intended to act as the project's working progress tracker.

The roadmap follows the project's most important implementation principle:

> **Build one school and one semester end-to-end first, validate the entire pipeline, then scale to the full synthetic dataset.**

---

# 2. Project Execution Strategy

Acadexa should not be developed as isolated features.

The recommended implementation flow is:

```text
Documentation
    ↓
Repository foundation
    ↓
Configuration + schema contract
    ↓
Synthetic generator
    ↓
One-school / one-semester data
    ↓
MongoDB + Parquet
    ↓
Spark cleaning
    ↓
Feature engineering
    ↓
Analytics
    ↓
Gold collections
    ↓
Dashboard
    ↓
Validation / recovery
    ↓
Benchmarking
    ↓
Full-scale generation
    ↓
Full-scale pipeline
    ↓
Final testing
    ↓
Documentation / report / viva
```

---

# 3. Development Principles

## 3.1 Vertical slice first

The first milestone is not:

```text
build generator
```

or:

```text
build dashboard
```

It is:

```text
one school
+
one semester
+
real generated records
+
MongoDB
+
PySpark
+
gold outputs
+
working Streamlit view
```

The complete path must work before large-scale generation.

## 3.2 Scale second

After the vertical slice works:

```text
1 school / 1 semester
        ↓
full hierarchy
        ↓
2 academic years / 4 semesters
        ↓
12,000 students
        ↓
~70M LMS events
```

## 3.3 Validate continuously

Every major stage should have a validation checkpoint.

Do not wait until the end to discover schema or data-quality problems.

---

# 4. Status Convention

Use the following status values:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
REVIEW
DONE
DEFERRED
```

Recommended task notation:

```text
- [ ] NOT_STARTED — Task
- [~] IN_PROGRESS — Task
- [!] BLOCKED — Task
- [>] REVIEW — Task
- [x] DONE — Task
- [-] DEFERRED — Task
```

The status should be updated as implementation progresses.

---

# 5. Phase Overview

| Phase | Name | Main Outcome |
|---|---|---|
| P0 | Documentation & Foundation | Repository and project contracts |
| P1 | Configuration & Schema | Stable synthetic-data contract |
| P2 | Synthetic Generator | Reproducible one-slice dataset |
| P3 | MongoDB & Parquet | Operational/raw data layer |
| P4 | Spark Processing | Cleaning and feature pipeline |
| P5 | Analytics | Correlation, trends and risk signals |
| P6 | Gold Layer | Dashboard-ready analytical data |
| P7 | Dashboard | Role-aware Streamlit application |
| P8 | Validation | Recovery, quality and integration tests |
| P9 | Benchmarking | Pandas/Mongo/Spark measurements |
| P10 | Full-Scale Run | 12k / 2-year / ~70M target |
| P11 | Finalization | Report, demo, documentation and viva |

---

# 6. P0 — Documentation & Repository Foundation

## Objective

Create the project structure and establish a shared source of truth before implementation.

### Tasks

- [x] DONE — Create repository `acadexa`.
- [x] DONE — Establish `docs/` directory.
- [x] DONE — Define PRD.
- [x] DONE — Define architecture.
- [x] DONE — Define technology stack.
- [x] DONE — Define feature specification.
- [x] DONE — Define folder structure.
- [x] DONE — Define implementation rules.
- [x] DONE — Define UI/UX design direction.
- [ ] NOT_STARTED — Create `tasks.md`.
- [ ] NOT_STARTED — Create `memory.md`.
- [ ] NOT_STARTED — Create `README.md`.
- [ ] NOT_STARTED — Create `.gitignore`.
- [ ] NOT_STARTED — Create `.env.example`.
- [ ] NOT_STARTED — Create dependency file.
- [ ] NOT_STARTED — Initialize Python package structure.
- [ ] NOT_STARTED — Add base test configuration.

### Exit Criteria

```text
Repository structure exists
AND
documentation contracts exist
AND
Python project can be initialized
AND
secrets/generated data are excluded from Git
```

---

# 7. P1 — Configuration & Schema Contract

## Objective

Create the stable contracts that every subsequent component consumes.

### 7.1 University configuration

- [ ] NOT_STARTED — Define RAS University configuration.
- [ ] NOT_STARTED — Define six schools.
- [ ] NOT_STARTED — Define department hierarchy.
- [ ] NOT_STARTED — Define program hierarchy.
- [ ] NOT_STARTED — Define course catalog.
- [ ] NOT_STARTED — Define academic years.
- [ ] NOT_STARTED — Define semesters.
- [ ] NOT_STARTED — Define course metadata.
- [ ] NOT_STARTED — Define configurable school-specific behavior.

### 7.2 Generator configuration

- [ ] NOT_STARTED — Define student target count.
- [ ] NOT_STARTED — Define semester count.
- [ ] NOT_STARTED — Define LMS event target.
- [ ] NOT_STARTED — Define random seed.
- [ ] NOT_STARTED — Define behavior distributions.
- [ ] NOT_STARTED — Define course-difficulty parameters.
- [ ] NOT_STARTED — Define decliner population.
- [ ] NOT_STARTED — Define quality-injection rates.

### 7.3 Risk configuration

- [ ] NOT_STARTED — Define attendance threshold.
- [ ] NOT_STARTED — Define LMS decline threshold.
- [ ] NOT_STARTED — Define late-submission threshold.
- [ ] NOT_STARTED — Define marks-decline threshold.
- [ ] NOT_STARTED — Define quiz bottom-quartile rule.

### 7.4 Schema contract

- [ ] NOT_STARTED — Define `students`.
- [ ] NOT_STARTED — Define `courses`.
- [ ] NOT_STARTED — Define `academic_records`.
- [ ] NOT_STARTED — Define `attendance`.
- [ ] NOT_STARTED — Define `coursework`.
- [ ] NOT_STARTED — Define `lms_events`.
- [ ] NOT_STARTED — Define `student_features`.
- [ ] NOT_STARTED — Define `course_metrics`.
- [ ] NOT_STARTED — Define `school_summary`.
- [ ] NOT_STARTED — Define `risk_indicators`.

### Exit Criteria

```text
All core entities have stable field definitions
AND
hierarchy is configuration-driven
AND
generator/risk settings are externalized
AND
downstream code can rely on the schema
```

---

# 8. P2 — Synthetic Data Generator

## Objective

Build a deterministic generator capable of producing realistic, internally consistent synthetic university data.

---

## 8.1 Generator foundation

- [ ] NOT_STARTED — Create generator package.
- [ ] NOT_STARTED — Implement seed handling.
- [ ] NOT_STARTED — Implement configuration loading.
- [ ] NOT_STARTED — Implement reproducibility checks.
- [ ] NOT_STARTED — Implement generation metadata.

---

## 8.2 University entities

- [ ] NOT_STARTED — Generate schools.
- [ ] NOT_STARTED — Generate departments.
- [ ] NOT_STARTED — Generate programs.
- [ ] NOT_STARTED — Generate courses.
- [ ] NOT_STARTED — Generate students.

---

## 8.3 Academic records

- [ ] NOT_STARTED — Generate semester records.
- [ ] NOT_STARTED — Generate course enrollments.
- [ ] NOT_STARTED — Generate marks.
- [ ] NOT_STARTED — Generate grades/statuses where defined.
- [ ] NOT_STARTED — Maintain hierarchy consistency.

---

## 8.4 Attendance

- [ ] NOT_STARTED — Generate weekly attendance.
- [ ] NOT_STARTED — Apply student behavioral variation.
- [ ] NOT_STARTED — Apply course variation.
- [ ] NOT_STARTED — Validate attendance ranges.

---

## 8.5 Coursework

- [ ] NOT_STARTED — Generate assignments.
- [ ] NOT_STARTED — Generate quizzes.
- [ ] NOT_STARTED — Generate submission timestamps/status.
- [ ] NOT_STARTED — Generate late submissions.
- [ ] NOT_STARTED — Generate quiz attempts.

---

## 8.6 LMS events

- [ ] NOT_STARTED — Implement event-type distribution.
- [ ] NOT_STARTED — Implement timestamp generation.
- [ ] NOT_STARTED — Implement weekly rhythms.
- [ ] NOT_STARTED — Implement semester rhythms.
- [ ] NOT_STARTED — Implement engagement variation.
- [ ] NOT_STARTED — Implement chunked generation.
- [ ] NOT_STARTED — Write LMS events to Parquet.

---

## 8.7 Behavioral model

- [ ] NOT_STARTED — Implement ability trait.
- [ ] NOT_STARTED — Implement diligence trait.
- [ ] NOT_STARTED — Implement engagement trait.
- [ ] NOT_STARTED — Implement course difficulty.
- [ ] NOT_STARTED — Implement approximately 8% decliners.
- [ ] NOT_STARTED — Ensure planted relationships are reproducible.

---

## 8.8 Ground truth

- [ ] NOT_STARTED — Create planted relationship registry.
- [ ] NOT_STARTED — Record intended relationships.
- [ ] NOT_STARTED — Record decoy relationship.
- [ ] NOT_STARTED — Store generator metadata.
- [ ] NOT_STARTED — Store generation manifest.

---

## 8.9 Data-quality injection

- [ ] NOT_STARTED — Duplicate LMS events.
- [ ] NOT_STARTED — Controlled nulls.
- [ ] NOT_STARTED — Timestamp inconsistencies.
- [ ] NOT_STARTED — Course-ID formatting issues.
- [ ] NOT_STARTED — Orphan records.
- [ ] NOT_STARTED — Out-of-range values.
- [ ] NOT_STARTED — Generate injection manifest.

---

## 8.10 MVP generator milestone

Generate:

```text
One school
+
One semester
+
All required entity types
+
Small LMS event volume
```

Then verify:

- [ ] NOT_STARTED — Referential integrity.
- [ ] NOT_STARTED — Record counts.
- [ ] NOT_STARTED — Reproducibility.
- [ ] NOT_STARTED — Ground-truth metadata.
- [ ] NOT_STARTED — Data-quality injection.

### Exit Criteria

The same seed and configuration produce reproducible results, and the one-school/one-semester dataset is valid enough to run through the complete pipeline.

---

# 9. P3 — MongoDB & Parquet Data Layer

## Objective

Build the raw and operational storage layer.

---

## 9.1 MongoDB setup

- [ ] NOT_STARTED — Create Acadexa database.
- [ ] NOT_STARTED — Create core collections.
- [ ] NOT_STARTED — Create LMS time-series collection/slice where applicable.
- [ ] NOT_STARTED — Create gold collections.
- [ ] NOT_STARTED — Create indexes.
- [ ] NOT_STARTED — Add database initialization script.

---

## 9.2 Data loading

- [ ] NOT_STARTED — Load students.
- [ ] NOT_STARTED — Load courses.
- [ ] NOT_STARTED — Load academic records.
- [ ] NOT_STARTED — Load attendance.
- [ ] NOT_STARTED — Load coursework.
- [ ] NOT_STARTED — Load defined LMS slice.

---

## 9.3 MongoDB demonstrations

Implement representative examples of:

- [ ] NOT_STARTED — CRUD.
- [ ] NOT_STARTED — `$match`.
- [ ] NOT_STARTED — `$group`.
- [ ] NOT_STARTED — `$project`.
- [ ] NOT_STARTED — `$sort`.
- [ ] NOT_STARTED — `$lookup`.
- [ ] NOT_STARTED — `$unwind`.
- [ ] NOT_STARTED — `$setWindowFields`.
- [ ] NOT_STARTED — `$facet`.
- [ ] NOT_STARTED — Time-series queries.

---

## 9.4 Validation

- [ ] NOT_STARTED — Validate document counts.
- [ ] NOT_STARTED — Validate indexes.
- [ ] NOT_STARTED — Validate sample queries.
- [ ] NOT_STARTED — Validate orphan behavior.
- [ ] NOT_STARTED — Validate LMS slice.

### Exit Criteria

The MVP dataset exists in the intended storage layers and can be queried reliably.

---

# 10. P4 — PySpark Processing Pipeline

## Objective

Implement the large-scale batch processing layer.

---

# 10.1 Spark environment

- [ ] NOT_STARTED — Configure PySpark local mode.
- [ ] NOT_STARTED — Configure memory limits.
- [ ] NOT_STARTED — Configure MongoDB Spark connectivity.
- [ ] NOT_STARTED — Validate Spark startup.
- [ ] NOT_STARTED — Validate Parquet reads.

---

# 10.2 J1 — Clean & Validate

- [ ] NOT_STARTED — Read raw datasets.
- [ ] NOT_STARTED — Detect duplicates.
- [ ] NOT_STARTED — Handle nulls.
- [ ] NOT_STARTED — Normalize course identifiers.
- [ ] NOT_STARTED — Handle timestamp inconsistencies.
- [ ] NOT_STARTED — Detect orphan records.
- [ ] NOT_STARTED — Detect out-of-range values.
- [ ] NOT_STARTED — Produce quality metrics.
- [ ] NOT_STARTED — Write cleaned output.

---

# 10.3 J2 — Event Aggregation

- [ ] NOT_STARTED — Aggregate LMS events by student.
- [ ] NOT_STARTED — Aggregate by week.
- [ ] NOT_STARTED — Calculate event counts.
- [ ] NOT_STARTED — Calculate active days.
- [ ] NOT_STARTED — Calculate activity categories.
- [ ] NOT_STARTED — Preserve course context where required.

---

# 10.4 J3 — Feature Table

Create integrated student-level features.

- [ ] NOT_STARTED — Join academic records.
- [ ] NOT_STARTED — Join attendance.
- [ ] NOT_STARTED — Join coursework.
- [ ] NOT_STARTED — Join LMS features.
- [ ] NOT_STARTED — Calculate marks trends.
- [ ] NOT_STARTED — Calculate attendance metrics.
- [ ] NOT_STARTED — Calculate LMS metrics.
- [ ] NOT_STARTED — Calculate late-submission metrics.
- [ ] NOT_STARTED — Create student feature table.

---

# 10.5 J4 — Correlation

- [ ] NOT_STARTED — Implement within-course normalization.
- [ ] NOT_STARTED — Implement Spearman correlation.
- [ ] NOT_STARTED — Implement optional Pearson correlation.
- [ ] NOT_STARTED — Calculate attendance/marks association.
- [ ] NOT_STARTED — Calculate LMS/marks association.
- [ ] NOT_STARTED — Calculate late-submission/marks association.
- [ ] NOT_STARTED — Calculate decoy relationship.
- [ ] NOT_STARTED — Store correlation outputs.

---

# 10.6 J5 — Trend Detection

- [ ] NOT_STARTED — Implement rolling four-week windows.
- [ ] NOT_STARTED — Compare current vs previous window.
- [ ] NOT_STARTED — Detect engagement decline.
- [ ] NOT_STARTED — Detect marks decline.
- [ ] NOT_STARTED — Generate interpretable trend records.

---

# 10.7 J6 — Risk Signals

Implement exactly the five documented rules.

- [ ] NOT_STARTED — Attendance signal.
- [ ] NOT_STARTED — LMS decline signal.
- [ ] NOT_STARTED — Late-submission signal.
- [ ] NOT_STARTED — Marks-decline signal.
- [ ] NOT_STARTED — Quiz-activity signal.
- [ ] NOT_STARTED — Aggregate signal count.
- [ ] NOT_STARTED — Store triggered-signal explanation.

---

# 10.8 J7 — Publish

- [ ] NOT_STARTED — Publish student features.
- [ ] NOT_STARTED — Publish course metrics.
- [ ] NOT_STARTED — Publish school summaries.
- [ ] NOT_STARTED — Publish risk indicators.
- [ ] NOT_STARTED — Validate published counts.
- [ ] NOT_STARTED — Validate dashboard-readiness.

---

# 10.9 J8 — Benchmark

- [ ] NOT_STARTED — Define benchmark workload.
- [ ] NOT_STARTED — Define dataset slices.
- [ ] NOT_STARTED — Implement timing.
- [ ] NOT_STARTED — Implement memory measurement where practical.
- [ ] NOT_STARTED — Compare pandas.
- [ ] NOT_STARTED — Compare MongoDB.
- [ ] NOT_STARTED — Compare PySpark.
- [ ] NOT_STARTED — Store measured results.

### Exit Criteria

The full analytical pipeline runs on the MVP dataset from raw input to gold collections.

---

# 11. P5 — Analytics Validation

## Objective

Verify that the analytical system recovers intended synthetic relationships and produces correct rule-based outputs.

---

## 11.1 Correlation recovery

- [ ] NOT_STARTED — Compare planted vs observed relationships.
- [ ] NOT_STARTED — Verify attendance/marks association.
- [ ] NOT_STARTED — Verify LMS/marks association.
- [ ] NOT_STARTED — Verify late-submission/marks relationship.
- [ ] NOT_STARTED — Verify course difficulty effect/confounding behavior.
- [ ] NOT_STARTED — Verify decoy does not appear artificially strong.

---

## 11.2 Decliner/trend validation

- [ ] NOT_STARTED — Verify planted decliners show intended trend patterns.
- [ ] NOT_STARTED — Compare observed trends with generator ground truth.
- [ ] NOT_STARTED — Record recovery rate.

---

## 11.3 Risk validation

- [ ] NOT_STARTED — Create boundary cases.
- [ ] NOT_STARTED — Verify each signal independently.
- [ ] NOT_STARTED — Verify signal counts.
- [ ] NOT_STARTED — Verify no prediction output exists.

---

# 12. P6 — Gold Layer

## Objective

Create dashboard-ready analytical collections.

### Tasks

- [ ] NOT_STARTED — Finalize `student_features`.
- [ ] NOT_STARTED — Finalize `course_metrics`.
- [ ] NOT_STARTED — Finalize `school_summary`.
- [ ] NOT_STARTED — Finalize `risk_indicators`.
- [ ] NOT_STARTED — Add required indexes.
- [ ] NOT_STARTED — Validate aggregation grain.
- [ ] NOT_STARTED — Validate completeness.
- [ ] NOT_STARTED — Validate freshness metadata/run metadata where needed.

### Exit Criteria

The dashboard can operate primarily against gold/serving data without repeatedly executing expensive raw-data processing.

---

# 13. P7 — Streamlit Dashboard

## Objective

Build the role-aware analytical interface.

---

## 13.1 Authentication

- [ ] NOT_STARTED — Create dummy user configuration.
- [ ] NOT_STARTED — Create login page.
- [ ] NOT_STARTED — Create session state.
- [ ] NOT_STARTED — Implement logout.
- [ ] NOT_STARTED — Implement role resolution.

---

## 13.2 Navigation

- [ ] NOT_STARTED — Overview.
- [ ] NOT_STARTED — Schools.
- [ ] NOT_STARTED — Courses.
- [ ] NOT_STARTED — Students.
- [ ] NOT_STARTED — Analysis.
- [ ] NOT_STARTED — Data Quality.

---

## 13.3 University overview

- [ ] NOT_STARTED — KPI cards.
- [ ] NOT_STARTED — School comparison.
- [ ] NOT_STARTED — Academic overview.
- [ ] NOT_STARTED — Attendance overview.
- [ ] NOT_STARTED — LMS overview.
- [ ] NOT_STARTED — Trend summary.
- [ ] NOT_STARTED — Risk summary.

---

## 13.4 School/department view

- [ ] NOT_STARTED — School summary.
- [ ] NOT_STARTED — Department summary.
- [ ] NOT_STARTED — Course breakdown.
- [ ] NOT_STARTED — Trend view.
- [ ] NOT_STARTED — Risk distribution.

---

## 13.5 Course view

- [ ] NOT_STARTED — Course metadata.
- [ ] NOT_STARTED — Marks.
- [ ] NOT_STARTED — Attendance.
- [ ] NOT_STARTED — Coursework.
- [ ] NOT_STARTED — LMS engagement.
- [ ] NOT_STARTED — Trend.
- [ ] NOT_STARTED — Association analysis.

---

## 13.6 Student view

- [ ] NOT_STARTED — Student profile.
- [ ] NOT_STARTED — Academic summary.
- [ ] NOT_STARTED — Attendance.
- [ ] NOT_STARTED — Coursework.
- [ ] NOT_STARTED — LMS engagement.
- [ ] NOT_STARTED — Trends.
- [ ] NOT_STARTED — Five-rule risk breakdown.

---

## 13.7 Analysis view

- [ ] NOT_STARTED — Correlation matrix.
- [ ] NOT_STARTED — Factor comparison.
- [ ] NOT_STARTED — Trend analysis.
- [ ] NOT_STARTED — Ground-truth recovery.
- [ ] NOT_STARTED — Methodology notes.

---

## 13.8 Data-quality view

- [ ] NOT_STARTED — Quality KPIs.
- [ ] NOT_STARTED — Issue table.
- [ ] NOT_STARTED — Injection vs detection.
- [ ] NOT_STARTED — Cleaning results.

---

## 13.9 Dashboard UX validation

- [ ] NOT_STARTED — Empty states.
- [ ] NOT_STARTED — Error states.
- [ ] NOT_STARTED — Loading states.
- [ ] NOT_STARTED — Scope-aware filters.
- [ ] NOT_STARTED — Breadcrumbs/drill-down.
- [ ] NOT_STARTED — Synthetic-data disclosure.
- [ ] NOT_STARTED — Accessibility review.

### Exit Criteria

All core MVP views work against actual generated/gold data.

---

# 14. P8 — Testing & Integration

## Objective

Ensure the project works as one system.

---

## 14.1 Unit tests

- [ ] NOT_STARTED — Configuration tests.
- [ ] NOT_STARTED — Generator tests.
- [ ] NOT_STARTED — Schema tests.
- [ ] NOT_STARTED — Attendance tests.
- [ ] NOT_STARTED — Coursework tests.
- [ ] NOT_STARTED — Quality-injection tests.
- [ ] NOT_STARTED — Risk-rule tests.
- [ ] NOT_STARTED — Feature-calculation tests.

---

## 14.2 Integration tests

- [ ] NOT_STARTED — Generator → Parquet.
- [ ] NOT_STARTED — Generator → MongoDB.
- [ ] NOT_STARTED — Parquet → Spark.
- [ ] NOT_STARTED — MongoDB → Spark.
- [ ] NOT_STARTED — Spark → Gold.
- [ ] NOT_STARTED — Gold → Dashboard data layer.

---

## 14.3 End-to-end test

Run:

```text
generate
→ load
→ clean
→ aggregate
→ feature
→ correlation
→ trends
→ risk
→ publish
→ dashboard
```

using the MVP dataset.

### Exit Criteria

The complete MVP pipeline can be reproduced from a clean environment.

---

# 15. P9 — Benchmarking

## Objective

Demonstrate why multiple technologies are used.

### Benchmark workloads

- [ ] NOT_STARTED — Weekly LMS engagement aggregation.
- [ ] NOT_STARTED — Appropriate full-set workload.
- [ ] NOT_STARTED — Full feature-table join.
- [ ] NOT_STARTED — Equivalent pandas workload where feasible.
- [ ] NOT_STARTED — Equivalent MongoDB aggregation where feasible.
- [ ] NOT_STARTED — Equivalent Spark workload.

### Metrics

- [ ] NOT_STARTED — Wall-clock time.
- [ ] NOT_STARTED — Peak memory where practical.
- [ ] NOT_STARTED — Dataset size.
- [ ] NOT_STARTED — Environment details.

### Reporting

- [ ] NOT_STARTED — Generate benchmark report.
- [ ] NOT_STARTED — Add benchmark dashboard/report section.
- [ ] NOT_STARTED — Document workload limitations.

---

# 16. P10 — Full-Scale Dataset

## Objective

Scale the validated pipeline to the intended project target.

Target:

```text
~12,000 students
2 academic years
4 semesters
~6 schools / ~18 departments / ~40 programs
~250 courses
~70M LMS events
```

These are target values. Actual generated counts and measured storage/performance must be recorded after the generator and pipeline run.

---

## 16.1 Pre-scale checklist

Before full generation:

- [ ] MVP end-to-end pipeline passes.
- [ ] Generator is reproducible.
- [ ] Schema is stable.
- [ ] MongoDB indexes validated.
- [ ] Spark local mode validated.
- [ ] Memory behavior measured.
- [ ] Dashboard reads gold data correctly.
- [ ] Recovery test passes.
- [ ] Benchmark framework works.

Do not start full-scale generation before these checks are substantially complete.

---

## 16.2 Full generation

- [ ] NOT_STARTED — Generate complete hierarchy.
- [ ] NOT_STARTED — Generate complete student population.
- [ ] NOT_STARTED — Generate four semesters.
- [ ] NOT_STARTED — Generate full LMS Parquet.
- [ ] NOT_STARTED — Generate MongoDB LMS slice.
- [ ] NOT_STARTED — Generate manifests.
- [ ] NOT_STARTED — Record actual counts.
- [ ] NOT_STARTED — Record actual disk usage.

---

## 16.3 Full processing

- [ ] NOT_STARTED — Run J1.
- [ ] NOT_STARTED — Run J2.
- [ ] NOT_STARTED — Run J3.
- [ ] NOT_STARTED — Run J4.
- [ ] NOT_STARTED — Run J5.
- [ ] NOT_STARTED — Run J6.
- [ ] NOT_STARTED — Run J7.
- [ ] NOT_STARTED — Run J8.

---

## 16.4 Full-scale validation

- [ ] NOT_STARTED — Validate counts.
- [ ] NOT_STARTED — Validate quality.
- [ ] NOT_STARTED — Validate recovery.
- [ ] NOT_STARTED — Validate risk signals.
- [ ] NOT_STARTED — Validate gold collections.
- [ ] NOT_STARTED — Validate dashboard performance.
- [ ] NOT_STARTED — Measure memory usage.
- [ ] NOT_STARTED — Measure processing times.

---

# 17. P11 — Finalization

## Objective

Prepare Acadexa for final demonstration, submission and viva.

---

## 17.1 Documentation

- [ ] NOT_STARTED — Finalize README.
- [ ] NOT_STARTED — Finalize PRD.
- [ ] NOT_STARTED — Finalize architecture.
- [ ] NOT_STARTED — Finalize tech stack.
- [ ] NOT_STARTED — Finalize features.
- [ ] NOT_STARTED — Finalize rules.
- [ ] NOT_STARTED — Finalize design.
- [ ] NOT_STARTED — Finalize tasks.
- [ ] NOT_STARTED — Finalize memory.
- [ ] NOT_STARTED — Document measured dataset size.
- [ ] NOT_STARTED — Document measured performance.
- [ ] NOT_STARTED — Document benchmark results.
- [ ] NOT_STARTED — Document recovery results.

---

## 17.2 Final report

Include:

- [ ] NOT_STARTED — Problem statement.
- [ ] NOT_STARTED — Objectives.
- [ ] NOT_STARTED — Architecture.
- [ ] NOT_STARTED — Dataset generation.
- [ ] NOT_STARTED — MongoDB design.
- [ ] NOT_STARTED — Spark processing.
- [ ] NOT_STARTED — Analytics.
- [ ] NOT_STARTED — Risk indicator.
- [ ] NOT_STARTED — Dashboard.
- [ ] NOT_STARTED — Data quality.
- [ ] NOT_STARTED — Benchmarking.
- [ ] NOT_STARTED — Recovery test.
- [ ] NOT_STARTED — Limitations.
- [ ] NOT_STARTED — Future scope.

---

## 17.3 Demo preparation

- [ ] NOT_STARTED — Prepare login demonstration.
- [ ] NOT_STARTED — Demonstrate university overview.
- [ ] NOT_STARTED — Demonstrate school/department drill-down.
- [ ] NOT_STARTED — Demonstrate course analytics.
- [ ] NOT_STARTED — Demonstrate student integrated view.
- [ ] NOT_STARTED — Demonstrate risk signal explanation.
- [ ] NOT_STARTED — Demonstrate correlation.
- [ ] NOT_STARTED — Demonstrate trend detection.
- [ ] NOT_STARTED — Demonstrate data-quality page.
- [ ] NOT_STARTED — Demonstrate MongoDB operations.
- [ ] NOT_STARTED — Demonstrate Spark jobs.
- [ ] NOT_STARTED — Demonstrate benchmark.
- [ ] NOT_STARTED — Demonstrate recovery test.

---

# 18. Two-Person Team Split

The split should follow functional ownership while keeping both members familiar with the complete architecture.

## Track A — Data Engineering & Analytics

Primary ownership:

```text
Configuration
Generator
MongoDB
Parquet
PySpark
Analytics
Gold layer
Benchmarks
```

Tasks:

- [ ] NOT_STARTED — Own generator implementation.
- [ ] NOT_STARTED — Own MongoDB loading/indexing.
- [ ] NOT_STARTED — Own J1–J8.
- [ ] NOT_STARTED — Own recovery test.
- [ ] NOT_STARTED — Own benchmark pipeline.

---

## Track B — Application & Validation

Primary ownership:

```text
Dashboard
Role/login
Visualization
Integration
Testing
Documentation/demo
```

Tasks:

- [ ] NOT_STARTED — Own Streamlit application.
- [ ] NOT_STARTED — Own dashboard role/scope.
- [ ] NOT_STARTED — Own visualization system.
- [ ] NOT_STARTED — Own integration tests.
- [ ] NOT_STARTED — Own dashboard validation.
- [ ] NOT_STARTED — Own demo/report preparation.

---

## Shared responsibilities

Both members should participate in:

- [ ] NOT_STARTED — Schema review.
- [ ] NOT_STARTED — MVP vertical slice.
- [ ] NOT_STARTED — Architecture decisions.
- [ ] NOT_STARTED — Recovery validation.
- [ ] NOT_STARTED — Full-scale validation.
- [ ] NOT_STARTED — Final presentation/viva.

---

# 19. Dependency Graph

The critical dependency chain is:

```text
Schema
  ↓
Generator
  ↓
MVP Data
  ↓
MongoDB / Parquet
  ↓
Spark J1
  ↓
Spark J2
  ↓
Spark J3
  ↓
J4 / J5 / J6
  ↓
J7 Gold
  ↓
Dashboard
  ↓
End-to-End Validation
  ↓
Full Scale
  ↓
Benchmark / Finalization
```

Some work can proceed in parallel.

For example:

```text
Generator ───────────────┐
                         ├──→ Integration
Dashboard shell ─────────┤
                         │
Mongo schema ────────────┘
```

The dashboard shell does not need to wait for the full dataset, but dashboard analytical values should not be fabricated.

---

# 20. MVP Definition

The MVP is complete when all of the following work together:

```text
One school
+
One semester
+
Synthetic generator
+
MongoDB
+
Parquet
+
Spark cleaning
+
Feature engineering
+
At least core analytics
+
Five-rule risk signals
+
Gold collections
+
Streamlit
+
Dummy login
+
At least one role-aware flow
+
Data-quality reporting
```

The MVP must use actual generated data.

Mock UI data may be used temporarily during interface development, but it must be replaced before the MVP is declared complete.

---

# 21. MVP Gate

Do not scale to the full dataset until the following questions can be answered "yes":

- [ ] Can the dataset be regenerated using the same seed?
- [ ] Are the schemas stable?
- [ ] Can MongoDB load and query the data?
- [ ] Can Spark process it successfully?
- [ ] Can gold collections be produced?
- [ ] Does the dashboard read gold data?
- [ ] Does the five-rule risk indicator work?
- [ ] Can the planted relationships be recovered?
- [ ] Are injected quality problems measurable?
- [ ] Are the main tests passing?

---

# 22. Full-Scale Gate

Before final demonstration:

- [ ] Full target dataset generated.
- [ ] Actual counts recorded.
- [ ] Actual disk usage recorded.
- [ ] Actual MongoDB size recorded.
- [ ] Actual Spark execution times recorded.
- [ ] Peak memory measured where practical.
- [ ] Full gold layer generated.
- [ ] Dashboard tested against full data.
- [ ] Benchmark results captured.
- [ ] Recovery test documented.
- [ ] No critical test failures.

---

# 23. Task Priorities

Use:

```text
P0 = Blocks the entire project
P1 = Required for MVP
P2 = Required for full project
P3 = Enhancement
```

Examples:

### P0

```text
Schema contract
Generator foundation
MongoDB connection
Spark environment
```

### P1

```text
MVP pipeline
Five-rule risk indicator
Gold collections
Dashboard core
```

### P2

```text
Full-scale generation
Benchmarking
Recovery reporting
Advanced analytical views
```

### P3

```text
UI polish
Additional visualizations
Convenience features
```

---

# 24. What Not to Build Before MVP

Do not prioritize the following before the vertical slice works:

- production authentication,
- cloud deployment,
- Kafka,
- streaming,
- ML prediction,
- advanced recommendation systems,
- mobile application,
- complex notification systems,
- unnecessary microservices,
- external institutional integrations.

These are outside the current core scope.

---

# 25. Progress Tracking Rules

When a task is completed:

1. Change its status.
2. Verify the result.
3. Update dependent tasks if unblocked.
4. Update documentation if the implementation changed a requirement.
5. Record significant measured results.

Do not mark a task `DONE` simply because code was written.

---

# 26. Blocker Rules

When blocked, record:

```text
BLOCKER:
Reason:
Affected tasks:
Required decision/action:
```

Examples:

```text
BLOCKER:
MongoDB connection unavailable.

Affected:
P3, P4, P7.

Required:
Restore local MongoDB service.
```

Avoid working around blockers with undocumented architectural changes.

---

# 27. Milestones

## M1 — Repository Ready

```text
Documentation
+
Project structure
+
Configuration foundation
```

## M2 — MVP Data Ready

```text
One school
+
One semester
+
Synthetic data
+
MongoDB
+
Parquet
```

## M3 — MVP Pipeline Ready

```text
Generator
→ Mongo/Parquet
→ Spark
→ Gold
```

## M4 — MVP Dashboard Ready

```text
Login
+
Roles
+
Overview
+
Course
+
Student
+
Risk
```

## M5 — Analytical Validation Ready

```text
Correlation
+
Trends
+
Recovery
+
Data quality
```

## M6 — Full Scale Ready

```text
12k students
+
2 academic years
+
~70M LMS events
```

## M7 — Final Submission Ready

```text
Working system
+
Benchmarks
+
Report
+
Documentation
+
Demo
+
Viva preparation
```

---

# 28. Current Progress Baseline

At the time this roadmap was created:

```text
Documentation foundation:
████████████████████░  mostly established

Repository:
██████████░░░░░░░░░░  foundation established

Implementation:
░░░░░░░░░░░░░░░░░░░░  not yet started in this roadmap

MVP:
░░░░░░░░░░░░░░░░░░░░  not started

Full-scale pipeline:
░░░░░░░░░░░░░░░░░░░░  not started
```

The task statuses in this file should be updated as actual implementation progresses.

---

# 29. Recommended Immediate Execution Order

The next implementation actions should be:

```text
1. Create README.md
2. Create .gitignore
3. Create .env.example
4. Create Python project/package skeleton
5. Create configuration files
6. Freeze schema contract
7. Implement one-school/one-semester generator
8. Validate generated data
9. Load MongoDB
10. Write/read Parquet
11. Implement J1
12. Implement J2
13. Implement J3
14. Implement J4/J5/J6
15. Implement J7
16. Build MVP dashboard
17. Run end-to-end MVP
18. Run recovery/quality validation
19. Implement benchmark framework
20. Scale to full dataset
21. Measure actual resources/performance
22. Finalize report and demo
```

---

# 30. Final Task Rule

The project should always prefer:

```text
Working vertical slice
        >
unfinished collection of modules
```

and:

```text
measured result
        >
assumed result
```

and:

```text
documented decision
        >
silent architectural change
```

and:

```text
explainable analytical signal
        >
unsupported AI prediction
```

---

# 31. Completion Definition

Acadexa is ready for final submission when:

```text
Synthetic data generation is reproducible
        AND
MongoDB and Parquet layers work
        AND
PySpark processes the intended scale
        AND
Gold analytical collections are generated
        AND
Correlation/trend/risk analytics are validated
        AND
Five-rule risk indicators are explainable
        AND
Streamlit dashboard works with dummy login and roles
        AND
Data quality is measured
        AND
Benchmarks are measured
        AND
Ground-truth recovery is documented
        AND
Final documentation/report/demo are complete
```

The target scale is an engineering objective, not a guaranteed number until the actual generator and pipeline have been executed and measured.

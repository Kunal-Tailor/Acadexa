# Acadexa — Coding & Implementation Rules

**Document:** `docs/rules.md`  
**Project:** Acadexa  
**Repository:** `acadexa`  
**Institution model:** RAS University  
**Status:** Working baseline  
**Primary references:** `data.md`, `docs/prd.md`, `docs/architecture.md`, `docs/features.md`, `docs/tech_stack.md`, `docs/folder_structure.md`

---

# 1. Purpose

This document defines the implementation rules for Acadexa.

It is intended for:

- project developers,
- both project team members,
- IDE coding agents,
- code reviewers,
- future maintainers.

The rules exist to keep implementation aligned with the approved product requirements and architecture.

When implementation decisions conflict with these rules, do not silently choose a new direction. Identify the conflict and update the relevant project documentation after the decision is made.

---

# 2. Rule Priority

When deciding how to implement something, use this order:

```text
1. Explicit project-owner decisions
2. Product requirements in prd.md
3. Architecture in architecture.md
4. Feature definitions in features.md
5. Technology constraints in tech_stack.md
6. Repository structure in folder_structure.md
7. These implementation rules
8. Local implementation preference
```

A lower-level implementation preference must not silently override a higher-level project requirement.

---

# 3. Core Project Invariants

The following are architectural/product invariants unless explicitly changed:

1. The university is **RAS University**.
2. The dataset is **fully synthetic**.
3. Real student or institutional data is never required.
4. The target demonstration scale is approximately 12,000 students over two academic years.
5. The target LMS event scale is approximately 70M events.
6. Data generation is seeded and reproducible.
7. MongoDB is the operational and serving database.
8. Full LMS events are stored in Parquet.
9. Only the defined LMS slice is stored in MongoDB.
10. PySpark is the primary large-scale batch-processing engine.
11. Spark runs in local mode for the project.
12. Streamlit is the dashboard layer.
13. Dummy login is required.
14. The dashboard supports the four defined personas.
15. Risk indicators are rule-based.
16. Risk indicators do not predict failure.
17. ML is not part of the core implementation.
18. Kafka is not part of the core implementation.
19. Spark Structured Streaming is not part of the core implementation.
20. The first implementation milestone is a one-school, one-semester vertical slice.
21. Correlation must not be presented as causation.
22. Synthetic analytical results must not be presented as discoveries about real students.

---

# 4. General Coding Principles

## 4.1 Prefer clarity over cleverness

Code should be easy for another team member or IDE agent to understand.

Prefer:

```python
calculate_weekly_engagement(...)
```

over opaque abstractions that make the data flow difficult to follow.

## 4.2 Keep functions focused

A function should have one clear responsibility.

Avoid functions that simultaneously:

- read configuration,
- generate data,
- connect to MongoDB,
- run Spark transformations,
- render UI.

Separate those responsibilities.

## 4.3 Avoid unnecessary abstraction

Do not introduce:

- unnecessary design patterns,
- excessive class hierarchies,
- framework layers,
- dependency injection systems,
- service abstractions,

unless they solve an actual project problem.

## 4.4 Avoid duplication

If the same business rule appears in multiple places, identify a canonical implementation.

Examples:

- risk thresholds,
- attendance calculation,
- ID normalization,
- course hierarchy resolution.

---

# 5. Python Rules

## 5.1 Naming

Use `snake_case` for:

- variables,
- functions,
- modules.

Use `PascalCase` for:

- classes.

Use `UPPER_SNAKE_CASE` for true constants.

Examples:

```python
student_id
calculate_risk_score
StudentFeature
DEFAULT_RISK_THRESHOLD
```

## 5.2 Type hints

Use type hints for reusable functions and important interfaces.

Example:

```python
def calculate_attendance(attended: int, conducted: int) -> float:
    ...
```

Type hints should improve readability, not create unnecessary complexity.

## 5.3 Docstrings

Public/reusable functions should have concise docstrings explaining:

- purpose,
- important inputs,
- output,
- important assumptions.

## 5.4 Error handling

Do not use broad exception handling such as:

```python
except Exception:
    pass
```

unless there is an explicit reason and the error is intentionally handled.

Errors that affect data correctness must be surfaced.

---

# 6. Configuration Rules

Configuration must not be scattered throughout source code.

Centralize configurable values such as:

- university hierarchy,
- generator seed,
- dataset scale,
- school behavior parameters,
- course difficulty,
- data-quality injection rates,
- risk thresholds,
- MongoDB connection settings,
- dummy users.

Do not hard-code project-level thresholds inside unrelated functions.

Bad:

```python
if attendance < 75:
```

Prefer:

```python
if attendance < risk_config.low_attendance_threshold:
```

The exact configuration mechanism may evolve, but the principle remains.

---

# 7. Secrets and Environment Variables

Never commit:

- MongoDB passwords,
- API keys,
- connection credentials,
- private tokens,
- real `.env` files.

Use:

```text
.env
```

for local secrets.

Use:

```text
.env.example
```

for safe placeholders.

Example:

```text
MONGODB_URI=<your-local-or-development-uri>
MONGODB_DATABASE=acadexa
```

Never place actual credentials in:

- Python source,
- YAML/JSON configuration,
- notebooks,
- README,
- documentation,
- tests.

---

# 8. Data Generation Rules

## 8.1 Synthetic data only

Acadexa must not depend on real student or institutional data.

Do not introduce real student datasets into the repository or development workflow.

## 8.2 Seeded generation

The generator must accept/use a deterministic seed.

A developer must be able to reproduce a generation run using the same configuration and seed.

## 8.3 Configuration-driven generation

Schools, departments, programs, courses and behavior parameters should come from configuration.

Do not create one-off generator logic for a particular school when a configuration-driven solution is appropriate.

## 8.4 Chunk large generation

Never attempt to construct the complete ~70M-event LMS dataset as one enormous in-memory pandas/NumPy object.

Generate/write in chunks.

Conceptually:

```text
generate chunk
    ↓
validate chunk
    ↓
write chunk
    ↓
release memory
    ↓
generate next chunk
```

## 8.5 Generation metadata

Generation should retain enough metadata to reproduce and audit the dataset.

At minimum where applicable:

- seed,
- configuration,
- target counts,
- actual counts,
- generation timestamp.

---

# 9. Ground Truth Rules

The synthetic generator intentionally plants relationships.

The project must retain a ground-truth registry describing what was planted.

Do not modify the registry after seeing analytical results in order to make the results appear successful.

The ground truth is established before the recovery analysis.

The recovery test must compare:

```text
what was planted
```

against:

```text
what analytics recovered
```

---

# 10. Data Quality Rules

The generator may intentionally introduce controlled quality problems.

Examples:

- duplicates,
- selected nulls,
- timestamp inconsistencies,
- course-ID casing/whitespace problems,
- orphan records,
- out-of-range values.

## 10.1 Key fields

Key identifiers must not be intentionally nulled.

## 10.2 Manifest

Every injection run should record exact injected counts.

## 10.3 Cleaning traceability

The cleaning pipeline should make it possible to determine:

```text
Injected
Detected
Corrected
Dropped
Remaining
```

Do not silently discard invalid records without documenting the outcome.

---

# 11. Data Schema Rules

The schema defined by the project must remain stable unless a schema change is explicitly approved.

Core collections:

```text
students
courses
academic_records
attendance
coursework
```

Gold collections:

```text
student_features
course_metrics
school_summary
risk_indicators
```

LMS events:

```text
lms_events
```

## Schema-change rule

Before changing:

- field names,
- field meaning,
- grain,
- collection structure,
- data types,

check whether the change affects:

- PRD,
- architecture,
- features,
- Spark jobs,
- dashboard,
- tests,
- documentation.

Do not silently alter the data contract.

---

# 12. Data Grain Rules

Always document and preserve the intended grain.

Examples:

```text
students
→ one document per student

courses
→ one document per course

academic_records
→ student × course × semester

attendance
→ student × course × week

coursework
→ student × coursework item

lms_events
→ one document/event per LMS event
```

Do not accidentally introduce duplicate records at a supposedly unique grain.

---

# 13. Attendance Rules

Attendance is stored using:

```text
classes_conducted
classes_attended
```

Attendance percentage is derived.

Do not treat a stored percentage as the authoritative raw attendance value if the underlying counts are available.

Guard against invalid denominators.

---

# 14. LMS Event Rules

Supported activity types include:

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

Do not introduce arbitrary event types without updating the project data specification.

LMS events should have meaningful timestamps and identifiers.

---

# 15. Parquet Rules

Parquet is the raw landing format for the full LMS event dataset.

Rules:

1. Keep large raw event data in Parquet.
2. Partition data appropriately for processing.
3. Avoid unnecessary duplication of the full dataset.
4. Do not load the entire target dataset into memory merely to write it.
5. Keep raw data separate from processed/gold data.
6. Do not modify raw data in place as a substitute for a cleaning pipeline.

---

# 16. MongoDB Rules

MongoDB is the operational and serving layer.

## 16.1 Responsibilities

MongoDB should handle:

- CRUD,
- indexed queries,
- operational lookups,
- appropriate aggregations,
- time-series LMS slice,
- gold collections,
- dashboard serving.

## 16.2 Full LMS dataset

Do not load all ~70M LMS events into MongoDB simply because MongoDB can technically store them.

The defined MongoDB LMS slice exists to control resource usage and demonstrate practical serving.

## 16.3 Indexes

Indexes should be created for actual query patterns.

Do not create dozens of speculative indexes.

## 16.4 Aggregations

Use MongoDB aggregation when it is appropriate to the workload.

Do not force every calculation into Spark if the project intentionally demonstrates MongoDB aggregation.

Conversely, do not move large cross-domain analytics into MongoDB merely to avoid writing Spark code.

---

# 17. Spark Rules

## 17.1 Spark is the large-scale processing engine

Use PySpark for:

- cleaning,
- deduplication,
- large joins,
- feature engineering,
- event aggregation,
- correlation,
- trend detection,
- risk signals,
- gold publication.

## 17.2 Local mode

Spark must remain executable in local mode under the project's resource constraints.

## 17.3 DataFrames

Prefer Spark DataFrames and Spark SQL functions for structured transformations.

Avoid unnecessary Python-side loops over Spark rows.

## 17.4 Lazy evaluation awareness

Understand Spark's lazy execution model.

Do not trigger unnecessary actions such as:

```python
count()
collect()
show()
```

repeatedly on large datasets.

## 17.5 Avoid `collect()` on large data

Never use `collect()` to bring the complete LMS event dataset or another large analytical dataset into driver memory.

## 17.6 Broadcast joins

Use broadcast joins only when the broadcast side is known to be small enough for the available driver/executor memory.

Do not blindly broadcast large tables.

## 17.7 Caching

Cache/persist only when repeated reuse justifies the memory cost.

Unnecessary caching is prohibited.

---

# 18. Spark Job Rules

The intended sequence is:

```text
J1 Clean and Validate
J2 Event Aggregation
J3 Feature Table
J4 Correlation
J5 Trend Detection
J6 Risk Signals
J7 Publish
J8 Benchmark
```

Each job should have:

- clear inputs,
- clear outputs,
- defined responsibility,
- useful logging,
- controlled failure behavior.

A failed analytical job must not silently produce or publish incomplete gold data.

---

# 19. Spark–MongoDB Rules

When Spark reads from or writes to MongoDB:

1. Use the configured MongoDB/Spark integration.
2. Read only the required fields where practical.
3. Avoid unnecessary full-collection scans.
4. Publish complete/validated analytical outputs.
5. Do not expose MongoDB connection credentials in source code.
6. Verify connector compatibility with the selected Spark/MongoDB versions.

---

# 20. Analytics Rules

## 20.1 Correlation

The project uses correlation as an association measure.

Always use language such as:

```text
associated with
correlated with
observed relationship
```

Do not write:

```text
X causes Y
```

unless a separate causal methodology exists—which is outside the current project.

## 20.2 Within-course normalization

Where required by the specification, values should be normalized within course before correlation to reduce course-difficulty distortion.

## 20.3 Spearman

Spearman is the default correlation measure.

Pearson may be shown alongside it.

Do not silently replace the specified method without documenting why.

---

# 21. Trend Detection Rules

Trend analysis should use the defined temporal logic.

The core engagement comparison uses rolling four-week windows.

The implementation should preserve:

```text
current 4-week period
vs
previous 4-week period
```

A trend flag must be traceable to the underlying measurements.

Do not generate unexplained trend labels.

---

# 22. Risk Indicator Rules

The risk indicator is one of the most important project boundaries.

## 22.1 It is rule-based

The five signals are:

1. Low attendance.
2. LMS decline.
3. Late submissions.
4. Marks decline.
5. Low quiz activity.

Each contributes one point.

## 22.2 It is not ML

Do not introduce:

- classifiers,
- regression models,
- neural networks,
- probability outputs,
- trained risk models,

into the core risk indicator.

## 22.3 It is not failure prediction

Never describe:

```text
3/5 signals
```

as:

```text
70% chance of failure
```

or any equivalent prediction.

## 22.4 It is not a decision engine

The signal count must not automatically:

- fail a student,
- recommend disciplinary action,
- change grades,
- block registration,
- make institutional decisions.

It is an analytical signal.

---

# 23. Dashboard Rules

## 23.1 Streamlit is presentation

Streamlit should retrieve and display processed data.

It should not become the main data-processing engine.

## 23.2 No hard-coded KPIs

Never write:

```python
students = 12000
```

as a dashboard metric.

The dashboard must read actual values from project data.

## 23.3 Hierarchical navigation

Preserve:

```text
University
→ School
→ Department
→ Program
→ Course
→ Student
```

## 23.4 Filters

Filters should narrow data rather than trigger unnecessary full-dataset recomputation.

## 23.5 User-friendly errors

Database or processing failures should result in controlled user-facing errors.

Never show fabricated fallback numbers when the database is unavailable.

---

# 24. Authentication Rules

The login is demonstrational.

It should:

- use configured dummy users,
- resolve a role,
- establish a session,
- determine scope.

It should not claim to be production-grade security.

Do not store plaintext real credentials.

Do not add external authentication infrastructure unless explicitly approved.

---

# 25. Dashboard Role Rules

Supported roles:

```text
University Admin
School / Department Admin
Faculty
Academic Analyst
```

Role logic should be centralized.

Do not duplicate permission conditions throughout every page.

Conceptually:

```text
authenticated user
        ↓
role
        ↓
scope
        ↓
allowed capabilities
```

---

# 26. Dashboard Data Access Rules

The dashboard should primarily consume:

```text
MongoDB gold collections
+
MongoDB operational data
+
defined LMS slice
```

Do not make every dashboard page read raw Parquet directly.

Do not make every page start a Spark job.

---

# 27. UI/UX Implementation Rules

The exact visual direction belongs in `design.md`.

Until then:

- prioritize clarity,
- preserve hierarchy,
- avoid dashboard clutter,
- make filters understandable,
- show units and time periods,
- label analytical values,
- distinguish raw metrics from derived signals,
- make risk indicators explainable.

Do not add visual elements merely for decoration.

---

# 28. Testing Rules

Every important business rule should have a verification path.

Prioritize tests for:

- seeded generation,
- schema correctness,
- attendance calculations,
- data-quality injection,
- cleaning,
- risk signals,
- feature calculations,
- critical MongoDB queries,
- recovery logic.

## Risk rule tests

Each risk signal should have:

```text
positive case
negative case
boundary case
```

where practical.

Example:

```text
attendance = 74.99%
attendance = 75%
attendance = 75.01%
```

Threshold behavior must be explicit.

---

# 29. Integration Testing

Integration tests should verify important boundaries such as:

```text
Generator → Parquet
Generator → MongoDB
MongoDB → Spark
Parquet → Spark
Spark → MongoDB
MongoDB → Dashboard data layer
```

Use small fixtures.

Do not use the full 70M-event dataset for ordinary test execution.

---

# 30. Benchmark Rules

Benchmark results must be measured.

Do not manufacture or pre-select results to make Spark appear superior.

If pandas is faster for a workload, record it.

If MongoDB is better suited to a query, record it.

The purpose of benchmarking is to demonstrate:

```text
where each tool fits
```

not to prove a predetermined winner.

Record enough context to make measurements interpretable:

- dataset size,
- workload,
- environment,
- execution time,
- memory where practical.

---

# 31. Recovery-Test Rules

The ground-truth recovery test must remain independent from the generator's ground-truth declaration.

Do not modify expected relationships after inspecting analytical results.

The test should distinguish:

```text
planted
recovered
not recovered
decoy
```

where appropriate.

---

# 32. Data Quality Rules for Reporting

Reports must distinguish:

```text
Injected problems
Detected problems
Corrected problems
Dropped problems
Remaining problems
```

Do not report detected counts as if they were the exact injected counts unless the comparison confirms that.

---

# 33. Logging Rules

Use structured/clear application logging where practical.

Important events to log include:

- generation start/end,
- seed,
- target volume,
- actual counts,
- Spark job start/end,
- database connection failures,
- validation results,
- publication status,
- benchmark start/end.

Do not log:

- passwords,
- credentials,
- full connection strings containing secrets,
- unnecessary millions of individual LMS events.

---

# 34. Performance Rules

The implementation must respect the local resource budget.

Target:

```text
24 GB system RAM
~10–12 GB intended project usage
```

Avoid:

- unnecessary data duplication,
- large Python lists,
- full-dataset `collect()`,
- unnecessary caching,
- repeated full scans,
- loading the complete LMS dataset into MongoDB,
- loading the complete LMS dataset into pandas.

Measure actual performance before optimizing based on assumptions.

---

# 35. File Placement Rules

Follow `folder_structure.md`.

General rule:

```text
docs/        → project knowledge
config/      → non-secret configuration
src/         → application implementation
scripts/     → execution entry points
tests/       → tests
data/        → generated/local data
reports/     → generated analytical outputs
logs/        → runtime logs
notebooks/   → exploration
```

Do not create duplicate implementations simply because another directory seems convenient.

---

# 36. Notebook Rules

Notebooks are for exploration.

Do not make the final production-style pipeline dependent on:

```text
Run notebook A
then notebook B
then notebook C
```

If notebook logic becomes required application functionality, move it into `src/acadexa/`.

---

# 37. Documentation Rules

When a change affects:

- product scope,
- architecture,
- features,
- technology,
- folder structure,
- UI behavior,
- project tasks,

update the relevant documentation.

Do not allow the codebase and documentation to diverge silently.

---

# 38. Agent Context Rules

An IDE agent working on Acadexa should:

1. Read the relevant documentation before making major changes.
2. Respect `prd.md` for product requirements.
3. Respect `architecture.md` for component boundaries.
4. Respect `features.md` for feature behavior.
5. Respect `tech_stack.md` for technology choices.
6. Respect `folder_structure.md` for file placement.
7. Use `memory.md` for persistent project context.
8. Check `tasks.md` before selecting implementation work.
9. Avoid inventing unspecified requirements.
10. Ask for clarification when a decision materially changes scope.

---

# 39. Agent Must Not

An IDE agent must not silently:

- add Kafka,
- add Structured Streaming,
- add ML risk prediction,
- use real student data,
- change RAS University,
- replace MongoDB with another database,
- replace Spark with a different Big Data engine,
- replace Streamlit with another dashboard framework,
- move all LMS events into MongoDB,
- turn the risk score into a failure prediction,
- present correlation as causation,
- hard-code dashboard KPIs,
- commit secrets,
- commit the full generated dataset,
- restructure the repository without reason,
- introduce dependencies without checking the technology documentation.

---

# 40. Change Management Rules

Before making a significant architectural or product change, identify:

```text
What changes?
Why?
Which document is affected?
Which code is affected?
Which tests are affected?
Does the resource budget change?
```

Examples of changes requiring explicit review:

- changing database,
- changing dashboard framework,
- adding streaming,
- adding ML,
- changing data grain,
- changing risk rules,
- changing target scale,
- changing university hierarchy,
- adding real data,
- changing the first milestone.

---

# 41. Backward Compatibility Within the Project

When changing schemas or APIs:

1. Identify consumers.
2. Update affected code.
3. Update tests.
4. Update documentation.
5. Regenerate affected synthetic data if necessary.
6. Verify the dashboard.

Do not make isolated schema changes that break downstream Spark jobs or dashboard queries.

---

# 42. Code Review Checklist

Before considering a significant change complete, verify:

### Scope

- [ ] Does it belong to the approved project scope?
- [ ] Does it preserve the core architecture?

### Code

- [ ] Clear naming?
- [ ] Focused functions?
- [ ] No unnecessary abstraction?
- [ ] Type hints where useful?
- [ ] Errors handled appropriately?

### Data

- [ ] Correct grain?
- [ ] Correct schema?
- [ ] No silent data loss?
- [ ] No accidental large-memory operation?

### Spark

- [ ] No unnecessary `collect()`?
- [ ] No unnecessary actions?
- [ ] No inappropriate caching?
- [ ] Reasonable joins?

### MongoDB

- [ ] Query pattern understood?
- [ ] Appropriate indexes?
- [ ] No unnecessary full scans?
- [ ] No unnecessary LMS data loading?

### Dashboard

- [ ] No hard-coded KPI?
- [ ] Correct role/scope?
- [ ] Controlled errors?
- [ ] Explainable analytical output?

### Security

- [ ] No credentials committed?
- [ ] No secrets in logs?
- [ ] `.env` ignored?

### Documentation

- [ ] Relevant documentation updated?
- [ ] New dependency documented?
- [ ] New architectural decision documented?

---

# 43. Definition of Done

A code change is considered complete when:

1. The requested behavior works.
2. The implementation follows the architecture.
3. The correct folder owns the code.
4. Relevant tests pass.
5. No known data-contract violations exist.
6. No secrets are introduced.
7. Resource behavior is reasonable.
8. Relevant documentation is updated.
9. The change does not silently expand project scope.

---

# 44. Minimal-Change Principle

When fixing a bug or implementing a feature:

> Make the smallest clean change that satisfies the requirement.

Do not rewrite unrelated parts of the project merely because they could be improved.

If a broader refactor is necessary, explain why and treat it as a separate architectural decision.

---

# 45. No Fake Completion

The project must not claim a feature is complete when only:

- a UI placeholder exists,
- mock values are displayed,
- a function is stubbed,
- a hard-coded result is shown,
- an unexecuted pipeline exists.

A feature is complete when its actual underlying behavior works and can be verified.

---

# 46. No Silent Scope Expansion

If an implementation idea introduces a capability that was not part of the approved scope:

```text
identify it
→ classify it
→ discuss it
→ document it
→ then implement if approved
```

Do not silently turn future scope into core scope.

---

# 47. Academic Integrity Rule

Acadexa is an academic Big Data project.

Documentation, demonstrations and reports must accurately distinguish:

```text
synthetic ground truth
actual measured results
engineering estimates
assumptions
future work
```

Do not present:

- generated relationships as real-world discoveries,
- estimated scale as measured scale,
- simulated risk signals as predictions,
- benchmark assumptions as benchmark results.

---

# 48. Final Implementation Constitution

The central implementation principle is:

> **Build the smallest correct system that demonstrates the approved Acadexa architecture, then scale and deepen it without violating its boundaries.**

The project should prioritize:

```text
Correctness
    ↓
Reproducibility
    ↓
Architectural clarity
    ↓
Measured performance
    ↓
Analytical depth
    ↓
UI refinement
```

rather than adding complexity for its own sake.

---

# 49. Canonical Rules Statement

> Acadexa must be implemented as a reproducible, synthetic-data-only, local Big Data analytics system using Python, MongoDB, Parquet, PySpark and Streamlit within the documented architecture. Code must preserve the defined data contracts, processing boundaries, role model, five-rule risk indicator and batch-processing scope. Large data must be handled in memory-conscious ways, analytical claims must remain explainable and non-causal, secrets and large generated datasets must remain outside version control, and significant changes must be explicitly reflected in the project's documentation rather than introduced silently.

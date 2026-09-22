# Acadexa — Repository Folder Structure

**Document:** `docs/folder_structure.md`  
**Project:** Acadexa  
**Repository:** `acadexa`  
**Local project folder:** `acadexa`  
**Institution model:** RAS University  
**Status:** Working baseline  
**Primary references:** `data.md`, `docs/prd.md`, `docs/architecture.md`, `docs/features.md`, `docs/tech_stack.md`

---

# 1. Purpose

This document defines the canonical repository structure for Acadexa.

Its purpose is to ensure that:

- source code has predictable locations,
- documentation remains centralized,
- generated data is separated from source code,
- configuration is separated from implementation,
- Spark jobs remain organized,
- dashboard code remains independent,
- tests have a consistent location,
- IDE agents know where new files belong,
- generated artifacts are not accidentally committed to GitHub.

The structure is designed around the current Acadexa architecture:

```text
Synthetic Generator
        ↓
Parquet + MongoDB
        ↓
PySpark
        ↓
Gold MongoDB collections
        ↓
Streamlit
```

---

# 2. Canonical Repository Layout

The intended repository structure is:

```text
acadexa/
│
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── requirements.txt / pyproject.toml
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
│       ├── __init__.py
│       │
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

The exact presence of optional directories may evolve during implementation, but the ownership boundaries defined below should remain stable.

---

# 3. Root Directory

The repository root contains project-level files only.

```text
acadexa/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── requirements.txt / pyproject.toml
└── ...
```

## Root-level responsibilities

### `README.md`

Public project introduction.

Should contain:

- project overview,
- problem statement,
- architecture summary,
- technology stack,
- setup instructions,
- project scope,
- screenshots when available,
- run instructions,
- documentation links.

It should not duplicate every detail from `docs/`.

### `LICENSE`

Defines repository licensing.

The final license should be selected explicitly rather than assumed.

### `.gitignore`

Prevents generated/runtime/secrets from entering Git.

At minimum, it should cover:

```text
.env
__pycache__/
*.pyc
.venv/
venv/
logs/
large generated data
local database/runtime files
IDE files
temporary files
```

The exact rules should be finalized with the implementation.

### `.env.example`

Documents environment variables required by local development without containing real credentials.

Possible categories:

```text
MongoDB connection
database name
environment mode
dashboard configuration
```

### `requirements.txt` / `pyproject.toml`

Defines the Python environment.

Only one dependency-management approach should become canonical.

---

# 4. `docs/`

`docs/` is the **project reference layer**.

It contains the textual and architectural information that humans and IDE agents use to understand how Acadexa should be built.

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

## Important rule

`docs/` is not the location for application source code.

Do not place Python implementation files inside `docs/`.

---

# 5. Documentation Responsibilities

## `prd.md`

Defines:

```text
WHAT Acadexa must be
```

Contains:

- product goals,
- users,
- requirements,
- constraints,
- scope,
- success criteria.

## `architecture.md`

Defines:

```text
HOW the system is structured
```

Contains:

- components,
- data flow,
- system boundaries,
- storage architecture,
- processing architecture.

## `rules.md`

Defines:

```text
HOW implementation should be performed
```

Contains:

- coding rules,
- naming rules,
- data rules,
- architecture rules,
- testing rules,
- agent behavior.

## `design.md`

Defines:

```text
HOW the dashboard should look and behave
```

Contains:

- visual direction,
- navigation,
- layout,
- components,
- interaction patterns,
- accessibility guidance.

## `tasks.md`

Defines:

```text
WHAT is being built now
```

Contains:

- phases,
- tasks,
- status,
- owners,
- dependencies,
- progress.

## `memory.md`

Defines:

```text
WHAT an IDE agent should remember between implementation sessions
```

Contains concise persistent project context.

It should not become a duplicate of every other document.

## `folder_structure.md`

Defines:

```text
WHERE things belong
```

This document.

## `tech_stack.md`

Defines:

```text
WHICH technologies are allowed/used
```

## `features.md`

Defines:

```text
WHAT capabilities the application provides
```

---

# 6. `config/`

The `config/` directory contains project configuration that should not be scattered through application source code.

```text
config/
├── university/
├── generator/
├── dashboard/
└── risk/
```

## `config/university/`

Contains configuration for:

- schools,
- departments,
- programs,
- courses,
- academic structure.

The university model is configuration-driven.

## `config/generator/`

Contains:

- generator seed,
- target volume,
- event-generation parameters,
- behavioral parameters,
- data-quality injection settings.

## `config/dashboard/`

Contains non-secret dashboard configuration such as:

- navigation configuration,
- dashboard display settings,
- dummy-user definitions if appropriate,
- environment-specific presentation settings.

## `config/risk/`

Contains:

- risk signal thresholds,
- signal configuration,
- rule metadata.

Risk thresholds should not be duplicated throughout Python source files.

---

# 7. `src/`

`src/` contains the actual application and library source code.

```text
src/
└── acadexa/
```

The Python package should use the project namespace:

```text
acadexa
```

This creates a clean boundary between repository files and Python implementation.

---

# 8. `src/acadexa/`

The package is divided by architectural responsibility.

```text
src/acadexa/
├── __init__.py
├── config/
├── generator/
├── database/
├── processing/
├── analytics/
├── dashboard/
├── validation/
├── benchmarks/
└── utils/
```

---

# 9. `src/acadexa/config/`

### Responsibility

Configuration loading and validation.

Possible responsibilities:

- read configuration files,
- load environment variables,
- validate required configuration,
- expose typed/normalized configuration to other modules.

### Must not

Contain:

- business analytics,
- dashboard rendering,
- database-specific logic unrelated to configuration.

---

# 10. `src/acadexa/generator/`

### Responsibility

Synthetic data generation.

Possible modules:

```text
generator/
├── __init__.py
├── university.py
├── students.py
├── courses.py
├── academic_records.py
├── attendance.py
├── coursework.py
├── lms_events.py
├── ground_truth.py
├── quality_injection.py
└── orchestrator.py
```

These names are guidance, not mandatory file names.

### Generator owns

- synthetic entities,
- event generation,
- seeded randomness,
- planted relationships,
- data-quality injection,
- generation metadata.

### Generator does not own

- Streamlit pages,
- Spark analytical jobs,
- dashboard presentation.

---

# 11. `src/acadexa/database/`

### Responsibility

MongoDB interaction and database infrastructure.

Possible structure:

```text
database/
├── __init__.py
├── client.py
├── collections.py
├── indexes.py
├── queries.py
├── aggregations.py
├── timeseries.py
└── repositories/
```

### Owns

- MongoDB client setup,
- collection definitions,
- indexes,
- operational queries,
- aggregations,
- time-series configuration,
- data-loading utilities.

### Does not own

Large-scale Spark processing.

---

# 12. `src/acadexa/processing/`

### Responsibility

PySpark processing pipeline.

Possible structure:

```text
processing/
├── __init__.py
├── spark_session.py
├── jobs/
│   ├── clean_validate.py
│   ├── event_aggregation.py
│   ├── feature_table.py
│   ├── correlation.py
│   ├── trend_detection.py
│   ├── risk_signals.py
│   └── publish_gold.py
└── common/
```

The project-defined job sequence is:

```text
J1 clean and validate
J2 event aggregation
J3 feature table
J4 correlation
J5 trend detection
J6 risk signals
J7 publish
J8 benchmark
```

The exact module layout can be adjusted during implementation, but responsibilities must remain clear.

---

# 13. `src/acadexa/analytics/`

### Responsibility

Reusable analytical logic that is conceptually separate from Spark job orchestration.

Possible areas:

```text
analytics/
├── correlation.py
├── trends.py
├── risk.py
├── metrics.py
└── ground_truth.py
```

This layer may contain:

- analytical formulas,
- threshold logic,
- interpretation helpers,
- recovery-test logic,
- metric definitions.

Avoid duplicating business rules between:

```text
analytics/
```

and:

```text
processing/jobs/
```

Where a calculation is a core domain rule, establish one canonical implementation.

---

# 14. `src/acadexa/dashboard/`

### Responsibility

Streamlit application.

Possible structure:

```text
dashboard/
├── __init__.py
├── app.py
├── auth.py
├── session.py
├── navigation.py
├── permissions.py
├── pages/
│   ├── university.py
│   ├── school.py
│   ├── department.py
│   ├── program.py
│   ├── course.py
│   ├── student.py
│   ├── analysis.py
│   ├── data_quality.py
│   └── benchmarks.py
├── components/
│   ├── kpis.py
│   ├── charts.py
│   ├── tables.py
│   └── filters.py
└── services/
```

The exact page organization can change as the Streamlit implementation evolves.

### Dashboard owns

- login interface,
- session state,
- navigation,
- role-aware views,
- charts,
- tables,
- filters,
- user-facing errors.

### Dashboard does not own

- full-scale Spark computation,
- raw 70M-event processing,
- core data generation.

---

# 15. `src/acadexa/validation/`

### Responsibility

Project validation.

Possible modules:

```text
validation/
├── __init__.py
├── schema.py
├── data_quality.py
├── recovery.py
├── consistency.py
└── manifests.py
```

Responsibilities:

- schema validation,
- generated-data checks,
- injection-vs-detection comparison,
- ground-truth recovery testing,
- consistency checks.

---

# 16. `src/acadexa/benchmarks/`

### Responsibility

Performance measurement.

Possible structure:

```text
benchmarks/
├── __init__.py
├── pandas/
├── mongodb/
├── spark/
├── runner.py
└── report.py
```

Benchmark code should remain isolated from the main production-style processing pipeline.

The benchmark must use comparable workloads.

---

# 17. `src/acadexa/utils/`

### Responsibility

Small reusable utilities that do not belong to another architectural module.

Possible examples:

- logging helpers,
- date utilities,
- ID normalization,
- file helpers,
- timing utilities.

Do not turn `utils/` into a dumping ground.

If a utility has a clear domain owner, place it there instead.

---

# 18. `scripts/`

The `scripts/` directory contains explicit command-line entry points for common project operations.

Example:

```text
scripts/
├── generate_data.py
├── load_mongodb.py
├── run_pipeline.py
├── publish_gold.py
└── run_benchmarks.py
```

### `generate_data.py`

Starts the synthetic generation process.

### `load_mongodb.py`

Loads the required generated datasets into MongoDB.

### `run_pipeline.py`

Runs the Spark processing pipeline.

### `publish_gold.py`

May be used when gold publication needs a separate explicit operation.

### `run_benchmarks.py`

Runs the benchmark suite.

Scripts should call reusable functionality from `src/acadexa/`.

They should not contain the entire implementation themselves.

---

# 19. `tests/`

Tests are separated from application source.

```text
tests/
├── unit/
├── integration/
├── data/
└── fixtures/
```

## `tests/unit/`

Tests isolated functions and components.

Examples:

- risk rules,
- configuration parsing,
- ID normalization,
- generator calculations.

## `tests/integration/`

Tests component interaction.

Examples:

- generator → Parquet,
- loader → MongoDB,
- Spark → MongoDB,
- dashboard data services.

## `tests/data/`

Contains small test datasets and expected analytical outputs.

These must remain small.

Do not store the complete 70M-event dataset here.

## `tests/fixtures/`

Reusable test objects and fixtures.

---

# 20. `data/`

The `data/` directory contains generated/local datasets.

```text
data/
├── raw/
├── processed/
├── generated/
├── manifests/
└── samples/
```

The exact generated-data strategy may evolve, but the conceptual separation must remain.

---

# 21. `data/raw/`

Contains raw generated data before processing.

Examples:

```text
raw/
└── lms_events/
    └── year=.../
        └── month=.../
```

The complete LMS event dataset belongs conceptually here.

Because the target dataset is large, this directory should normally be ignored by Git.

---

# 22. `data/generated/`

Contains generator outputs that are not necessarily raw event landing data.

Possible examples:

- generated CSV/JSON subsets,
- generated metadata,
- local development outputs.

Large generated files should not be committed.

---

# 23. `data/processed/`

Contains local processed/intermediate datasets.

Examples:

- cleaned samples,
- aggregated development outputs,
- temporary analytical datasets.

Large intermediate outputs should generally remain outside Git.

---

# 24. `data/manifests/`

Contains metadata describing generated data.

Examples:

```text
generation_manifest.json
injection_manifest.json
dataset_metadata.json
```

These files are important for reproducibility.

Small manifests may be committed if they contain no secrets and are useful as project artifacts.

---

# 25. `data/samples/`

Contains small representative datasets for:

- development,
- unit tests,
- dashboard prototyping,
- documentation examples.

Samples should be intentionally small.

They must not be confused with the full target dataset.

---

# 26. `reports/`

The `reports/` directory contains generated analytical/reporting artifacts.

```text
reports/
├── quality/
├── benchmarks/
├── recovery/
└── exports/
```

## `reports/quality/`

Contains:

- data-quality reports,
- injected-vs-detected comparisons.

## `reports/benchmarks/`

Contains:

- timing results,
- memory results,
- benchmark tables.

## `reports/recovery/`

Contains:

- planted-relationship recovery results,
- decoy relationship results.

## `reports/exports/`

Contains generated exports intended for reports/presentations where appropriate.

These are generated artifacts, not source code.

---

# 27. `logs/`

Contains local runtime logs.

Examples:

```text
logs/
├── generator.log
├── spark/
└── dashboard.log
```

Logs should generally be excluded from Git unless a small sanitized example is intentionally documented.

Do not commit logs containing:

- credentials,
- connection strings,
- sensitive environment information.

---

# 28. `notebooks/`

Notebooks are optional exploratory artifacts.

```text
notebooks/
└── exploratory/
```

They may be used for:

- data exploration,
- visualization experiments,
- debugging,
- academic analysis.

### Important rule

The final production-style pipeline should not depend on manually executing notebooks.

If notebook logic becomes part of the product, move the logic into `src/acadexa/`.

---

# 29. Data vs Source Separation

The repository must maintain a clear distinction:

```text
SOURCE CODE
src/
scripts/
tests/

CONFIGURATION
config/

DOCUMENTATION
docs/

GENERATED DATA
data/

REPORT OUTPUTS
reports/

RUNTIME OUTPUTS
logs/
```

This distinction is mandatory for maintainability.

---

# 30. What Should Be Committed to GitHub

Generally commit:

```text
README.md
LICENSE
.gitignore
.env.example
dependency manifest
docs/
src/
scripts/
tests/
config/
small test/sample data
small manifests
```

Do not commit by default:

```text
.env
large Parquet datasets
~70M LMS events
large generated MongoDB exports
logs
temporary files
local virtual environments
cache files
IDE metadata
```

The exact `.gitignore` should reflect these boundaries.

---

# 31. Generated Data Policy

The target dataset is intentionally large.

Therefore:

```text
Source repository
        ≠
Full generated dataset
```

The GitHub repository should contain the machinery needed to generate the dataset rather than necessarily containing the complete generated dataset.

Small sample datasets may be committed where useful.

---

# 32. MongoDB Data Policy

MongoDB itself is an external/local runtime service rather than a directory inside the repository.

Do not create a repository directory that attempts to imitate a MongoDB data directory.

Instead, the repository should contain:

```text
database/
```

code/configuration and scripts for MongoDB operations.

Actual MongoDB database files belong to the MongoDB runtime environment.

---

# 33. Configuration vs Secrets

Configuration belongs in:

```text
config/
```

Secrets belong in:

```text
.env
```

The repository may contain:

```text
.env.example
```

but must not contain real credentials.

Example:

```text
config/
    non-secret project configuration

.env
    local secrets / connection strings

.env.example
    required variable names and safe placeholders
```

---

# 34. Naming Conventions

Use:

### Directories

Lowercase with underscores where required:

```text
data_quality
risk_signals
```

or simple lowercase names:

```text
generator
database
dashboard
```

### Python files

Lowercase `snake_case`:

```text
risk_signals.py
event_aggregation.py
mongo_client.py
```

### Documentation

Lowercase `snake_case`:

```text
folder_structure.md
tech_stack.md
```

### Data artifacts

Use predictable names with clear semantic meaning.

Avoid ambiguous names such as:

```text
final.csv
new_final.csv
final2.csv
```

Prefer:

```text
student_features_2025_s1.parquet
```

where appropriate.

---

# 35. Where New Files Should Go

Before creating a file, determine its responsibility.

| If the file is for... | Put it in... |
|---|---|
| Product requirements | `docs/` |
| Architecture | `docs/` |
| Coding rules | `docs/` |
| UI/UX specification | `docs/` |
| Project context | `docs/` |
| Source Python code | `src/acadexa/` |
| Command-line entry point | `scripts/` |
| Tests | `tests/` |
| University configuration | `config/university/` |
| Generator configuration | `config/generator/` |
| Risk configuration | `config/risk/` |
| Dashboard configuration | `config/dashboard/` |
| Raw generated data | `data/raw/` |
| Generated datasets | `data/generated/` |
| Intermediate datasets | `data/processed/` |
| Metadata/manifests | `data/manifests/` |
| Small sample data | `data/samples/` |
| Quality reports | `reports/quality/` |
| Benchmark reports | `reports/benchmarks/` |
| Recovery results | `reports/recovery/` |
| Runtime logs | `logs/` |
| Exploration notebooks | `notebooks/exploratory/` |

---

# 36. Folder Ownership Rules

## `docs/`

Owns project knowledge.

## `config/`

Owns non-secret project configuration.

## `src/`

Owns reusable application implementation.

## `scripts/`

Owns execution entry points.

## `tests/`

Owns automated verification.

## `data/`

Owns generated/local data.

## `reports/`

Owns generated analytical/report artifacts.

## `logs/`

Owns runtime logs.

## `notebooks/`

Owns optional exploratory work.

No directory should silently take responsibility from another layer.

---

# 37. MVP Repository Structure

The first vertical slice does not need every final directory populated.

The minimum useful implementation can begin with:

```text
acadexa/
├── README.md
├── .gitignore
├── .env.example
│
├── docs/
│   ├── prd.md
│   ├── architecture.md
│   ├── features.md
│   ├── tech_stack.md
│   ├── folder_structure.md
│   ├── rules.md
│   ├── design.md
│   ├── tasks.md
│   └── memory.md
│
├── config/
│   ├── university/
│   ├── generator/
│   └── risk/
│
├── src/
│   └── acadexa/
│       ├── generator/
│       ├── database/
│       ├── processing/
│       ├── analytics/
│       ├── dashboard/
│       └── validation/
│
├── scripts/
│   ├── generate_data.py
│   └── run_pipeline.py
│
├── tests/
│   ├── unit/
│   └── fixtures/
│
└── data/
    └── samples/
```

As the project scales, add the remaining directories rather than prematurely filling the repository with unused files.

---

# 38. Full-Scale Repository Structure

After the MVP is stable:

```text
acadexa/
│
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── requirements.txt / pyproject.toml
│
├── docs/
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

---

# 39. IDE Agent Rules for File Placement

When an IDE agent creates or modifies a file:

1. Check `folder_structure.md`.
2. Identify the file's responsibility.
3. Place it under the corresponding ownership directory.
4. Do not create duplicate implementations in multiple directories.
5. Do not place source code inside `docs/`.
6. Do not place secrets inside `config/`.
7. Do not place large generated data inside `src/`.
8. Do not place production logic only inside notebooks.
9. Prefer modifying an existing appropriate module over creating a duplicate module.
10. Update documentation when a genuinely new architectural directory is required.

---

# 40. Anti-patterns

Avoid structures such as:

```text
src/
    everything.py
```

```text
scripts/
    entire_application.py
```

```text
dashboard/
    spark_pipeline.py
```

```text
docs/
    Python source files
```

```text
data/
    source code
```

```text
notebooks/
    only implementation of the final pipeline
```

```text
utils/
    unrelated business logic
```

The folder structure should communicate architecture rather than obscure it.

---

# 41. Repository Growth Strategy

Acadexa should grow in stages.

### Stage 1 — Vertical Slice

```text
Generate
→ Store
→ Process
→ Publish
→ Dashboard
```

### Stage 2 — Analytical Depth

Add:

- correlation,
- trend detection,
- risk signals,
- quality validation.

### Stage 3 — Scale

Expand to:

```text
6 schools
12,000 students
4 semesters
~70M LMS events
```

### Stage 4 — Benchmark and Validate

Add:

- pandas benchmark,
- MongoDB benchmark,
- Spark benchmark,
- recovery tests,
- data-quality comparisons.

### Stage 5 — Documentation and Academic Packaging

Finalize:

- report,
- diagrams,
- screenshots,
- benchmark tables,
- viva material.

The repository structure should support this progression without major reorganization.

---

# 42. Relationship to Other Documentation

```text
prd.md
   ↓
architecture.md
   ↓
tech_stack.md
   ↓
folder_structure.md
   ↓
rules.md
   ↓
tasks.md
```

`features.md` defines capabilities across this structure.

`design.md` defines the dashboard presentation.

`memory.md` stores concise persistent context for IDE agents.

This file specifically answers:

> **Where should each project artifact live?**

---

# 43. Canonical Folder Structure Statement

> Acadexa uses a layered repository structure in which `docs/` contains project knowledge, `config/` contains non-secret configuration, `src/acadexa/` contains reusable application code separated by architectural responsibility, `scripts/` contains execution entry points, `tests/` contains verification, `data/` contains generated/local datasets, `reports/` contains generated analytical outputs, `logs/` contains runtime artifacts, and `notebooks/` contains optional exploratory work. Large generated datasets such as the target LMS event volume are not treated as source-controlled application files.

# IDE Context — Acadexa Full Session Record (Task 0.1 → 4.9)

**Document:** `docs/IDE_Context.md`
**Purpose:** Complete, self-contained working context for any human developer or IDE agent resuming this project.
**Created by:** Task 4.9 (`Update - 4.9 - add IDE context documentation`)
**Snapshot date:** 2026-09-25
**Repository:** `D:\College\Secondary\Projects\acadexa`, branch `main`
**State at snapshot:** Tasks 0.1 → 4.8 committed (30 commits); test suite **219 passed**; task 4.9 = this file.

> **How to use this file:** Read Sections 1–4 before touching any code (they define the non-negotiables,
> the environment, and the working protocol). Section 5 is the full task-by-task execution history.
> Section 6–8 describe the current system, calibration numbers, and test suite. Sections 9–11 cover
> what works, what doesn't, session gotchas, and what comes next. When a future task prompt says
> "Proceed with task X from docs/TASKS.md", this file is the memory you read first.

---

## 1. Project in One Screen — Non-Negotiables

**Acadexa** = synthetic-data-only Big Data learning-analytics platform for fictional **RAS University**
(6 schools, ~18 departments, ~40 programs, ~250 courses, ~12,000 students, 2 academic years / 4 semesters,
~70M LMS events). Final-year Big Data Technologies academic project.

Pipeline: `Synthetic generator (Python/NumPy) → Parquet + MongoDB → PySpark local (J1–J8) → Gold collections → Streamlit dashboard`.

Hard rules (from `docs/rules.md`, `docs/prd.md`, `docs/memory.md`, `docs/tasks.md`):

1. **One task at a time**, top to bottom. Never bundle later tasks, never scaffold future tasks, never self-advance.
2. **The agent never runs `git commit`** — stop, mark the task `[x]` in `docs/tasks.md`, tell the user it is ready; the user reviews the diff and commits manually with message `Update - <Phase>.<Task> - <description>`.
3. **100% synthetic data.** No real student data. Always disclose synthetic nature.
4. **Frozen schemas** (`src/acadexa/validation/schema.py`, rules.md §11) — never add fields (e.g., decliner flags and behavioral traits are hidden generator state, never written to student documents).
5. **Reproducibility:** same seed + same config ⇒ byte-identical output (rules.md §8.2). All randomness flows through `GeneratorRun.child_rng("<name>")` deterministic sub-streams.
6. **Configuration-driven:** no hard-coded behavioral values; everything lives in `config/**/*.toml`. Validation exists at two layers: `ConfigurationError` (config loading, `src/acadexa/config/validation.py`) and `GeneratorError` (generator runtime, fail-fast `_check()`).
7. **No ML prediction, no streaming/Kafka, no causal language** ("associated with", never "causes"). Risk = exactly five rule-based signals, output 0–5 observed signals.
8. **Correlation method:** Spearman default; Pearson optional (task 8.5, not started).
9. **MVP hard gate:** one school + one semester end-to-end before full-scale generation (Phase 10 checkpoint).
10. **Never commit** `.env`, generated datasets, Parquet, logs, caches.
11. **LMS storage split:** full LMS → Parquet; only a defined serving slice → MongoDB. Never load 70M events into MongoDB.
12. **No large Spark `collect()`**, no premature optimization, no permanent mock dashboard numbers.

Documentation rule priority (highest wins): **owner decisions > `prd.md` > `architecture.md` > `features.md` > `tech_stack.md` > `folder_structure.md` > `rules.md` > local preference.**
Docs are consulted contextually per task, not re-read fully every time.

---

## 2. Environment & Toolchain

| Item | Value |
|---|---|
| OS / shell | Windows 11 (`win32`), PowerShell 5.1 |
| Python | 3.11.9 (stdlib `tomllib` for TOML — no third-party TOML lib) |
| pytest | 8.3.5, config in `pytest.ini` |
| Git branch | `main` |
| Test command | `$env:PYTHONPATH='src'; python -m pytest -q` from project root |
| Targeted run | `$env:PYTHONPATH='src'; python -m pytest tests/unit/test_X.py -q --tb=short` |
| Full-suite runtime | ~3 min (189–193 s; varies with machine load) |
| Temp probe scripts | `C:\Users\Rishav\AppData\Local\Temp\opencode\` (pre-approved scratch dir; probe files like `probe48.py` live here, never in repo) |
| Dependencies | `requirements.txt` (minimal, Phase 1.8 — no speculative libraries) |

**PowerShell gotchas (learned the hard way):**
- Nested f-string quotes break PowerShell parsing → write calibration probes as temp `.py` files and run them, instead of `python -c "..."`.
- Use `; if ($?) { ... }` to chain, not `&&`.
- `PYTHONPATH` must be set per command (`$env:PYTHONPATH='src'`), tests are not installed as a package.

**Repository layout (root):** `config/` `data/` `docs/` `logs/` `notebooks/` `reports/` `scripts/` `src/` `tests/`, plus `.env.example`, `.gitignore`, `pytest.ini`, `README.md`, `requirements.txt`.
Generated data dirs contain only `.gitkeep`.

---

## 3. Documentation Map (`docs/`)

| File | Role |
|---|---|
| `prd.md` | What the product must accomplish (requirements) |
| `architecture.md` | How the system is structured |
| `tech_stack.md` | Which technologies and why |
| `features.md` | Feature list (F-B*, F-D* IDs are referenced in code comments) |
| `folder_structure.md` | Canonical repo structure (implemented in 1.4) |
| `rules.md` | How implementation must behave (§8 reproducibility, §10 no null keys, §11 frozen schemas, §13 store raw counts only) |
| `design.md` | UX for dashboard (Phase 11–12, not yet used) |
| `tasks.md` | The implementation plan — 17 phases, ~100 tasks, gates, never-bundle list. **Checkbox file: mark `[x]` only after completion.** |
| `memory.md` | Compact persistent project context (sections cited in code: §6 behavioral model + 8% decliners, §7 planted relationships, §12 quality rates, §24 resource constraints) |
| `original_idea_of_project.md` | Origin ideas — cited for decliner design (§7.1: "~8% decliners, engagement fades, marks drop a few weeks later") and LMS rhythms (§7.1) |
| `IDE_Context.md` | **This file** (task 4.9) |

---

## 4. Session Working Protocol (the user's task prompt)

Every task follows this pattern (from `docs/tasks.md`):

```text
Proceed with task <TASK_ID> from docs/TASKS.md only.

Rules still apply:
1. Only this task — nothing from later tasks, even if it seems convenient to bundle in.
2. When done, stop and tell me it's ready to commit. Do not run git commit yourself.
3. Don't scaffold anything for future tasks in advance.
4. Don't self-advance to the next task after this one.
5. Use the docs/ directory to contextually understand requirements, architecture, rules, design and constraints.
```

Completion ritual: implement → run full test suite → mark `[x]` in `docs/tasks.md` → report ready-to-commit with the exact commit message → **stop**.

---

## 5. Execution History — Task 0.1 through 4.9

> Source note: tasks 0.1–4.6 were executed in earlier sessions; they are reconstructed here from the
> authoritative `git log` (30 commits), `docs/tasks.md`, and the current repository state. Tasks
> **4.7 and 4.8 were executed in this session window** and are recorded in full depth — decisions,
> reasons, breakage, calibration, and failure modes.

### Commit history (complete, oldest → newest)

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
```

Note: the user manually bundled 1.4+1.5 and 1.6+1.7+1.8 into two commits (their choice); every task
was still implemented separately. From Phase 2 onward, strictly one task = one commit.

### Phase 0 — Documentation Baseline (0.1–0.3) — DONE

- **0.1** Added the finalized `docs/` set verbatim (`prd.md`, `architecture.md`, `tech_stack.md`, `features.md`, `rules.md`, `design.md`, `tasks.md`, `memory.md`, `folder_structure.md`). No content edits. (The repo also contains `original_idea_of_project.md`, an additional source doc referenced by code comments.)
- **0.2** Consistency-only review — fixed path/name references so the repo matches documented structure. Explicitly **no** new architecture/features. Decision: docs are the source of truth; only obvious mechanical mismatches were fixed.
- **0.3** Updated `tasks.md` and `README.md` "for project betterment".
- **Checkpoint met:** documentation source of truth exists; zero application code.

### Phase 1 — Repository Foundation (1.1–1.8) — DONE

- **1.1** Root `.gitignore`: Python envs, IDE files, `.env`, logs, generated data, Parquet, caches, Spark artifacts.
- **1.2** `README.md`: overview, architecture summary, stack, target scale, setup outline, repo structure, scope boundaries, academic synthetic-data disclaimer (details kept in `docs/`).
- **1.3** `.env.example` with MongoDB placeholders only — never real credentials.
- **1.4** Folder structure built from `docs/folder_structure.md` using only `.gitkeep`/`__init__.py` placeholders — **no business logic** (rule: no scaffolding beyond the task).
- **1.5** Python package skeleton `src/acadexa/` with empty module boundaries: config, generator, database, processing, analytics, dashboard, validation, benchmarks, utils.
- **1.6** Script entry-point placeholders under `scripts/`: `generate_data.py`, `load_mongodb.py`, `run_pipeline.py`, `publish_gold.py`, `run_benchmarks.py` (minimal entry points only; implementation comes in Phases 5–9).
- **1.7** Test structure `tests/` (`unit/`, `integration/`, `fixtures/`, `data/`) + `pytest.ini` so the runner executes with no app tests.
- **1.8** `requirements.txt` with foundational deps only.
- **Checkpoint met:** structure/docs/tests exist; zero functional logic.

### Phase 2 — Configuration Contract (2.1–2.6) — DONE

Decision that shaped everything: **config before code** — no generator value may be hard-coded.
- **2.1** `src/acadexa/config/loader.py` — TOML + env-var loading without hard-coded secrets.
- **2.2** `config/university/hierarchy.toml` — 6 schools / ~18 departments / ~40 programs, config-driven (not embedded in generator logic) + initial `courses.toml` catalog.
- **2.3** `config/university/academic_periods.toml` — 2 academic years, 4 semesters, identifiers + dates (generator derives semester weeks from these dates).
- **2.4** `config/generator/generator.toml` — seed 42, scale (12,000 students with per-school population split summing to target), behavioral parameters, course difficulty shares (0.30/0.45/0.25), data-quality injection rates. (Extensively extended in 4.7/4.8 — see Section 6.)
- **2.5** `config/risk/risk_signals.toml` — exactly the five approved thresholds: attendance 75%, LMS decline ≤50% of prior 4 weeks, late >30%, marks decline ≥10 pts over latest-3 vs earlier average, quiz bottom quartile. **These thresholds are consumed by task 8.7 — do not over-fit generator behavior to them; plant clear declines only.**
- **2.6** `src/acadexa/config/validation.py` — required fields, ranges, incompatible values + `tests/unit/test_config_validation.py`. Raises `ConfigurationError`. Public API: `validate_generator(configs, hierarchy)`, `validate_project_config()` (loads all five TOMLs and validates).
- **Checkpoint met:** all project-level values are configuration-driven.

### Phase 3 — Schema Contract (3.1–3.8) — DONE

Freeze-before-generate decision: schemas became immutable in Phase 3, which is why later features
(traits, decliner flags) had to be hidden internal state instead of new fields.
- **3.1–3.7** `src/acadexa/validation/schema.py` defines: `STUDENTS_SCHEMA`, `COURSES_SCHEMA`, `ACADEMIC_RECORDS_SCHEMA` (student×course×semester grain), `ATTENDANCE_SCHEMA` (student×course×week grain, raw `classes_attended`/`classes_conducted` counts — attendance % is never stored, rules.md §13), `COURSEWORK_SCHEMA`, `LMS_EVENT_SCHEMA` (approved event types only), and gold schemas `student_features`, `course_metrics`, `school_summary`, `risk_indicators`.
- **3.8** `src/acadexa/validation/validators.py` — required fields, types, identifier formats, expected grain; small-fixture tests in `tests/unit/test_schema_validation.py`.
- **Checkpoint met:** generator/MongoDB/Spark/dashboard all reference a stable contract.

### Phase 4 — Synthetic Generator Foundation (4.1–4.8) — DONE

#### 4.1 — Deterministic generator foundation (`fa2c06b`)
- `src/acadexa/generator/foundation.py`: `GeneratorError(ValueError)`, module-level `_check(cond, msg)` fail-fast helper, `GeneratorRunMetadata` (seed, config digest, as_dict), `GeneratorRun(configs)`.
- **Key design (must not change):** `run.child_rng("<name>")` returns `np.random.default_rng(int.from_bytes(sha_digest, "big"))` — a SHA-derived sub-stream seeded from the run seed + name. Fresh every call ⇒ every consumer (and every re-invocation) sees identical draws. `run.rng` is the raw sequential stream (avoid for parallel features). Non-empty name enforced.
- Why: additive features (traits, decliners) must never shift other consumers' random sequences — adding a new named stream is side-effect-free.

#### 4.2 — University hierarchy generation (`570bed9`)
- `generator/university.py` builds schools → departments → programs → courses **deterministically from config** (no RNG needed — pure config expansion). Tests: `test_university_generation.py`.

#### 4.3 — Synthetic students (`6b7f173`)
- `generator/students.py`: `run.child_rng("students")`; stable IDs; population slots filled by permutation of school slots (so per-school counts exactly match config); program chosen from school; semester enrollment indexes assigned. Fails fast if school population ≠ target (validated upstream too). Tests: `test_student_generation.py`.

#### 4.4 — Academic records (`d2b5ad5`)
- `generator/academic_records.py`: `run.child_rng("academic_records")`. Creates the enrollment plan (6 courses/student/semester: 3 in-school + 3 electives drawn outside the school), latent record score ~ `N(baseline − difficulty_drag + ability_shift, record_std)` (4.7+), three components `internal/midterm/endterm = latent + noise`, clipped 0–100, letter grade from unweighted mean via `[behavior.grade_scale]`, course difficulty applied as score drag + attendance drag (confounder, F-B09). Tests: `test_academic_records_generation.py` (incl. difficulty ordering: easy > medium > hard means).

#### 4.5 — Attendance (`c738e1a`)
- `generator/attendance.py`: `run.child_rng("attendance")`. Per student×course×week: `classes_attended ~ Binomial(classes_conducted, p)`; `p` = base 0.85 × school profile multiplier − difficulty drag + **alignment with the student's term aggregate marks** (`alignment_weight = 0.20`, plants attendance↔marks) + weekly noise, clipped to [0.05, 0.98]. Raw counts only. Tests: `test_attendance_generation.py`.

#### 4.6 — Coursework (`9f39693`)
- `generator/coursework.py`: `run.child_rng("coursework")`. Items defined **per course-semester, shared by all enrolled students** (rows = enrollment × items ⇒ drives the ~3.5M target): 8 assignments + 4 quizzes/semester (quiz count scaled by school `quiz_activity`), due = assigned + window. Statuses MISSING/ON_TIME/LATE; late timing scales with school `late_submission` profile and aligns negatively against term marks (`late_marks_alignment = 0.9`, plants late↔miss) — decliner late-rises were explicitly **rejected** in 4.8 (see below). Quiz retries via binomial; score quality = marks alignment + noise. Tests: `test_coursework_generation.py`.

#### 4.7 — Behavioral model (`4f8fed5`) — full session detail

**What:** latent traits `ability`, `diligence`, `engagement` in [0,1] + controlled influence on outcomes.

- **New module** `generator/behavioral_model.py`: `generate_behavioral_traits(run, students)` draws a `(n, 3)` latent matrix from `run.child_rng("behavioral_model")` using per-trait `mean/std` config, adds `observation_noise_std` Gaussian jitter, clips to [0,1]. Returns `student_id → {"ability","diligence","engagement"}` dict. Module docstring documents: trait semantics, clip rationale, weight-validation ownership (each consumer validates its own weight — later revised in context of 4.8 docstring), and explicit deferral of LMS rhythms to 5.2.
- **Config:** four weight keys in `[behavior.student_traits]`: `ability_marks_weight`, `diligence_attendance_weight`, `engagement_attendance_weight`, `diligence_late_weight`.
- **Wiring:** records = ability shift added to latent score; attendance = `diligence×w + engagement×w` added to probability before clipping; coursework = diligence multiplies late probability (fewer late for diligent students).
- **Why a dedicated RNG stream:** traits are a Phase-4 add-on; giving them their own SHA stream meant zero movement of records/attendance/coursework draws → previously calibrated values stayed valid.
- **Validation ownership decision:** `validation.py` validates all weights (range, ≥0 where required); each consumer does a fail-fast `_check` on the weight it reads → layer-correct errors (`ConfigurationError` at load, `GeneratorError` at run).
- **Calibration (mid-scale probe, 600 students, `_scaled_configs(600)` helper):** measured Spearman — ability→marks **0.879** (weight=0 control: 0.022 ⇒ the weight really is the mechanism), diligence→attendance **0.296**, engagement→attendance **0.227**, diligence→late **−0.281**. Final weights chosen: `24.0`, `0.13`, `0.10`, `0.4`.
- **Tests:** new `tests/unit/test_behavioral_model.py` (25 tests) + 4 config-validation tests; suite at that point **192 passed in 34.55 s**.
- **What almost broke / decision points:** attendance↔marks correlation risk (weight too strong → ρ > 0.75 band); resolved by measuring, not guessing — weights set to land mid-band (observed full-scale ρ = 0.49 pre-4.8).

#### 4.8 — Decliner population (`eb3a8e3`) — full session detail (executed entirely in this window)

**Requirement:** `docs/original_idea_of_project.md` §7.1: "Around 8% of students are decliners whose engagement fades during the semester, with marks dropping a few weeks later"; `docs/memory.md` §6 "~8%". Downstream consumers: F-D05 trend detection (weekly engagement + graded-item score trends) and F-D06 risk signals (attendance <75%, marks-decline ≥10) must later see these declines. PRD line 64 mentions decliners in an analytics context — **decision: no late-submission change for decliners** (the PRD sentence is an analytics question, not a generator requirement; late↔marks is already an F-B09 planted relationship).

**Design decisions and why:**

1. **New module `generator/decliners.py`** owning BOTH flag generation and centralized validation of the entire `[behavior.decliners]` section (7 keys). This deliberately differs from 4.7's per-consumer weight validation — documented in the module docstring as an engineering decision: one section, one owner, one error message set; consumers only fail-fast on the section's presence.
2. **`generate_decliner_flags(run, students=None) -> dict[str, bool]`**: validates params first (cheap, fail-fast), generates students if needed, then one Bernoulli draw per student from `run.child_rng("decliners")`. Consumers call it first, then read validated params.
3. **Hidden state:** flags are never written to student documents — `STUDENTS_SCHEMA` is frozen (rules.md §11). Test asserts no student key contains `"declin"`.
4. **Deterministic post-processing after RNG draws:** the flag stream is consumed entirely before any decline math, so decline arithmetic touches no RNG → **non-decliner rows are byte-identical** to a `rate=0` run (proved by test with 0 differing rows across attendance/records/coursework), and adding decliners never shifted other streams.
5. **Decline model (config-driven, three surfaces):**
   - *Attendance* (engagement fade): `p = clip((probability + noise) × decay, floor, ceiling)` where for decliners `decay = (1 − weekly_engagement_decay) ** max(0, week − start_week + 1)` (decay = 1 before `start_week`); non-decliner branch mathematically unchanged.
   - *Marks* (drop "a few weeks later"): component values minus `component_penalty` where penalty = 0 before `decline_start = start_week + marks_decline_lag_weeks` (default week 8), then `marks_weekly_decline × (weeks elapsed)`: penalty = [0, 4, 16] at internal(week 4)/midterm(week 9)/endterm(week 15) with defaults. Component collection weeks moved into config as `component_weeks = { internal = 4, midterm = 9, endterm = 15 }` because the decline needs them.
   - *Coursework scores:* `quality *= score_decay_by_week[due_week]` for decliners, `score_decay_by_week[w] = 1.0 if w < score_start else (1 − score_weekly_decay) ** (w − score_start + 1)`; statuses/timing/attempts unchanged.
   - LMS engagement decay explicitly **deferred to tasks 5.1/5.2** (do not scaffold).
6. **Added then removed `late_weekly_rise`:** initially added a decliner late-submission rise; decision: out of scope for 4.8 (see decision 1 rationale above) — removed before committing to keep the task focused and avoid over-fitting to the 30% late risk threshold of task 8.7.
7. **New config keys** (final): `rate = 0.08`, `start_week = 5`, `weekly_engagement_decay = 0.07`, `marks_decline_lag_weeks = 3`, `component_weeks = {4, 9, 15}`, `marks_weekly_decline = 2.0`, `score_weekly_decay = 0.04`.
8. **Two-layer validation:** `validation.py` `_require_keys` all 7 keys + range/order checks (e.g., `component_weeks` must be positive ints with internal < midterm < endterm; `weekly_engagement_decay` ∈ [0,1); `marks_weekly_decline` ≥ 0 — explicit `isinstance` because this file has no `_is_number` helper); `decliners.py` mirrors it for `GeneratorError`; each of records/attendance/coursework gained `_check("decliners" in behavior, "configs missing generator behavior.decliners")` at the top of its config section.
9. **Exported** `generate_decliner_flags` from `generator/__init__.py` (alphabetical order).
10. **Docstring cross-refs updated** in `behavioral_model.py`, `academic_records.py`, `attendance.py`, `coursework.py`: decline behavior now documented as implemented; remaining deferrals reduced to LMS-only ("LMS rhythms (5.2) are not applied here").

**What actually happened during 4.8 (breakage log — all resolved):**
- `late_weekly_rise` added to TOML, then removed after scope decision.
- Probe script bug #1: read `row["due_week"]` from output rows — **coursework rows don't carry `due_week`** (frozen schema; `due_week` exists only on internal item dicts). Fixed by deriving week from `due_date` vs semester dates.
- Probe script bug #2: coursework rows have **no `semester_id`** either — fixed by locating the semester whose date range contains `due_date`.
- One `edit` tool call failed: oldString mismatch on `behavioral_model.py` docstring (lines hadn't been read with exact text) — fixed by reading the exact lines first, then editing.
- Nothing else broke: all 107 pre-existing related tests passed on the first full run after wiring (records + attendance + coursework + behavioral model + config validation), and the final full suite passed.

**Calibration probe results (measured, mid-scale n=600 + full-scale n=12,000):**

| Measure | Result | Band / expectation |
|---|---|---|
| Decliner share (full scale) | **7.77 %** (932/12,000) | test band [0.06, 0.10] ✅ |
| Decliner share (mid scale) | 9.33 % (56/600) | sampling noise, fine |
| Attendance decliners | 0.869 → **0.432** (late vs early) | clear fade; test asserts ≤ −0.20 ✅ |
| Attendance non-decliners | 0.888 → 0.888 (Δ 0.000) | flat; test asserts ≤ 0.05 ✅ |
| Records decliners | internal 66.2 → midterm 62.5 → **endterm 50.4** (−15.8) | test asserts ≥ 8 pts ✅ |
| Records non-decliners | 66.0 / 66.0 / 65.9 (flat) | test asserts ≤ 3 ✅ |
| Aggregate marks | decliners 59.7 vs others 66.0 (−6.3) | test asserts ≥ 3 ✅ |
| Score quality decliners | 0.597 → **0.450** (late vs early due week) | test asserts ≤ −0.07 ✅ |
| Score quality non-decliners | 0.657 → 0.657 | flat ✅ |
| Late rate | decliners 0.126 vs others 0.105; overall **0.107** | late↔marks alignment artifact (decliners weaker → more late), not an explicit rise; band [0.06, 0.16] ✅ |
| score↔marks ρ | 0.914 | ≥ 0.70 ✅ |
| attendance↔marks ρ (mid) | 0.427 (was 0.326 pre-decliners) | decliners *strengthen* it (both decline together) — full-scale band [0.40, 0.75], watch ceiling ✅ (observed 0.49 pre-4.8) |
| Non-decliner rows vs `rate=0` run | **0 differing rows** (attendance, records, coursework) | identity guarantee ✅ |
| Error paths | all 10 decliner GeneratorError paths + 4 ConfigurationError paths raise correct messages | ✅ |

**Tests written:** new `tests/unit/test_decliner_population.py` (23 tests: 7 population, 5 decline-behavior incl. the zero-rate identity test, 11 error paths, plus hidden-state & reproducibility) + 4 new config-validation tests (`test_generator_missing_decliner_key_raises`, `..._engagement_decay_out_of_range_raises`, `..._component_weeks_unordered_raises`, `..._negative_marks_weekly_decline_raises`).
**Full suite after 4.8: 219 passed.** Task marked `[x]`; commit `Update - 4.8 - implement synthetic decliner population` (user committed `eb3a8e3`).

### Task 4.9 — This task (`Update - 4.9 - add IDE context documentation`)

**What:** Create `docs/IDE_Context.md` — this file — capturing the complete session record: every
executed task 0.1 → 4.8 with what was done, decisions taken and *why*, what broke and what didn't,
what is working/deferred, calibration numbers, environment conventions, and the documentation set
that governs the work. Add task 4.9 to `docs/tasks.md`.
**Why:** so any human or IDE agent can resume the project without re-deriving context; it is a
documentation-only task (no code changes, no scaffolding for Phase 5).
**Scope discipline:** created exactly one file + one tasks.md checkbox entry; nothing else touched.

---

## 6. Current System Architecture (as of 4.8)

### Generation data flow

```text
validate_project_config()            # loads 5 TOMLs, raises ConfigurationError
        │
GeneratorRun(configs)                 # seed 42, metadata, _check fail-fast
        │
generate_university(run)              # deterministic config expansion (4.2)
generate_students(run)                # child_rng("students")            (4.3)
generate_courses / course difficulty   # child_rng("course_difficulty")  (4.2/4.4)
generate_behavioral_traits(run, stu)   # child_rng("behavioral_model")   (4.7)
generate_decliner_flags(run, stu)      # child_rng("decliners")          (4.8)
        │
generate_academic_records(run, stu)    # child_rng("academic_records")   (4.4 + 4.7 ability + 4.8 penalty)
generate_attendance(run, stu, recs)    # child_rng("attendance")         (4.5 + 4.7 traits + 4.8 decay)
generate_coursework(run, stu, recs)    # child_rng("coursework")         (4.6 + 4.7 diligence + 4.8 score decay)
        │
   [5.1–5.4 LMS events → Parquet — NOT YET IMPLEMENTED]
```

### Named RNG streams (all SHA-derived via `run.child_rng`, deterministic per seed+name)

`students`, `course_difficulty`, `behavioral_model`, `decliners`, `academic_records`, `attendance`, `coursework`.
Adding a feature = add a new named stream ⇒ zero side effects on existing output.

### Module inventory (`src/acadexa/`)

| Module | Status |
|---|---|
| `config/loader.py`, `config/validation.py` | ✅ done (2.1, 2.6) |
| `generator/foundation.py` | ✅ GeneratorRun / GeneratorError / child_rng (4.1) |
| `generator/university.py`, `courses.py` | ✅ hierarchy + course difficulty (4.2) |
| `generator/students.py` | ✅ (4.3) |
| `generator/academic_records.py` | ✅ (4.4, wired 4.7/4.8) |
| `generator/attendance.py` | ✅ (4.5, wired 4.7/4.8) |
| `generator/coursework.py` | ✅ (4.6, wired 4.7/4.8) |
| `generator/behavioral_model.py` | ✅ traits (4.7) |
| `generator/decliners.py` | ✅ flags + validation (4.8) |
| `validation/schema.py`, `validators.py` | ✅ frozen schemas (Phase 3) |
| `database/`, `processing/`, `analytics/`, `dashboard/`, `benchmarks/`, `utils/` | ⬜ empty `__init__.py` only — Phases 6–13 |

### Config files

`config/university/hierarchy.toml`, `courses.toml`, `academic_periods.toml`; `config/risk/risk_signals.toml`; `config/generator/generator.toml` (full contents = seed/scale/traits+weights/decliners/rhythms/academic_performance/grade_scale/weekly_attendance/coursework/school_profiles/course_difficulty/data_quality_injection — see the file; it is heavily commented and every "tunable" marker was calibrated in Phase 4).

### Validation layers

- **Layer 1 — `ConfigurationError`** (`src/acadexa/config/validation.py`): runs on config load; required keys, ranges, orderings, cross-field consistency (e.g., school population sums, difficulty shares = 1.0, null_key_fields_allowed = false).
- **Layer 2 — `GeneratorError`** (`foundation._check` + per-module validators): fail-fast at generation time with generator-flavored messages (e.g., `generator behavior.decliners.rate must be in [0, 1]`).
- **Layer 3 — schema validation** (`validation/validators.py`): record grain/types/identifier formats on output.
- **Layer 4 — test bands** (Section 7): statistical invariants that catch silent calibration regressions.

---

## 7. Calibration Reference (measured — re-verify after any generator change)

Full-scale tests assert these bands; observed values from probes/4.7–4.8 runs:

| Test band (full scale, n=12,000) | Range | Last observed |
|---|---|---|
| Decliner share | [0.06, 0.10] | 0.0777 |
| attendance↔marks Spearman (term grain) | [0.40, 0.75] | ~0.49 pre-4.8; decliners strengthen (mid-scale 0.326 → 0.427) |
| score↔marks Spearman (term grain) | ≥ 0.70 | 0.914 |
| late↔marks Spearman | [−0.45, −0.12] | ~−0.24 |
| Overall late rate | [0.06, 0.16] | 0.105–0.108 |
| School late gap (lad − sci) | ≥ 0.01 | pass |
| Missing rate | [0.03, 0.05] | pass |
| Volume (coursework rows) | [3.2M, 3.6M] | pass |
| Records difficulty ordering | easy > medium > hard | pass |
| ability→marks Spearman | ≥ 0.5 | 0.879 |
| diligence→attendance | ≥ 0.15 | 0.296 (pre-decliners) |
| engagement→attendance | ≥ 0.10 | 0.227 (pre-decliners) |
| diligence→late | ≤ −0.12 | −0.281 |

Decline-specific assertions: decliner attendance fade ≥ 0.20 (measured 0.437), decliner internal−endterm ≥ 8 pts (measured 15.8), decliner aggregate below others ≥ 3 pts (measured 6.3), decliner score-quality gap ≥ 0.07 (measured 0.148), non-decliner flatness ≤ 0.05/3/0.03 (measured ≈ 0).

**Calibration method (reuse for future tasks):** write a probe script in the temp dir that builds scaled configs (`deepcopy(validate_project_config())` → set `scale.target_students` + per-school `school_population`), runs the generation chain, computes Spearman manually (rankdata + corrcoef — **no scipy dependency**), prints measured values vs bands, and loops on config values. Never calibrate by intuition.

---

## 8. Test Suite Status (219 passed, ~3 min)

```text
$env:PYTHONPATH='src'; python -m pytest -q        # from project root
219 passed
```

| Test file | Covers | ~Tests |
|---|---|---|
| `test_smoke.py` | runner sanity | small |
| `test_config_validation.py` | all ConfigurationError paths (incl. 4 decliner keys added in 4.8) | 32 |
| `test_schema_validation.py` | frozen schemas / grain / types | — |
| `test_generator_foundation.py` | seed determinism, child_rng behavior, GeneratorError | — |
| `test_university_generation.py` | hierarchy from config | — |
| `test_student_generation.py` | stable IDs, school counts | — |
| `test_academic_records_generation.py` | difficulty bands, ability link, decline penalty | — |
| `test_attendance_generation.py` | counts, trait links, decliner decay, flat non-decliners | — |
| `test_coursework_generation.py` | volumes, late/missing bands, score links, score decay | — |
| `test_behavioral_model.py` | traits distribution, weight mechanisms (weight=0 controls), reproducibility | 25 |
| `test_decliner_population.py` | share band, hidden state, reproducibility, extremes, decline behavior, identity, error paths | 23 |

Conventions: module-scoped fixtures; full-scale (12,000) for statistical bands, `_scaled_configs(600)` mid-scale for correlation probes, 36-student `small_configs` for error paths; error tests never generate (validation raises first) so they are instant.

---

## 9. What Works / What Doesn't / Deferred

**Working:** all of Phases 0–4; reproducibility (same seed ⇒ identical outputs; different seed ⇒ different flags); two-layer validation; behavioral model with calibrated weights; decliner population with measured decline effects on attendance/marks/coursework; non-decliner identity guarantee; 219 green tests.

**Not yet implemented (expected — later phases):** LMS events (5.x), manifests, data-quality injection (config exists, code doesn't), MongoDB layer (6.x), Spark (7.x), analytics/risk (8.x), gold layer (9.x), MVP gate (10.x), dashboard (11–12), benchmarks (13), full-scale (14–16), final docs (17).

**Deliberate deferrals in code comments (do not "helpfully" implement early):**
- LMS weekly/semester rhythms → tasks **5.1/5.2** (rhythm config keys already exist in TOML under `[behavior.rhythms]` but are unused).
- Ground truth registry → 5.5; data-quality injection → 5.6.
- Pearson → 8.5; risk thresholds consumption → 8.7 (**do not tune the generator to hit specific risk counts**).

**Open watch items:**
- attendance↔marks ρ ceiling (0.75) as decliner noise and future changes push it up — measure, don't assume.
- 4.7 trait-rho floors (0.15/0.10/−0.12) are somewhat diluted by decliner variance — they still pass but have less headroom.

---

## 10. Session Gotchas & Lessons Learned

1. **Never edit an oldString you haven't read exactly** — one `edit` failed on `behavioral_model.py` docstring because remembered text ≠ file text; read the lines first.
2. **Frozen rows ≠ internal items:** internal item dicts may carry extra fields (e.g., `due_week`) that output rows never do; derive from dates when probing.
3. **PowerShell breaks nested f-strings** → temp probe `.py` files in `C:\Users\Rishav\AppData\Local\Temp\opencode\`.
4. **Calibrate with measured probes, not intuition** — every Phase 4 "tunable" was set from numbers.
5. **RNG isolation is the architecture** — new features get their own `child_rng` name; post-draw deterministic math keeps other rows byte-identical.
6. **Validation ownership must be decided explicitly and documented** — 4.7: per-consumer weight checks; 4.8: centralized section validation. Both patterns are intentional; don't mix them silently.
7. **Scope creep caught early:** `late_weekly_rise` was added then removed within 4.8; a task's diff should contain only what its description asks for.
8. **Checkboxes:** `docs/tasks.md` must be updated in the same change as the completed work.
9. **Reconstruction discipline:** claims about earlier tasks in this file come from `git log` + repo state, not memory of transcripts — when in doubt, `git show <commit>` is the ground truth.

---

## 11. What Comes Next — Task 5.1 and beyond

Next task (not started):

```text
5.1 — Implement LMS event-type generation using only the approved event types
      and configuration-driven distributions.
Commit: Update - 5.1 - implement LMS event generation
```

Constraints to carry in:
- Only **approved LMS event types** (`LMS_EVENT_SCHEMA`, `features.md`); distributions from config (`lms_events_per_student_per_day = 15`, school `lms_activity` multipliers, `[behavior.rhythms]` factors become relevant in 5.2).
- Follow the established pattern: named RNG stream (e.g., `child_rng("lms_events")`), module docstring with engineering decisions, two-layer validation for any new config keys, module-scoped tests with statistical bands calibrated by probe, mark `[x]` + report, never commit.
- 5.3 will require **chunked** generation (never accumulate ~70M rows in memory — rules.md §24); don't pre-build the chunking in 5.1 (no scaffolding).
- 5.5 ground truth must be generated **before** analytics are observed (memory.md §23) — decliner registry will be re-exported there; `generate_decliner_flags` is the API to reuse.
- Full-phase checklist: 5.1 event types → 5.2 timestamps/rhythms → 5.3 chunked → 5.4 dev Parquet + read-back → 5.5 ground-truth registry → 5.6 quality injection → 5.7 manifests → 5.8 `scripts/generate_data.py` entry point.

---

## 12. Quick Command Sheet

```powershell
# full test suite (from repo root)
$env:PYTHONPATH='src'; python -m pytest -q

# one file with short tracebacks
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_decliner_population.py -q --tb=short

# collect-only count (expect 219 at this snapshot)
$env:PYTHONPATH='src'; python -m pytest --collect-only -q 2>$null | Select-Object -Last 1

# git inspection (agent must NOT commit)
git status --short
git diff --stat
git log --oneline

# run a calibration probe
python C:\Users\Rishav\AppData\Local\Temp\opencode\probe48.py
```

---

*End of file. Update this document at the end of each future phase (or when the user requests it) so it remains the authoritative resume point.*

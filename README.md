# Acadexa

> An Integrated University Academic Intelligence System Using MongoDB and PySpark

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySpark](https://img.shields.io/badge/PySpark-batch%20processing-E25A1C?logo=apachespark&logoColor=white)](https://spark.apache.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-serving%20layer-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Parquet](https://img.shields.io/badge/Apache%20Parquet-raw%20events-0550AE?logo=apache-parquet&logoColor=white)](https://parquet.apache.org/)

Acadexa is a **Big Data learning-analytics platform** for a multi-school university. It generates large-scale synthetic academic and LMS data, processes it through a **PySpark batch pipeline**, stores results in **MongoDB**, and surfaces cross-factor analytics, trends, and rule-based risk signals through a **Streamlit dashboard**.

Built as a final-year **Big Data Technologies** project around *RAS University*, a synthetic university modeled on MIT-WPU's academic structure.

> **Note:** 100% synthetic, seeded, reproducible data — no real student or institutional data is used.

---

## How It Works

```text
Synthetic Data Generator ──→ Parquet (raw LMS events)
         │                        │
         └────────────────→ MongoDB (core collections)
                                  │
                             PySpark (J1–J8)
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
               Features     Analytics     Risk Signals
                    └─────────────┼─────────────┘
                                  ▼
                        Gold Collections (MongoDB)
                                  │
                                  ▼
                         Streamlit Dashboard
```

**Spark jobs:** Clean & Validate → Event Aggregation → Feature Table → Correlation → Trend Detection → Risk Signals → Publish → Benchmark

---

## Key Features

- **Synthetic data platform** — config-driven generator: ~12k students, ~250 courses, ~70M LMS events, planted relationships with a ground-truth registry, and controlled data-quality injection
- **Cross-factor analytics** — Spearman correlations across attendance, marks, coursework, and LMS engagement
- **Trend detection** — rolling 4-week engagement windows with a known ~8% "decliner" population for validation
- **Rule-based risk signals** — 5 transparent signals scored 0–5 (explicitly not ML prediction)
- **Role-aware dashboard** — University → School → Department → Program → Course → Student drill-down for 4 personas
- **Benchmarking** — pandas vs MongoDB aggregation vs PySpark on comparable workloads

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language & generation | Python, NumPy |
| Raw event storage | Apache Parquet |
| Serving & analytics DB | MongoDB (incl. time-series + aggregation) |
| Batch processing | PySpark (local mode) + MongoDB Spark Connector |
| Dashboard | Streamlit |

---

## Target Scale

6 schools · ~18 departments · ~40 programs · ~250 courses · ~12,000 students · 2 years / 4 semesters · **~70M LMS events**

---

## Quick Start

**Prerequisites:** Python · MongoDB · Java runtime (for PySpark) · Git

```bash
git clone <repository-url>
cd acadexa

python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env   # set MONGODB_URI, MONGODB_DATABASE
```

**Execution flow** (once implementation is complete):

```bash
python scripts/generate_data.py     # synthetic data → Parquet + MongoDB
python scripts/load_mongodb.py      # load core collections
python scripts/run_pipeline.py      # Spark jobs J1–J8
python scripts/publish_gold.py      # publish gold collections
python scripts/run_benchmarks.py    # pandas / Mongo / Spark benchmarks
streamlit run src/acadexa/dashboard/app.py
```

---

## Repository Structure

```text
acadexa/
├── docs/          # project knowledge (requirements, architecture, rules…)
├── config/        # non-secret configuration (university, generator, risk…)
├── src/acadexa/   # application code (generator, database, processing, dashboard…)
├── scripts/       # execution entry points
├── tests/         # unit / integration tests & fixtures
├── data/          # generated & local data (mostly git-ignored)
├── reports/       # generated analytical outputs
├── logs/          # runtime logs (git-ignored)
└── notebooks/     # exploratory work
```

Large generated datasets are never committed — the repository contains the machinery to generate them. Full layout: [`docs/folder_structure.md`](docs/folder_structure.md).

---

## Scope

**In scope:** synthetic data generation, Parquet/MongoDB storage, PySpark batch analytics (association, trends, rule-based signals), gold-layer publishing, benchmarking, role-aware Streamlit dashboard.

**Out of scope:** Kafka, Spark Structured Streaming, live streaming, ML/failure prediction, real student or institutional data, production IAM, cloud deployment, loading the full LMS dataset into MongoDB.

---

## Documentation

The `docs/` directory is the project's source of truth:

| Document | Purpose |
|---|---|
| [`prd.md`](docs/prd.md) | Product requirements |
| [`architecture.md`](docs/architecture.md) | System architecture |
| [`tech_stack.md`](docs/tech_stack.md) | Technology decisions |
| [`features.md`](docs/features.md) | Feature specification |
| [`design.md`](docs/design.md) | UI/UX direction |
| [`rules.md`](docs/rules.md) | Coding & implementation rules |
| [`tasks.md`](docs/tasks.md) | Implementation roadmap |
| [`memory.md`](docs/memory.md) | Persistent project context |
| [`folder_structure.md`](docs/folder_structure.md) | Repository organization |

---

## Project Status

**Current stage:** Documentation complete — implementation starting

- [x] Requirements, architecture, tech stack, features, design, rules, roadmap
- [ ] **Next:** one-school, one-semester end-to-end vertical slice (MVP)
- [ ] Scale to full target dataset

---

## Disclaimer

Acadexa uses **fully synthetic data** for educational purposes. Generated records, relationships, trends, and risk signals do not represent real students or institutions. Analytical relationships are **associations, not causal conclusions**.

---

## License

Academic project — license to be decided by the team.

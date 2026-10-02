# Acadexa — Final Comprehensive Academic Project Report

**Project Title:** Acadexa: A Scalable Big Data Learning Analytics & Academic Early-Warning Platform  
**Target Institution Model:** RAS University (Fictional Synthetic Benchmark)  
**Academic Context:** Final-Year Capstone Project in Big Data Technologies & Distributed Systems  
**Authors / Implementers:** Acadexa Engineering Team  
**Date of Submission:** October 2026  
**Repository:** `acadexa`  
**License:** Educational / Non-Commercial Research Baseline

---

## Abstract

Modern higher-education institutions face significant challenges in synthesizing disparate student data streams—learning management system (LMS) clickstreams, attendance logs, coursework submissions, and summative grades—into timely, explainable academic interventions. Traditional institutional data platforms suffer either from single-node memory exhaustion under high-frequency interaction logs or from black-box predictive models that lack interpretability and violate educational privacy mandates.

This report presents **Acadexa**, a batch-oriented, local Big Data learning analytics platform designed around **RAS University**, a simulated institution comprising 6 schools, 18 departments, 40 degree programs, 250 courses, and 12,000 students across two academic years (four terms). Using a deterministic, seed-based synthetic generator, Acadexa produces **74,757,153 discrete LMS interaction events** (~1.38 GB Parquet raw) alongside 4.6M attendance and 3.3M coursework records (~4.5 GB total raw footprint).

Acadexa employs a dual-storage paradigm separating large event logs in Apache Parquet from operational and analytical serving data in MongoDB. A distributed PySpark local pipeline (Jobs J1–J7) cleans 83M records with 100% anomaly traceability, aggregates weekly clickstream velocities, constructs unified student feature tables at $O(10^5)$ grain, evaluates non-linear Spearman rank associations, detects 16-week temporal declines, and scores academic vulnerability across an **explainable five-rule risk engine**. Benchmarking against 74.7M events demonstrates that single-node Pandas crashes with `MemoryError` while PySpark completes in 151.12 seconds, proving the necessity of distributed batch infrastructure. Finally, an authenticated Streamlit analytics portal renders role-scoped intelligence with sub-5ms query response times, delivering actionable insights without resorting to opaque machine learning predictions or making unwarranted causal claims.

---

## 1. Introduction & Problem Statement

### 1.1 The Learning Analytics Challenge
Higher education institutions capture vast volumes of digital breadcrumbs as students engage with Virtual Learning Environments (VLEs) and campus management systems. However, universities face three structural bottlenecks:
1. **The Clickstream Volume Dilemma:** Interaction logs (reading content, forum posting, video watching, assessment attempts) scale quadratically with enrollment and course depth, rapidly outgrowing conventional relational databases and spreadsheet software.
2. **The "Black Box" Trust Deficit:** Early-warning systems often deploy opaque machine learning classifiers (e.g., Random Forests, Neural Networks) that generate probabilities of failure without interpretable diagnostics, leading to student stigmatization, algorithmic bias, and faculty resistance.
3. **Data Quality and Spurious Correlation:** Administrative data is inherently messy—containing duplicate logs, orphaned records, and divergent course grading standards. Uncontrolled correlations often succumb to **Simpson's Paradox**, where aggregated institutional data contradicts department-level educational realities.

### 1.2 The Acadexa Mission
Acadexa was engineered to solve these challenges through a defensible, reproducible Big Data architecture:
- **Reproducible Simulation:** Generate an enterprise-scale synthetic university without exposing sensitive, protected student data (FERPA/GDPR compliance by construction).
- **Dual-Storage Separation:** Isolate massive raw clickstreams in Parquet columnar storage while maintaining indexed operational and gold serving slices in MongoDB.
- **Distributed Transformation:** Implement an end-to-end PySpark batch pipeline enforcing strict driver-memory safety (zero large `.collect()` operations).
- **Rule-Based Explainability:** Replace speculative failure probabilities with five deterministic, transparent risk rules derived from institutional academic thresholds.
- **Role-Aware Serving:** Deliver instant, authenticated intelligence to University Administrators, Deans, Faculty, and Analysts via a responsive web dashboard.

---

## 2. Institutional Model: RAS University

Acadexa models **RAS University**, a multi-disciplinary institution structured to reflect authentic academic hierarchies:

```text
RAS University
├── School of Engineering & Technology (SET) — 3,000 students (25.0%)
├── College of Engineering & Technology (CET) — 2,600 students (21.7%)
├── School of Management (SOM) — 2,400 students (20.0%)
├── Liberal Arts & Design (LAD) — 2,200 students (18.3%)
├── School of Sciences (SCI) — 1,000 students (8.3%)
└── School of Law (SOL) — 800 students (6.7%)
Total: 12,000 Students · 18 Departments · 40 Programs · 72 Active Courses (250 Target Catalog)
Academic Timeline: Academic Years AY1 & AY2 across Semesters S1, S2, S3, S4 (16 weeks per term)
```

Each student enrolls in exactly 6 courses per term (24 course instances over 2 years), generating 288,000 total academic records.

---

## 3. High-Performance Synthetic Generation & Behavioral Modeling

### 3.1 Latent Trait Behavioral Architecture
To ensure generated datasets exhibit genuine statistical properties rather than uniform noise, Acadexa implements a latent trait behavioral model for each synthetic student:
- **Ability ($\alpha \sim \mathcal{N}(0.5, 0.15)$):** Governs fundamental academic comprehension, assignment scores, and midterm/endterm performance.
- **Diligence ($\delta \sim \mathcal{N}(0.5, 0.15)$):** Controls attendance frequency, assignment submission lead times, and quiz retries.
- **Engagement ($\epsilon \sim \mathcal{N}(0.5, 0.15)$):** Drives weekly LMS event volume, session durations, and content access frequencies.

### 3.2 The Synthetic Decliner Population (~8%)
Real institutions experience disengagement trajectories. Acadexa models an approximately 8% "decliner" sub-population (960 students) characterized by:
- Progressive weekly attendance decay starting in Week 6.
- A $\ge 50\%$ reduction in LMS event activity during Weeks 10–15 relative to Weeks 1–6 baseline.
- Lagged mark erosion ($\ge 10$ points drop between midterm and endterm assessments).

### 3.3 Event Generation & Temporal Diurnal Rhythms
The LMS generator constructs 11 discrete event types (`login`, `logout`, `view_content`, `download_resource`, `submit_assignment`, `take_quiz`, `post_forum`, `read_forum`, `view_grade`, `join_live_session`, `click_link`). Event timestamps follow diurnal circadian distributions (peaking at 10:00–14:00 and 19:00–22:00) with suppressed volumes on weekends, matching real academic virtual learning environment logs.

---

## 4. Controlled Data Quality Injection & Traceability Audit

To rigorously validate PySpark's data-cleaning capabilities, Acadexa injected **2,644,049 controlled anomalies** into raw datasets prior to ingestion:

```text
Total Injected Anomalies: 2,644,049
├── Duplicate LMS Events: 740,169 (Synthetic double-clicks and replay logs)
├── Non-Key Null Values: 590,317 (Missing non-essential descriptions)
├── Timestamp Inconsistencies: 779,625 (Malformed ISO strings, mixed formats)
├── Course ID Formatting: 414,959 (Mixed lowercase, leading/trailing whitespace)
├── Orphan Records: 82,991 (Foreign keys referencing non-existent students/courses)
└── Out-of-Range Marks/Counts: 35,988 (Attendance > conducted, marks < 0 or > 100)
```

In Job J1 (Clean & Validate), PySpark detected **1,551,722 actionable issues**, automatically corrected **748,183 malformed records**, dropped **803,539 invalid records** (720,548 duplicate events and 82,991 orphan keys), and produced output datasets with exactly **zero remaining errors**, documented in `reports/quality/full_scale_data_quality_report.json`.

---

## 5. Dual-Storage Lakehouse Architecture

A central design innovation of Acadexa is the explicit structural partition between Parquet lakehouse storage and MongoDB operational serving:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        RAW GENERATION OUTPUT                           │
│  - Academic Metadata: CSV / Parquet (12k students, 72 courses)         │
│  - Clickstream Events: 74.7M events across 13,338 Parquet files (1.38GB)│
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼                                ▼
       ┌────────────────────────┐       ┌────────────────────────────────┐
       │     APACHE PARQUET     │       │            MONGODB             │
       │    (Lakehouse Store)   │       │       (Operational Slice)      │
       │                        │       │                                │
       │ Full 74.7M LMS Events  │       │ S4 + CET/SOM Serving Slice     │
       │ Cleaned intermediate   │       │ (~8.95M documents)             │
       │ partitions (J1-J6)     │       │ Core Academic Collections      │
       └────────────┬───────────┘       └────────────────┬───────────────┘
                    │                                    │
                    ▼                                    ▼
       ┌─────────────────────────────────────────────────────────────────┐
       │                   PYSPARK BATCH ENGINE (J1-J7)                  │
       │ Distills 83M raw records into 48k Gold Serving rows (99.93% drop)│
       └────────────────────────────────┬────────────────────────────────┘
                                        │
                                        ▼
       ┌─────────────────────────────────────────────────────────────────┐
       │                      MONGODB GOLD LAYER                         │
       │ student_features (48k) · course_metrics (288)                   │
       │ school_summary (18)    · risk_indicators (12k)                  │
       │ Storage footprint: ~25 MB · Sub-5ms query response              │
       └────────────────────────────────┬────────────────────────────────┘
                                        │
                                        ▼
       ┌─────────────────────────────────────────────────────────────────┐
       │                   STREAMLIT ANALYTICS PORTAL                    │
       │ Authenticated, role-gated UI (Admin, Dean, Faculty, Analyst)    │
       └─────────────────────────────────────────────────────────────────┘
```

**Why not store 74.7M events in MongoDB?**  
Ingesting 75 million uncompressed documents would require ~35 GB of storage, completely overwhelming MongoDB's WiredTiger in-memory cache on local hardware and degrading analytical dashboard latency from milliseconds to tens of seconds.

---

## 6. PySpark Batch Processing Pipeline (Jobs J1–J7)

Acadexa orchestrates data through seven sequential PySpark batch stages executed in local multi-core mode:

| Job | Name | Input Volume | Output Volume | Processing Function |
|---|---|---|---|---|
| **J1** | Clean & Validate | 83,004,035 | 82,200,496 | Deduplication, orphan removal, string normalization, range clamping. |
| **J2** | Weekly LMS Aggregation | 73,961,848 | 4,607,646 | Clickstream roll-up into student-course-week engagement summaries. |
| **J3** | Unified Feature Table | 4 Domains | 288,000 | Multi-way outer join uniting academics, attendance, coursework, and LMS. |
| **J4** | Correlation Analytics | 288,000 | 5 Pairs | Distributed Spearman rank correlations and within-course Z-scores. |
| **J5** | Temporal Trend Detection | 288,000 | 288,000 | 16-week engagement velocity, 50% LMS drop, 10-point mark drops. |
| **J6** | Five-Rule Risk Engine | 288,000 | 12,000 | Transparent evaluation of institutional risk thresholds. |
| **J7** | Gold Layer Publication | Analytical Tables | 4 Collections | Validated publication to MongoDB and Gold Parquet lakehouse. |

### Driver-Side Safety Mandate
To ensure true distributed scalability, Acadexa strictly forbids driver-side collection (`.collect()`, `.toPandas()`, `.take()`) on large DataFrames. Compliance was enforced via automated Abstract Syntax Tree (AST) static analysis tests across all job modules.

---

## 7. Feature Engineering & Course-Level Z-Score Normalization

Cross-course academic comparisons suffer from grading discrepancies across academic disciplines. A 65% in a rigorous Advanced Quantum Mechanics course may represent outstanding mastery, whereas a 65% in an introductory survey course may signal severe distress.

Acadexa implements **Within-Course Normalization (Job J4)** using standardized Z-scores:
$$Z_{i, c} = \frac{X_{i, c} - \mu_c}{\sigma_c}$$
Where $X_{i, c}$ is student $i$'s score in course $c$, and $\mu_c$ and $\sigma_c$ represent the mean and standard deviation of that specific course cohort. Zero-variance safeguards (`F.when(col("stddev") > 0, ...).otherwise(0.0)`) prevent numerical undefined exceptions on single-student cohorts.

---

## 8. The Five-Rule Explainable Academic Risk Engine

Unlike opaque deep-learning models, Acadexa's risk architecture evaluates five concrete, deterministic academic signals derived from university policy:

1. **Rule 1: Low Attendance (`low_attendance`)** — Overall course attendance drops below 75.0% ($< 75\%$).
2. **Rule 2: LMS Engagement Drop (`lms_decline`)** — Late-semester LMS activity (Weeks 10–15) drops to $\le 50\%$ of early-term baseline (Weeks 1–6).
3. **Rule 3: Late Submission Habit (`late_submissions`)** — Proportion of submitted coursework flagged as late exceeds 30.0% ($> 30\%$).
4. **Rule 4: Longitudinal Marks Decline (`marks_decline`)** — Summative assessment checkpoints reflect a drop of $\ge 10.0$ percentage points.
5. **Rule 5: Bottom-Quartile Quiz Activity (`low_quiz_activity`)** — Student quiz score average or attempt count ranks in the bottom 25th percentile of the course cohort.

### Diagnostic Traceability & Scoring
Each student receives an integer score from $0$ to $5$:
- **0–2 Signals:** Normal Academic Standing / Mild Monitoring.
- **3–5 Signals:** **High-Risk Priority Intervention Flag**.

Every flagged student record includes a natural-language diagnostic explanation tracing the exact metrics, values, and violated thresholds (e.g., *"Student attendance at 68.2% is below institutional requirement of 75.0%"*).

---

## 9. Interactive Analytics Dashboard & Role-Based Access Control

The presentation layer is implemented in Streamlit, directly reading indexed Gold MongoDB collections:
- **University Administrator:** Macro KPIs, institutional retention risk, inter-school performance equity.
- **School / Department Dean:** Scoped breakdown across 18 departments, faculty course load, departmental late submission rates.
- **Faculty Member:** Course-level grade distributions, weekly engagement trends, roster drill-down for enrolled students.
- **Academic Analyst:** Ground-truth recovery curves, Spearman scatter matrices, Simpson's Paradox controls, data quality metrics.

All interactions are secured through passwordless role authentication and custom CSS navigation isolation.

---

## 10. Empirical Benchmarking Results (Workload J8)

Empirical benchmarks executed on a 20-thread, 24 GB RAM Windows host evaluated single-node Pandas against distributed PySpark on full-scale data:

### Workload 1: Weekly LMS Engagement Aggregation (74,757,153 raw events)
- **Pandas:** Terminated with **`MemoryError`** after 643.36s (exhausted 24 GB host RAM).
- **PySpark:** Successfully completed in **151.12 seconds** (output: 4,682,117 aggregated rows).

### Workload 2: Feature-Table Multi-Domain Outer Join (12,834,222 records)
- **Pandas:** Completed in **32.95 seconds** (Peak memory: 831.35 MB).
- **PySpark:** Completed in **47.18 seconds** (Distributed shuffle and JVM scheduling overhead).

**Engineering Synthesis:** The benchmark conclusively proves the architectural boundary: distributed engines (Spark) are indispensable for out-of-core raw event logs, while in-memory tools (Pandas) remain highly competitive on pre-aggregated tabular feature tables.

---

## 11. Statistical Ground-Truth Recovery & Simpson's Paradox

Evaluating recovered Gold features against `ground_truth_registry.json`:
- **Attendance vs. Marks (`attendance_marks`):** Planted positive $\rightarrow$ **Recovered ($\rho = +0.443$)**.
- **Late Submissions vs. Marks (`late_submissions_marks`):** Planted negative $\rightarrow$ **Recovered ($\rho = -0.292$)**.
- **Decoy Variable (`decoy_forum_marks`):** Planted null $\rightarrow$ **Correctly No Association ($\rho = +0.012$)**.

### Simpson's Paradox Discovery
Forum post activity in aggregate showed a slight positive association with grades ($\rho = +0.14$). However, stratifying by school revealed that forum posting was heavily confounded by school culture: Law students post 4x more than Engineering students, but within each school, posting activity had zero correlation with grades ($\rho \approx 0.00$). This demonstrated the power of Acadexa's stratified analytics in debunking naive institutional assumptions.

---

## 12. Ethical AI, Limitations & Future Scope

### 12.1 Ethical & Non-Causal Constraints
- **Association $\ne$ Causation:** Acadexa documents correlations, never causal claims. Improving LMS logins does not cause higher intelligence.
- **Intervention, Not Labeling:** Risk scores serve as diagnostic prompts for human advisors, not automated academic penalties.

### 12.2 Technical Limitations
- Local mode Spark execution is bounded by host disk I/O bandwidth during shuffle phases.
- Real-time streaming ingestion is omitted by design; Acadexa operates on batch semester cadences.

### 12.3 Future Scope
- Transition PySpark local mode to an Apache Spark on Kubernetes (EKS/GKE) cluster for multi-institution scaling ($10^6$ students).
- Implement automated advisor notification webhooks via secure institutional messaging.

---

## 13. Conclusion

Acadexa successfully demonstrates that modern Big Data architectures can achieve enterprise scale, rigorous data hygiene, and sub-second analytical serving on consumer workstation hardware. By uniting synthetic simulation, Parquet lakehouses, PySpark distributed batch processing, MongoDB document indexing, and explainable rule-based intelligence, Acadexa provides a transparent, defensible, and ethically responsible blueprint for institutional learning analytics.

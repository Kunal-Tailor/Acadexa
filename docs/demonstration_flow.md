# Acadexa — Final Demonstration & Viva Presentation Flow

**Document:** `docs/demonstration_flow.md`  
**Purpose:** Step-by-step presentation script, timed demonstration flow, and technical defense guide for academic evaluators, project vivas, and faculty panels.  
**Target Duration:** 15–20 minutes  
**Application URL:** `http://localhost:8501` (`streamlit run src/acadexa/dashboard/app.py`)

---

## 1. Quick Launch Checklist (Before the Presentation)

1. **Verify MongoDB Service:**
   ```powershell
   Get-Service MongoDB  # Must be Running
   ```
2. **Start Dashboard:**
   ```powershell
   $env:PYTHONPATH='d:\College\Secondary\Projects\acadexa\src'
   streamlit run src/acadexa/dashboard/app.py
   ```
3. **Open Browser:** Navigate to `http://localhost:8501`. Ensure browser zoom is set to 100% and sidebar is expanded.

---

## 2. Timed Demonstration Script (Minute-by-Minute)

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        DEMONSTRATION TIMELINE                          │
│                                                                        │
│ 00:00 - 02:00  [Phase 1] Project Orientation & Big Data Context        │
│ 02:00 - 04:00  [Phase 2] Role Selection & University Overview          │
│ 04:00 - 06:00  [Phase 3] School & Department Hierarchy Drill-Down      │
│ 06:00 - 08:00  [Phase 4] Course Intelligence & Z-Score Normalization   │
│ 08:00 - 10:00  [Phase 5] Student Profile & Longitudinal Clickstream    │
│ 10:00 - 12:00  [Phase 6] Explainable Five-Rule Risk Engine             │
│ 12:00 - 14:00  [Phase 7] Advanced Analytics & Simpson's Paradox        │
│ 14:00 - 16:00  [Phase 8] Data Quality & Ingestion Traceability         │
│ 16:00 - 18:00  [Phase 9] J8 Benchmarks & Empirical Scalability Proof   │
│ 18:00 - 20:00  [Phase 10] Architecture Defense & Panel Q&A             │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 1: Project Orientation & Big Data Context (00:00 – 02:00)
- **Speaker Action:** Introduce the project title and core problem.
- **Key Talking Points:**
  - *"Acadexa is an end-to-end, batch-oriented Big Data analytics and academic early-warning platform modeled on the fictional RAS University."*
  - *"Higher education institutions capture massive interaction clickstreams (74.7M events across 12,000 students), but face two critical barriers: single-node memory exhaustion and opaque, untrustworthy machine learning black boxes."*
  - *"Acadexa demonstrates that a dual-storage architecture—Apache Parquet for event lakes, MongoDB for operational serving, and PySpark for out-of-core batch processing—delivers sub-5ms analytical serving with 100% explainable, rule-based student risk diagnostics."*
- **Visual:** Display the README architectural diagrams and terminal window.

---

### Phase 2: Role Selection & University Overview (02:00 – 04:00)
- **Action:** On the login screen, select **University Administrator** (`admin`). Click *Login*.
- **Key Talking Points:**
  - *"Notice the role-based access control (RBAC). Acadexa enforces four strict roles: Admin, Dean, Faculty, and Analyst."*
  - *"On the University Overview page, we observe institution-wide KPIs computed by PySpark J7: 12,000 total students, 6 schools, and macro attendance and LMS engagement averages."*
  - *"Change the semester filter (S1 through S4) to demonstrate multi-term tracking across academic years."*
- **Visual:** Highlight KPI cards and the School Comparison bar chart.

---

### Phase 3: School & Department Hierarchy Drill-Down (04:00 – 06:00)
- **Action:** Click **Schools & Departments** in the sidebar. Select **School of Engineering & Technology (SET)**.
- **Key Talking Points:**
  - *"Here we drill down into the institution hierarchy. SET represents 3,000 students across multiple departments (e.g., Computer Science, Electrical Engineering)."*
  - *"Notice how department-level metrics (average final scores, submission lateness rates) automatically re-scope without querying unaggregated clickstream events."*
  - *"Highlight the department risk distribution showing the breakdown of students triggering multiple early-warning flags."*
- **Visual:** Department performance matrix and late submission distribution.

---

### Phase 4: Course Intelligence & Z-Score Normalization (06:00 – 08:00)
- **Action:** Click **Courses** in the sidebar. Select a core course (e.g., `CS101` or `MGT101`).
- **Key Talking Points:**
  - *"Raw course marks can be deceptive: an average of 60% in a rigorous engineering course might represent higher mastery than 75% in an introductory elective."*
  - *"Acadexa resolves this via PySpark Job J4 by implementing within-course Z-score normalization: $(X - \mu)/\sigma$."*
  - *"Point out the difficulty-adjusted performance metric and enrollment counts across term offerings."*
- **Visual:** Course enrollment count, grade distribution bell curve, and assignment completion rate.

---

### Phase 5: Student Profile & Longitudinal Clickstream (08:00 – 10:00)
- **Action:** Click **Students** in the sidebar. Enter a student ID (e.g., `STU000001` or select a sample student).
- **Key Talking Points:**
  - *"This view synthesizes four separate data domains: demographics, multi-term academic grades, weekly class attendance, coursework submission timing, and LMS engagement velocity."*
  - *"Highlight the weekly attendance sparkline and coursework completion progress."*
  - *"Explain that the underlying data represents a seamless multi-way outer join executed by PySpark Job J3."*
- **Visual:** Integrated student radar chart, coursework completion table, and attendance history.

---

### Phase 6: Explainable Five-Rule Risk Engine (10:00 – 12:00)
- **Action:** Scroll to the **Academic Risk Diagnostics** section of the student profile.
- **Key Talking Points:**
  - *"Crucial Design Choice: Acadexa explicitly rejects black-box ML failure probability scores (e.g., '78% chance of dropout'). Faculty and advisors cannot act on unexplained probabilities."*
  - *"Instead, Job J6 implements an explainable five-rule risk engine:"*
    1. *Attendance $< 75\%$*
    2. *Late-semester LMS drop $\le 50\%$ of baseline*
    3. *Coursework late submission rate $> 30\%$*
    4. *Marks decline between checkpoints $\ge 10$ points*
    5. *Quiz activity in bottom quartile ($< 25\text{th}$ percentile)*
  - *"Show the diagnostic explanation box: Acadexa provides clear natural-language evidence explaining exactly why the flag was triggered."*
- **Visual:** Risk badge ($0 \dots 5$), signal breakdown cards, and human-readable explanation text.

---

### Phase 7: Advanced Analytics & Simpson's Paradox (12:00 – 14:00)
- **Action:** Logout and log in as **Academic Analyst** (`analyst`). Navigate to **Analytics**.
- **Key Talking Points:**
  - *"This page demonstrates PySpark Job J4 and non-parametric Spearman rank correlation ($\rho$)."*
  - *"Show Ground-Truth Recovery: Attendance positively correlates with marks ($\rho = +0.443$), late submissions negatively correlate ($\rho = -0.292$), and our decoy variable correctly displays zero correlation ($\rho = +0.012$)."*
  - *"Showcase Simpson's Paradox: Naive aggregate analysis suggests forum posts correlate with higher marks. But when stratified by school, forum posting has zero effect on grades—the aggregate correlation was an artifact of School of Law having a higher baseline discussion culture."*
- **Visual:** Spearman correlation matrix and school-stratified forum scatter plots.

---

### Phase 8: Data Quality & Ingestion Traceability (14:00 – 16:00)
- **Action:** Click **Data Quality** in the sidebar.
- **Key Talking Points:**
  - *"Real-world data is corrupted. We injected 2.64 million controlled anomalies into the synthetic raw dataset (duplicate logs, null fields, malformed course IDs, orphan keys)."*
  - *"Walk through Job J1's measurable outcomes: 1,551,722 detected; 748,183 corrected; 803,539 dropped."*
  - *"Point to the bottom line: Exactly zero anomalies remained in the cleaned dataset before analytical jobs commenced."*
- **Visual:** Category-by-category Data Quality health matrix (Healthy / Attention / Dropped).

---

### Phase 9: J8 Benchmarks & Empirical Scalability Proof (16:00 – 18:00)
- **Action:** Present `reports/benchmarks/full_scale_benchmark_report.md`.
- **Key Talking Points:**
  - *"To prove our architecture was necessary and not over-engineered, Job J8 benchmarked Pandas against PySpark on 74,757,153 raw LMS events."*
  - *"Result: Single-node Pandas exhausted 24 GB of RAM and crashed with `MemoryError` after 643 seconds. PySpark completed the out-of-core aggregation in 151 seconds."*
  - *"This empirical failure boundary proves that distributed batch architectures are mandatory for institutional clickstream analytics."*
- **Visual:** Benchmark comparison table and execution time graphs.

---

### Phase 10: Technical Defense & Panel Q&A (18:00 – 20:00)
- **Action:** Open floor for faculty evaluation and defense questions.

---

## 3. Defense FAQ & Model Answers for Project Viva

#### Q1: "Why did you choose a rule-based risk engine instead of training an XGBoost or Random Forest model?"
> **Answer:** *"In higher education, predictive ML models suffer from three fatal flaws: lack of interpretability (the 'black box' problem), historical training bias that reinforces demographic inequities, and legal/ethical accountability. A student told they have an '82% risk of failure' receives no diagnostic guidance. Acadexa's five rules directly mirror institutional policies (e.g. 75% attendance rules) and produce actionable natural-language explanations (e.g. 'Attendance is 68%, coursework submitted 4 days late'), enabling advisors to intervene transparently."*

#### Q2: "How does 4.5 GB of raw data compress into a Gold MongoDB layer of only 25 MB?"
> **Answer:** *"This is the fundamental principle of Big Data dimensionality reduction. The Bronze layer stores high-frequency clickstream actions—74.7 million individual clicks, downloads, and page views. The Gold layer aggregates these events into student-semester summaries (attendance rates, engagement hours, average scores). This represents a 99.93% reduction in row cardinality (from 74.7M rows to 48,000 student-semester rows). By pre-computing this aggregation offline in PySpark (~14 minutes), MongoDB can return indexed analytical queries to Streamlit in under 5 milliseconds."*

#### Q3: "Why not ingest all 74.7 million LMS events directly into MongoDB?"
> **Answer:** *"Loading 75 million uncompressed JSON documents would consume ~35 GB of disk space and completely exhaust MongoDB's WiredTiger cache on workstation hardware, causing severe disk thrashing and 10–30 second dashboard query latencies. By keeping the full clickstream lake in partitioned Parquet files and loading only an operational serving slice (~8.95M documents for S4 CET/SOM) into MongoDB, we maintain instantaneous sub-second query responsiveness while preserving complete analytical auditability in Parquet."*

#### Q4: "What makes Acadexa's synthetic data academically valid?"
> **Answer:** *"Rather than injecting random noise, Acadexa implements a latent trait behavioral model where each student is parameterized with latent ability, diligence, and engagement traits sampled from Gaussian distributions. We pre-register mathematical ground truth (positive attendance correlation, negative late submission correlation, and a decoy forum variable), and then verify in Job J4 that our analytical pipeline recovers the planted associations within $|\Delta \rho| \le 0.10$ without discovering spurious relationships."*

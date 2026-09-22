# Acadexa — UI/UX & Design Specification

**Document:** `docs/design.md`  
**Project:** Acadexa  
**Institution:** RAS University  
**Status:** Working baseline  
**Primary references:** `data.md`, `docs/prd.md`, `docs/architecture.md`, `docs/features.md`, `docs/rules.md`

---

# 1. Purpose

This document defines the visual, interaction and information-design direction for the Acadexa dashboard.

Acadexa is a Big Data academic intelligence system. The dashboard must therefore communicate:

- academic performance,
- attendance,
- LMS engagement,
- coursework behavior,
- trends,
- risk signals,
- data quality,
- analytical relationships,

without making the interface look like a generic student-management portal.

The UI should make the underlying Big Data pipeline visible through useful analytical views while remaining understandable to university users.

---

# 2. Design Principles

The design follows these principles:

1. **Analytical first** — prioritize useful information over decoration.
2. **Hierarchy first** — university → school → department → program → course → student.
3. **Explainability** — every derived indicator should be understandable.
4. **Progressive detail** — overview first, detail on demand.
5. **Role awareness** — users should see information relevant to their scope.
6. **Consistency** — the same metric should look and behave consistently across pages.
7. **Data honesty** — estimated, synthetic, measured and derived values must not be visually confused.
8. **Performance awareness** — the UI should primarily consume prepared MongoDB/gold data rather than repeatedly running expensive processing.
9. **Academic neutrality** — risk signals are analytical indicators, not predictions or judgments about a student's future.
10. **Professional presentation** — the final dashboard should be suitable for a final-year Big Data project demonstration.

---

# 3. Product Personality

Acadexa should feel:

```text
Professional
Analytical
Clean
Trustworthy
Technical
Academic
Calm
Data-driven
```

It should not feel:

```text
Gamified
Social-media-like
Overly colorful
Consumer-fintech-like
AI-hype-heavy
Artificially futuristic
```

The interface should communicate that Acadexa is an analytical platform rather than a decorative AI dashboard.

---

# 4. Visual Direction

## 4.1 Overall style

Use a modern academic analytics dashboard with:

- spacious layouts,
- restrained color usage,
- strong typography,
- compact but readable data cards,
- clean tables,
- purposeful charts,
- clear section hierarchy.

Avoid excessive:

- gradients,
- glassmorphism,
- glowing effects,
- animated backgrounds,
- decorative illustrations,
- oversized icons.

---

# 5. Color System

The color system should use a restrained academic/enterprise palette.

Suggested semantic system:

| Purpose | Role |
|---|---|
| Primary | Main Acadexa actions and selected navigation |
| Secondary | Supporting UI elements |
| Background | Main application canvas |
| Surface | Cards, panels and tables |
| Text | Primary readable text |
| Muted text | Supporting metadata |
| Success | Positive/healthy state |
| Warning | Attention state |
| Danger | High-risk/data-quality issue |
| Info | Informational analytical state |

The exact hex values may be adjusted during implementation, but semantic roles must remain stable.

## 5.1 Semantic colors

Do not use red simply because a value is numerically low.

Red should represent:

- a defined warning/risk condition,
- a data-quality failure,
- an explicit exception.

Similarly:

- green = healthy/positive state,
- amber = attention,
- blue/neutral = information.

The five-rule risk indicator should use semantic severity carefully.

---

# 6. Typography

Use a clean sans-serif interface font.

Typography hierarchy:

```text
Application title
    ↓
Page title
    ↓
Section title
    ↓
Metric value
    ↓
Metric label
    ↓
Body text
    ↓
Metadata / helper text
```

Avoid using many font families.

Recommended hierarchy:

- Page titles: strong/bold
- Section headings: semibold
- KPI values: bold
- Labels: medium
- Supporting text: regular
- Metadata: smaller and muted

Numbers should be easy to scan.

---

# 7. Layout System

The application should use a consistent desktop-first dashboard structure.

Conceptually:

```text
┌───────────────────────────────────────────────────────────────┐
│ Acadexa                                  User / Role / Logout │
├──────────────┬────────────────────────────────────────────────┤
│              │                                                │
│ Navigation   │ Page header                                   │
│              │ Context / filters                              │
│              ├────────────────────────────────────────────────┤
│              │ KPI cards                                      │
│              ├───────────────────────┬────────────────────────┤
│              │ Primary analytical    │ Secondary insight      │
│              │ visualization         │ / breakdown            │
│              ├───────────────────────┴────────────────────────┤
│              │ Detailed table / explanation                   │
│              │                                                │
└──────────────┴────────────────────────────────────────────────┘
```

The exact Streamlit implementation may differ, but the information hierarchy should remain.

---

# 8. Navigation

The primary navigation should expose the major analytical areas.

Recommended structure:

```text
Overview
Schools
Courses
Students
Analysis
Data Quality
```

A separate login screen precedes the dashboard.

The navigation should not expose every internal Spark job or database collection.

Users interact with analytical concepts, not implementation internals.

---

# 9. Header

The header should communicate:

- Acadexa identity,
- current page,
- current academic context,
- logged-in user,
- role,
- logout/session control.

Example:

```text
Acadexa
Academic Intelligence

University Overview                         RAS University
AY 2025–26 · Semester 2                    Academic Analyst
```

Avoid excessive header controls.

---

# 10. Global Filters

Where applicable, filters should appear near the page header.

Potential filters include:

```text
Academic Year
Semester
School
Department
Program
Course
```

Not every page needs every filter.

Filters must respect the user's scope.

For example:

```text
University Admin
→ can select university-wide schools

School Admin
→ school is fixed or restricted

Faculty
→ course scope is restricted

Academic Analyst
→ broad analytical access
```

---

# 11. Context Breadcrumbs

Detailed views should communicate hierarchy.

Example:

```text
RAS University
› School of Computing
› Department of Computer Science
› B.Tech AI & Data Science
› Big Data Technologies
› Student
```

This makes navigation context clear.

---

# 12. KPI Cards

KPI cards should answer important high-level questions quickly.

Examples:

```text
Active Students
12,000

Average Marks
72.4

Average Attendance
81.7%

LMS Engagement
68.2%

Students With Risk Signals
1,284
```

These are examples of presentation patterns, not hard-coded values.

The dashboard must retrieve actual values from the data layer.

Each KPI should have:

- clear label,
- current value,
- unit where necessary,
- time context,
- optional comparison,
- optional short explanatory text.

---

# 13. KPI Rules

Never show a number without enough context to interpret it.

Bad:

```text
72.4
```

Better:

```text
Average Marks
72.4 / 100
Semester 2 · 2025–26
```

For percentages:

```text
Average Attendance
81.7%
```

For counts:

```text
Active Students
12,000 students
```

---

# 14. University Overview

The University Overview is the primary landing page after login for broad-scope users.

It should answer:

1. How large is the academic population?
2. What is overall academic performance?
3. What is attendance like?
4. How engaged are students with the LMS?
5. Where are notable differences between schools?
6. Are there visible trend/risk signals?
7. What should the user inspect next?

Suggested structure:

```text
Header
↓
Global context
↓
University KPIs
↓
School comparison
↓
Academic vs engagement overview
↓
Trend section
↓
Risk signal summary
↓
Recent/important analytical observations
```

---

# 15. School View

The School view should compare schools without creating an unfair or overly simplistic ranking.

Display:

- student population,
- average marks,
- attendance,
- LMS engagement,
- coursework behavior,
- trend indicators,
- risk-signal distribution.

Useful visualizations:

- grouped bar chart,
- dot plot,
- compact comparison table,
- trend lines.

Avoid presenting a single composite "best school" score unless such a metric is explicitly added to the requirements.

---

# 16. Department View

Department pages should provide a similar analytical structure at department level.

Recommended sections:

```text
Department summary
↓
Student population
↓
Academic performance
↓
Attendance
↓
LMS engagement
↓
Course-level breakdown
↓
Trend/risk indicators
```

The user should be able to move from department to course.

---

# 17. Course View

The Course view is important because the synthetic generator intentionally includes course difficulty and planted relationships.

Show:

- course metadata,
- enrollment,
- average marks,
- attendance,
- coursework performance,
- LMS engagement,
- late submissions,
- trend,
- relevant associations.

Where appropriate, show:

```text
Course Performance
        vs
Attendance
        vs
LMS Engagement
```

Do not imply that one factor causes another.

---

# 18. Student View

The student view should integrate multiple factors rather than only display marks.

Recommended structure:

```text
Student profile
↓
Academic summary
↓
Attendance
↓
Coursework
↓
LMS engagement
↓
Recent trend
↓
Risk signal breakdown
↓
Explanation
```

The student page should make it possible to understand why a student received a particular number of risk signals.

Example:

```text
Risk signals: 3 / 5

✓ Attendance below threshold
✓ LMS engagement declined
✕ No late-submission signal
✓ Marks trend declined
✕ Quiz activity not in bottom quartile
```

The interface should say **signal** rather than **prediction**.

---

# 19. Risk Indicator UX

The risk indicator must be visually prominent but not sensational.

Preferred presentation:

```text
Risk Signals
3 / 5

3 observed indicators require attention
```

Avoid:

```text
HIGH FAILURE PROBABILITY
```

or:

```text
Student will fail
```

because the system does not make those claims.

## 19.1 Signal breakdown

Always provide the underlying signals when possible.

Example:

```text
Attendance       ● Triggered
LMS decline      ● Triggered
Late submissions ○ Not triggered
Marks decline    ● Triggered
Quiz activity    ○ Not triggered
```

This makes the result auditable.

---

# 20. Analysis Page

The Analysis page is the technical/analytical centerpiece.

It should expose:

- cross-factor correlations,
- trend analysis,
- engagement analysis,
- recovery-test results where appropriate,
- analytical methodology notes.

Suggested sections:

```text
Analysis Overview
↓
Factor Relationships
↓
Trend Detection
↓
Engagement Analysis
↓
Ground-Truth Recovery
↓
Methodology
```

---

# 21. Correlation Visualization

Correlation should be visually understandable.

Suitable options:

- correlation matrix,
- scatter plot,
- ranked association table.

Example factors:

```text
Attendance
LMS Engagement
Late Submission Rate
Marks
```

When using a correlation coefficient, display:

- method,
- coefficient,
- sample scope,
- course/semester context where applicable.

Example:

```text
Spearman ρ = 0.42
Attendance ↔ Marks
Within-course normalized
Semester 2
```

Do not label this as causal impact.

---

# 22. Trend Visualization

Trend views should emphasize change over time.

Use:

- line charts,
- rolling-period comparisons,
- before/after windows,
- small multiples where useful.

For the defined engagement logic:

```text
Previous 4 weeks
        vs
Current 4 weeks
```

The visual should make the comparison obvious.

---

# 23. LMS Engagement Visualization

Useful measures may include:

- weekly active days,
- event counts,
- content views,
- assignment interactions,
- quiz attempts,
- submission activity.

Avoid presenting raw event volume as automatically equivalent to learning quality.

Use labels such as:

```text
LMS activity
Engagement events
Weekly active days
```

rather than unsupported interpretations such as:

```text
Learning quality
Student intelligence
```

---

# 24. Coursework Visualization

Coursework views should expose:

- submissions,
- late submissions,
- quiz performance,
- assignment performance,
- trend where available.

Use tables when exact values matter.

Use charts when comparisons or trends matter.

---

# 25. Data Quality Page

The Data Quality page is an important demonstration feature because veracity is one of Acadexa's Big Data dimensions.

It should communicate:

```text
Records processed
Issues injected
Issues detected
Issues corrected
Issues dropped
Remaining issues
```

Potential issue categories:

```text
Duplicates
Nulls
Timestamp inconsistencies
Course-ID formatting
Orphan records
Out-of-range values
```

A compact table is preferable to decorative charts.

---

# 26. Data Quality Status

Use clear states:

```text
Healthy
Attention
Issue
```

Each status should have an explanation.

Example:

```text
Duplicate LMS events
Injected: 70,000
Detected: 69,842
Resolved: 69,842
Status: Healthy
```

Actual values must come from measured pipeline output.

---

# 27. Benchmark Page / Section

Benchmark results should be presented as engineering measurements.

Compare:

```text
Pandas
MongoDB Aggregation
PySpark
```

where the workload supports the comparison.

Display:

- workload,
- dataset size,
- execution time,
- peak memory where measured,
- environment.

Do not visually imply that one technology "won" unless the underlying benchmark interpretation genuinely supports a specific conclusion; the page should primarily show measured trade-offs.

---

# 28. Tables

Tables should be used when users need:

- exact values,
- sorting,
- filtering,
- identifiers,
- detailed records.

Recommended columns should be limited to what users need.

Avoid tables containing 20+ columns when a drill-down can provide the details.

---

# 29. Charts

Every chart should answer a question.

Before adding a chart, ask:

```text
What question does this visualization answer?
```

If the answer is unclear, do not add the chart.

Charts should include:

- meaningful title,
- axis labels where applicable,
- units,
- legend where necessary,
- sensible formatting.

Avoid 3D charts.

Avoid pie charts when many categories exist.

Avoid decorative chart animations.

---

# 30. Empty States

Empty states must be explicit.

Examples:

```text
No course data is available for this selection.
```

```text
No risk signals were detected for the selected scope.
```

Do not interpret empty data as zero unless the data model explicitly supports that interpretation.

---

# 31. Error States

Errors should be understandable to users.

Example:

```text
Unable to load course analytics.

The analytical data service is currently unavailable.
Please check the database connection and try again.
```

Do not expose raw Python stack traces in the normal UI.

Detailed technical information should remain in logs.

---

# 32. Loading States

Long-running operations should communicate progress where possible.

Examples:

```text
Loading university metrics...
Loading course analytics...
Preparing benchmark results...
```

The UI should avoid appearing frozen.

The dashboard should not trigger expensive Spark processing merely because a user changes a filter unless that behavior is intentionally designed.

---

# 33. Login Screen

The login page should be simple.

Suggested structure:

```text
        Acadexa

Academic Intelligence Platform
RAS University

[ Username ]

[ Password ]

[ Sign In ]

Demo environment
```

Because the authentication is demonstrational, the UI should not imply production security.

---

# 34. Role-Aware Experience

## University Admin

Primary needs:

- university overview,
- school comparisons,
- high-level trends,
- risk-signal distribution,
- data-quality status.

## School / Department Admin

Primary needs:

- scoped school/department analytics,
- course comparisons,
- student-level drill-down,
- trends,
- risk indicators.

## Faculty

Primary needs:

- course analytics,
- attendance,
- coursework,
- LMS engagement,
- student-level analytical view within permitted scope.

## Academic Analyst

Primary needs:

- broad analytical access,
- cross-factor analysis,
- trends,
- recovery testing,
- benchmarks,
- data quality.

---

# 35. Responsive Behavior

The primary target is desktop/laptop usage because Acadexa is an academic analytics dashboard.

Still:

- avoid fixed-width content that becomes unusable,
- allow charts to resize,
- preserve readable tables,
- avoid excessive horizontal scrolling,
- keep navigation usable at smaller widths.

Mobile-first optimization is not a core requirement.

---

# 36. Accessibility

The dashboard should provide:

- readable contrast,
- meaningful labels,
- text explanations for important visual indicators,
- non-color-only status communication,
- sensible heading hierarchy.

For example, do not communicate risk using only:

```text
red = risk
green = safe
```

Also show text:

```text
3 / 5 signals triggered
```

---

# 37. Microcopy Rules

Use concise, factual language.

Prefer:

```text
3 of 5 risk signals triggered
```

over:

```text
This student is at serious risk of failing!
```

Prefer:

```text
LMS engagement decreased 38% compared with the previous four-week period.
```

over:

```text
Student engagement collapsed.
```

Prefer:

```text
Observed association
```

over:

```text
Impact
```

unless the metric genuinely represents impact.

---

# 38. Synthetic Data Disclosure

The application should clearly communicate that Acadexa uses synthetic data.

A suitable global or About-area notice:

```text
Acadexa uses fully synthetic academic and LMS data for demonstration,
analysis and Big Data engineering purposes. Results do not represent
real students or real institutional outcomes.
```

This disclosure should be visible without dominating the interface.

---

# 39. Analytical Methodology Disclosure

Where technical analytics are displayed, expose enough methodology to prevent misinterpretation.

For example:

```text
Method: Spearman correlation
Scope: Within-course normalized observations
Interpretation: Association, not causation
```

For risk:

```text
Risk indicator = count of five predefined observed signals.
It is not a failure prediction model.
```

---

# 40. Design for the MVP

The first vertical slice is:

```text
One school
+
One semester
+
End-to-end data
+
MongoDB
+
PySpark
+
Gold collections
+
Streamlit dashboard
```

The MVP UI should already demonstrate:

- login,
- role,
- overview,
- school/department context,
- course view,
- student view,
- risk signals,
- at least one analytical view,
- data-quality view.

Do not build every advanced visualization before the vertical slice works.

---

# 41. Design for Full Scale

After the MVP works, expand the same UI system to:

```text
6 schools
~18 departments
~40 programs
~250 courses
12,000 students
2 academic years
~70M LMS events
```

The visual system should not need a redesign merely because the data volume increases.

---

# 42. Information Hierarchy Rule

Every page should answer, in order:

```text
Where am I?
↓
What is happening?
↓
How large/significant is it?
↓
Where is the variation?
↓
Why might it be happening?
↓
What should I inspect next?
```

The final question is about investigation, not automated decision-making.

---

# 43. Drill-Down Pattern

Use consistent drill-down behavior:

```text
University
    ↓
School
    ↓
Department
    ↓
Program
    ↓
Course
    ↓
Student
```

A user should not have to return to the home page to move between adjacent levels.

---

# 44. Detail-on-Demand

Do not place every metric on the overview page.

Use:

- expandable sections,
- detail pages,
- tabs where appropriate,
- drill-down links,
- tooltips for definitions.

The overview should remain scannable.

---

# 45. No Fake Intelligence

The UI must not use words such as:

```text
AI predicts
AI knows
AI detected future failure
AI guarantees
```

unless an explicitly approved future feature actually implements such capability.

Acadexa's intelligence comes from:

```text
integrated data
+
Big Data processing
+
analytical rules
+
cross-factor analysis
+
trend detection
```

---

# 46. No Decorative AI Branding

Do not add:

- robot illustrations,
- unnecessary AI brain graphics,
- glowing neural-network backgrounds,
- generic "AI-powered" badges,

unless they serve a real communication purpose.

Acadexa should look like a serious academic analytics platform.

---

# 47. Component Consistency

Repeated components should share a common design.

Examples:

```text
KPI card
Risk signal card
Filter bar
Chart card
Data table
Section header
Status badge
Breadcrumb
```

Do not create five visually different KPI-card styles.

---

# 48. Recommended Component Anatomy

## KPI Card

```text
Label
Value
Unit
Context
Optional comparison
```

## Analytical Card

```text
Title
Short explanation
Visualization
Method/context
Optional source metric
```

## Risk Card

```text
Signal count
Severity/context
Triggered signals
Explanation
```

## Data Quality Card

```text
Issue type
Injected
Detected
Resolved
Status
```

---

# 49. Visual Priority

When a page contains many elements, prioritize:

1. Current scope/context
2. Primary KPIs
3. Main analytical finding
4. Supporting breakdown
5. Detailed records
6. Methodology/help

Do not give secondary metadata the same visual weight as the primary analytical result.

---

# 50. Design Quality Checklist

Before accepting a page, verify:

### Hierarchy

- [ ] Is the current scope obvious?
- [ ] Is the most important information visually dominant?
- [ ] Can a user understand the page quickly?

### Data

- [ ] Are numbers real rather than hard-coded?
- [ ] Are units visible?
- [ ] Is the time period clear?
- [ ] Are synthetic-data limitations clear where relevant?

### Analytics

- [ ] Are associations described as associations?
- [ ] Are risk signals explained?
- [ ] Are trend comparisons explicit?

### UX

- [ ] Are filters understandable?
- [ ] Can users drill down?
- [ ] Are empty states handled?
- [ ] Are errors understandable?

### Visuals

- [ ] Is the color system consistent?
- [ ] Is there unnecessary decoration?
- [ ] Are charts readable?
- [ ] Is color not the only status indicator?

### Roles

- [ ] Does the page respect the user's scope?
- [ ] Are irrelevant controls hidden or disabled?

---

# 51. Design Invariants

The following must remain true as the UI evolves:

1. Acadexa remains an analytical dashboard, not a generic ERP.
2. The hierarchy remains visible.
3. Risk remains a five-rule signal count.
4. Correlation remains non-causal.
5. Synthetic data is disclosed.
6. Dashboard values are data-backed.
7. Role scope is respected.
8. Data-quality information remains inspectable.
9. Big Data capabilities are demonstrated through meaningful analytics rather than decorative UI.
10. The dashboard remains usable under the documented local resource constraints.

---

# 52. Final Design Direction

> **Acadexa should present complex academic Big Data as a calm, structured analytical experience: users begin with university-level signals, move through school/department/course hierarchy, inspect integrated student evidence, and drill into the underlying metrics without losing context.**

The interface should make the project's technical depth visible through:

```text
Scale
+
Hierarchy
+
Cross-factor analytics
+
Temporal trends
+
Data quality
+
Explainable risk signals
+
Measured Big Data processing
```

rather than through visual complexity.

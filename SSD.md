# ProbabilityLab Software Specification Document (SSD)

## 1. Project Overview

### Project Name

**ProbabilityLab -- 这城有良田掉率分析平台**

### Goal

Build a Streamlit application for collecting production data, estimating
true drop rates, validating statistical hypotheses, and simulating game
mechanics using Monte Carlo.

The platform is designed to be extensible while remaining simple enough
for a single-player SQLite deployment.

------------------------------------------------------------------------

# 2. Tech Stack

-   Python 3.13+
-   Streamlit
-   SQLite
-   SQLAlchemy ORM
-   Pandas
-   NumPy
-   SciPy
-   Statsmodels
-   Plotly
-   Pydantic
-   Loguru

Do NOT use: - tkinter - matplotlib - raw sqlite3 - global variables

------------------------------------------------------------------------

# 3. Folder Structure

``` text
ProbabilityLab/
│
├── app.py
├── requirements.txt
├── README.md
├── SSD.md
│
├── config/
│   └── settings.py
│
├── data/
│   └── probability.db
│
├── database/
│   ├── db.py
│   ├── models.py
│   └── repository.py
│
├── services/
│   ├── statistics.py
│   ├── simulator.py
│   ├── estimator.py
│   └── validation.py
│
├── charts/
│   └── plotly_chart.py
│
├── pages/
│   ├── 1_Dashboard.py
│   ├── 2_Data_Entry.py
│   ├── 3_Data_Manager.py
│   ├── 4_Material_Analysis.py
│   ├── 5_Skill_Analysis.py
│   ├── 6_Monte_Carlo.py
│   └── 7_Settings.py
│
├── imports/
├── exports/
└── logs/
```

------------------------------------------------------------------------

# 4. Materials

Initial materials:

-   玉料
-   金精
-   宝珠
-   兽骨
-   锦缎
-   熟皮
-   绢布
-   丝线
-   钢材

Skill Levels:

-   9
-   10
-   11
-   12

------------------------------------------------------------------------

# 5. Database Design

## Material

  Field   Type
  ------- -------------
  id      INTEGER PK
  name    TEXT UNIQUE

## ProductionLog

  Field          Type
  -------------- ------------
  id             INTEGER PK
  datetime       DATETIME
  material_id    INTEGER FK
  skill_level    INTEGER
  quantity       INTEGER
  red_quantity   INTEGER
  remark         TEXT

Validation

-   quantity \> 0
-   red_quantity \>= 0
-   red_quantity \<= quantity
-   skill_level ∈ {9,10,11,12}

## Settings

  Field   Type
  ------- ---------
  key     TEXT PK
  value   TEXT

------------------------------------------------------------------------

# 6. Streamlit Pages

## Dashboard

Display

-   Total Produced
-   Total Red
-   Overall Drop Rate
-   Today
-   This Week
-   This Month

Charts

-   Material Ranking
-   Drop Rate Trend
-   Daily Production
-   Sample Growth

------------------------------------------------------------------------

## Data Entry

Fields

-   Material
-   Skill Level
-   Quantity (default 18)
-   Red Quantity (default 0)
-   Remark

Save immediately into SQLite.

------------------------------------------------------------------------

## Data Manager

Features

-   Search
-   Filter
-   Edit
-   Delete
-   CSV Import
-   CSV Export

------------------------------------------------------------------------

## Material Analysis

Statistics

-   Produced
-   Red
-   Drop Rate
-   95% Confidence Interval
-   Sample Size

Charts

-   Daily Trend
-   Weekly Trend
-   Monthly Trend
-   Histogram

------------------------------------------------------------------------

## Skill Analysis

Filter

-   One Material
-   All Materials

Display

\|Skill\|Produced\|Red\|Rate\|95% CI\|

Charts

-   Drop Rate by Skill
-   Error Bar
-   Sample Size by Skill

------------------------------------------------------------------------

## Monte Carlo

Inputs

-   Material
-   Probability
-   Iterations
-   Quantity Per Production (default 18)

Model V1

Independent Probability

Outputs

-   Mean
-   Median
-   Std
-   Min
-   Max
-   Histogram
-   Overlay with Real Data

Future Models

-   Batch
-   Lucky
-   Guaranteed
-   Custom

------------------------------------------------------------------------

## Settings

-   Default Quantity
-   Default Iterations
-   Theme

------------------------------------------------------------------------

# 7. Statistics Module

Implement

-   calculate_drop_rate()
-   confidence_interval()
-   sample_size()
-   binomial_test()
-   chi_square_test()
-   proportion_z_test()

------------------------------------------------------------------------

# 8. Monte Carlo Module

Class

ProductionSimulator

Methods

-   simulate()
-   simulate_day()
-   simulate_month()
-   simulate_year()

Parameters

-   probability
-   quantity
-   iterations

------------------------------------------------------------------------

# 9. Parameter Fitting (Recommended)

Automatically search probability.

User provides

-   Probability Range
-   Step
-   Iterations

Example

2.5% ↓

4.0%

Step

0.05%

Run Monte Carlo for every candidate.

Compare against real observations.

Return

-   Best Probability
-   Top 10 Candidates
-   Error Score

------------------------------------------------------------------------

# 10. Sample Sufficiency

Every material and every skill level should display

-   Sample Count
-   Estimated Drop Rate
-   95% CI
-   Margin of Error

Quality Rating

A Very Reliable

B Reliable

C Need More Data

D Insufficient

------------------------------------------------------------------------

# 11. CSV

Export

Entire database

Import

Validate

-   Material Exists
-   Skill Valid
-   Quantity Valid
-   Red Valid

If any error exists

Reject import and report row number.

------------------------------------------------------------------------

# 12. Visualization

Use Plotly only.

Charts

-   Line
-   Bar
-   Scatter
-   Histogram
-   Box Plot
-   Heatmap

Support Dark Mode.

------------------------------------------------------------------------

# 13. Error Handling

Show user-friendly errors.

Log every exception.

Never crash Streamlit.

------------------------------------------------------------------------

# 14. Coding Standards

-   PEP8
-   Type Hints
-   Docstrings
-   Repository Pattern
-   Service Layer
-   No duplicated logic
-   Modular architecture

------------------------------------------------------------------------

# 15. Future Roadmap

Phase 2

-   Bayesian Estimation
-   Logistic Regression
-   Multiple Simulation Models

Phase 3

-   Multi-user
-   Cloud Database
-   REST API
-   Community Data Upload

------------------------------------------------------------------------

# 16. Development Order

1.  Database
2.  SQLAlchemy Models
3.  Repository
4.  Data Entry
5.  Dashboard
6.  Material Analysis
7.  Skill Analysis
8.  Monte Carlo
9.  Parameter Fitting
10. CSV
11. Settings
12. Optimization

------------------------------------------------------------------------

# 17. Acceptance Criteria

-   SQLite stores all production records.
-   All CRUD operations work.
-   Statistical calculations are validated.
-   Monte Carlo supports at least 100,000 iterations.
-   Plotly charts render correctly.
-   CSV import/export passes validation.
-   Application remains responsive during long simulations using
    Streamlit spinner.

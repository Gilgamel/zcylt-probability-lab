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

Deletion requires both explicit irreversible-action confirmation and a password
that matches `DELETE_PASSWORD` from Streamlit Secrets. The password must never
be stored in source code, application data, or logs. Deletion remains disabled
when that secret is not configured.

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

# 18. V1.1 Amendment — New Game Categories

> **This section supersedes any earlier SSD requirement that treats all tracked outcomes as material production.**

The application must now support three top-level game categories:

1. **官匠营** — material production
2. **马厩** — selectable horse search
3. **灵禽院** — random or targeted bird/spirit cultivation

The existing nine materials remain under **官匠营**.

## 18.1 官匠营

Materials:

- 玉料
- 金精
- 宝珠
- 兽骨
- 锦缎
- 熟皮
- 绢布
- 丝线
- 钢材

Skill levels currently relevant to the project:

- 9
- 10
- 11
- 12

Known proficiency requirements:

| Transition | Proficiency |
|---|---:|
| 9 → 10 | 200 |
| 10 → 11 | 800 |
| 11 → 12 | 1600 |

These are reference values only. Do not use them as statistical weights.

## 18.2 马厩

Horse breeds:

- 浴火烈马
- 踏水飞马
- 穿林骏马
- 裂岩铁马

Rules:

- The player selects the horse breed before searching.
- One search session allows at most **8** searches.
- Default level is **10**, because level 10 is currently treated as max level.
- The main target is **橙品** probability.
- Full quality results should also be recorded so the complete displayed distribution can be tested.

Displayed probabilities:

| Quality | Displayed |
|---|---:|
| 绿品 | 41% |
| 蓝品 | 50% |
| 紫品 | 7% |
| 橙品 | 1% |

**Important:** these displayed probabilities total 99%.

The application must NOT silently normalize them.

The UI must show a warning:

> 马厩提示概率合计为 99%，请确认游戏是否存在四舍五入、未显示的小数概率或其他结果。

For simulation, support two modes:

### Literal Display Mode

Use:

```text
Green  0.41
Blue   0.50
Purple 0.07
Orange 0.01
Other  0.01
```

The remaining 1% is explicitly represented as `Other / Unaccounted`.

### Normalized Display Mode

Normalize 41/50/7/1 to 100% only for simulation.

The UI must clearly label this as:

`仅用于模拟的归一化概率`

Never treat normalized probabilities as the official displayed probabilities.

## 18.3 灵禽院

Bird types:

- 铁羽雁
- 九炎鹊
- 出云鹤
- 暗铁鸦

Rules:

- The player may use ordinary cultivation, where each result produces one of the four types.
- The player may instead choose a specific bird type before targeted cultivation.
- Random and targeted cultivation must be stored separately so targeted records do not enter the non-official equal-25% species test.
- Default level is **10**.
- The main target is **橙品** probability.
- Record both resulting species and quality whenever practical.

Displayed quality probabilities:

| Quality | Displayed |
|---|---:|
| 蓝品 | 79% |
| 紫品 | 20% |
| 橙品 | 1% |

These sum to 100%.

The application must separately analyze:

1. Overall quality probability.
2. Bird species distribution.
3. Quality × bird species.

If equal species probability is tested, use 25% per species as a **test hypothesis only**. Do not claim that 25% is an official probability unless the game explicitly states it.

# 19. V1.1 Database Model

The previous material-only model must be generalized.

Recommended final V1 database tables:

```text
Category
Item
Observation
ProbabilityTarget
Settings
SimulationRun
```

## 19.1 Category

```text
id
name
category_type
```

Seed data:

```text
官匠营 | MATERIAL_PRODUCTION
马厩   | HORSE_SEARCH
灵禽院 | BIRD_RANDOM
```

## 19.2 Item

```text
id
category_id
name
active
```

Items include all materials, horse breeds, and bird species.

## 19.3 Observation

Use one normalized observation table so the statistical engine can work across all systems.

```text
id
observed_at
category_id
item_id
level
attempt_count
green_count
blue_count
purple_count
orange_count
unaccounted_count
remark
```

`item_id` semantics differ by category:

- 官匠营: selected material.
- 马厩: selected horse breed.
- 灵禽院: resulting bird species.

## 19.4 ProbabilityTarget

```text
id
category_id
item_id
level
quality
displayed_probability
source_note
```

Displayed probabilities must be stored in the database rather than hard-coded in UI or simulation code.

## 19.5 SimulationRun

```text
id
created_at
category_id
item_id
model_name
probability
trial_count
simulation_runs
random_seed
result_json
```

# 20. V1.1 Data Entry Workflows

## 20.1 官匠营

Input:

- Material
- Skill level
- Quantity
- Orange/red count
- Optional full quality counts
- Remark

Default quantity: **18**.

The entry form should be optimized for repeated hourly collection.

## 20.2 马厩

Input:

- Horse breed
- Level
- Search count
- Green count
- Blue count
- Purple count
- Orange count
- Remark

Defaults:

```text
Level = 10
Search count = 1
```

Validation:

```text
1 <= search_count <= 8
```

Example valid batch:

```text
Horse = 浴火烈马
Level = 10
Searches = 8
Green = 3
Blue = 3
Purple = 1
Orange = 1
```

Known quality counts must equal search count unless an `unaccounted_count` is explicitly recorded.

## 20.3 灵禽院

Input:

- Level
- Search count
- Bird species result(s)
- Quality result(s)
- Remark

Defaults:

```text
Level = 10
Search count = 1
```

The UI must **not** ask the user to choose a desired bird species before searching.

Recommended fast-entry UI for individual observations:

```text
Search 1 → Species [dropdown] → Quality [dropdown]
Search 2 → Species [dropdown] → Quality [dropdown]
...
```

An aggregated batch-entry mode may also be provided.

# 21. V1.1 Horse Analysis

Create page:

```text
pages/6_Horse_Analysis.py
```

Filters:

- Horse breed
- Level
- Date range
- Session size

Main metrics:

- Total searches
- Orange count
- Observed orange probability
- Displayed orange probability = 1%
- Difference in percentage points
- 95% confidence interval
- Exact binomial test p-value
- Sample sufficiency

Full quality table:

| Quality | Observed | Displayed |
|---|---:|---:|
| Green | ... | 41% |
| Blue | ... | 50% |
| Purple | ... | 7% |
| Orange | ... | 1% |
| Other | ... | 1%* |

`*` only applies to literal display mode because the supplied displayed values total 99%.

## 21.1 Horse Breed Comparison

Compare:

| Breed | Searches | Orange | Rate | 95% CI |
|---|---:|---:|---:|---:|
| 浴火烈马 | ... | ... | ... | ... |
| 踏水飞马 | ... | ... | ... | ... |
| 穿林骏马 | ... | ... | ... | ... |
| 裂岩铁马 | ... | ... | ... | ... |

This analysis must not assume that the four breeds have identical probabilities merely because the displayed quality probabilities are the same.

# 22. V1.1 Bird Analysis

Create page:

```text
pages/7_Bird_Analysis.py
```

Main quality table:

| Quality | Observed | Displayed |
|---|---:|---:|
| Blue | ... | 79% |
| Purple | ... | 20% |
| Orange | ... | 1% |

Main target:

`Observed orange probability vs displayed 1%`

## 22.1 Bird Species Distribution

Display:

| Species | Count | Share |
|---|---:|---:|
| 铁羽雁 | ... | ... |
| 九炎鹊 | ... | ... |
| 出云鹤 | ... | ... |
| 暗铁鸦 | ... | ... |

Optional hypothesis:

```text
H0: each species has probability 25%
```

Use chi-square goodness-of-fit if all expected counts are sufficiently large.

## 22.2 Bird Quality × Species

Display:

| Species | Blue | Purple | Orange |
|---|---:|---:|---:|
| 铁羽雁 | ... | ... | ... |
| 九炎鹊 | ... | ... | ... |
| 出云鹤 | ... | ... | ... |
| 暗铁鸦 | ... | ... | ... |

This is a diagnostic analysis to determine whether orange probability appears to vary by species.

# 23. V1.1 Unified Probability Analysis

All three systems must eventually feed into the same statistical pipeline:

```text
Raw Observation
      ↓
Validation
      ↓
Aggregation
      ↓
Observed Probability
      ↓
Confidence Interval
      ↓
Hypothesis Test
      ↓
Monte Carlo
      ↓
Real vs Simulated Comparison
```

This is the central architecture of the project.

# 24. V1.1 Monte Carlo Requirements

## 24.1 Material

For a material target:

```text
n = production quantity
p = candidate red probability
```

Use an independent Bernoulli model.

## 24.2 Horse

For one search:

```text
Green  = 0.41
Blue   = 0.50
Purple = 0.07
Orange = 0.01
Other  = 0.01   # literal mode only
```

Support 1–8 searches per session.

For 8 searches, display:

- expected orange count
- probability of zero orange
- probability of at least one orange
- probability of 2+ orange
- simulated orange-count distribution

## 24.3 Bird

For quality:

```text
Blue   = 0.79
Purple = 0.20
Orange = 0.01
```

Species should be simulated separately when the species distribution hypothesis is enabled.

Do not assume equal species probability in the primary quality simulation unless explicitly selected by the user.

# 25. V1.1 Real vs Monte Carlo Comparison

For every target, provide:

```text
Observed probability
Displayed probability
Monte Carlo probability
Difference
95% CI
Simulation interval
```

Example:

```text
Horse orange

Observed       1.08%
Displayed      1.00%
Monte Carlo    1.00%
Difference     +0.08 pp
```

The chart must overlay actual and simulated distributions where the observation structure allows it.

# 26. V1.1 Monte Carlo Parameter Fitting

Parameter fitting must be available for:

- 官匠营 red/orange target
- 马厩 orange target
- 灵禽院 orange target

Example search range:

```text
0.50% → 1.50%
step = 0.01 percentage point
```

For each candidate:

1. Run simulation.
2. Calculate expected outcome.
3. Compare against observed data.
4. Record an error score.
5. Rank candidates.

Return:

```text
Best-fit probability
Top 10 candidate probabilities
Error score
Displayed probability rank
```

Important statistical note:

For a simple independent Bernoulli process, the observed success rate is the natural maximum-likelihood estimate. Monte Carlo fitting is primarily a validation/model-comparison mechanism, not a replacement for direct estimation.

# 27. V1.1 Session Analysis

Both 马厩 and 灵禽院 should support session-level analysis.

A session can contain up to 8 searches.

Display:

- Number of sessions
- Average searches/session
- Sessions with 0 orange
- Sessions with >=1 orange
- Sessions with >=2 orange
- Orange per session

Compare actual session outcomes against Monte Carlo.

For an independent orange probability `p`, the probability of at least one orange in an n-search session is:

```text
1 - (1 - p)^n
```

The application must calculate this dynamically rather than hard-code values.

# 28. V1.1 Statistical Tests

## Orange probability

For horse and bird:

```text
H0: p = 0.01
H1: p != 0.01
```

Use exact binomial testing when appropriate.

## Horse full distribution

Test observed quality counts against the displayed distribution.

Because the supplied probabilities total 99%, literal mode must include the explicit 1% `Other` category.

## Bird full distribution

Test:

```text
Blue = 79%
Purple = 20%
Orange = 1%
```

## Bird species

Optional:

```text
H0: four species are equally likely
```

Use chi-square goodness-of-fit where assumptions are met.

# 29. V1.1 Sample Sufficiency

The application must prioritize **absolute margin of error** for 1% events.

For every target show:

- samples
- observed probability
- 95% CI
- absolute CI width
- margin of error
- estimated additional samples required
- rating

Suggested rating:

```text
A = very strong
B = useful
C = preliminary
D = insufficient
```

The thresholds should be configurable rather than hard-coded into the UI.

# 30. V1.1 Data Collection Strategy

Because orange outcomes are rare, the application must make data collection efficient.

### 官匠营

Record each collection batch.

Default:

```text
Quantity = 18
```

### 马厩

Record one full search session whenever possible.

Maximum:

```text
8 searches/session
```

This is more efficient than recording eight separate rows.

### 灵禽院

Record individual species + quality results whenever possible because species distribution is itself an analysis target.

If speed is more important, allow aggregated batch entry and preserve the aggregate counts.

# 31. V1.1 Recommended Dashboard Sections

Top-level navigation:

```text
Dashboard
Data Entry
Data Manager
官匠营 Analysis
Skill Analysis
马厩 Analysis
灵禽院 Analysis
Monte Carlo
Settings
```

Dashboard cards:

```text
官匠营
Total Production
Red/Orange
Observed Rate

马厩
Searches
Orange
Observed Rate
Displayed Rate

灵禽院
Searches
Orange
Observed Rate
Displayed Rate
```

# 32. V1.1 Acceptance Criteria

## 官匠营

- [ ] Nine materials exist under 官匠营.
- [ ] Skill 9–12 can be recorded.
- [ ] Quantity defaults to 18.
- [ ] Red/orange results can be recorded.
- [ ] Material and skill analysis work.

## 马厩

- [ ] Four horse breeds exist.
- [ ] User selects the breed before searching.
- [ ] Search count is limited to 8.
- [ ] Level defaults to 10.
- [ ] Green/Blue/Purple/Orange counts can be recorded.
- [ ] Orange probability can be compared with 1%.
- [ ] Full distribution can be compared with 41/50/7/1%.
- [ ] The 99% total warning is displayed.
- [ ] Literal and normalized simulation modes both work.

## 灵禽院

- [ ] Four bird species exist.
- [ ] User cannot preselect a desired species.
- [ ] Level defaults to 10.
- [ ] Species result can be recorded.
- [ ] Blue/Purple/Orange can be recorded.
- [ ] Orange probability can be compared with 1%.
- [ ] Quality distribution can be compared with 79/20/1%.
- [ ] Species distribution can be analyzed.
- [ ] Optional 25% equal-species hypothesis can be tested.

## Monte Carlo

- [ ] Material binary simulation works.
- [ ] Horse multinomial simulation works.
- [ ] Bird quality simulation works.
- [ ] 1–8 search sessions can be simulated.
- [ ] Real vs simulated distributions can be compared.
- [ ] Probability fitting works.
- [ ] Fixed random seed produces reproducible results.

# 33. Codex Priority Rule

When implementing this amendment, do not create separate duplicated data models for materials, horses, and birds.

Use:

```text
Category → Item → Observation
```

and make the data-entry and analysis behavior category-specific.

This keeps the database extensible and allows future systems to be added without redesigning the core statistics engine.

When a game mechanic is uncertain, store the raw observation rather than making an irreversible assumption.

The primary goal is not to prove a predetermined probability. The primary goal is to collect enough structured data to determine whether the observed outcomes are consistent with the game's displayed probabilities and whether an independent Monte Carlo model can reproduce those observations.

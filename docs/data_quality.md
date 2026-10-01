# Data Quality Audit & Health Score Methodology

The Data Quality Auditor (`app/tools/quality_tool.py`) performs an automated, multi-dimensional assessment of tabular datasets and computes an objective **Dataset Health Score (0–100)**.

---

## 1. Quality Dimensions Evaluated

| Dimension | Scope | Method & Thresholds | Severity |
| :--- | :--- | :--- | :--- |
| **Row Uniqueness** | Table-wide | Identifies exact duplicate rows across all columns. | **PASS** if 0 duplicates<br>**WARN** if < 5% duplicates<br>**FAIL** if ≥ 5% duplicates |
| **Completeness** | Column-level | Calculates missing/null count and percentage per column. | **WARN** if < 15% missing<br>**FAIL** if ≥ 15% missing |
| **String Integrity** | Text/Object columns | Detects blank whitespace or empty string `""` entries masquerading as valid data. | **WARN** if blank strings present |
| **Domain Validity** | Numeric columns | Flags invalid negative values in strictly non-negative columns (`Quantity`, `Price`, `Cost`, `Revenue`). | **FAIL** if any negative numbers detected |
| **Distribution Outliers** | Numeric columns | Computes Tukey's IQR fences: $[Q_1 - 1.5\text{IQR}, Q_3 + 1.5\text{IQR}]$. | **INFO** if outlier rate < 3%<br>**WARN** if outlier rate ≥ 3% |

---

## 2. Health Score Mathematical Formula

The dataset starts with a baseline score of **100 points**. Penalties are deducted based on identified quality violations:

$$\text{Health Score} = \max\Big(0,\; 100 - \big(\text{FAIL Count} \times 20\big) - \big(\text{WARN Count} \times 5\big)\Big)$$

Where:
- $\text{FAIL Count}$: Number of critical structural violations (e.g. duplicate rate $\ge 5\%$, column null rate $\ge 15\%$, or invalid negative quantities/prices).
- $\text{WARN Count}$: Number of moderate quality warnings (e.g. low-rate duplicates, empty text strings, missing values $< 15\%$, or high statistical outlier rate $\ge 3\%$).
- Floor: Score is bounded between **0** and **100**.

### Score Interpretation
- **90 – 100 (Excellent)**: Clean, high-integrity dataset ready for production analysis without preprocessing.
- **70 – 89 (Good / Moderate)**: Minor missing data or benign statistical outliers; recommended for analysis with standard filtering.
- **Below 70 (Action Required)**: Significant data defects (e.g. missing fields, duplicate rows, negative prices) requiring cleaning or deduplication before reliable inference.

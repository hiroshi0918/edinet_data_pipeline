-- EDINET analytics query collection for DuckDB UI / CLI.
--
-- Recommended DuckDB UI workflow:
--
--   duckdb -ui notebooks/duckdb_ui_catalog.duckdb
--
-- Then run this setup block first. The UI catalog database stores DuckDB UI
-- notebooks and state. The EDINET analytics database is attached read-only so
-- analysis cannot mutate the exported snapshot.
--
-- If the alias already exists in your current DuckDB UI session, run:
--
--   DETACH edinet;
--
-- before running the ATTACH statement again.

ATTACH '/Users/h_terashima/Dev/edinet_data_pipeline/artifacts/analytics/edinet_analytics.duckdb'
  AS edinet (READ_ONLY);

-- ---------------------------------------------------------------------------
-- Common views
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TEMP VIEW v_company_year AS
SELECT *
FROM edinet.analytics.company_year_metrics;

CREATE OR REPLACE TEMP VIEW v_evidence AS
SELECT *
FROM edinet.analytics.metric_evidence;

-- Financial metrics are repeated across scope/worker_type rows. Use this view
-- for normal company/year analysis to avoid double counting.
CREATE OR REPLACE TEMP VIEW v_reporting_all AS
SELECT *
FROM v_company_year
WHERE scope = 'reporting_company'
  AND worker_type = 'all'
  AND status = 'processed';

CREATE OR REPLACE TEMP VIEW v_hc_evidence AS
SELECT *
FROM v_evidence
WHERE metric_name IN (
  'female_manager_ratio',
  'male_childcare_leave_ratio',
  'gender_wage_gap'
);

-- Labels and sort order for the six human-capital dimensions.
CREATE OR REPLACE TEMP VIEW v_dimension_labels AS
SELECT *
FROM (
  VALUES
    ('reporting_company', 'all', '提出会社 x 全労働者', 1, 1),
    ('reporting_company', 'regular', '提出会社 x 正規雇用', 1, 2),
    ('reporting_company', 'non_regular', '提出会社 x 非正規雇用', 1, 3),
    ('consolidated_subsidiary', 'all', '連結子会社 x 全労働者', 2, 1),
    ('consolidated_subsidiary', 'regular', '連結子会社 x 正規雇用', 2, 2),
    ('consolidated_subsidiary', 'non_regular', '連結子会社 x 非正規雇用', 2, 3)
) AS t(scope, worker_type, dimension_label, scope_order, worker_type_order);

-- Human-capital metrics should be compared across all scope/worker_type
-- dimensions. Financial metrics are repeated on these rows, so do not use this
-- view for sales/profit analysis.
CREATE OR REPLACE TEMP VIEW v_hc_all_dimensions AS
SELECT
  c.*,
  l.dimension_label,
  l.scope_order,
  l.worker_type_order
FROM v_company_year c
JOIN v_dimension_labels l
  ON l.scope = c.scope
 AND l.worker_type = c.worker_type
WHERE c.status = 'processed';

-- Long format makes it easy to group by metric, year, and dimension.
CREATE OR REPLACE TEMP VIEW v_hc_long AS
SELECT
  edinet_code,
  company_name,
  fiscal_year,
  doc_id,
  submitted_date,
  scope,
  worker_type,
  dimension_label,
  scope_order,
  worker_type_order,
  'female_manager_ratio' AS metric_name,
  '女性管理職比率' AS metric_label,
  female_manager_ratio AS metric_value
FROM v_hc_all_dimensions
UNION ALL
SELECT
  edinet_code,
  company_name,
  fiscal_year,
  doc_id,
  submitted_date,
  scope,
  worker_type,
  dimension_label,
  scope_order,
  worker_type_order,
  'male_childcare_leave_ratio' AS metric_name,
  '男性育休取得率' AS metric_label,
  male_childcare_leave_ratio AS metric_value
FROM v_hc_all_dimensions
UNION ALL
SELECT
  edinet_code,
  company_name,
  fiscal_year,
  doc_id,
  submitted_date,
  scope,
  worker_type,
  dimension_label,
  scope_order,
  worker_type_order,
  'gender_wage_gap' AS metric_name,
  '男女賃金格差' AS metric_label,
  gender_wage_gap AS metric_value
FROM v_hc_all_dimensions;

-- ---------------------------------------------------------------------------
-- 1. Overview
-- ---------------------------------------------------------------------------

-- 1-1. Tables in the attached EDINET database.
SELECT
  table_catalog,
  table_schema,
  table_name,
  table_type
FROM information_schema.tables
WHERE table_catalog = 'edinet'
ORDER BY table_schema, table_name;

-- 1-2. Dataset size and date range.
SELECT
  COUNT(*) AS rows,
  COUNT(DISTINCT doc_id) AS docs,
  COUNT(DISTINCT edinet_code) AS companies,
  MIN(fiscal_year) AS min_fiscal_year,
  MAX(fiscal_year) AS max_fiscal_year,
  MIN(submitted_date) AS first_submission,
  MAX(submitted_date) AS latest_submission
FROM v_reporting_all;

-- 1-3. Year x status distribution. This uses the default reporting-company row
-- so each document is counted once.
SELECT
  fiscal_year,
  status,
  COUNT(*) AS docs
FROM v_company_year
WHERE scope = 'reporting_company'
  AND worker_type = 'all'
GROUP BY fiscal_year, status
ORDER BY fiscal_year, status;

-- 1-4. Scope x worker type row distribution.
SELECT
  scope,
  worker_type,
  COUNT(*) AS rows,
  COUNT(DISTINCT doc_id) AS docs,
  COUNT(DISTINCT edinet_code) AS companies
FROM v_company_year
GROUP BY scope, worker_type
ORDER BY scope, worker_type;

-- 1-5. Scope x worker type combinations with Japanese labels.
SELECT
  l.dimension_label,
  l.scope,
  l.worker_type,
  COUNT(c.doc_id) AS rows,
  COUNT(DISTINCT c.doc_id) AS docs,
  COUNT(DISTINCT c.edinet_code) AS companies,
  MIN(c.fiscal_year) AS min_fiscal_year,
  MAX(c.fiscal_year) AS max_fiscal_year
FROM v_dimension_labels l
LEFT JOIN v_company_year c
  ON c.scope = l.scope
 AND c.worker_type = l.worker_type
GROUP BY
  l.dimension_label,
  l.scope,
  l.worker_type,
  l.scope_order,
  l.worker_type_order
ORDER BY l.scope_order, l.worker_type_order;

-- ---------------------------------------------------------------------------
-- 2. Coverage / Data quality
-- ---------------------------------------------------------------------------

-- 2-1. Yearly metric coverage.
SELECT
  fiscal_year,
  COUNT(*) AS docs,
  ROUND(100.0 * COUNT(sales) / COUNT(*), 1) AS sales_pct,
  ROUND(100.0 * COUNT(operating_profit) / COUNT(*), 1) AS operating_profit_pct,
  ROUND(100.0 * COUNT(net_profit) / COUNT(*), 1) AS net_profit_pct,
  ROUND(100.0 * COUNT(employee_count) / COUNT(*), 1) AS employee_count_pct,
  ROUND(100.0 * COUNT(female_manager_ratio) / COUNT(*), 1) AS female_mgr_pct,
  ROUND(100.0 * COUNT(male_childcare_leave_ratio) / COUNT(*), 1) AS childcare_pct,
  ROUND(100.0 * COUNT(gender_wage_gap) / COUNT(*), 1) AS wage_gap_pct
FROM v_reporting_all
GROUP BY fiscal_year
ORDER BY fiscal_year;

-- 2-2. Companies with many missing metrics.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  (sales IS NULL)::INT
    + (operating_profit IS NULL)::INT
    + (net_profit IS NULL)::INT
    + (employee_count IS NULL)::INT
    + (female_manager_ratio IS NULL)::INT
    + (male_childcare_leave_ratio IS NULL)::INT
    + (gender_wage_gap IS NULL)::INT AS missing_count,
  sales,
  operating_profit,
  net_profit,
  employee_count,
  female_manager_ratio,
  male_childcare_leave_ratio,
  gender_wage_gap
FROM v_reporting_all
ORDER BY missing_count DESC, fiscal_year DESC, company_name
LIMIT 100;

-- 2-3. Extraction method distribution.
SELECT
  metric_name,
  matched_by,
  COUNT(*) AS evidence_rows,
  COUNT(DISTINCT doc_id) AS docs,
  COUNT(DISTINCT edinet_code) AS companies
FROM v_evidence
GROUP BY metric_name, matched_by
ORDER BY metric_name, evidence_rows DESC;

-- 2-4. Human-capital extraction method distribution.
SELECT
  metric_name,
  matched_by,
  COUNT(*) AS evidence_rows,
  COUNT(DISTINCT doc_id) AS docs,
  COUNT(DISTINCT edinet_code) AS companies
FROM v_hc_evidence
GROUP BY metric_name, matched_by
ORDER BY metric_name, evidence_rows DESC;

-- 2-5. Values extracted by weaker fallback paths. Review these first when
-- checking extraction quality.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  metric_name,
  matched_by,
  raw_value,
  item_name,
  scope,
  worker_type,
  source_file
FROM v_hc_evidence
WHERE matched_by IN ('text_fallback', 'llm_fallback')
ORDER BY fiscal_year DESC, company_name, metric_name
LIMIT 200;

-- 2-6. F=M silent-bug regression check.
SELECT
  COUNT(*) AS comparable_rows,
  SUM((female_manager_ratio = male_childcare_leave_ratio)::INT) AS f_eq_m,
  ROUND(
    100.0 * SUM((female_manager_ratio = male_childcare_leave_ratio)::INT)
      / NULLIF(COUNT(*), 0),
    2
  ) AS f_eq_m_pct
FROM v_reporting_all
WHERE female_manager_ratio IS NOT NULL
  AND male_childcare_leave_ratio IS NOT NULL;

-- 2-7. Rows where female manager ratio equals male childcare leave ratio.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  female_manager_ratio,
  male_childcare_leave_ratio,
  gender_wage_gap
FROM v_reporting_all
WHERE female_manager_ratio = male_childcare_leave_ratio
  AND female_manager_ratio IS NOT NULL
ORDER BY fiscal_year DESC, company_name;

-- 2-8. Human-capital coverage by all six dimensions.
SELECT
  fiscal_year,
  dimension_label,
  COUNT(*) AS rows,
  ROUND(100.0 * COUNT(female_manager_ratio) / COUNT(*), 1) AS female_mgr_pct,
  ROUND(100.0 * COUNT(male_childcare_leave_ratio) / COUNT(*), 1) AS childcare_pct,
  ROUND(100.0 * COUNT(gender_wage_gap) / COUNT(*), 1) AS wage_gap_pct
FROM v_hc_all_dimensions
GROUP BY
  fiscal_year,
  dimension_label,
  scope_order,
  worker_type_order
ORDER BY fiscal_year, scope_order, worker_type_order;

-- 2-9. Evidence extraction method by human-capital dimension.
SELECT
  e.metric_name,
  l.dimension_label,
  e.matched_by,
  COUNT(*) AS evidence_rows,
  COUNT(DISTINCT e.doc_id) AS docs,
  COUNT(DISTINCT e.edinet_code) AS companies
FROM v_hc_evidence e
LEFT JOIN v_dimension_labels l
  ON l.scope = e.scope
 AND l.worker_type = e.worker_type
GROUP BY
  e.metric_name,
  l.dimension_label,
  l.scope_order,
  l.worker_type_order,
  e.matched_by
ORDER BY e.metric_name, l.scope_order, l.worker_type_order, evidence_rows DESC;

-- ---------------------------------------------------------------------------
-- 3. Financial analysis
-- ---------------------------------------------------------------------------

-- 3-1. Sales ranking.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  sales,
  operating_profit,
  net_profit,
  employee_count
FROM v_reporting_all
WHERE sales IS NOT NULL
ORDER BY fiscal_year DESC, sales DESC
LIMIT 50;

-- 3-2. Operating margin ranking.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  sales,
  operating_profit,
  ROUND(100.0 * operating_profit / NULLIF(sales, 0), 2) AS operating_margin_pct
FROM v_reporting_all
WHERE sales > 0
  AND operating_profit IS NOT NULL
ORDER BY operating_margin_pct DESC, sales DESC
LIMIT 50;

-- 3-3. Loss-making companies.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  sales,
  operating_profit,
  net_profit
FROM v_reporting_all
WHERE operating_profit < 0
   OR net_profit < 0
ORDER BY fiscal_year DESC, net_profit ASC NULLS LAST;

-- 3-4. Sales per employee.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  sales,
  employee_count,
  ROUND(sales / NULLIF(employee_count, 0), 0) AS sales_per_employee
FROM v_reporting_all
WHERE sales IS NOT NULL
  AND employee_count > 0
ORDER BY sales_per_employee DESC
LIMIT 50;

-- 3-5. Sales year-over-year growth.
WITH base AS (
  SELECT
    edinet_code,
    company_name,
    fiscal_year,
    doc_id,
    sales,
    LAG(sales) OVER (
      PARTITION BY edinet_code
      ORDER BY fiscal_year
    ) AS prev_sales
  FROM v_reporting_all
)
SELECT
  company_name,
  fiscal_year,
  doc_id,
  sales,
  prev_sales,
  ROUND(100.0 * (sales - prev_sales) / NULLIF(prev_sales, 0), 2) AS sales_yoy_pct
FROM base
WHERE sales IS NOT NULL
  AND prev_sales IS NOT NULL
ORDER BY sales_yoy_pct DESC
LIMIT 50;

-- 3-6. Operating profit improvement.
WITH base AS (
  SELECT
    edinet_code,
    company_name,
    fiscal_year,
    doc_id,
    operating_profit,
    LAG(operating_profit) OVER (
      PARTITION BY edinet_code
      ORDER BY fiscal_year
    ) AS prev_operating_profit
  FROM v_reporting_all
)
SELECT
  company_name,
  fiscal_year,
  doc_id,
  operating_profit,
  prev_operating_profit,
  operating_profit - prev_operating_profit AS operating_profit_diff
FROM base
WHERE operating_profit IS NOT NULL
  AND prev_operating_profit IS NOT NULL
ORDER BY operating_profit_diff DESC
LIMIT 50;

-- ---------------------------------------------------------------------------
-- 4. Human capital analysis
-- ---------------------------------------------------------------------------

-- 4-1. Yearly average and median.
SELECT
  fiscal_year,
  COUNT(*) AS docs,
  COUNT(female_manager_ratio) AS female_mgr_n,
  ROUND(AVG(female_manager_ratio), 2) AS avg_female_mgr,
  MEDIAN(female_manager_ratio) AS med_female_mgr,
  COUNT(male_childcare_leave_ratio) AS childcare_n,
  ROUND(AVG(male_childcare_leave_ratio), 2) AS avg_childcare,
  MEDIAN(male_childcare_leave_ratio) AS med_childcare,
  COUNT(gender_wage_gap) AS wage_gap_n,
  ROUND(AVG(gender_wage_gap), 2) AS avg_wage_gap,
  MEDIAN(gender_wage_gap) AS med_wage_gap
FROM v_reporting_all
GROUP BY fiscal_year
ORDER BY fiscal_year;

-- 4-2. Female manager ratio ranking.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  female_manager_ratio,
  employee_count
FROM v_reporting_all
WHERE female_manager_ratio IS NOT NULL
ORDER BY fiscal_year DESC, female_manager_ratio DESC
LIMIT 50;

-- 4-3. Companies with low gender wage gap values.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  gender_wage_gap,
  employee_count
FROM v_reporting_all
WHERE gender_wage_gap IS NOT NULL
ORDER BY gender_wage_gap ASC, fiscal_year DESC
LIMIT 50;

-- 4-4. Male childcare leave ratio summary.
SELECT
  fiscal_year,
  COUNT(male_childcare_leave_ratio) AS non_null,
  SUM((male_childcare_leave_ratio = 0)::INT) AS eq_0,
  SUM((male_childcare_leave_ratio > 100)::INT) AS gt_100,
  SUM((male_childcare_leave_ratio = 200)::INT) AS eq_200,
  MIN(male_childcare_leave_ratio) AS min_value,
  MEDIAN(male_childcare_leave_ratio) AS median_value,
  MAX(male_childcare_leave_ratio) AS max_value
FROM v_reporting_all
GROUP BY fiscal_year
ORDER BY fiscal_year;

-- 4-5. Male childcare leave ratio = 0%.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  male_childcare_leave_ratio,
  female_manager_ratio,
  gender_wage_gap
FROM v_reporting_all
WHERE male_childcare_leave_ratio = 0
ORDER BY fiscal_year DESC, company_name
LIMIT 100;

-- 4-6. Male childcare leave ratio > 100%.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  scope,
  worker_type,
  male_childcare_leave_ratio,
  female_manager_ratio,
  gender_wage_gap
FROM v_company_year
WHERE male_childcare_leave_ratio > 100
ORDER BY male_childcare_leave_ratio DESC, company_name;

-- 4-7. Male childcare leave ratio = 200%.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  scope,
  worker_type,
  male_childcare_leave_ratio,
  female_manager_ratio,
  gender_wage_gap
FROM v_company_year
WHERE male_childcare_leave_ratio = 200
ORDER BY scope, company_name, fiscal_year;

-- 4-8. Human-capital median/average by year and dimension.
SELECT
  fiscal_year,
  dimension_label,
  COUNT(*) AS rows,
  COUNT(female_manager_ratio) AS female_mgr_n,
  ROUND(AVG(female_manager_ratio), 2) AS avg_female_mgr,
  MEDIAN(female_manager_ratio) AS med_female_mgr,
  COUNT(male_childcare_leave_ratio) AS childcare_n,
  ROUND(AVG(male_childcare_leave_ratio), 2) AS avg_childcare,
  MEDIAN(male_childcare_leave_ratio) AS med_childcare,
  COUNT(gender_wage_gap) AS wage_gap_n,
  ROUND(AVG(gender_wage_gap), 2) AS avg_wage_gap,
  MEDIAN(gender_wage_gap) AS med_wage_gap
FROM v_hc_all_dimensions
GROUP BY
  fiscal_year,
  dimension_label,
  scope_order,
  worker_type_order
ORDER BY fiscal_year, scope_order, worker_type_order;

-- 4-9. Long-format summary: metric x year x dimension.
SELECT
  fiscal_year,
  metric_label,
  dimension_label,
  COUNT(metric_value) AS n,
  ROUND(AVG(metric_value), 2) AS avg_value,
  MEDIAN(metric_value) AS median_value,
  QUANTILE_CONT(metric_value, 0.25) AS p25_value,
  QUANTILE_CONT(metric_value, 0.75) AS p75_value,
  MIN(metric_value) AS min_value,
  MAX(metric_value) AS max_value,
  SUM((metric_value = 0)::INT) AS eq_0,
  SUM((metric_value > 100)::INT) AS gt_100
FROM v_hc_long
GROUP BY
  fiscal_year,
  metric_name,
  metric_label,
  dimension_label,
  scope_order,
  worker_type_order
ORDER BY fiscal_year, metric_name, scope_order, worker_type_order;

-- 4-10. Latest fiscal year comparison across the six dimensions.
WITH latest_year AS (
  SELECT MAX(fiscal_year) AS fiscal_year
  FROM v_hc_all_dimensions
)
SELECT
  h.metric_label,
  h.dimension_label,
  COUNT(h.metric_value) AS n,
  ROUND(AVG(h.metric_value), 2) AS avg_value,
  MEDIAN(h.metric_value) AS median_value,
  QUANTILE_CONT(h.metric_value, 0.25) AS p25_value,
  QUANTILE_CONT(h.metric_value, 0.75) AS p75_value,
  MIN(h.metric_value) AS min_value,
  MAX(h.metric_value) AS max_value
FROM v_hc_long h
JOIN latest_year y
  ON y.fiscal_year = h.fiscal_year
GROUP BY
  h.metric_name,
  h.metric_label,
  h.dimension_label,
  h.scope_order,
  h.worker_type_order
ORDER BY h.metric_name, h.scope_order, h.worker_type_order;

-- 4-11. Company-level matrix for one metric in the latest fiscal year.
-- Change metric_name to 'female_manager_ratio', 'male_childcare_leave_ratio',
-- or 'gender_wage_gap' depending on what you want to inspect.
WITH latest_year AS (
  SELECT MAX(fiscal_year) AS fiscal_year
  FROM v_hc_all_dimensions
),
selected_metric AS (
  SELECT *
  FROM v_hc_long
  WHERE metric_name = 'gender_wage_gap'
    AND fiscal_year = (SELECT fiscal_year FROM latest_year)
)
SELECT
  company_name,
  fiscal_year,
  doc_id,
  MAX(CASE WHEN scope = 'reporting_company' AND worker_type = 'all' THEN metric_value END)
    AS reporting_all,
  MAX(CASE WHEN scope = 'reporting_company' AND worker_type = 'regular' THEN metric_value END)
    AS reporting_regular,
  MAX(CASE WHEN scope = 'reporting_company' AND worker_type = 'non_regular' THEN metric_value END)
    AS reporting_non_regular,
  MAX(CASE WHEN scope = 'consolidated_subsidiary' AND worker_type = 'all' THEN metric_value END)
    AS subsidiary_all,
  MAX(CASE WHEN scope = 'consolidated_subsidiary' AND worker_type = 'regular' THEN metric_value END)
    AS subsidiary_regular,
  MAX(CASE WHEN scope = 'consolidated_subsidiary' AND worker_type = 'non_regular' THEN metric_value END)
    AS subsidiary_non_regular
FROM selected_metric
GROUP BY company_name, fiscal_year, doc_id
ORDER BY reporting_all ASC NULLS LAST, company_name
LIMIT 200;

-- 4-12. Reporting company vs consolidated subsidiary gap by worker type.
SELECT
  rc.company_name,
  rc.fiscal_year,
  rc.doc_id,
  rc.worker_type,
  rc.female_manager_ratio AS reporting_female_mgr,
  cs.female_manager_ratio AS subsidiary_female_mgr,
  cs.female_manager_ratio - rc.female_manager_ratio AS female_mgr_gap,
  rc.male_childcare_leave_ratio AS reporting_childcare,
  cs.male_childcare_leave_ratio AS subsidiary_childcare,
  cs.male_childcare_leave_ratio - rc.male_childcare_leave_ratio AS childcare_gap,
  rc.gender_wage_gap AS reporting_wage_gap,
  cs.gender_wage_gap AS subsidiary_wage_gap,
  cs.gender_wage_gap - rc.gender_wage_gap AS wage_gap_gap
FROM v_hc_all_dimensions rc
JOIN v_hc_all_dimensions cs
  ON cs.doc_id = rc.doc_id
 AND cs.worker_type = rc.worker_type
 AND cs.scope = 'consolidated_subsidiary'
WHERE rc.scope = 'reporting_company'
ORDER BY ABS(childcare_gap) DESC NULLS LAST, rc.company_name
LIMIT 200;

-- 4-13. All workers vs regular/non-regular gap within each scope.
-- Change metric_name to inspect another metric.
WITH selected_metric AS (
  SELECT *
  FROM v_hc_long
  WHERE metric_name = 'gender_wage_gap'
)
SELECT
  company_name,
  fiscal_year,
  doc_id,
  scope,
  MAX(CASE WHEN worker_type = 'all' THEN metric_value END) AS all_workers,
  MAX(CASE WHEN worker_type = 'regular' THEN metric_value END) AS regular_workers,
  MAX(CASE WHEN worker_type = 'non_regular' THEN metric_value END) AS non_regular_workers,
  MAX(CASE WHEN worker_type = 'regular' THEN metric_value END)
    - MAX(CASE WHEN worker_type = 'all' THEN metric_value END) AS regular_minus_all,
  MAX(CASE WHEN worker_type = 'non_regular' THEN metric_value END)
    - MAX(CASE WHEN worker_type = 'all' THEN metric_value END) AS non_regular_minus_all
FROM selected_metric
GROUP BY company_name, fiscal_year, doc_id, scope
HAVING all_workers IS NOT NULL
   OR regular_workers IS NOT NULL
   OR non_regular_workers IS NOT NULL
ORDER BY fiscal_year DESC, ABS(non_regular_minus_all) DESC NULLS LAST, company_name
LIMIT 200;

-- 4-14. Top outliers by metric, year, and dimension.
WITH ranked AS (
  SELECT
    metric_label,
    fiscal_year,
    dimension_label,
    company_name,
    doc_id,
    metric_value,
    ROW_NUMBER() OVER (
      PARTITION BY metric_name, fiscal_year, scope, worker_type
      ORDER BY metric_value DESC NULLS LAST
    ) AS rank_in_dimension
  FROM v_hc_long
  WHERE metric_value IS NOT NULL
)
SELECT
  metric_label,
  fiscal_year,
  dimension_label,
  rank_in_dimension,
  company_name,
  doc_id,
  metric_value
FROM ranked
WHERE rank_in_dimension <= 10
ORDER BY metric_label, fiscal_year DESC, dimension_label, rank_in_dimension;

-- ---------------------------------------------------------------------------
-- 5. Audit / evidence checks
-- ---------------------------------------------------------------------------

-- 5-1. Evidence for one document. Replace the doc_id as needed.
SELECT
  company_name,
  fiscal_year,
  doc_id,
  metric_name,
  raw_value,
  matched_by,
  element_id,
  scope,
  worker_type,
  source_file
FROM v_evidence
WHERE doc_id = 'S100TNI7'
ORDER BY metric_name, scope, worker_type, source_file;

-- 5-2. Evidence for male childcare 200%.
SELECT
  m.company_name,
  m.fiscal_year,
  m.doc_id,
  m.scope,
  m.worker_type,
  m.male_childcare_leave_ratio,
  e.raw_value,
  e.relative_year,
  e.matched_by,
  e.element_id,
  e.source_file
FROM v_company_year m
JOIN v_evidence e
  ON e.doc_id = m.doc_id
 AND e.metric_name = 'male_childcare_leave_ratio'
 AND COALESCE(e.scope, '') = COALESCE(m.scope, '')
 AND COALESCE(e.worker_type, '') = COALESCE(m.worker_type, '')
WHERE m.male_childcare_leave_ratio = 200
ORDER BY m.scope, m.company_name, m.fiscal_year;

-- 5-3. Metric values with their extraction evidence.
SELECT
  m.company_name,
  m.fiscal_year,
  m.doc_id,
  e.metric_name,
  CASE e.metric_name
    WHEN 'sales' THEN m.sales
    WHEN 'operating_profit' THEN m.operating_profit
    WHEN 'net_profit' THEN m.net_profit
    WHEN 'employee_count' THEN m.employee_count
    WHEN 'female_manager_ratio' THEN m.female_manager_ratio
    WHEN 'male_childcare_leave_ratio' THEN m.male_childcare_leave_ratio
    WHEN 'gender_wage_gap' THEN m.gender_wage_gap
  END AS final_value,
  e.raw_value,
  e.matched_by,
  e.element_id,
  e.scope,
  e.worker_type,
  e.source_file
FROM v_reporting_all m
JOIN v_evidence e
  ON e.doc_id = m.doc_id
WHERE e.metric_name IN (
  'sales',
  'operating_profit',
  'net_profit',
  'employee_count',
  'female_manager_ratio',
  'male_childcare_leave_ratio',
  'gender_wage_gap'
)
  AND (
    e.scope IS NULL
    OR (e.scope = m.scope AND e.worker_type = m.worker_type)
  )
ORDER BY m.fiscal_year DESC, m.company_name, e.metric_name
LIMIT 200;

-- 5-4. Reporting-company Article71-4 Item1 / Item2 evidence families.
SELECT
  CASE
    WHEN element_id LIKE '%Article714Item1%' THEN 'Article714Item1'
    WHEN element_id LIKE '%Article714Item2%' THEN 'Article714Item2'
    WHEN element_id LIKE '%MetricsOfConsolidatedSubsidiaries%' THEN 'ConsolidatedSubsidiaries'
    WHEN element_id IS NULL THEN '(no element_id)'
    ELSE 'Other'
  END AS element_family,
  scope,
  worker_type,
  COUNT(*) AS evidence_rows,
  COUNT(DISTINCT doc_id) AS docs,
  MIN(TRY_CAST(raw_value AS DOUBLE)) AS min_raw,
  MAX(TRY_CAST(raw_value AS DOUBLE)) AS max_raw
FROM v_evidence
WHERE metric_name = 'male_childcare_leave_ratio'
GROUP BY element_family, scope, worker_type
ORDER BY element_family, scope, worker_type;

-- 5-5. Analytics-DuckDB-only check for consolidated subsidiary first-wins risk.
-- Note: This exported DuckDB snapshot does not include raw_edinet_facts, so it
-- cannot show every RowMember candidate. It can only show the accepted evidence
-- row. For a full first-wins audit, query PostgreSQL raw_edinet_facts.
SELECT
  m.company_name,
  m.fiscal_year,
  m.doc_id,
  m.male_childcare_leave_ratio AS accepted_value,
  e.raw_value AS accepted_raw_value,
  e.element_id,
  e.source_file
FROM v_company_year m
JOIN v_evidence e
  ON e.doc_id = m.doc_id
 AND e.metric_name = 'male_childcare_leave_ratio'
 AND e.scope = m.scope
 AND e.worker_type = m.worker_type
WHERE m.scope = 'consolidated_subsidiary'
  AND m.worker_type = 'all'
  AND m.male_childcare_leave_ratio IS NOT NULL
ORDER BY m.male_childcare_leave_ratio DESC, m.company_name
LIMIT 100;

-- 5-6. PostgreSQL-only full first-wins audit reference.
-- Run this against PostgreSQL, not DuckDB UI, because raw_edinet_facts is not
-- exported to analytics.edinet_analytics.duckdb.
--
-- WITH cons AS (
--   SELECT
--     doc_id,
--     COUNT(*) AS raw_rows,
--     STRING_AGG(raw_value || ':row' || row_number, ' | ' ORDER BY row_number)
--       AS raw_values_in_order
--   FROM raw_edinet_facts
--   WHERE element_id LIKE
--     '%RatioOfMaleEmployeesTakingChildcareLeaveMetricsOfConsolidatedSubsidiaries%'
--   GROUP BY doc_id
-- )
-- SELECT
--   fr.doc_id,
--   c.company_name,
--   cons.raw_rows,
--   hcm.male_childcare_leave_ratio AS accepted_value,
--   cons.raw_values_in_order
-- FROM cons
-- JOIN financial_reports fr USING (doc_id)
-- JOIN companies c ON c.edinet_code = fr.edinet_code
-- LEFT JOIN human_capital_metrics hcm
--   ON hcm.edinet_code = fr.edinet_code
--  AND hcm.fiscal_year = fr.fiscal_year
--  AND hcm.scope = 'consolidated_subsidiary'
--  AND hcm.worker_type = 'all'
-- WHERE cons.raw_rows > 1
-- ORDER BY cons.raw_rows DESC, c.company_name;

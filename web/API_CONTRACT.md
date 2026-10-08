# Web dashboard API contract

Rails (`/api/v1`) と React の接点。JSON キーは snake_case。GET のみ。

Base: `http://localhost:3000/api/v1`（Vite が `/api` を Rails へ proxy）。

実装の対応:

| エンドポイント | Query | 画面 |
| --- | --- | --- |
| `GET /meta` | `MetaQuery` | 全ページの KPI・既定年度 |
| `GET /companies` | `CompaniesQuery.index` | Combobox |
| `GET /companies/:code` | `CompaniesQuery.show` | `/companies/:code` |
| `GET /companies/:code/spotlight` | `SpotlightQuery` | `/companies/:code/spotlight` |
| `GET /industries/hc_distribution` | `HcDistributionQuery` | `/industry` |
| `GET /rankings/human_capital` | `HumanCapitalRankingQuery` | `/hc-ranking` |
| `GET /rankings/size` | `SizeRankingQuery` | `/size-hc` |

## Shared params

- `year` integer fiscal year
- `scope` `reporting_company` | `consolidated_subsidiary` (default `reporting_company`)
- `worker_type` `all` | `regular` | `non_regular` (default `all`)
- Invalid metric/scope/worker_type → `400 { "error": "..." }`
- Unknown company code → `404 { "error": "..." }`

## Endpoints

### GET /api/v1/meta

```json
{
  "company_count": 1234,
  "year_count": 4,
  "total_records": 5000,
  "latest_submission": "2025-06-27",
  "fiscal_years": [2022, 2023, 2024, 2025],
  "default_year": 2024
}
```

KPI counts use default dimension (`reporting_company` × `all`). `default_year` is the year with the most companies in that dimension.

### GET /api/v1/companies?q=&limit=

Without `q`: distinct `edinet_code, company_name, industry` ordered by upper(company_name). `limit` を付けたときだけその件数。省略時は全件。

With `q`: `company_name ILIKE %q%`. `limit` の既定は 50。

```json
{
  "companies": [
    { "edinet_code": "E05206", "company_name": "株式会社セプテーニ・ホールディングス", "industry": "サービス業" }
  ]
}
```

### GET /api/v1/companies/:code

All (year, scope, worker_type) rows for one company.

```json
{
  "edinet_code": "E05206",
  "company_name": "株式会社セプテーニ・ホールディングス",
  "industry": "サービス業",
  "rows": [
    {
      "fiscal_year": 2024,
      "scope": "reporting_company",
      "worker_type": "all",
      "doc_id": "S100XXXX",
      "submitted_date": "2025-06-27",
      "sales": 17628035000,
      "operating_profit": 1000000000,
      "net_profit": 800000000,
      "employee_count": 58,
      "female_manager_ratio": 12.3,
      "male_childcare_leave_ratio": 45.0,
      "gender_wage_gap": 78.5,
      "average_annual_salary": 6500000,
      "average_years_of_service": 8.2,
      "average_age": 36.4
    }
  ]
}
```

### GET /api/v1/companies/:code/spotlight?year=&scope=&worker_type=

`scope=auto` (or omitted with `auto=1`) runs holding-company detection: if reporting_company × all has both `female_manager_ratio` and `male_childcare_leave_ratio` NULL, use `consolidated_subsidiary`.

```json
{
  "edinet_code": "E05206",
  "company_name": "...",
  "industry": "サービス業",
  "fiscal_year": 2024,
  "scope": "consolidated_subsidiary",
  "scope_auto": true,
  "worker_type": "all",
  "target": { "sales": 1, "operating_profit": 1, "employee_count": 58, "female_manager_ratio": 12.3, "male_childcare_leave_ratio": 80.0, "gender_wage_gap": 70.0 },
  "industry_rank": {
    "industry": "サービス業",
    "industry_total": 40,
    "metrics": [
      { "key": "sales", "rank": 5, "among": 38 },
      { "key": "operating_profit", "rank": 8, "among": 40 },
      { "key": "female_manager_ratio", "rank": 12, "among": 30 }
    ]
  },
  "industry_peers": [ { "edinet_code": "...", "company_name": "...", "industry": "...", "employee_count": 10, "sales": 1, "operating_profit": 1, "net_profit": 1, "female_manager_ratio": 1, "male_childcare_leave_ratio": 1, "gender_wage_gap": 1 } ],
  "size_peers": [],
  "ideal_cluster": [],
  "benchmarks": {
    "female_manager_ratio": { "current": 12.3, "industry_p75": 20.0, "size_peer_p75": 18.0, "ideal_cluster_avg": 25.0, "industry_top10_avg": 30.0 },
    "male_childcare_leave_ratio": {},
    "gender_wage_gap": {}
  }
}
```

Size peers: `LOG10(employee_count)` within target ± 0.3. Ideal cluster: 3 HC ≥ P75 of the same year/scope/worker set AND operating_profit/sales ≥ P50.

`industry_rank.metrics[].among` は順位の分母。売上と女性管理職は非 NULL の社数。営業利益は業種の全社数（Streamlit と同じ）。

### GET /api/v1/industries/hc_distribution?year=&scope=&worker_type=&metric=

`metric` one of `female_manager_ratio`, `male_childcare_leave_ratio`, `gender_wage_gap`. Drop industries with fewer than 5 non-null values.

```json
{
  "metric": "female_manager_ratio",
  "rows": [
    { "industry": "情報・通信業", "edinet_code": "E00001", "company_name": "...", "value": 15.2 }
  ]
}
```

### GET /api/v1/rankings/human_capital?year=&scope=&worker_type=&metric=

`metric` `female_manager_ratio` or `gender_wage_gap` only. Top/bottom 10, NULL excluded. Sort DESC for top, ASC for bottom (higher `gender_wage_gap` = closer to parity = 上位).

```json
{
  "metric": "female_manager_ratio",
  "top": [ { "rank": 1, "edinet_code": "...", "company_name": "...", "industry": "...", "value": 40.0 } ],
  "bottom": []
}
```

### GET /api/v1/rankings/size?year=&scope=&worker_type=&axis=

`axis` `sales` | `operating_profit` | `employee_count`. Top/bottom 10. Bottom floors: sales ≥ 1e8, employee_count ≥ 1, operating_profit none. Include `female_manager_ratio` and `gender_wage_gap` on each row.

```json
{
  "axis": "sales",
  "top": [ { "rank": 1, "edinet_code": "...", "company_name": "...", "industry": "...", "value": 1e12, "female_manager_ratio": 12.0, "gender_wage_gap": 70.0 } ],
  "bottom": []
}
```

## Domain constants

- Default scope `reporting_company`, worker_type `all`
- Lookup employee-info cards always read `(reporting_company, all)` for that year
- Childcare leave chart display clip 0–100, values >100 still in data
- Do not include childcare leave on ranking/size tables

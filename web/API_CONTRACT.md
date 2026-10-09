# Web ダッシュボード API 契約

Rails（`/api/v1`）と React の接点。JSON のキーは snake_case。メソッドは GET のみ。

基底 URL は `http://localhost:3000/api/v1`（Vite が `/api` を Rails へ proxy）。

エンドポイントと Query の対応。

| エンドポイント | Query |
| --- | --- |
| `GET /meta` | `MetaQuery` |
| `GET /companies` | `CompaniesQuery.index` |
| `GET /companies/:code` | `CompaniesQuery.show` |
| `GET /companies/:code/sheet` | `SheetQuery` |
| `GET /companies/:code/story` | `StoryQuery` |
| `GET /companies/:code/spotlight` | `SpotlightQuery` |
| `GET /industries` | `IndustriesQuery` |
| `GET /industries/hc_distribution` | `HcDistributionQuery` |
| `GET /rankings` | `RankingsQuery` |
| `GET /rankings/human_capital` | `HumanCapitalRankingQuery` |
| `GET /rankings/size` | `SizeRankingQuery` |
| `GET /nikkei225` | `Nikkei225Query` |

図鑑の画面は `/`、`/companies/:code`、`/companies/:code/story`、`/compare`、`/rankings`、`/nikkei225`。`/` は表紙で、業種の目次に `GET /industries` を読む。`/companies/:code` は `GET /companies/:code/sheet` を読む。`/rankings` は `?industry=&axis=` を URL に持つ。`/compare` は `?a=&b=` に会社コードを持ち、2社の `GET /companies/:code/story` を読んで売上高・営業利益・営業利益率を同じ目盛りで重ねる（BS は未取り込みなので対象外）。spotlight、業種分布、人的資本ランキング、規模ランキングのエンドポイントは残している。

## 共通パラメータ

- `year` は会計年度の整数
- `scope` は `reporting_company` または `consolidated_subsidiary`（既定は `reporting_company`）
- `worker_type` は `all`、`regular`、`non_regular`（既定は `all`）
- metric、scope、worker_type が不正なら `400 { "error": "..." }`
- 未知の会社コードは `404 { "error": "..." }`

## エンドポイント

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

KPI の件数は、既定の次元（`reporting_company` × `all`）で数える。`default_year` は、その次元で会社数が最も多い会計年度。

### GET /api/v1/companies?q=&limit=

`q` が無いとき。`edinet_code`、`company_name`、`industry` の重複を除き、`upper(company_name)` の順に並べる。`limit` を付けたときだけその件数。省略したときは全件。

`q` があるとき。`company_name` を `ILIKE %q%` で探す。`limit` の既定は 50。

`securities_code` は companies の証券コード。検索候補の企業ロゴに使う。無いときは null。

```json
{
  "companies": [
    {
      "edinet_code": "E05206",
      "company_name": "株式会社セプテーニ・ホールディングス",
      "industry": "サービス業",
      "securities_code": "4293"
    }
  ]
}
```

### GET /api/v1/companies/:code

1社について、年度・scope・worker_type の組の行をすべて返す。

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

### GET /api/v1/companies/:code/sheet

最新有報年度のキャラクターシート。年度、scope、worker_type は受け取らない。人的資本は `reporting_company` × `all` だけ。比較相手はその年度の同じ業種である。軸ごとに、比較相手の非欠損が 5 社未満なら `score` は null。点は「自分以下の社数 / 比較社数」を 100 点満点に丸めた値。`level` は、score がある軸の平均。開示の 0 は平均に入れる。期待は、株価が揃うまで null。業種が無い会社は、点も level も null。未知のコードは 404。`securities_code` は companies の証券コードで、無いときは null。点の計算には使わない。

```json
{
  "edinet_code": "E05206",
  "company_name": "株式会社セプテーニ・ホールディングス",
  "industry": "サービス業",
  "securities_code": "4293",
  "fiscal_year": 2024,
  "level": 86,
  "axes": [
    { "key": "sales", "label": "売上高", "nickname": "規模", "score": 80, "value": 17628035000, "peer_count": 40 },
    { "key": "employee_count", "label": "従業員数", "nickname": "人数", "score": 40, "value": 58, "peer_count": 40 },
    { "key": "operating_margin", "label": "営業利益率", "nickname": "稼ぐ力", "score": 70, "value": 0.0567, "peer_count": 38 },
    {
      "key": "people",
      "label": "人的資本",
      "nickname": "人",
      "score": 60,
      "value": null,
      "peer_count": null,
      "average_age": 36.4,
      "metrics": [
        { "key": "female_manager_ratio", "value": 12.3, "score": 40, "peer_count": 30 },
        { "key": "male_childcare_leave_ratio", "value": null, "score": null, "peer_count": 4 },
        { "key": "gender_wage_gap", "value": 78.5, "score": 80, "peer_count": 28 }
      ],
      "disclosure": { "key": "disclosure", "label": "人の開示", "nickname": "開示", "score": 67, "value": 2, "peer_count": null, "disclosed_count": 2, "expected_count": 3 }
    },
    { "key": "average_annual_salary", "label": "平均年間給与", "nickname": "待遇", "score": 55, "value": 6500000, "peer_count": 36 },
    { "key": "average_years_of_service", "label": "平均勤続年数", "nickname": "定着", "score": 50, "value": 8.2, "peer_count": 36 },
    { "key": "expectation", "label": "株価売上高倍率", "nickname": "期待", "score": null, "value": null, "peer_count": null, "per": null, "psr_basis": null }
  ]
}
```

`gender_wage_gap` は高いほど均衡に近い。人の欠測は 0 点にしない。営業利益率は売上が 0 以下なら null。開示は人的資本の `disclosure`。期待の `psr_basis` は `close`（決算月の終値）か `reported_per`（有報の株価収益率から戻した倍率）。

### GET /api/v1/companies/:code/story

直近10年の売上・営業利益・従業員数と、事業の内容・沿革。保存済みの書き直しがあればそれを返し、無ければ原文の抜粋を返す。事業の `source` は事業の内容の全文、沿革の `source` は根拠の引用。この GET は書き直さない。保存は `bin/rails 'story:rewrite[EDINETコード]'`。

### GET /api/v1/industries

表紙の業種の目次。companies を業種で数える。業種が無い会社は数えない。並びは業種名の順。数え方は `GET /rankings?industry=` の社数と同じ。

```json
{
  "industries": [
    { "industry": "輸送用機器", "company_count": 123 }
  ]
}
```

### GET /api/v1/rankings?industry=&axis=

図鑑のランキング。`axis` を省略すると総合点。`sales`、`employee_count`、`operating_margin`、`people`、`average_annual_salary`、`average_years_of_service`、`expectation`、`disclosure` のいずれかなら、その軸の点で並べる。点がない会社は末尾。`industry` はその業種だけ。未知の `axis` は 400。各行の `edinet_code` はシートの会社コード。

```json
{
  "axis": "level",
  "industry": null,
  "industries": ["輸送用機器"],
  "axes": [{ "key": "level", "label": "総合" }],
  "companies": [
    {
      "edinet_code": "E02144",
      "company_name": "トヨタ自動車株式会社",
      "industry": "輸送用機器",
      "fiscal_year": 2026,
      "level": 78,
      "score": 78
    }
  ]
}
```

### GET /api/v1/nikkei225

日経平均の構成銘柄。`data/nikkei225.json`（2026-10-08 時点）を、EDINETコードで companies に結ぶ。`level` はシートと同じ総合点。図鑑に無い銘柄は `has_sheet: false` で、`edinet_code` と `level` は null。並びは総合点の降順で、点が無い会社は末尾。

```json
{
  "as_of": "2026-10-08",
  "source_note": "日経平均プロフィルの構成銘柄を証券コードで結んだ。",
  "companies": [
    {
      "securities_code": "7203",
      "short_name": "トヨタ",
      "listed_name": "トヨタ自動車（株）",
      "nikkei_sector": "自動車",
      "edinet_code": "E02144",
      "company_name": "トヨタ自動車株式会社",
      "industry": "輸送用機器",
      "fiscal_year": 2026,
      "level": 76,
      "has_sheet": true
    }
  ]
}
```

### GET /api/v1/companies/:code/spotlight?year=&scope=&worker_type=

`scope=auto` のとき、または scope を省いて `auto=1` のとき、持株会社の判定をする。`reporting_company` × `all` で `female_manager_ratio` と `male_childcare_leave_ratio` がどちらも NULL なら、`consolidated_subsidiary` を使う。

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

規模が近い会社（size peers）は、対象の `LOG10(employee_count)` から ±0.3 の範囲。理想集団（ideal cluster）は、人的資本 3 指標が同じ年度・scope・worker の集合の P75 以上で、かつ `operating_profit / sales` が P50 以上。

`industry_rank.metrics[].among` は順位の分母。売上と女性管理職は非 NULL の社数。営業利益は業種の全社数（Streamlit と同じ）。

### GET /api/v1/industries/hc_distribution?year=&scope=&worker_type=&metric=

`metric` は `female_manager_ratio`、`male_childcare_leave_ratio`、`gender_wage_gap` のいずれか。非 NULL の値が 5 未満の業種は除く。

```json
{
  "metric": "female_manager_ratio",
  "rows": [
    { "industry": "情報・通信業", "edinet_code": "E00001", "company_name": "...", "value": 15.2 }
  ]
}
```

### GET /api/v1/rankings/human_capital?year=&scope=&worker_type=&metric=

`metric` は `female_manager_ratio` か `gender_wage_gap` だけ。上位と下位は各 10 件で、NULL は除く。上位は降順、下位は昇順に並べる（`gender_wage_gap` は高いほど均衡に近く、上位になる）。

```json
{
  "metric": "female_manager_ratio",
  "top": [ { "rank": 1, "edinet_code": "...", "company_name": "...", "industry": "...", "value": 40.0 } ],
  "bottom": []
}
```

### GET /api/v1/rankings/size?year=&scope=&worker_type=&axis=

`axis` は `sales`、`operating_profit`、`employee_count` のいずれか。上位と下位は各 10 件。下位の下限は、sales が 1e8 以上、employee_count が 1 以上。operating_profit に下限は無い。各行に `female_manager_ratio` と `gender_wage_gap` を含める。

```json
{
  "axis": "sales",
  "top": [ { "rank": 1, "edinet_code": "...", "company_name": "...", "industry": "...", "value": 1e12, "female_manager_ratio": 12.0, "gender_wage_gap": 70.0 } ],
  "bottom": []
}
```

## ドメインの定数

- 既定の scope は `reporting_company`、worker_type は `all`
- Lookup の従業員情報カードは、その年度の `(reporting_company, all)` を常に読む
- 育休のグラフは、表示を 0〜100 に切る。100 を超える値はデータに残す
- ランキングと規模の表に、育休は含めない

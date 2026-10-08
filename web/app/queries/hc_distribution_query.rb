# 業種別箱ひげ用。企業ごとの生値を返し、開示社数が少ない業種は落とす。
class HcDistributionQuery < ApplicationQuery
  def self.call(metric:, year:, scope:, worker_type:, min_companies: Dimension::DISTRIBUTION_MIN_COMPANIES)
    column = Dimension.column!(metric, Dimension::HC_METRICS)
    Dimension.validate_scope!(scope)
    Dimension.validate_worker_type!(worker_type)

    # DuckDB QUALIFY をサブクエリ + COUNT(*) OVER に置き換える。
    rows = select_all(<<~SQL, year, scope, worker_type, min_companies)
      SELECT industry, edinet_code, company_name, #{column}
        FROM (
          SELECT industry, edinet_code, company_name, #{column},
                 COUNT(*) OVER (PARTITION BY industry) AS industry_n
            FROM #{VIEW}
           WHERE fiscal_year = ?
             AND scope = ?
             AND worker_type = ?
             AND #{column} IS NOT NULL
             AND industry IS NOT NULL
        ) counted
       WHERE industry_n >= ?
       ORDER BY industry, edinet_code
    SQL

    {
      metric: column,
      rows: rows.map { |row| row.merge(value: row.delete(column.to_sym)) }
    }
  end
end

# KPI と「企業数が最多の年度」（フィルタの既定値）。
class MetaQuery < ApplicationQuery
  def self.call
    kpi = select_one(<<~SQL, Dimension::DEFAULT_SCOPE, Dimension::DEFAULT_WORKER_TYPE) || {}
      SELECT
        COUNT(DISTINCT edinet_code) AS company_count,
        COUNT(DISTINCT fiscal_year) AS year_count,
        COUNT(*)                    AS total_records,
        MAX(submitted_date)         AS latest_submission
      FROM #{VIEW}
      WHERE scope = ? AND worker_type = ?
    SQL

    fiscal_years = select_all(<<~SQL).map { |row| row[:fiscal_year] }
      SELECT DISTINCT fiscal_year
        FROM #{VIEW}
       ORDER BY fiscal_year
    SQL

    {
      company_count: kpi[:company_count] || 0,
      year_count: kpi[:year_count] || 0,
      total_records: kpi[:total_records] || 0,
      latest_submission: kpi[:latest_submission],
      fiscal_years: fiscal_years,
      default_year: default_year
    }
  end

  def self.default_year
    row = select_one(<<~SQL, Dimension::DEFAULT_SCOPE, Dimension::DEFAULT_WORKER_TYPE)
      SELECT fiscal_year
        FROM #{VIEW}
       WHERE scope = ? AND worker_type = ?
       GROUP BY fiscal_year
       ORDER BY COUNT(DISTINCT edinet_code) DESC, fiscal_year DESC
       LIMIT 1
    SQL
    row&.fetch(:fiscal_year)
  end
end

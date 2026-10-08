# 企業一覧（q ありは部分一致）と、1 社の全次元行。
class CompaniesQuery < ApplicationQuery
  # limit 未指定かつ q なしは全件。q ありで limit 未指定は SEARCH_DEFAULT_LIMIT。
  def self.index(q: nil, limit: nil)
    binds = []
    where_sql = ""
    if q.present?
      where_sql = "WHERE company_name ILIKE ?"
      binds << "%#{ApplicationRecord.sanitize_sql_like(q)}%"
    end

    effective_limit = q.present? ? (limit || Dimension::SEARCH_DEFAULT_LIMIT) : limit
    limit_sql = ""
    if effective_limit
      limit_sql = "LIMIT ?"
      binds << effective_limit
    end

    select_all(<<~SQL, *binds)
      SELECT edinet_code, company_name, industry
        FROM (
          SELECT DISTINCT edinet_code, company_name, industry
            FROM #{VIEW}
           #{where_sql}
        ) companies
       ORDER BY UPPER(company_name)
       #{limit_sql}
    SQL
  end

  def self.show(edinet_code)
    company = Company.find_by(edinet_code: edinet_code)
    return nil unless company

    rows = select_all(<<~SQL, edinet_code)
      SELECT fiscal_year, scope, worker_type, doc_id, submitted_date,
             sales, operating_profit, net_profit, employee_count,
             female_manager_ratio, male_childcare_leave_ratio, gender_wage_gap,
             average_annual_salary, average_years_of_service, average_age
        FROM #{VIEW}
       WHERE edinet_code = ?
       ORDER BY fiscal_year DESC, scope, worker_type
    SQL

    {
      edinet_code: company.edinet_code,
      company_name: company.company_name,
      industry: company.industry,
      rows: rows
    }
  end
end

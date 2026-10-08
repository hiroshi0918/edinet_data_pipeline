# 歩み。直近10年度の枠に、有報から取れた売上・営業利益・従業員数を置く。
# 文章は保存済みの書き直し。無ければ有報の抜粋。書き直しは bin/rails story:rewrite。
class StoryQuery < ApplicationQuery
  class << self
    def call(edinet_code)
      company = Company.find_by(edinet_code: edinet_code)
      return nil unless company

      reports = reports_for(company.edinet_code)
      latest = reports.max_by { |report| [ report[:fiscal_year], report[:submitted_date].to_s ] }
      {
        edinet_code: company.edinet_code,
        company_name: company.company_name,
        industry: company.industry,
        fiscal_year: latest&.dig(:fiscal_year),
        series: StorySeries.build(reports),
        narrative: latest ? StoryNarrative.build(latest[:doc_id]) : StoryNarrative.empty
      }
    end

    private

    def reports_for(edinet_code)
      select_all(<<~SQL, edinet_code)
        SELECT doc_id, fiscal_year, submitted_date, sales, operating_profit, employee_count
          FROM financial_reports
         WHERE edinet_code = ?
         ORDER BY fiscal_year, submitted_date, doc_id
      SQL
    end
  end
end

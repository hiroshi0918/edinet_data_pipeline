# テスト用人的資本。doc_id で financial_reports に紐づく。
FactoryBot.define do
  factory :human_capital_metric do
    association :financial_report
    edinet_code { financial_report.edinet_code }
    fiscal_year { financial_report.fiscal_year }
    doc_id { financial_report.doc_id }
    scope { "reporting_company" }
    worker_type { "all" }
    source_name { "EDINET_CSV" }
    female_manager_ratio { 12.3 }
    male_childcare_leave_ratio { 45.0 }
    gender_wage_gap { 78.5 }
  end
end

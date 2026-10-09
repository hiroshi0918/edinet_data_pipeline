module DashboardHelpers
  def json_body
    JSON.parse(response.body)
  end

  # 企業 + 有報 + 人的資本を 1 セット投入し、ビュー経由で読める状態にする。
  def create_listed_company(**attrs)
    hc_keys = %i[
      scope worker_type female_manager_ratio male_childcare_leave_ratio
      gender_wage_gap average_annual_salary average_years_of_service average_age
    ]
    report_keys = %i[
      fiscal_year sales operating_profit net_profit employee_count submitted_date status
    ]
    company_keys = %i[edinet_code company_name industry securities_code]

    company = create(:company, **attrs.slice(*company_keys))
    report = create(:financial_report, company: company, **attrs.slice(*report_keys))
    unless attrs[:skip_hc]
      create(:human_capital_metric, financial_report: report, **attrs.slice(*hc_keys))
    end
    company
  end
end

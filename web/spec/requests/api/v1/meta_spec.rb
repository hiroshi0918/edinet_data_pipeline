require "rails_helper"

RSpec.describe "GET /api/v1/meta", type: :request do
  it "returns KPI counts on the default dimension" do
    create_listed_company(
      edinet_code: "E00001",
      company_name: "アルファ株式会社",
      fiscal_year: 2024
    )
    create_listed_company(
      edinet_code: "E00002",
      company_name: "ベータ株式会社",
      fiscal_year: 2023
    )
    create_listed_company(
      edinet_code: "E00003",
      company_name: "ガンマ株式会社",
      fiscal_year: 2024
    )

    get "/api/v1/meta", as: :json

    expect(response).to have_http_status(:ok)
    expect(json_body["company_count"]).to eq(3)
    expect(json_body["year_count"]).to eq(2)
    expect(json_body["total_records"]).to eq(3)
    expect(json_body["latest_submission"]).to eq("2025-06-27")
    expect(json_body["fiscal_years"]).to eq([ 2023, 2024 ])
    expect(json_body["default_year"]).to eq(2024)
  end
end

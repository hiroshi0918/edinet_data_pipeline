require "rails_helper"

RSpec.describe "Api::V1::Companies", type: :request do
  describe "GET /api/v1/companies" do
    before do
      create_listed_company(
        edinet_code: "E05206",
        company_name: "株式会社セプテーニ・ホールディングス",
        industry: "サービス業"
      )
      create_listed_company(
        edinet_code: "E00001",
        company_name: "アルファ株式会社",
        industry: "情報・通信業"
      )
    end

    it "lists distinct companies ordered by name" do
      get "/api/v1/companies", as: :json

      expect(response).to have_http_status(:ok)
      names = json_body["companies"].map { |row| row["company_name"] }
      expect(names).to eq([ "アルファ株式会社", "株式会社セプテーニ・ホールディングス" ])
      expect(json_body["companies"].first).to include(
        "edinet_code" => "E00001",
        "industry" => "情報・通信業"
      )
    end

    it "searches by company name" do
      get "/api/v1/companies", params: { q: "セプテーニ", limit: 10 }, as: :json

      expect(response).to have_http_status(:ok)
      expect(json_body["companies"].length).to eq(1)
      expect(json_body["companies"].first["edinet_code"]).to eq("E05206")
    end

    it "honors limit without a search query" do
      get "/api/v1/companies", params: { limit: 1 }, as: :json

      expect(response).to have_http_status(:ok)
      expect(json_body["companies"].length).to eq(1)
    end

    it "returns 400 for a non-numeric limit" do
      get "/api/v1/companies", params: { limit: "abc" }, as: :json

      expect(response).to have_http_status(:bad_request)
      expect(json_body["error"]).to include("Invalid limit")
    end
  end

  describe "GET /api/v1/companies/:code" do
    it "returns all dimension rows for the company" do
      create_listed_company(
        edinet_code: "E05206",
        company_name: "株式会社セプテーニ・ホールディングス",
        industry: "サービス業",
        sales: 17_628_035_000,
        employee_count: 58,
        female_manager_ratio: 12.3
      )

      get "/api/v1/companies/E05206", as: :json

      expect(response).to have_http_status(:ok)
      expect(json_body["edinet_code"]).to eq("E05206")
      expect(json_body["company_name"]).to eq("株式会社セプテーニ・ホールディングス")
      expect(json_body["rows"].length).to eq(1)
      expect(json_body["rows"].first["fiscal_year"]).to eq(2024)
      expect(json_body["rows"].first["scope"]).to eq("reporting_company")
      expect(json_body["rows"].first["female_manager_ratio"]).to eq(12.3)
    end

    it "returns 404 for an unknown company code" do
      get "/api/v1/companies/E99999", as: :json

      expect(response).to have_http_status(:not_found)
      expect(json_body).to include("error")
    end
  end

  describe "GET /api/v1/companies/:code/spotlight" do
    it "uses consolidated_subsidiary when reporting_company HC is NULL" do
      company = create(
        :company,
        edinet_code: "E05206",
        company_name: "株式会社セプテーニ・ホールディングス",
        industry: "サービス業"
      )
      report = create(
        :financial_report,
        company: company,
        employee_count: 10,
        sales: 1_000_000_000,
        operating_profit: 100_000_000
      )
      create(
        :human_capital_metric,
        financial_report: report,
        scope: "reporting_company",
        female_manager_ratio: nil,
        male_childcare_leave_ratio: nil,
        gender_wage_gap: 80.0
      )
      create(
        :human_capital_metric,
        financial_report: report,
        scope: "consolidated_subsidiary",
        female_manager_ratio: 12.3,
        male_childcare_leave_ratio: 80.0,
        gender_wage_gap: 70.0
      )

      get "/api/v1/companies/E05206/spotlight",
          params: { year: 2024, scope: "auto" },
          as: :json

      expect(response).to have_http_status(:ok)
      expect(json_body["scope"]).to eq("consolidated_subsidiary")
      expect(json_body["scope_auto"]).to eq(true)
      expect(json_body["target"]["female_manager_ratio"]).to eq(12.3)
      expect(json_body["industry_rank"]["industry"]).to eq("サービス業")
      expect(json_body["industry_rank"]["metrics"].map { |row| row["key"] }).to eq(
        %w[sales operating_profit female_manager_ratio]
      )
      sales = json_body["industry_rank"]["metrics"].find { |row| row["key"] == "sales" }
      expect(sales["rank"]).to eq(1)
      expect(sales["among"]).to eq(1)
      operating_profit = json_body["industry_rank"]["metrics"].find { |row| row["key"] == "operating_profit" }
      expect(operating_profit["among"]).to eq(json_body["industry_rank"]["industry_total"])
    end

    it "returns 404 for an unknown company" do
      get "/api/v1/companies/E99999/spotlight", params: { year: 2024 }, as: :json

      expect(response).to have_http_status(:not_found)
    end
  end
end

require "rails_helper"

RSpec.describe "Api::V1::Rankings", type: :request do
  describe "GET /api/v1/rankings/human_capital" do
    before do
      create_listed_company(
        edinet_code: "E00001",
        company_name: "高比率株式会社",
        female_manager_ratio: 40.0,
        gender_wage_gap: 90.0
      )
      create_listed_company(
        edinet_code: "E00002",
        company_name: "中比率株式会社",
        female_manager_ratio: 20.0,
        gender_wage_gap: 70.0
      )
      create_listed_company(
        edinet_code: "E00003",
        company_name: "低比率株式会社",
        female_manager_ratio: 5.0,
        gender_wage_gap: 50.0
      )
    end

    it "returns top descending and bottom ascending" do
      get "/api/v1/rankings/human_capital",
          params: { year: 2024, metric: "female_manager_ratio" },
          as: :json

      expect(response).to have_http_status(:ok)
      expect(json_body["metric"]).to eq("female_manager_ratio")
      expect(json_body["top"].map { |row| row["edinet_code"] }).to eq(%w[E00001 E00002 E00003])
      expect(json_body["top"].first["value"]).to eq(40.0)
      expect(json_body["bottom"].map { |row| row["edinet_code"] }).to eq(%w[E00003 E00002 E00001])
      expect(json_body["bottom"].first["value"]).to eq(5.0)
    end

    it "returns 400 for an invalid metric" do
      get "/api/v1/rankings/human_capital",
          params: { year: 2024, metric: "male_childcare_leave_ratio" },
          as: :json

      expect(response).to have_http_status(:bad_request)
      expect(json_body["error"]).to include("Invalid metric")
    end

    it "returns 400 for an invalid scope" do
      get "/api/v1/rankings/human_capital",
          params: { year: 2024, metric: "female_manager_ratio", scope: "bogus" },
          as: :json

      expect(response).to have_http_status(:bad_request)
      expect(json_body["error"]).to include("Invalid scope")
    end
  end

  describe "GET /api/v1/rankings/size" do
    before do
      create_listed_company(edinet_code: "E10001", company_name: "巨大", sales: 1_000_000_000)
      create_listed_company(edinet_code: "E10002", company_name: "中位", sales: 200_000_000)
      create_listed_company(edinet_code: "E10003", company_name: "下限", sales: 100_000_000)
      create_listed_company(edinet_code: "E10004", company_name: "未満", sales: 50_000_000)
      create_listed_company(edinet_code: "E10005", company_name: "アーティファクト", sales: 1)
    end

    it "excludes sales below 1e8 from the bottom ranking" do
      get "/api/v1/rankings/size",
          params: { year: 2024, axis: "sales" },
          as: :json

      expect(response).to have_http_status(:ok)
      expect(json_body["axis"]).to eq("sales")
      expect(json_body["top"].first["edinet_code"]).to eq("E10001")
      expect(json_body["top"].first["value"]).to eq(1_000_000_000)
      bottom_codes = json_body["bottom"].map { |row| row["edinet_code"] }
      expect(bottom_codes).to include("E10003")
      expect(bottom_codes).not_to include("E10004", "E10005")
      expect(json_body["bottom"].first["value"]).to be >= 100_000_000
    end
  end
end

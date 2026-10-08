require "rails_helper"

RSpec.describe "GET /api/v1/industries/hc_distribution", type: :request do
  it "drops industries with fewer than 5 disclosed companies" do
    5.times do |i|
      create_listed_company(
        edinet_code: "E1#{i.to_s.rjust(4, '0')}",
        company_name: "情報#{i}",
        industry: "情報・通信業",
        female_manager_ratio: 10.0 + i
      )
    end
    4.times do |i|
      create_listed_company(
        edinet_code: "E2#{i.to_s.rjust(4, '0')}",
        company_name: "サービス#{i}",
        industry: "サービス業",
        female_manager_ratio: 20.0 + i
      )
    end

    get "/api/v1/industries/hc_distribution",
        params: { year: 2024, metric: "female_manager_ratio" },
        as: :json

    expect(response).to have_http_status(:ok)
    industries = json_body["rows"].map { |row| row["industry"] }.uniq
    expect(industries).to eq([ "情報・通信業" ])
    expect(json_body["rows"].length).to eq(5)
  end

  it "returns 400 for an invalid metric" do
    get "/api/v1/industries/hc_distribution",
        params: { year: 2024, metric: "sales" },
        as: :json

    expect(response).to have_http_status(:bad_request)
    expect(json_body["error"]).to include("Invalid metric")
  end
end

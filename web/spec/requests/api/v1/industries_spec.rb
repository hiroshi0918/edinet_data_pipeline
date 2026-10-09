require "rails_helper"

RSpec.describe "GET /api/v1/industries", type: :request do
  it "counts listed companies per industry and skips blanks" do
    create(:company, industry: "輸送用機器", securities_code: "7203")
    create(:company, industry: "輸送用機器", securities_code: "7267")
    create(:company, industry: "水産・農林業", securities_code: "1332")
    create(:company, industry: nil, securities_code: "9999")
    create(:company, industry: "輸送用機器", securities_code: nil)
    create(:company, industry: "サービス業", securities_code: "")
    create(:company, industry: "サービス業", securities_code: "   ")

    get "/api/v1/industries", as: :json

    expect(response).to have_http_status(:ok)
    expect(json_body["industries"]).to eq([
      { "industry" => "水産・農林業", "company_count" => 1 },
      { "industry" => "輸送用機器", "company_count" => 2 }
    ])
  end

  it "matches the company count of the industry ranking" do
    create(:company, industry: "輸送用機器", securities_code: "7203")
    create(:company, industry: "輸送用機器", securities_code: nil)

    get "/api/v1/industries", as: :json
    counted = json_body["industries"].find { |row| row["industry"] == "輸送用機器" }["company_count"]

    get "/api/v1/rankings", params: { industry: "輸送用機器" }, as: :json
    expect(json_body["companies"].length).to eq(counted)
  end
end

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

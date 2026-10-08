require "rails_helper"

RSpec.describe "Api::V1::Rankings index", type: :request do
  def seed_peer(code, industry:, sales:, employees:, skip_hc: false)
    create_listed_company(
      edinet_code: code,
      company_name: "会社#{code}",
      industry: industry,
      sales: sales,
      operating_profit: sales / 10,
      employee_count: employees,
      female_manager_ratio: 20.0,
      male_childcare_leave_ratio: 50.0,
      gender_wage_gap: 80.0,
      average_annual_salary: 5_000_000,
      average_years_of_service: 10.0,
      skip_hc: skip_hc
    )
  end

  before do
    [
      [ "E91001", 1_000, 50 ],
      [ "E91002", 2_000, 40 ],
      [ "E91003", 3_000, 30 ],
      [ "E91004", 4_000, 20 ],
      [ "E91005", 5_000, 10 ]
    ].each do |code, sales, employees|
      seed_peer(code, industry: "輸送用機器", sales: sales, employees: employees)
    end
    create(:company, edinet_code: "E91008", company_name: "書類なし", industry: "輸送用機器")
    seed_peer("E91009", industry: "水産・農林業", sales: 9_000, employees: 90, skip_hc: true)
    Company.find("E91001").update!(securities_code: "7203")
  end

  def codes
    json_body["companies"].map { |row| row["edinet_code"] }
  end

  it "orders by the sheet's overall score and puts missing scores last" do
    get "/api/v1/rankings", as: :json

    expect(response).to have_http_status(:ok)
    expect(json_body["axis"]).to eq("level")
    expect(codes).to eq(%w[E91001 E91002 E91003 E91004 E91005 E91009 E91008])
    expect(json_body["companies"].first["score"]).to eq(json_body["companies"].first["level"])
    expect(json_body["companies"].map { |row| row["score"] }.last(2)).to eq([ 0, nil ])
    expect(json_body["companies"]).to all(include("edinet_code", "securities_code"))
    expect(json_body["companies"].find { |row| row["edinet_code"] == "E91001" }["securities_code"]).to eq("7203")
    expect(json_body["companies"].find { |row| row["edinet_code"] == "E91008" }["securities_code"]).to be_nil
  end

  it "restricts the list to one industry" do
    get "/api/v1/rankings", params: { industry: "輸送用機器" }, as: :json

    expect(codes).to eq(%w[E91001 E91002 E91003 E91004 E91005 E91008])
    expect(codes).not_to include("E91009")
    expect(json_body["industries"]).to include("水産・農林業", "輸送用機器")
    expect(json_body["axes"].map { |item| item["key"] }).to include("level", "disclosure")
  end

  it "reorders by an axis score" do
    get "/api/v1/rankings", params: { axis: "sales", industry: "輸送用機器" }, as: :json

    expect(codes.first(5)).to eq(%w[E91005 E91004 E91003 E91002 E91001])
    expect(codes.last).to eq("E91008")

    get "/api/v1/rankings", params: { axis: "employee_count", industry: "輸送用機器" }, as: :json

    expect(codes.first(5)).to eq(%w[E91001 E91002 E91003 E91004 E91005])
  end

  it "rejects an unknown axis" do
    get "/api/v1/rankings", params: { axis: "pbr" }, as: :json

    expect(response).to have_http_status(:bad_request)
  end
end

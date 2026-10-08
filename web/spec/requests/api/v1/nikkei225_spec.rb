require "rails_helper"

RSpec.describe "Api::V1::Nikkei225", type: :request do
  def constituent(code:, edinet:, sector: "自動車")
    {
      "securities_code" => code,
      "short_name" => "短#{code}",
      "listed_name" => "上場#{code}",
      "nikkei_sector" => sector,
      "edinet_code" => edinet
    }
  end

  it "lists constituents with sheet levels, highest first" do
    5.times do |index|
      create_listed_company(
        edinet_code: "E3000#{index}",
        company_name: "会社#{index}",
        industry: "輸送用機器",
        sales: (index + 1) * 1_000,
        operating_profit: (index + 1) * 100
      )
    end

    catalog = {
      "as_of" => "2026-10-08",
      "source_note" => "test",
      "constituents" => [
        constituent(code: "0001", edinet: "E30000"),
        constituent(code: "0005", edinet: "E30004"),
        constituent(code: "9999", edinet: "E99999", sector: "海運")
      ]
    }
    allow(Nikkei225Catalog).to receive(:load).and_return(catalog)

    get "/api/v1/nikkei225", as: :json

    expect(response).to have_http_status(:ok)
    expect(json_body["as_of"]).to eq("2026-10-08")
    codes = json_body["companies"].map { |row| row["securities_code"] }
    expect(codes).to eq([ "0005", "0001", "9999" ])
    top = json_body["companies"].first
    expect(top).to include(
      "company_name" => "会社4",
      "has_sheet" => true,
      "fiscal_year" => 2024,
      "nikkei_sector" => "自動車"
    )
    expect(top["level"]).to be > json_body["companies"][1]["level"]
    missing = json_body["companies"].last
    expect(missing).to include(
      "has_sheet" => false,
      "company_name" => "上場9999",
      "edinet_code" => nil,
      "level" => nil
    )
  end

  it "ships a 225-name snapshot" do
    catalog = Nikkei225Catalog.load

    expect(catalog["as_of"]).to eq("2026-10-08")
    codes = catalog["constituents"].map { |row| row["securities_code"] }
    expect(codes).to include("7203", "285A")
    expect(codes.uniq.length).to eq(225)
  end
end

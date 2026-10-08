require "rails_helper"

RSpec.describe "Api::V1::Companies sheet", type: :request do
  def axis(body, key)
    if key == "disclosure"
      return axis(body, "people").fetch("disclosure")
    end

    body["axes"].find { |item| item["key"] == key }
  end

  def seed_company(code, industry:, sales:, **attrs)
    merged = {
      edinet_code: code,
      company_name: "会社#{code}",
      industry: industry,
      fiscal_year: 2024,
      sales: sales,
      operating_profit: sales / 10,
      employee_count: 100,
      female_manager_ratio: 20.0,
      male_childcare_leave_ratio: 50.0,
      gender_wage_gap: 80.0,
      average_annual_salary: 5_000_000,
      average_years_of_service: 10.0,
      average_age: 40.0
    }.merge(attrs)
    create_listed_company(**merged)
  end

  describe "GET /api/v1/companies/:code/sheet" do
    it "returns 404 for an unknown company" do
      get "/api/v1/companies/E99999/sheet", as: :json

      expect(response).to have_http_status(:not_found)
    end

    it "returns no scores when the company has no filing" do
      create(:company, edinet_code: "E00002", company_name: "書類なし株式会社", industry: "情報・通信業")

      get "/api/v1/companies/E00002/sheet", as: :json

      expect(response).to have_http_status(:ok)
      expect(json_body["fiscal_year"]).to be_nil
      expect(json_body["level"]).to be_nil
      expect(json_body["securities_code"]).to be_nil
      expect(axis(json_body, "disclosure")["score"]).to be_nil
      expect(json_body["axes"].map { |item| item["key"] }).not_to include("disclosure")
    end

    it "returns values without scores when the company has no industry" do
      create_listed_company(
        edinet_code: "E00001",
        company_name: "業種なし株式会社",
        industry: nil,
        sales: 2_000
      )

      get "/api/v1/companies/E00001/sheet", as: :json

      expect(response).to have_http_status(:ok)
      expect(json_body["fiscal_year"]).to eq(2024)
      expect(json_body["level"]).to be_nil
      expect(axis(json_body, "sales")).to include("value" => 2_000, "score" => nil)
      expect(axis(json_body, "disclosure")["score"]).to be_nil
      expect(axis(json_body, "expectation")["score"]).to be_nil
    end

    it "uses the company's latest fiscal year" do
      company = create(:company, edinet_code: "E00010", industry: "情報・通信業", securities_code: "6758")
      create(:financial_report, company: company, fiscal_year: 2023, sales: 1, submitted_date: Date.new(2024, 6, 1))
      create(:financial_report, company: company, fiscal_year: 2024, sales: 9, submitted_date: Date.new(2025, 6, 1))

      get "/api/v1/companies/E00010/sheet", as: :json

      expect(axis(json_body, "sales")["value"]).to eq(9)
      expect(json_body["fiscal_year"]).to eq(2024)
      expect(json_body["securities_code"]).to eq("6758")
    end

    it "leaves an axis blank when fewer than five peers have a value, and still scores disclosure" do
      4.times do |index|
        seed_company("E1000#{index}", industry: "小売業", sales: (index + 1) * 100)
      end

      get "/api/v1/companies/E10000/sheet", as: :json

      expect(axis(json_body, "sales")["score"]).to be_nil
      expect(axis(json_body, "sales")["peer_count"]).to eq(4)
      expect(axis(json_body, "disclosure")).to include("score" => 100, "disclosed_count" => 3)
      expect(json_body["level"]).to eq(100)
    end

    it "scores disclosure as 0, 33, 67, or 100 from how many of the three people metrics exist" do
      cases = {
        "E20000" => { skip_hc: true, expected: 0 },
        "E20001" => { female_manager_ratio: 10.0, male_childcare_leave_ratio: nil, gender_wage_gap: nil, expected: 33 },
        "E20002" => { female_manager_ratio: 10.0, male_childcare_leave_ratio: 20.0, gender_wage_gap: nil, expected: 67 },
        "E20003" => { expected: 100 }
      }
      cases.each do |code, attrs|
        expected = attrs.delete(:expected)
        seed_company(code, industry: "建設業", sales: 100, **attrs)
        get "/api/v1/companies/#{code}/sheet", as: :json
        expect(axis(json_body, "disclosure")["score"]).to eq(expected)
      end
    end

    it "gives a higher people score to a higher wage gap, which means closer to parity" do
      [ 10.0, 30.0, 50.0, 70.0, 90.0 ].each_with_index do |gap, index|
        seed_company("E3000#{index}", industry: "サービス業", sales: 1_000, gender_wage_gap: gap)
      end

      get "/api/v1/companies/E30000/sheet", as: :json
      low = axis(json_body, "people")
      get "/api/v1/companies/E30004/sheet", as: :json
      high = axis(json_body, "people")

      low_gap = low["metrics"].find { |metric| metric["key"] == "gender_wage_gap" }
      high_gap = high["metrics"].find { |metric| metric["key"] == "gender_wage_gap" }
      expect(high_gap["score"]).to be > low_gap["score"]
      expect(high["score"]).to be > low["score"]
    end

    it "does not treat a missing people metric as zero" do
      5.times do |index|
        seed_company(
          "E4000#{index}",
          industry: "製造業",
          sales: 1_000,
          female_manager_ratio: index * 10.0
        )
      end
      seed_company(
        "E40009",
        industry: "製造業",
        sales: 1_000,
        female_manager_ratio: nil
      )

      get "/api/v1/companies/E40000/sheet", as: :json
      zero_female = axis(json_body, "people")["score"]
      get "/api/v1/companies/E40009/sheet", as: :json
      missing_female = axis(json_body, "people")["score"]

      expect(missing_female).to be > zero_female
    end

    it "leaves operating margin blank when sales are not positive" do
      5.times do |index|
        seed_company("E5000#{index}", industry: "運輸業", sales: (index + 1) * 1_000)
      end
      seed_company("E50009", industry: "運輸業", sales: 0, operating_profit: 10)

      get "/api/v1/companies/E50009/sheet", as: :json

      expect(axis(json_body, "operating_margin")).to include("value" => nil, "score" => nil)
      expect(axis(json_body, "sales")["value"]).to eq(0)
      expect(axis(json_body, "sales")["score"]).to eq(17)
    end

    it "scores PSR inside the industry when a fiscal-month close exists" do
      5.times do |index|
        company = create(
          :company,
          edinet_code: "E8000#{index}",
          industry: "精密機器",
          securities_code: "800#{index}",
          fiscal_month: 3
        )
        create(
          :financial_report,
          company: company,
          sales: 1_000,
          net_profit: 100,
          shares_outstanding: 100,
          operating_profit: 100
        )
        ActiveRecord::Base.connection.exec_insert(<<~SQL.squish, "price", [])
          INSERT INTO equity_month_closes (securities_code, fiscal_year, month, close_price)
          VALUES ('800#{index}', 2024, 3, #{index + 1})
        SQL
      end

      get "/api/v1/companies/E80000/sheet", as: :json
      low = axis(json_body, "expectation")
      get "/api/v1/companies/E80004/sheet", as: :json
      high = axis(json_body, "expectation")

      expect(low["score"]).to eq(20)
      expect(high["score"]).to eq(100)
      expect(high["per"]).to be > low["per"]
      expect(high["psr_basis"]).to eq("close")
    end

    it "scores PSR from the close for a loss-maker with no reported PER" do
      5.times do |index|
        company = create(
          :company,
          edinet_code: "E8100#{index}",
          industry: "空運業",
          securities_code: "810#{index}",
          fiscal_month: 3
        )
        create(
          :financial_report,
          company: company,
          sales: 1_000,
          net_profit: index.zero? ? -50 : 100,
          shares_outstanding: 100,
          operating_profit: 10
        )
        ActiveRecord::Base.connection.exec_insert(<<~SQL.squish, "price", [])
          INSERT INTO equity_month_closes (securities_code, fiscal_year, month, close_price)
          VALUES ('810#{index}', 2024, 3, #{(index + 1) * 2})
        SQL
      end

      get "/api/v1/companies/E81000/sheet", as: :json

      expectation = axis(json_body, "expectation")
      expect(expectation["value"]).to eq(0.2)
      expect(expectation["per"]).to be_nil
      expect(expectation["score"]).to eq(20)
      expect(expectation["psr_basis"]).to eq("close")
    end

    it "marks PSR taken from the reported PER when there is no close" do
      5.times do |index|
        company = create(:company, edinet_code: "E8200#{index}", industry: "保険業")
        report = create(
          :financial_report,
          company: company,
          sales: 1_000,
          net_profit: 100,
          operating_profit: 10,
          shares_outstanding: nil
        )
        ActiveRecord::Base.connection.exec_insert(<<~SQL.squish, "per", [])
          INSERT INTO raw_edinet_facts
            (doc_id, source_file, row_number, item_name, relative_year, raw_value)
          VALUES
            (#{ActiveRecord::Base.connection.quote(report.doc_id)}, 'spec.csv', 1,
             '株価収益率、経営指標等', '当期', '#{(index + 1) * 10}')
        SQL
      end

      get "/api/v1/companies/E82000/sheet", as: :json
      low = axis(json_body, "expectation")
      get "/api/v1/companies/E82004/sheet", as: :json
      high = axis(json_body, "expectation")

      expect(low["psr_basis"]).to eq("reported_per")
      expect(low["value"]).to eq(1)
      expect(low["per"]).to eq(10)
      expect(high["value"]).to eq(5)
      expect(high["score"]).to be > low["score"]
    end

    it "scores sales inside the industry and ignores other industries" do
      5.times do |index|
        seed_company("E6000#{index}", industry: "卸売業", sales: (index + 1) * 10)
      end
      seed_company("E60009", industry: "銀行業", sales: 10_000_000)

      get "/api/v1/companies/E60000/sheet", as: :json
      expect(axis(json_body, "sales")["score"]).to eq(20)

      get "/api/v1/companies/E60004/sheet", as: :json
      expect(axis(json_body, "sales")["score"]).to eq(100)
      expect(json_body["level"]).to eq(100)
      expect(axis(json_body, "expectation")["score"]).to be_nil
    end
  end
end

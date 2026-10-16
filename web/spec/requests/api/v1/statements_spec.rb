require "rails_helper"

RSpec.describe "Api::V1::Companies statements", type: :request do
  let(:base_statement) do
    {
      accounting_standard: "jgaap",
      basis: "consolidated",
      total_assets: 1_000,
      current_assets: 600,
      cash_and_deposits: 200,
      trade_receivables: 100,
      inventories: 50,
      noncurrent_assets: 400,
      property_plant_equipment: 250,
      intangible_assets: 30,
      goodwill: 10,
      investment_securities: 60,
      total_liabilities: 600,
      current_liabilities: 400,
      noncurrent_liabilities: 200,
      interest_bearing_debt: 300,
      net_assets: 400,
      retained_earnings: 300,
      net_sales: 2_400,
      cost_of_sales: 1_800,
      gross_profit: 600,
      sga_expenses: 450,
      operating_income: 150,
      ordinary_income: 140,
      net_income: 90,
      operating_cf: 120,
      investing_cf: -80,
      financing_cf: -30
    }
  end

  def insert_statement(report, **attrs)
    values = base_statement.merge(
      doc_id: report.doc_id,
      edinet_code: report.edinet_code,
      fiscal_year: report.fiscal_year
    ).merge(attrs)
    connection = ActiveRecord::Base.connection
    columns = values.keys.join(", ")
    quoted = values.values.map { |value| connection.quote(value) }.join(", ")
    connection.execute("INSERT INTO financial_statements (#{columns}) VALUES (#{quoted})")
  end

  def seed(industry: "情報・通信業", report_attrs: {}, **attrs)
    company = create(:company, edinet_code: "E80001", company_name: "お財布株式会社", industry: industry)
    report = create(:financial_report, company: company, fiscal_year: 2025, **report_attrs)
    insert_statement(report, **attrs)
    company
  end

  def fetch
    get "/api/v1/companies/E80001/statements", as: :json
    expect(response).to have_http_status(:ok)
    json_body
  end

  def insight_keys(body)
    body["insights"].map { |item| item["key"] }
  end

  def part(parts, key)
    parts.find { |item| item["key"] == key }
  end

  it "returns 404 for an unknown company" do
    get "/api/v1/companies/E99999/statements", as: :json

    expect(response).to have_http_status(:not_found)
  end

  it "returns empty statements when nothing was extracted" do
    create(:company, edinet_code: "E80001", company_name: "空株式会社")

    body = fetch

    expect(body["company_name"]).to eq("空株式会社")
    expect(body["balance_sheet"]).to be_nil
    expect(body["income_statement"]).to be_nil
    expect(body["insights"]).to eq([])
  end

  it "uses the latest fiscal year" do
    company = create(:company, edinet_code: "E80001")
    old = create(:financial_report, company: company, fiscal_year: 2024)
    new = create(:financial_report, company: company, fiscal_year: 2025)
    insert_statement(old, total_assets: 1)
    insert_statement(new)

    body = fetch

    expect(body["fiscal_year"]).to eq(2025)
    expect(body["doc_id"]).to eq(new.doc_id)
    expect(body["balance_sheet"]["total_assets"]).to eq(1_000)
  end

  it "splits assets and funding without overlap" do
    seed

    body = fetch
    assets = body["balance_sheet"]["assets"]
    funding = body["balance_sheet"]["funding"]

    expect(assets.map { |item| item["key"] }).to eq(%w[cash receivables inventories property intangibles investments other])
    expect(part(assets, "cash")).to include("amount" => 200, "share" => 0.2)
    expect(part(assets, "other")["amount"]).to eq(1_000 - 200 - 100 - 50 - 250 - 30 - 60)
    expect(assets.sum { |item| item["amount"] }).to eq(1_000)
    expect(funding.map { |item| item["key"] }).to eq(%w[debt other_liabilities net_assets])
    expect(part(funding, "other_liabilities")["amount"]).to eq(300)
    expect(body["balance_sheet"]["debt_known"]).to be(true)
  end

  it "merges liabilities when borrowings are unknown and skips the net cash call" do
    seed(accounting_standard: "ifrs", interest_bearing_debt: nil, cash_and_deposits: 900)

    body = fetch
    funding = body["balance_sheet"]["funding"]

    expect(funding.map { |item| item["key"] }).to eq(%w[liabilities net_assets])
    expect(body["balance_sheet"]["debt_known"]).to be(false)
    expect(insight_keys(body)).not_to include("net_cash")
  end

  it "fills missing PL lines from the others and falls back to report sales" do
    seed(net_sales: nil, cost_of_sales: nil, sga_expenses: nil, report_attrs: { sales: 2_400 })

    income = fetch["income_statement"]

    expect(income["net_sales"]).to eq(2_400)
    expect(income["sales_source"]).to eq("summary")
    expect(income["cost_of_sales"]).to eq(1_800)
    expect(income["sga_expenses"]).to eq(450)
  end

  describe "insights" do
    it "calls a stable, cash-rich company with no debt" do
      seed(net_assets: 500, total_liabilities: 500, interest_bearing_debt: 0, cash_and_deposits: 300)

      body = fetch
      keys = insight_keys(body)

      expect(keys).to include("stable", "cash_rich", "net_cash")
      expect(body["insights"].find { |item| item["key"] == "net_cash" }["text"]).to eq("借入金や社債がありません。")
      expect(body["ratios"]["equity_ratio"]).to eq(0.5)
    end

    it "uses months of sales for cash even when the share is small" do
      seed(cash_and_deposits: 100, net_sales: 400)

      body = fetch

      expect(body["ratios"]["cash_months"]).to eq(3.0)
      expect(insight_keys(body)).to include("cash_rich")
    end

    it "flags an equity ratio below 20 percent" do
      seed(net_assets: 199, total_liabilities: 801)
      expect(insight_keys(fetch)).to include("leveraged")
    end

    it "flags negative net assets ahead of leverage" do
      seed(net_assets: -10, total_liabilities: 1_010, net_income: -5)

      keys = insight_keys(fetch)

      expect(keys).to include("insolvent", "net_loss")
      expect(keys).not_to include("leveraged")
    end

    it "reads the shape of assets at the thresholds" do
      seed(
        property_plant_equipment: 400,
        intangible_assets: 200,
        investment_securities: 250,
        inventories: 200,
        cash_and_deposits: 10,
        trade_receivables: 0
      )

      keys = insight_keys(fetch)

      expect(keys).to include("asset_heavy", "acquisitive", "investor", "inventory")
    end

    it "stays quiet just below the thresholds" do
      seed(
        property_plant_equipment: 399,
        intangible_assets: 199,
        investment_securities: 249,
        inventories: 199,
        cash_and_deposits: 10,
        net_assets: 499,
        total_liabilities: 501,
        gross_profit: 1_199,
        cost_of_sales: 1_201
      )

      keys = insight_keys(fetch)

      expect(keys & %w[asset_heavy acquisitive investor inventory stable cash_rich high_margin low_margin]).to eq([])
    end

    it "reads gross margin" do
      seed(gross_profit: 1_200, cost_of_sales: 1_200)
      expect(insight_keys(fetch)).to include("high_margin")
    end

    it "reads a thin gross margin" do
      seed(gross_profit: 360, cost_of_sales: 2_040)
      expect(insight_keys(fetch)).to include("low_margin")
    end

    it "names the cash flow pattern" do
      seed

      body = fetch

      expect(body["cash_flow"]["pattern"]["key"]).to eq("steady")
      expect(insight_keys(body)).to include("cash_flow_steady")
    end

    it "names a company living on financing" do
      seed(operating_cf: -10, investing_cf: -5, financing_cf: 40)
      expect(fetch["cash_flow"]["pattern"]["key"]).to eq("funding_gap")
    end

    it "leaves the pattern empty when a cash flow is missing" do
      seed(financing_cf: nil)

      body = fetch

      expect(body["cash_flow"]["pattern"]).to be_nil
      expect(insight_keys(body).grep(/cash_flow/)).to eq([])
    end
  end

  it "shows a note instead of insights for financial industries" do
    seed(industry: "銀行業", net_assets: 50, total_liabilities: 950)

    body = fetch

    expect(body["is_financial"]).to be(true)
    expect(body["note"]).to include("銀行")
    expect(body["insights"]).to eq([])
    expect(body["balance_sheet"]).not_to be_nil
  end
end

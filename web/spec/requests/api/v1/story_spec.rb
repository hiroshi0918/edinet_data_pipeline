require "rails_helper"

RSpec.describe "Api::V1::Companies story", type: :request do
  def insert_fact(doc_id:, row:, element_id:, relative_year:, raw_value:, item_name: "指標")
    ActiveRecord::Base.connection.exec_insert(<<~SQL.squish, "insert fact", [])
      INSERT INTO raw_edinet_facts
        (doc_id, source_file, row_number, element_id, item_name, relative_year, raw_value)
      VALUES
        (#{ActiveRecord::Base.connection.quote(doc_id)}, 'spec.csv', #{row},
         #{ActiveRecord::Base.connection.quote(element_id)},
         #{ActiveRecord::Base.connection.quote(item_name)},
         #{ActiveRecord::Base.connection.quote(relative_year)},
         #{ActiveRecord::Base.connection.quote(raw_value)})
    SQL
  end

  it "returns a 10-year frame and excerpts from the filing" do
    company = create(:company, edinet_code: "E70001", company_name: "歩み株式会社", industry: "情報・通信業")
    report = create(
      :financial_report,
      company: company,
      fiscal_year: 2026,
      sales: 100,
      operating_profit: 20,
      employee_count: 10
    )
    insert_fact(
      doc_id: report.doc_id,
      row: 1,
      element_id: "jpcrp_cor:NetSalesSummaryOfBusinessResults",
      relative_year: "当期",
      raw_value: "100",
      item_name: "売上高、経営指標等"
    )
    insert_fact(
      doc_id: report.doc_id,
      row: 2,
      element_id: "jpcrp_cor:NetSalesSummaryOfBusinessResults",
      relative_year: "前期",
      raw_value: "80",
      item_name: "売上高、経営指標等"
    )
    insert_fact(
      doc_id: report.doc_id,
      row: 3,
      element_id: "jpcrp_cor:NetSalesSummaryOfBusinessResults",
      relative_year: "四期前",
      raw_value: "40",
      item_name: "売上高、経営指標等"
    )
    insert_fact(
      doc_id: report.doc_id,
      row: 4,
      element_id: nil,
      relative_year: nil,
      raw_value: " ３ 【事業の内容】　当社はソフトを作る。次の文です。",
      item_name: "事業の内容 [テキストブロック]"
    )
    insert_fact(
      doc_id: report.doc_id,
      row: 5,
      element_id: nil,
      relative_year: nil,
      raw_value: "1990年に創業した。2001年に上場した。",
      item_name: "沿革 [テキストブロック]"
    )

    get "/api/v1/companies/E70001/story", as: :json

    expect(response).to have_http_status(:ok)
    years = json_body["series"].map { |point| point["fiscal_year"] }
    expect(years).to eq((2017..2026).to_a)
    by_year = json_body["series"].index_by { |point| point["fiscal_year"] }
    expect(by_year[2026]["sales"]).to eq(100)
    expect(by_year[2025]["sales"]).to eq(80)
    expect(by_year[2022]["sales"]).to eq(40)
    expect(by_year[2017]["sales"]).to be_nil
    expect(json_body["narrative"]["business"]["text"]).to start_with("当社はソフトを作る")
    expect(json_body["narrative"]["business"]["source"]).to start_with("当社はソフトを作る")
    expect(json_body["narrative"]["rewritten"]).to be(false)
    labels = json_body["narrative"]["history"].map { |beat| beat["label"] }
    expect(labels).to include("1990年", "2001年")
  end

  it "does not call Claude while reading" do
    company = create(:company, edinet_code: "E70003", company_name: "読取株式会社", industry: "情報・通信業")
    create(:financial_report, company: company, fiscal_year: 2026, sales: 100)
    allow(StoryRewriter).to receive(:rewrite)

    get "/api/v1/companies/E70003/story", as: :json

    expect(response).to have_http_status(:ok)
    expect(StoryRewriter).not_to have_received(:rewrite)
  end

  it "returns a saved rewrite and replaces it when asked again" do
    company = create(:company, edinet_code: "E70004", company_name: "保存株式会社", industry: "情報・通信業")
    report = create(:financial_report, company: company, fiscal_year: 2026, sales: 100)
    insert_fact(
      doc_id: report.doc_id,
      row: 1,
      element_id: nil,
      relative_year: nil,
      raw_value: "当社は広告を営む。",
      item_name: "事業の内容 [テキストブロック]"
    )
    allow(StoryRewriter).to receive(:api_key).and_return("test-key")
    allow(StoryRewriter).to receive(:rewrite).and_return(
      {
        business: { text: "一度目。", source: "当社は広告を営む。" },
        history: [],
        rewritten: true
      },
      {
        business: { text: "二度目。", source: "当社は広告を営む。" },
        history: [],
        rewritten: true
      }
    )

    StoryNarrative.rewrite_document(report.doc_id)
    get "/api/v1/companies/E70004/story", as: :json
    expect(json_body["narrative"]["rewritten"]).to be(true)
    expect(json_body["narrative"]["business"]["text"]).to eq("一度目。")

    StoryNarrative.rewrite_document(report.doc_id)
    get "/api/v1/companies/E70004/story", as: :json
    expect(json_body["narrative"]["business"]["text"]).to eq("二度目。")
    expect(StoryRewriter).to have_received(:rewrite).twice
  end

  it "keeps the headline series when another element is longer, including a sharp drop" do
    company = create(:company, edinet_code: "E70005", company_name: "優先株式会社", industry: "情報・通信業")
    report = create(
      :financial_report,
      company: company,
      fiscal_year: 2026,
      sales: 100,
      operating_profit: 20,
      employee_count: 10
    )
    insert_fact(
      doc_id: report.doc_id, row: 50,
      element_id: "jpcrp_cor:RevenueIFRSKeyFinancialData",
      relative_year: "当期", raw_value: "100", item_name: "売上収益"
    )
    insert_fact(
      doc_id: report.doc_id, row: 51,
      element_id: "jpcrp_cor:RevenueIFRSKeyFinancialData",
      relative_year: "前期", raw_value: "90", item_name: "売上収益"
    )
    insert_fact(
      doc_id: report.doc_id, row: 52,
      element_id: "jpcrp_cor:RevenueIFRSKeyFinancialData",
      relative_year: "五期前", raw_value: "10", item_name: "売上収益"
    )
    insert_fact(
      doc_id: report.doc_id, row: 1,
      element_id: "jpcrp_cor:OperatingRevenue2SummaryOfBusinessResults",
      relative_year: "当期", raw_value: "100", item_name: "営業収益"
    )
    insert_fact(
      doc_id: report.doc_id, row: 2,
      element_id: "jpcrp_cor:OperatingRevenue2SummaryOfBusinessResults",
      relative_year: "前期", raw_value: "50", item_name: "営業収益"
    )
    insert_fact(
      doc_id: report.doc_id, row: 3,
      element_id: "jpcrp_cor:OperatingRevenue2SummaryOfBusinessResults",
      relative_year: "三期前", raw_value: "30", item_name: "営業収益"
    )
    insert_fact(
      doc_id: report.doc_id, row: 4,
      element_id: "jpcrp_cor:OperatingRevenue2SummaryOfBusinessResults",
      relative_year: "四期前", raw_value: "40", item_name: "営業収益"
    )
    insert_fact(
      doc_id: report.doc_id, row: 10,
      element_id: "jpcrp_cor:OperatingIncomeSummary",
      relative_year: "当期", raw_value: "20", item_name: "営業利益、経営指標等"
    )
    insert_fact(
      doc_id: report.doc_id, row: 11,
      element_id: "jpcrp_cor:OperatingIncomeSummary",
      relative_year: "前期", raw_value: "15", item_name: "営業利益、経営指標等"
    )
    insert_fact(
      doc_id: report.doc_id, row: 12,
      element_id: "jpcrp_cor:OperatingIncomeSummary",
      relative_year: "五期前", raw_value: "1", item_name: "営業利益、経営指標等"
    )
    insert_fact(
      doc_id: report.doc_id, row: 20,
      element_id: "jpcrp_cor:SegmentOperatingIncome",
      relative_year: "当期", raw_value: "20", item_name: "営業利益（セグメント）"
    )
    insert_fact(
      doc_id: report.doc_id, row: 21,
      element_id: "jpcrp_cor:SegmentOperatingIncome",
      relative_year: "前期", raw_value: "2", item_name: "営業利益（セグメント）"
    )
    insert_fact(
      doc_id: report.doc_id, row: 22,
      element_id: "jpcrp_cor:SegmentOperatingIncome",
      relative_year: "三期前", raw_value: "3", item_name: "営業利益（セグメント）"
    )
    insert_fact(
      doc_id: report.doc_id, row: 23,
      element_id: "jpcrp_cor:SegmentOperatingIncome",
      relative_year: "四期前", raw_value: "4", item_name: "営業利益（セグメント）"
    )

    get "/api/v1/companies/E70005/story", as: :json

    by_year = json_body["series"].index_by { |point| point["fiscal_year"] }
    expect(by_year[2025]["sales"]).to eq(90)
    expect(by_year[2021]["sales"]).to eq(10)
    expect(by_year[2022]["sales"]).to be_nil
    expect(by_year[2025]["operating_profit"]).to eq(15)
    expect(by_year[2021]["operating_profit"]).to eq(1)
    expect(by_year[2023]["operating_profit"]).to be_nil
  end

  it "shows an older filing's sales inside the 10-year window" do
    company = create(:company, edinet_code: "E70002", company_name: "二年株式会社", industry: "情報・通信業")
    create(:financial_report, company: company, fiscal_year: 2018, sales: 200, submitted_date: Date.new(2018, 6, 25))
    create(:financial_report, company: company, fiscal_year: 2026, sales: 500, submitted_date: Date.new(2026, 6, 25))

    get "/api/v1/companies/E70002/story", as: :json

    by_year = json_body["series"].index_by { |point| point["fiscal_year"] }
    expect(by_year.keys).to eq((2017..2026).to_a)
    expect(by_year[2018]["sales"]).to eq(200)
    expect(by_year[2026]["sales"]).to eq(500)
  end
end

require "rails_helper"

RSpec.describe StoryBatch do
  def insert_text(doc_id, row, item_name, raw_value)
    connection = ActiveRecord::Base.connection
    connection.exec_insert(<<~SQL.squish, "insert fact", [])
      INSERT INTO raw_edinet_facts
        (doc_id, source_file, row_number, element_id, item_name, relative_year, raw_value)
      VALUES
        (#{connection.quote(doc_id)}, 'spec.csv', #{row}, NULL,
         #{connection.quote(item_name)}, NULL, #{connection.quote(raw_value)})
    SQL
  end

  def text_message(text)
    double(stop_reason: :end_turn, content: [ double(type: :text, text: text) ])
  end

  def succeeded(doc_id, text)
    double(custom_id: doc_id, result: double(type: :succeeded, message: text_message(text)))
  end

  it "picks the same filing the story page shows" do
    company = create(:company, edinet_code: "E70101")
    create(:financial_report, company: company, doc_id: "S0000A01", fiscal_year: 2025)
    create(:financial_report, company: company, doc_id: "S0000A03", fiscal_year: 2026)
    create(:financial_report, company: company, doc_id: "S0000A02", fiscal_year: 2026)
    other = create(:company, edinet_code: "E70102")
    create(:financial_report, company: other, doc_id: "S0000B01", fiscal_year: 2026)

    expect(StoryBatch.latest_doc_ids).to contain_exactly("S0000A02", "S0000B01")
  end

  it "sends one request per filing that has text and skips the rest" do
    company = create(:company, edinet_code: "E70104")
    create(:financial_report, company: company, doc_id: "S0000C01")
    create(:financial_report, company: company, doc_id: "S0000C02")
    insert_text("S0000C01", 1, "事業の内容 [テキストブロック]", "３【事業の内容】当社は広告を営む。")
    batches = double
    allow(batches).to receive(:create).and_return(double(id: "msgbatch_1"))
    client = double(messages: double(batches: batches))

    ids = StoryBatch.submit(client, [ "S0000C01", "S0000C02" ])

    expect(ids).to eq([ "msgbatch_1" ])
    expect(batches).to have_received(:create) do |requests:|
      expect(requests.map { |request| request[:custom_id] }).to eq([ "S0000C01" ])
      expect(requests.first[:params][:messages].first[:content]).to include("当社は広告を営む。")
    end
  end

  it "saves parsed results and reports the ones it could not use" do
    company = create(:company, edinet_code: "E70103")
    report = create(:financial_report, company: company, doc_id: "S0000D01")
    insert_text(report.doc_id, 1, "事業の内容 [テキストブロック]", "当社は広告を営む。")
    errored = double(custom_id: "S0000D02", result: double(type: :errored))
    broken = succeeded("S0000D03", "JSON ではない")
    batches = double
    allow(batches).to receive(:results_streaming).with("msgbatch_1").and_return(
      [ succeeded(report.doc_id, { business: { text: "広告を作っています。" } }.to_json), errored, broken ]
    )
    client = double(messages: double(batches: batches))

    result = StoryBatch.collect(client, "msgbatch_1")

    expect(result).to eq(saved: 1, failed: [ "S0000D02", "S0000D03" ])
    expect(StoryCache.read(report.doc_id)[:business]).to eq(text: "広告を作っています。", source: "当社は広告を営む。")
  end
end

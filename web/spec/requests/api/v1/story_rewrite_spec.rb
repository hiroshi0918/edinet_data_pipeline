require "rails_helper"

RSpec.describe StoryRewriter do
  it "keeps the business text with the whole source and only history beats whose quote is in the source" do
    business = "当社は広告事業を営む。創業は東京である。"
    history = "1990年に設立した。2001年に上場した。"
    payload = {
      business: { text: "広告を作って売っています。" },
      history: [
        { label: "1990年", text: "1990年に始まった。", quote: "1990年に設立した。" },
        { label: "架空", text: "海外に進出した。", quote: "この引用は原文に無い。" }
      ]
    }.to_json
    allow(StoryRewriter).to receive(:request).and_return(payload)

    result = StoryRewriter.rewrite("test-key", business, history)

    expect(result[:rewritten]).to be(true)
    expect(result[:business]).to eq(text: "広告を作って売っています。", source: business)
    expect(result[:history].map { |beat| beat[:source] }).to eq([ "1990年に設立した。" ])
  end

  it "raises when the api key is missing" do
    allow(StoryRewriter).to receive(:api_key).and_return("")

    expect { StoryNarrative.rewrite_document("S00000001") }
      .to raise_error(StoryNarrative::RewriteError, /CLAUDE_API_KEY/)
  end
end

# 沿革と事業の内容を、原文の引用つきの短い文章にする。
require "json"

class StoryRewriter
  MODEL = :"claude-haiku-5-5"

  def self.rewrite(api_key, business_source, history_source)
    content = request(api_key, business_source, history_source).to_s
    return nil if content.empty?

    parsed = JSON.parse(extract_json(content))
    business = keep_quote(parsed["business"], business_source)
    history = Array(parsed["history"]).filter_map { |beat| keep_beat(beat, history_source) }
    return nil if business.nil? && history.empty?

    { business: business, history: history.first(6), rewritten: true }
  end

  def self.api_key
    ENV["CLAUDE_API_KEY"].to_s
  end

  def self.request(api_key, business_source, history_source)
    client = Anthropic::Client.new(api_key: api_key)
    message = client.messages.create(
      model: MODEL,
      max_tokens: 4096,
      system_: "有報の抜粋だけを材料に、日本語の短い文章を JSON だけ返す。原文に無い事実は書かない。各 text の quote には、その文の根拠になった原文の連続した引用を入れる。",
      messages: [
        {
          role: "user",
          content: <<~PROMPT
            次の形式だけを返す。説明や Markdown は付けない。
            {"business":{"text":"...","quote":"..."},"history":[{"label":"1990年","text":"...","quote":"..."}]}
            事業は1段落。歩みは時系列で最大6件。quote は下の原文から一文字も変えずに切り出す。

            事業の内容:
            #{business_source[0, 6000]}

            沿革:
            #{history_source[0, 6000]}
          PROMPT
        }
      ]
    )
    return "" if message.stop_reason.to_s == "refusal"

    message.content.filter_map { |block| block.text if block.type == :text }.join
  end

  def self.extract_json(content)
    match = content.match(/\{.*\}/m)
    match ? match[0] : content
  end

  def self.keep_quote(node, source)
    return nil unless node.is_a?(Hash)

    quote = node["quote"].to_s
    text = node["text"].to_s
    return nil if quote.empty? || text.empty? || !source.include?(quote)

    { text: text, source: quote }
  end

  def self.keep_beat(beat, source)
    kept = keep_quote(beat, source)
    return nil unless kept

    kept.merge(label: beat["label"].to_s.presence)
  end
end

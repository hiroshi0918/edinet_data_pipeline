# 事業の内容は一般向けの短い文章に、沿革は原文の引用つきの歩みにする。
require "json"

class StoryRewriter
  MODEL = :"claude-haiku-5-5"

  def self.rewrite(api_key, business_source, history_source)
    parse(request(api_key, business_source, history_source).to_s, business_source, history_source)
  end

  def self.parse(content, business_source, history_source)
    return nil if content.empty?

    parsed = JSON.parse(extract_json(content))
    return nil unless parsed.is_a?(Hash)

    business = keep_business(parsed["business"], business_source)
    history = Array(parsed["history"]).filter_map { |beat| keep_beat(beat, history_source) }
    return nil if business.nil? && history.empty?

    { business: business, history: history.first(6), rewritten: true }
  end

  def self.api_key
    ENV["CLAUDE_API_KEY"].to_s
  end

  def self.request(api_key, business_source, history_source)
    client = Anthropic::Client.new(api_key: api_key)
    text_of(client.messages.create(**params(business_source, history_source)))
  end

  def self.text_of(message)
    return "" if message.stop_reason.to_s == "refusal"

    message.content.filter_map { |block| block.text if block.type == :text }.join
  end

  def self.params(business_source, history_source)
    {
      model: MODEL,
      max_tokens: 16_000,
      system_: "有報の抜粋だけを材料に、日本語の短い文章を JSON だけ返す。原文に無い事実は書かない。",
      messages: [
        {
          role: "user",
          content: <<~PROMPT
            次の形式だけを返す。説明や Markdown は付けない。
            {"business":{"text":"..."},"history":[{"label":"1990年","text":"...","quote":"..."}]}

            business.text の書き方:
            - 読み手はこの業界に詳しくない人。中高生でも分かる言葉で、です・ます調、150〜200字、3〜4文で書く。
            - 何を作って・売っているか（製品やサービスを具体的に）、お客さんは誰か（個人か企業か、国内か海外か）、どうやって稼いでいるか、主力の事業とそれ以外の事業の位置づけ、を書く。
            - 専門用語や有報特有の言い回しは、ふだんの言葉に言い換える。
            - 子会社や関連会社の数、セグメント区分の説明、「次のとおり」のような前置きは書かない。
            - 原文に書かれていないことは足さない。製品名・数字・順位も原文にあるものだけ使う。原文から分からない項目は省く。

            history の書き方:
            - 時系列で最大6件。quote は下の沿革の原文から一文字も変えずに切り出す。

            事業の内容:
            #{business_source[0, 6000]}

            沿革:
            #{history_source[0, 6000]}
          PROMPT
        }
      ]
    }
  end

  def self.extract_json(content)
    match = content.match(/\{.*\}/m)
    match ? match[0] : content
  end

  def self.keep_business(node, source)
    return nil unless node.is_a?(Hash)

    text = node["text"].to_s
    return nil if text.empty? || source.empty?

    { text: text, source: source }
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

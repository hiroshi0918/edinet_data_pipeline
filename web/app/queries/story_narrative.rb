# 事業の内容と沿革を歩みにする。
# 読み取りは保存済みの書き直し、無ければ原文の抜粋。原文に無い文は出さない。
class StoryNarrative
  class RewriteError < StandardError; end

  BUSINESS_ITEM = "事業の内容 [テキストブロック]"
  HISTORY_ITEM = "沿革 [テキストブロック]"
  YEAR_PATTERN = /(?:平成|令和|昭和)?\d{1,4}年/

  def self.empty
    { business: nil, history: [], rewritten: false }
  end

  def self.build(doc_id)
    StoryCache.read(doc_id) || excerpt_for(doc_id)
  end

  # 明示したときだけ Claude を呼び、通った文章を保存する。失敗はそのまま上げる。
  def self.rewrite_document(doc_id)
    key = StoryRewriter.api_key
    raise RewriteError, "CLAUDE_API_KEY がありません" if key.empty?

    business_source, history_source = sources(doc_id)
    if business_source.empty? && history_source.empty?
      raise RewriteError, "事業の内容と沿革がありません"
    end

    rewritten = StoryRewriter.rewrite(key, business_source, history_source)
    raise RewriteError, "原文に沿った文章になりませんでした" if rewritten.nil?

    StoryCache.write(doc_id, rewritten)
    rewritten
  end

  def self.excerpt_for(doc_id)
    business_source, history_source = sources(doc_id)
    {
      business: excerpt(business_source),
      history: history_beats(history_source),
      rewritten: false
    }
  end

  def self.sources(doc_id)
    blocks = text_blocks(doc_id)
    [ clean(blocks[BUSINESS_ITEM]), clean(blocks[HISTORY_ITEM]) ]
  end

  def self.text_blocks(doc_id)
    rows = ApplicationQuery.select_all(<<~SQL, doc_id, BUSINESS_ITEM, HISTORY_ITEM)
      SELECT item_name, raw_value
        FROM raw_edinet_facts
       WHERE doc_id = ?
         AND item_name IN (?, ?)
    SQL
    rows.to_h { |row| [ row[:item_name], row[:raw_value].to_s ] }
  end

  def self.clean(text)
    return "" if text.nil?

    text.to_s
      .gsub(/<[^>]+>/, " ")
      .gsub(/[ \t]+/, " ")
      .gsub(/\n{2,}/, "\n")
      .strip
  end

  def self.excerpt(source)
    return nil if source.empty?

    sentences = source.split(/(?<=。)/).map(&:strip).reject(&:empty?)
    text = sentences.first(2).join
    text = source[0, 240] if text.empty?
    { text: text[0, 240], source: source }
  end

  def self.history_beats(source)
    return [] if source.empty?

    indexes = source.enum_for(:scan, YEAR_PATTERN).map { Regexp.last_match.begin(0) }
    return [ { label: nil, text: source[0, 180], source: source } ] if indexes.length < 2

    chosen = indexes.last(6)
    chosen.each_with_index.map do |start_at, index|
      limit = chosen[index + 1] || source.length
      finish_at = [ start_at + 160, limit ].min
      snippet = source[start_at...finish_at].to_s.strip
      period = snippet.index("。")
      snippet = snippet[0..period] if period
      { label: snippet[YEAR_PATTERN], text: snippet, source: snippet }
    end
  end
end

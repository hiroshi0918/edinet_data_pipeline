# 全社の最新有報の歩みを Message Batches でまとめて書き直し、解釈できたものを保存する。
class StoryBatch
  CHUNK_SIZE = 500
  POLL_SECONDS = 60

  # StoryQuery と同じ有報を選ぶ。同じ年度・提出日なら doc_id の若いほう。
  def self.latest_doc_ids
    ApplicationQuery.select_all(<<~SQL).map { |row| row[:doc_id] }
      SELECT DISTINCT ON (edinet_code) doc_id
        FROM financial_reports
       ORDER BY edinet_code, fiscal_year DESC, submitted_date DESC, doc_id
    SQL
  end

  def self.submit(client, doc_ids)
    doc_ids.each_slice(CHUNK_SIZE).filter_map do |slice|
      requests = slice.filter_map do |doc_id|
        business, history = StoryNarrative.sources(doc_id)
        next if business.empty? && history.empty?

        { custom_id: doc_id, params: StoryRewriter.params(business, history) }
      end
      next if requests.empty?

      batch = client.messages.batches.create(requests: requests)
      yield batch, requests.size if block_given?
      batch.id
    end
  end

  def self.wait(client, batch_id)
    loop do
      batch = client.messages.batches.retrieve(batch_id)
      yield batch if block_given?
      return batch if batch.processing_status == :ended

      sleep POLL_SECONDS
    end
  end

  def self.collect(client, batch_id)
    saved = 0
    failed = []
    client.messages.batches.results_streaming(batch_id).each do |response|
      narrative = narrative_for(response)
      if narrative
        StoryCache.write(response.custom_id, narrative)
        saved += 1
      else
        failed << response.custom_id
      end
    end
    { saved: saved, failed: failed }
  end

  def self.narrative_for(response)
    return nil unless response.result.type == :succeeded

    business, history = StoryNarrative.sources(response.custom_id)
    StoryRewriter.parse(StoryRewriter.text_of(response.result.message), business, history)
  rescue JSON::ParserError
    nil
  end
end

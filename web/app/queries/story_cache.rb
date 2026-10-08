# 原文チェックを通った書き直しだけを保存する。抜粋は保存しない。
class StoryCache
  def self.read(doc_id)
    row = ApplicationRecord.connection.select_one(
      ApplicationRecord.sanitize_sql_array(
        [ "SELECT payload FROM company_stories WHERE doc_id = ?", doc_id ]
      )
    )
    return nil unless row

    payload = row["payload"]
    payload = JSON.parse(payload) if payload.is_a?(String)
    {
      business: symbolize_excerpt(payload["business"]),
      history: Array(payload["history"]).map { |beat| symbolize_excerpt(beat) },
      rewritten: true
    }
  end

  def self.write(doc_id, narrative)
    return unless narrative[:rewritten]

    edinet_code = ApplicationRecord.connection.select_value(
      ApplicationRecord.sanitize_sql_array(
        [ "SELECT edinet_code FROM financial_reports WHERE doc_id = ?", doc_id ]
      )
    )
    return if edinet_code.nil?

    ApplicationRecord.connection.exec_insert(
      ApplicationRecord.sanitize_sql_array([ <<~SQL.squish, doc_id, edinet_code, JSON.generate(json_payload(narrative)) ]),
        INSERT INTO company_stories (doc_id, edinet_code, payload)
        VALUES (?, ?, CAST(? AS json))
        ON CONFLICT (doc_id) DO UPDATE SET payload = EXCLUDED.payload
      SQL
      "insert story",
      []
    )
  end

  def self.json_payload(narrative)
    {
      "business" => narrative[:business] && {
        "text" => narrative[:business][:text],
        "source" => narrative[:business][:source]
      },
      "history" => narrative[:history].map { |beat|
        { "label" => beat[:label], "text" => beat[:text], "source" => beat[:source] }
      }
    }
  end

  def self.symbolize_excerpt(node)
    return nil unless node.is_a?(Hash)

    {
      text: node["text"],
      source: node["source"],
      label: node["label"]
    }.compact
  end
end

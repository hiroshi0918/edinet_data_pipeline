# 人的資本。1 書類 × scope × worker_type で複数行。
class HumanCapitalMetric < ApplicationRecord
  self.record_timestamps = false

  belongs_to :financial_report, foreign_key: :doc_id, primary_key: :doc_id, inverse_of: :human_capital_metrics
  belongs_to :company, foreign_key: :edinet_code, primary_key: :edinet_code, optional: true
end

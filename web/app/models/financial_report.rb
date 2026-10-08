# 1 書類（有価証券報告書）。主キーは doc_id。
class FinancialReport < ApplicationRecord
  self.primary_key = "doc_id"
  self.record_timestamps = false

  attribute :source_metadata, default: -> { {} }

  belongs_to :company, foreign_key: :edinet_code, primary_key: :edinet_code, inverse_of: :financial_reports
  has_many :human_capital_metrics, foreign_key: :doc_id, primary_key: :doc_id, inverse_of: :financial_report
end

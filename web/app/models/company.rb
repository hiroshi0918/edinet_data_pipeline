# 企業マスタ。主キーは edinet_code。スキーマは alembic 管理。
class Company < ApplicationRecord
  self.primary_key = "edinet_code"
  self.record_timestamps = false

  has_many :financial_reports, foreign_key: :edinet_code, inverse_of: :company
end

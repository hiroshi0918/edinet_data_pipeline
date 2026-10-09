# 企業マスタ。主キーは edinet_code。スキーマは alembic 管理。
class Company < ApplicationRecord
  self.primary_key = "edinet_code"
  self.record_timestamps = false

  # 証券コードがある会社。空や空白だけの値は無しと同じ。
  # ランキングと業種の目次は、この範囲だけを数える。
  scope :with_securities_code, -> { where("NULLIF(BTRIM(securities_code), '') IS NOT NULL") }

  has_many :financial_reports, foreign_key: :edinet_code, inverse_of: :company
end

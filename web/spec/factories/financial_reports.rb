# テスト用の有価証券報告書。ビュー結合の起点。
FactoryBot.define do
  factory :financial_report do
    association :company
    sequence(:doc_id) { |n| "S#{n.to_s.rjust(8, '0')}" }
    fiscal_year { 2024 }
    status { "processed" }
    submitted_date { Date.new(2025, 6, 27) }
    sales { 1_000_000_000 }
    operating_profit { 100_000_000 }
    net_profit { 80_000_000 }
    employee_count { 100 }
    source_metadata { {} }
  end
end

# テスト用企業。edinet_code は E00001 形式で一意。
FactoryBot.define do
  factory :company do
    sequence(:edinet_code) { |n| "E#{n.to_s.rjust(5, '0')}" }
    sequence(:company_name) { |n| "テスト株式会社#{n}" }
    industry { "情報・通信業" }
  end
end

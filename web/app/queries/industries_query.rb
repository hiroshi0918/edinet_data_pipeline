# 図鑑の目次。証券コードのある会社を業種で数える。
# ランキングを業種で絞ったときの社数と同じ数え方。
class IndustriesQuery
  def self.call
    counts = Company.with_securities_code.where.not(industry: nil).group(:industry).count
    {
      industries: counts.sort_by { |industry, _| industry }.map do |industry, count|
        { industry: industry, company_count: count }
      end
    }
  end
end

# 図鑑の目次。業種ごとの社数。ランキングを業種で絞ったときの社数と同じ数え方。
class IndustriesQuery
  def self.call
    counts = Company.where.not(industry: nil).group(:industry).count
    {
      industries: counts.sort_by { |industry, _| industry }.map do |industry, count|
        { industry: industry, company_count: count }
      end
    }
  end
end

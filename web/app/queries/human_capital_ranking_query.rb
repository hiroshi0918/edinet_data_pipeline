# 女性管理職比率 / 賃金格差の上位・下位。育休はノイズが多いので対象外。
class HumanCapitalRankingQuery < ApplicationQuery
  def self.call(metric:, year:, scope:, worker_type:, limit: Dimension::RANKING_LIMIT)
    column = Dimension.column!(metric, Dimension::RANKING_HC_METRICS)
    Dimension.validate_scope!(scope)
    Dimension.validate_worker_type!(worker_type)

    {
      metric: column,
      top: ranked_metric(column, year, scope, worker_type, limit, ascending: false),
      bottom: ranked_metric(column, year, scope, worker_type, limit, ascending: true)
    }
  end
end

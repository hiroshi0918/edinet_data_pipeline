# 財務規模の上位/下位に女性管理職・賃金格差を併記。下位は BOTTOM_FLOORS で下限。
class SizeRankingQuery < ApplicationQuery
  HC_COLUMNS = %w[female_manager_ratio gender_wage_gap].freeze

  def self.call(axis:, year:, scope:, worker_type:, limit: Dimension::RANKING_LIMIT)
    column = Dimension.validate_axis!(axis)
    Dimension.validate_scope!(scope)
    Dimension.validate_worker_type!(worker_type)

    {
      axis: column,
      top: ranked_metric(
        column, year, scope, worker_type, limit,
        ascending: false, extra_columns: HC_COLUMNS
      ),
      bottom: ranked_metric(
        column, year, scope, worker_type, limit,
        ascending: true,
        extra_columns: HC_COLUMNS,
        min_value: Dimension::BOTTOM_FLOORS[column]
      )
    }
  end
end

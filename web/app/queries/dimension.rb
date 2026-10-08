# ダッシュボード API の次元・指標の許可リスト。SQL に列名を埋め込む前に必ず検証する。
class Dimension
  SCOPES = %w[reporting_company consolidated_subsidiary].freeze
  WORKER_TYPES = %w[all regular non_regular].freeze
  DEFAULT_SCOPE = "reporting_company"
  DEFAULT_WORKER_TYPE = "all"

  HC_METRICS = %w[
    female_manager_ratio
    male_childcare_leave_ratio
    gender_wage_gap
  ].freeze

  RANKING_HC_METRICS = %w[female_manager_ratio gender_wage_gap].freeze

  SIZE_AXES = %w[sales operating_profit employee_count].freeze

  FINANCIAL_METRICS = %w[sales operating_profit net_profit employee_count].freeze

  EMPLOYEE_INFO_METRICS = %w[
    average_annual_salary
    average_years_of_service
    average_age
  ].freeze

  ALL_METRICS = (
    FINANCIAL_METRICS + HC_METRICS + EMPLOYEE_INFO_METRICS
  ).freeze

  # 規模下位ランキングの下限。売上 1 億円未満は抽出アーティファクトとして除外する。
  BOTTOM_FLOORS = {
    "sales" => 1e8,
    "operating_profit" => nil,
    "employee_count" => 1
  }.freeze

  LOG_DEX = 0.3
  HC_PERCENTILE = 0.75
  OP_MARGIN_PERCENTILE = 0.50
  RANKING_LIMIT = 10
  DISTRIBUTION_MIN_COMPANIES = 5
  SEARCH_DEFAULT_LIMIT = 50

  def self.validate_scope!(scope)
    unless SCOPES.include?(scope)
      raise InvalidParameter, "Invalid scope: #{scope}"
    end
    scope
  end

  def self.validate_worker_type!(worker_type)
    unless WORKER_TYPES.include?(worker_type)
      raise InvalidParameter, "Invalid worker_type: #{worker_type}"
    end
    worker_type
  end

  def self.validate_metric!(metric, allowed = ALL_METRICS)
    unless allowed.include?(metric)
      raise InvalidParameter, "Invalid metric: #{metric}"
    end
    metric
  end

  def self.validate_axis!(axis)
    unless SIZE_AXES.include?(axis)
      raise InvalidParameter, "Invalid metric: #{axis}"
    end
    axis
  end

  def self.column!(name, allowed)
    validate_metric!(name, allowed)
  end
end

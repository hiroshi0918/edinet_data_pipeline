# 1 社の peer 比較一式。業界 peer・規模 peer（log ±0.3 dex）・理想クラスタ・業種内順位。
class SpotlightQuery < ApplicationQuery
  PEER_KEYS = %i[
    edinet_code company_name industry employee_count
    sales operating_profit net_profit
    female_manager_ratio male_childcare_leave_ratio gender_wage_gap
  ].freeze

  TARGET_KEYS = %i[
    sales operating_profit employee_count
    female_manager_ratio male_childcare_leave_ratio gender_wage_gap
  ].freeze

  # 営業利益の分母は Streamlit と同じく業種の全社数。売上と女性管理職は非 NULL の社数。
  RANK_METRICS = [
    [ :sales, :disclosed ],
    [ :operating_profit, :all_peers ],
    [ :female_manager_ratio, :disclosed ]
  ].freeze

  def self.call(company:, year:, scope:, worker_type:)
    scope_auto = scope.to_s == "auto"
    resolved_scope = if scope_auto
      detect_evaluation_scope(company.edinet_code, year)
    else
      Dimension.validate_scope!(scope)
    end
    Dimension.validate_worker_type!(worker_type)

    target = target_row(company.edinet_code, year, resolved_scope, worker_type)
    industry = target&.fetch(:industry) || company.industry
    employee_count = target&.fetch(:employee_count)

    industry_peers = query_industry_peers(industry, year, resolved_scope, worker_type)
    size_peers = query_size_peers(employee_count, year, resolved_scope, worker_type)
    ideal_cluster = query_ideal_cluster(year, resolved_scope, worker_type)

    {
      edinet_code: company.edinet_code,
      company_name: company.company_name,
      industry: industry,
      fiscal_year: year,
      scope: resolved_scope,
      scope_auto: scope_auto,
      worker_type: worker_type,
      target: target&.slice(*TARGET_KEYS),
      industry_rank: industry_rank(target, industry_peers),
      industry_peers: industry_peers.map { |row| row.slice(*PEER_KEYS) },
      size_peers: size_peers.map { |row| row.slice(*PEER_KEYS) },
      ideal_cluster: ideal_cluster.map { |row| row.slice(*PEER_KEYS) },
      benchmarks: benchmarks(target, industry_peers, size_peers, ideal_cluster)
    }
  end

  # 提出会社 × all の主要 2 HC が両方 NULL なら連結子会社で評価する（持株会社推定）。
  def self.detect_evaluation_scope(edinet_code, year)
    row = select_one(<<~SQL, edinet_code, Dimension::DEFAULT_SCOPE, Dimension::DEFAULT_WORKER_TYPE, year)
      SELECT female_manager_ratio, male_childcare_leave_ratio
        FROM #{VIEW}
       WHERE edinet_code = ?
         AND scope = ?
         AND worker_type = ?
         AND fiscal_year = ?
       LIMIT 1
    SQL
    return Dimension::DEFAULT_SCOPE if row.nil?

    if row[:female_manager_ratio].nil? && row[:male_childcare_leave_ratio].nil?
      "consolidated_subsidiary"
    else
      Dimension::DEFAULT_SCOPE
    end
  end
  private_class_method :detect_evaluation_scope

  def self.target_row(edinet_code, year, scope, worker_type)
    select_one(<<~SQL, edinet_code, year, scope, worker_type)
      SELECT #{PEER_KEYS.join(", ")}
        FROM #{VIEW}
       WHERE edinet_code = ?
         AND fiscal_year = ?
         AND scope = ?
         AND worker_type = ?
       LIMIT 1
    SQL
  end
  private_class_method :target_row

  def self.query_industry_peers(industry, year, scope, worker_type)
    return [] if industry.blank?

    select_all(<<~SQL, industry, year, scope, worker_type)
      SELECT #{PEER_KEYS.join(", ")}
        FROM #{VIEW}
       WHERE industry = ?
         AND fiscal_year = ?
         AND scope = ?
         AND worker_type = ?
    SQL
  end
  private_class_method :query_industry_peers

  # 従業員数の常用対数で ±0.3 dex（約 1/2〜2 倍）に入る企業。
  def self.query_size_peers(employee_count_target, year, scope, worker_type)
    return [] if employee_count_target.nil? || employee_count_target <= 0

    select_all(
      <<~SQL,
        SELECT #{PEER_KEYS.join(", ")}
          FROM #{VIEW}
         WHERE fiscal_year = ?
           AND scope = ?
           AND worker_type = ?
           AND employee_count IS NOT NULL
           AND employee_count > 0
           AND LOG10(employee_count::double precision)
               BETWEEN LOG10(?::double precision) - ?
                   AND LOG10(?::double precision) + ?
      SQL
      year, scope, worker_type,
      employee_count_target, Dimension::LOG_DEX,
      employee_count_target, Dimension::LOG_DEX
    )
  end
  private_class_method :query_size_peers

  # 3 HC が集合の P75 以上、かつ営業利益率が P50 以上。
  def self.query_ideal_cluster(year, scope, worker_type)
    select_all(
      <<~SQL,
        WITH base AS (
          SELECT *,
                 CASE WHEN sales IS NOT NULL AND sales > 0
                      THEN operating_profit::double precision / sales
                      ELSE NULL END AS op_margin
            FROM #{VIEW}
           WHERE fiscal_year = ?
             AND scope = ?
             AND worker_type = ?
        ),
        thresholds AS (
          SELECT
            percentile_cont(?) WITHIN GROUP (ORDER BY female_manager_ratio) AS f_thr,
            percentile_cont(?) WITHIN GROUP (ORDER BY male_childcare_leave_ratio) AS m_thr,
            percentile_cont(?) WITHIN GROUP (ORDER BY gender_wage_gap) AS g_thr,
            percentile_cont(?) WITHIN GROUP (ORDER BY op_margin) AS op_thr
          FROM base
        )
        SELECT b.edinet_code, b.company_name, b.industry, b.employee_count,
               b.sales, b.operating_profit, b.net_profit, b.op_margin,
               b.female_manager_ratio, b.male_childcare_leave_ratio, b.gender_wage_gap
          FROM base b, thresholds t
         WHERE b.female_manager_ratio       >= t.f_thr
           AND b.male_childcare_leave_ratio >= t.m_thr
           AND b.gender_wage_gap            >= t.g_thr
           AND b.op_margin                  >= t.op_thr
         ORDER BY b.op_margin DESC NULLS LAST
      SQL
      year, scope, worker_type,
      Dimension::HC_PERCENTILE, Dimension::HC_PERCENTILE,
      Dimension::HC_PERCENTILE, Dimension::OP_MARGIN_PERCENTILE
    )
  end
  private_class_method :query_ideal_cluster

  def self.industry_rank(target, peers)
    industry = target&.fetch(:industry, nil)
    if industry.blank?
      return { industry: nil, industry_total: 0, metrics: [] }
    end

    {
      industry: industry,
      industry_total: peers.length,
      metrics: RANK_METRICS.map { |key, denominator| rank_metric(key, denominator, target, peers) }
    }
  end
  private_class_method :industry_rank

  # 大きいほど上位（1 位）。NULL は順位対象外。
  def self.rank_metric(key, denominator, target, peers)
    target_val = target[key]
    valid = peers.filter_map { |row| row[key] }
    rank = if target_val.nil? || valid.empty?
      nil
    else
      valid.count { |value| value > target_val } + 1
    end
    among = denominator == :all_peers ? peers.length : valid.length

    { key: key.to_s, rank: rank, among: among }
  end
  private_class_method :rank_metric

  def self.benchmarks(target, industry_peers, size_peers, ideal_cluster)
    Dimension::HC_METRICS.each_with_object({}) do |metric, acc|
      key = metric.to_sym
      acc[key] = {
        current: target&.fetch(key, nil),
        industry_p75: percentile(industry_peers.map { |row| row[key] }, 75),
        size_peer_p75: percentile(size_peers.map { |row| row[key] }, 75),
        ideal_cluster_avg: mean(ideal_cluster.map { |row| row[key] }),
        industry_top10_avg: top_n_mean(industry_peers.map { |row| row[key] }, 10)
      }
    end
  end
  private_class_method :benchmarks
end

# 分析クエリの共通処理。対象は alembic のビュー vw_company_year_metrics。
class ApplicationQuery
  VIEW = "vw_company_year_metrics"

  # SQL が返す列名。別名 value はここでは扱わず、呼び出し側が元の列をコピーする。
  INTEGER_KEYS = %w[
    sales operating_profit net_profit employee_count fiscal_year shares_outstanding
    company_count year_count total_records
  ].freeze

  FLOAT_KEYS = %w[
    female_manager_ratio male_childcare_leave_ratio gender_wage_gap
    average_annual_salary average_years_of_service average_age
    op_margin
  ].freeze

  DATE_KEYS = %w[submitted_date latest_submission].freeze

  class << self
    def select_all(sql, *binds)
      result = ApplicationRecord.connection.select_all(
        ApplicationRecord.sanitize_sql_array([ sql, *binds ])
      )
      result.map { |row| cast_row(row) }
    end

    def select_one(sql, *binds)
      select_all(sql, *binds).first
    end

    def cast_row(row)
      row.each_with_object({}) do |(key, value), acc|
        acc[key.to_sym] = cast_value(key, value)
      end
    end

    def cast_value(key, value)
      return nil if value.nil?

      name = key.to_s
      if INTEGER_KEYS.include?(name)
        value.to_i
      elsif FLOAT_KEYS.include?(name)
        value.to_f
      elsif DATE_KEYS.include?(name)
        value.respond_to?(:iso8601) ? value.iso8601 : value.to_s
      else
        value
      end
    end

    # 指標列の型でキャストしてから value に移す。売上は整数、比率は float のまま。
    def ranked_metric(column, year, scope, worker_type, limit, ascending:, extra_columns: [], min_value: nil)
      order = ascending ? "ASC" : "DESC"
      selected = ([ column ] + extra_columns).join(", ")
      sql = <<~SQL
        SELECT edinet_code, company_name, industry, #{selected}
          FROM #{VIEW}
         WHERE fiscal_year = ?
           AND scope = ?
           AND worker_type = ?
           AND #{column} IS NOT NULL
      SQL
      binds = [ year, scope, worker_type ]
      if min_value
        sql += "   AND #{column} >= ?\n"
        binds << min_value
      end
      sql += " ORDER BY #{column} #{order} NULLS LAST\n LIMIT ?"
      binds << limit

      select_all(sql, *binds).each_with_index.map do |row, index|
        value = row.delete(column.to_sym)
        row.merge(rank: index + 1, value: value)
      end
    end

    # pandas quantile(linear) 相当。ベンチマーク計算用。
    def percentile(values, q)
      nums = values.compact.map(&:to_f)
      return nil if nums.empty?

      sorted = nums.sort
      return sorted.first if sorted.length == 1

      pos = (sorted.length - 1) * (q / 100.0)
      lower = pos.floor
      upper = pos.ceil
      return sorted[lower] if lower == upper

      weight = pos - lower
      sorted[lower] * (1 - weight) + sorted[upper] * weight
    end

    def top_n_mean(values, n)
      nums = values.compact.map(&:to_f).sort.reverse
      return nil if nums.empty?

      slice = nums.first(n)
      slice.sum / slice.length
    end

    def mean(values)
      nums = values.compact.map(&:to_f)
      return nil if nums.empty?

      nums.sum / nums.length
    end
  end
end

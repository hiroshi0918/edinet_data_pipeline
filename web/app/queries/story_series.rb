# 直近10年度の枠へ、有報の比較年度を埋める。
# 当期の値が financial_reports と一致する要素を、抽出と同じ優先順位で1つ選ぶ。
# 選んだ要素の前期以降は、増減の大きさで落とさない。
class StorySeries
  WINDOW = 10
  UNCLASSIFIED_RANK = 100

  OFFSETS = {
    "当期" => 0,
    "当年" => 0,
    "当期末" => 0,
    "前期" => 1,
    "前期末" => 1,
    "前々期" => 2,
    "前々期末" => 2,
    "三期前" => 3,
    "三期前時点" => 3,
    "四期前" => 4,
    "四期前時点" => 4,
    "五期前" => 5,
    "五期前時点" => 5,
    "六期前" => 6,
    "七期前" => 7,
    "八期前" => 8,
    "九期前" => 9
  }.freeze

  # extractors.py の SALES_ELEMENT_ID_PRIORITY。小さいほど先。
  SALES_PRIORITY = [
    %w[
      SalesAndFinancialServicesRevenueIFRSKeyFinancialData
      OperatingRevenuesIFRSKeyFinancialData
      RevenueIFRSKeyFinancialData
      NetSalesIFRSKeyFinancialData
    ],
    %w[RevenueIFRSSummaryOfBusinessResults],
    %w[NetSalesIFRS],
    %w[NetSalesSummaryOfBusinessResults],
    %w[OperatingRevenue1SummaryOfBusinessResults],
    %w[OperatingRevenue2SummaryOfBusinessResults],
    %w[NetSalesOfCompletedConstructionContractsSummaryOfBusinessResults],
    %w[GrossOperatingRevenueSummaryOfBusinessResults],
    %w[BusinessRevenueSummaryOfBusinessResults]
  ].freeze

  SALES_EXCLUDE = %w[CostOf Profit Income Intersegment ToCustomers GrossProfit Unearned].freeze

  ITEM_PATTERNS = {
    sales: %w[売上高 営業収益 売上収益 完成工事高],
    operating_profit: %w[営業利益 営業損失],
    employee_count: %w[従業員数]
  }.freeze

  class << self
    def build(reports)
      return [] if reports.empty?

      series = Hash.new { |hash, year| hash[year] = blank_point(year) }
      reports.each { |report| fill_stored(series, report) }
      reports.reverse_each do |report|
        facts = facts_for(report[:doc_id])
        extend_metric(series, report, facts, :sales, report[:sales])
        extend_metric(series, report, facts, :operating_profit, report[:operating_profit])
        extend_metric(series, report, facts, :employee_count, report[:employee_count])
      end

      latest_year = series.keys.max
      ((latest_year - (WINDOW - 1))..latest_year).map { |year| series[year] }
    end

    private

    def fill_stored(series, report)
      point = series[report[:fiscal_year]]
      point[:sales] = report[:sales] if report[:sales]
      point[:operating_profit] = report[:operating_profit] if report[:operating_profit]
      point[:employee_count] = report[:employee_count] if report[:employee_count]
    end

    # 保存値が 0 のときは、どの要素の当期か決められない。
    def extend_metric(series, report, facts, metric, stored_value)
      return if stored_value.nil? || stored_value.to_f.zero?

      chosen = choose(facts, metric, stored_value)
      return unless chosen

      chosen.sort_by { |fact| fact[:row_number].to_i }.each do |fact|
        offset = OFFSETS[fact[:relative_year].to_s]
        next if offset.nil?

        value = numeric(fact[:raw_value])
        next if value.nil?

        point = series[report[:fiscal_year] - offset]
        next if point[metric]

        point[metric] = value
      end
    end

    def choose(facts, metric, stored_value)
      groups = facts.reject { |fact| text_block?(fact) }.group_by do |fact|
        [ fact[:element_id].presence || fact[:item_name], fact[:context_id] ]
      end
      groups.values
        .select { |rows| current_match?(rows, stored_value) && candidate?(rows, metric) }
        .min_by { |rows| [ rank_for(rows, metric), rows.map { |row| row[:row_number].to_i }.min ] }
    end

    def current_match?(rows, stored_value)
      rows.any? { |row| OFFSETS[row[:relative_year].to_s] == 0 && same_number?(row[:raw_value], stored_value) }
    end

    def candidate?(rows, metric)
      return sales_candidate?(rows) if metric == :sales

      item_match?(rows, metric)
    end

    def sales_candidate?(rows)
      element_id = rows.first[:element_id]
      return true if sales_rank(element_id)
      return false if sales_excluded?(element_id)

      item_match?(rows, :sales)
    end

    def rank_for(rows, metric)
      return sales_rank(rows.first[:element_id]) || UNCLASSIFIED_RANK if metric == :sales

      0
    end

    def sales_rank(element_id)
      local = local_element(element_id)
      return nil if local.empty? || sales_excluded?(element_id)

      SALES_PRIORITY.each_with_index do |suffixes, rank|
        return rank if suffixes.any? { |suffix| local.include?(suffix) }
      end
      nil
    end

    def sales_excluded?(element_id)
      local = local_element(element_id)
      SALES_EXCLUDE.any? { |token| local.include?(token) }
    end

    def local_element(element_id)
      element_id.to_s.split(":", 2).last.to_s
    end

    def item_match?(rows, metric)
      patterns = ITEM_PATTERNS[metric]
      rows.any? { |row| patterns.any? { |pattern| row[:item_name].to_s.include?(pattern) } }
    end

    def text_block?(fact)
      fact[:element_id].to_s.end_with?("TextBlock") || fact[:item_name].to_s.include?("テキストブロック")
    end

    def facts_for(doc_id)
      years = OFFSETS.keys.map { |year| ApplicationRecord.connection.quote(year) }.join(", ")
      ApplicationQuery.select_all(<<~SQL, doc_id)
        SELECT element_id, item_name, context_id, relative_year, raw_value, row_number
          FROM raw_edinet_facts
         WHERE doc_id = ?
           AND relative_year IN (#{years})
           AND raw_value ~ '^[-0-9.]+$'
      SQL
    end

    def same_number?(raw, stored)
      number = numeric(raw)
      return false if number.nil?

      number.round == stored.to_i
    end

    def numeric(raw)
      text = raw.to_s.strip
      return nil unless text.match?(/\A-?\d+(\.\d+)?\z/)

      text.include?(".") ? text.to_f : text.to_i
    end

    def blank_point(year)
      { fiscal_year: year, sales: nil, operating_profit: nil, employee_count: nil }
    end
  end
end

# 会社シートの点。比較は「その会社の最新有報年度 × 同じ業種」。
# 人的資本は提出会社・全従業員だけを見る。連結子会社側の開示へは倒さない。
# 期待（PSR）は株価が揃うまで空欄。
class SheetQuery < ApplicationQuery
  PEOPLE_KEYS = %w[
    female_manager_ratio
    male_childcare_leave_ratio
    gender_wage_gap
  ].freeze

  SCOPE = "reporting_company"
  WORKER_TYPE = "all"

  # 点は CUME_DIST（自分以下の社数 / 比較社数）を 100 点満点に丸めたもの。
  # 同点は同じ点。単独の首位は 100。比較社数が 5 未満の軸は空欄。
  MIN_PEERS = Dimension::DISTRIBUTION_MIN_COMPANIES

  class << self
    def call(edinet_code)
      company = Company.find_by(edinet_code: edinet_code)
      return nil unless company

      year = FinancialReport.where(edinet_code: company.edinet_code).maximum(:fiscal_year)
      rows = year ? cohort_rows(company, year) : []
      target = rows.find { |row| row[:edinet_code] == company.edinet_code }
      build_sheet(company, year, target, rows)
    end

    # ランキングの軸。総合は各軸の平均なので、一覧の先頭に置く。
    def axis_catalog
      [ { key: "level", label: "総合" } ] + axis_definitions.map { |definition|
        { key: definition[:key], label: definition[:label] }
      }
    end

    # 複数社の総合点。業種と年度が同じ会社は、比較集団を1回だけ読む。
    def summaries_for(edinet_codes)
      codes = Array(edinet_codes).map(&:to_s).uniq
      return {} if codes.empty?

      companies = Company.where(edinet_code: codes).index_by(&:edinet_code)
      years = FinancialReport.where(edinet_code: codes).group(:edinet_code).maximum(:fiscal_year)
      grouped = Hash.new { |hash, key| hash[key] = [] }
      companies.each_value do |company|
        year = years[company.edinet_code]
        next if year.nil? || company.industry.blank?

        grouped[[ company.industry, year ]] << company
      end

      summaries = {}
      grouped.each do |(industry, year), members|
        rows = attach_market(attach_people(reports_for(year, industry: industry)))
        by_code = rows.index_by { |row| row[:edinet_code] }
        members.each do |company|
          target = by_code[company.edinet_code]
          axes = scored_axes(target, rows)
          summaries[company.edinet_code] = {
            fiscal_year: year,
            level: level_for(axes),
            scores: axes.to_h { |axis| [ axis[:key], axis[:score] ] }
          }
        end
      end
      summaries
    end

    private

    def cohort_rows(company, year)
      reports = if company.industry.blank?
        reports_for(year, edinet_code: company.edinet_code)
      else
        reports_for(year, industry: company.industry)
      end
      attach_market(attach_people(reports))
    end

    def reports_for(year, edinet_code: nil, industry: nil)
      binds = [ year ]
      filter = +"fr.fiscal_year = ?"
      if edinet_code
        filter << " AND fr.edinet_code = ?"
        binds << edinet_code
      else
        filter << " AND c.industry = ?"
        binds << industry
      end

      select_all(<<~SQL, *binds)
        SELECT DISTINCT ON (fr.edinet_code)
               fr.edinet_code, fr.doc_id, fr.fiscal_year,
               fr.sales, fr.operating_profit, fr.net_profit, fr.employee_count,
               fr.shares_outstanding, c.securities_code, c.fiscal_month
          FROM financial_reports fr
          JOIN companies c ON c.edinet_code = fr.edinet_code
         WHERE #{filter}
         ORDER BY fr.edinet_code, fr.submitted_date DESC, fr.doc_id DESC
      SQL
    end

    def attach_people(reports)
      by_doc = people_by_doc(reports.map { |row| row[:doc_id] })
      reports.map do |row|
        people = by_doc[row[:doc_id]] || {}
        row.merge(
          operating_margin: operating_margin(row[:sales], row[:operating_profit]),
          female_manager_ratio: people[:female_manager_ratio],
          male_childcare_leave_ratio: people[:male_childcare_leave_ratio],
          gender_wage_gap: people[:gender_wage_gap],
          average_annual_salary: people[:average_annual_salary],
          average_years_of_service: people[:average_years_of_service],
          average_age: people[:average_age]
        )
      end
    end

    # 期待は時価総額÷売上。終値があればそれを使い、無ければ有報の株価収益率から戻す。
    # 赤字で株価収益率も終値も無い会社は空欄。
    def attach_market(rows)
      prices = month_closes(rows)
      reported = reported_pers(rows)
      rows.map do |row|
        month = row[:fiscal_month].nil? ? nil : row[:fiscal_month].to_i
        price = prices[[ row[:securities_code], row[:fiscal_year], month ]]
        shares = row[:shares_outstanding].nil? ? nil : row[:shares_outstanding].to_i
        net = row[:net_profit]
        per = market_ratio(price, shares, net.nil? || net <= 0 ? nil : net)
        per = reported[row[:doc_id]] if per.nil?
        close_psr = market_ratio(price, shares, row[:sales])
        implied = implied_psr(per, row[:sales], net)
        row.merge(
          psr: close_psr.nil? ? implied : close_psr,
          per: per,
          psr_basis: psr_basis(close_psr, implied)
        )
      end
    end

    def reported_pers(rows)
      doc_ids = rows.map { |row| row[:doc_id] }.compact.uniq
      return {} if doc_ids.empty?

      placeholders = ([ "?" ] * doc_ids.length).join(", ")
      # WHERE は ix_raw_edinet_facts_reported_per の条件と揃える。
      # doc_id だけの索引だと、書類内の当期以外の行まで読む。
      select_all(<<~SQL, *doc_ids).to_h do |row|
        SELECT DISTINCT ON (doc_id) doc_id, raw_value
          FROM raw_edinet_facts
         WHERE doc_id IN (#{placeholders})
           AND relative_year = '当期'
           AND item_name IN ('株価収益率（IFRS）、経営指標等', '株価収益率、経営指標等')
           AND raw_value ~ '^[0-9.]+$'
         ORDER BY doc_id,
                  CASE item_name WHEN '株価収益率（IFRS）、経営指標等' THEN 0 ELSE 1 END
      SQL
        [ row[:doc_id], row[:raw_value].to_f ]
      end
    end

    def month_closes(rows)
      tuples = rows.filter_map do |row|
        month = row[:fiscal_month].nil? ? nil : row[:fiscal_month].to_i
        next if row[:securities_code].blank? || month.nil? || month <= 0

        [ row[:securities_code], row[:fiscal_year], month ]
      end.uniq
      return {} if tuples.empty?

      placeholders = tuples.map { "(?, ?, ?)" }.join(", ")
      select_all(<<~SQL, *tuples.flatten).to_h do |price|
        SELECT securities_code, fiscal_year, month, close_price
          FROM equity_month_closes
         WHERE (securities_code, fiscal_year, month) IN (#{placeholders})
      SQL
        [ [ price[:securities_code], price[:fiscal_year], price[:month].to_i ], price[:close_price].to_f ]
      end
    end

    def implied_psr(per, sales, net_profit)
      return nil if per.nil? || sales.nil? || sales <= 0 || net_profit.nil? || net_profit <= 0

      per.to_f * net_profit / sales
    end

    def psr_basis(close_psr, implied_psr)
      return "close" unless close_psr.nil?
      return "reported_per" unless implied_psr.nil?

      nil
    end

    def market_ratio(price, shares, base)
      return nil if price.nil? || shares.nil? || shares <= 0 || base.nil? || base <= 0

      price.to_f * shares / base
    end

    def people_by_doc(doc_ids)
      return {} if doc_ids.empty?

      placeholders = ([ "?" ] * doc_ids.length).join(", ")
      select_all(<<~SQL, SCOPE, WORKER_TYPE, *doc_ids).index_by { |row| row[:doc_id] }
        SELECT doc_id, female_manager_ratio, male_childcare_leave_ratio, gender_wage_gap,
               average_annual_salary, average_years_of_service, average_age
          FROM human_capital_metrics
         WHERE scope = ?
           AND worker_type = ?
           AND doc_id IN (#{placeholders})
      SQL
    end

    # 売上 0 以下は率にしない。欠測を 0 点にはしない。
    def operating_margin(sales, operating_profit)
      return nil if sales.nil? || operating_profit.nil? || sales <= 0

      operating_profit.to_f / sales
    end

    def build_sheet(company, year, target, rows)
      scoreable = company.industry.present? && year.present? && target.present?
      axes = axes_for(target, rows, scoreable:)
      {
        edinet_code: company.edinet_code,
        company_name: company.company_name,
        industry: company.industry,
        securities_code: company.securities_code.presence,
        fiscal_year: year,
        level: level_for(axes),
        axes: nest_disclosure(axes)
      }
    end

    # 比較しないときは点と peer_count を空にする。値は target から出す。
    def axes_for(target, rows, scoreable:)
      axis_definitions.map { |definition| axis_for(definition, target, rows, scoreable:) }
    end

    def axis_for(definition, target, rows, scoreable:)
      case definition[:key]
      when "disclosure"
        disclosure_axis(definition, target, score: scoreable ? disclosure_score(target) : nil)
      when "expectation"
        expectation_axis(definition, target, rows, scoreable:)
      when "people"
        people_axis(definition, target, rows, scoreable:)
      else
        percentile_axis(definition, target, rows, scoreable:)
      end
    end

    # 開示はランキングの軸でもある。シートでは人的資本の子にする。
    def nest_disclosure(axes)
      disclosure = axes.find { |axis| axis[:key] == "disclosure" }
      axes.filter_map do |axis|
        next if axis[:key] == "disclosure"

        axis[:key] == "people" ? axis.merge(disclosure: disclosure) : axis
      end
    end

    def scored_axes(target, rows)
      axes_for(target, rows, scoreable: target.present?)
    end

    def axis_definitions
      [
        { key: "sales", label: "売上高", nickname: "規模", value_key: :sales },
        { key: "employee_count", label: "従業員数", nickname: "人数", value_key: :employee_count },
        { key: "operating_margin", label: "営業利益率", nickname: "稼ぐ力", value_key: :operating_margin },
        { key: "people", label: "人的資本", nickname: "人", value_key: nil },
        { key: "average_annual_salary", label: "平均年間給与", nickname: "待遇", value_key: :average_annual_salary },
        { key: "average_years_of_service", label: "平均勤続年数", nickname: "定着", value_key: :average_years_of_service },
        { key: "expectation", label: "株価売上高倍率", nickname: "期待", value_key: :psr },
        { key: "disclosure", label: "人の開示", nickname: "開示", value_key: nil }
      ]
    end

    def percentile_axis(definition, target, rows, scoreable:)
      samples = scoreable ? rows.map { |row| row[definition[:value_key]] } : []
      axis_payload(
        definition,
        target,
        score: scoreable ? position_score(target_value(target, definition[:value_key]), samples) : nil,
        peer_count: scoreable ? samples.compact.length : nil
      )
    end

    def expectation_axis(definition, target, rows, scoreable:)
      percentile_axis(definition, target, rows, scoreable:).merge(
        per: target ? target[:per] : nil,
        psr_basis: target ? target[:psr_basis] : nil
      )
    end

    def people_axis(definition, target, rows, scoreable:)
      metrics = PEOPLE_KEYS.map do |key|
        samples = scoreable ? rows.map { |row| row[key.to_sym] } : []
        value = target ? target[key.to_sym] : nil
        {
          key: key,
          value: value,
          score: scoreable ? position_score(value, samples) : nil,
          peer_count: scoreable ? samples.compact.length : 0
        }
      end
      present_scores = metrics.filter_map { |metric| metric[:score] }
      axis_payload(
        definition,
        target,
        score: scoreable ? mean_score(present_scores) : nil,
        peer_count: nil
      ).merge(
        metrics: metrics,
        average_age: target ? target[:average_age] : nil
      )
    end

    def disclosure_axis(definition, target, score:)
      disclosed = disclosed_count(target)
      axis_payload(definition, target, score: score, peer_count: nil).merge(
        value: disclosed,
        disclosed_count: disclosed,
        expected_count: PEOPLE_KEYS.length
      )
    end

    def disclosed_count(target)
      PEOPLE_KEYS.count { |key| target && !target[key.to_sym].nil? }
    end

    def disclosure_score(target)
      (disclosed_count(target) * 100.0 / PEOPLE_KEYS.length).round
    end

    def axis_payload(definition, target, score:, peer_count:)
      value = definition[:value_key] ? target_value(target, definition[:value_key]) : nil
      {
        key: definition[:key],
        label: definition[:label],
        nickname: definition[:nickname],
        score: score,
        value: value,
        peer_count: peer_count
      }
    end

    def target_value(target, key)
      target ? target[key] : nil
    end

    def position_score(value, samples)
      return nil if value.nil?

      peers = samples.compact
      return nil if peers.length < MIN_PEERS

      at_or_below = peers.count { |peer| peer <= value }
      (at_or_below * 100.0 / peers.length).round
    end

    # 空欄の軸は平均に入れない。開示の 0 は空欄ではない。
    def level_for(axes)
      scores = axes.filter_map { |axis| axis[:score] }
      mean_score(scores)
    end

    def mean_score(scores)
      return nil if scores.empty?

      (scores.sum.to_f / scores.length).round
    end
  end
end

# お財布。最新の有報の財務諸表（BS・PL・CF）を、簿記を知らない人向けの内訳と読み解きにする。
# 値は financial_statements（パイプラインが raw_edinet_facts から抽出）。
# 売上が財務諸表から取れない会社（IFRS の独自要素など）は financial_reports.sales に倒す。
class StatementQuery < ApplicationQuery
  AMOUNT_KEYS = %i[
    total_assets current_assets cash_and_deposits trade_receivables inventories
    noncurrent_assets property_plant_equipment intangible_assets goodwill investment_securities
    total_liabilities current_liabilities noncurrent_liabilities interest_bearing_debt
    net_assets retained_earnings net_sales cost_of_sales gross_profit sga_expenses
    operating_income ordinary_income net_income operating_cf investing_cf financing_cf
    report_sales
  ].freeze

  # 持ち物の内訳。重ならない項目だけを並べ、残りは「その他」にする。
  ASSET_PARTS = [
    { key: "cash", value_key: :cash_and_deposits, label: "現金・預金", hint: "すぐに使えるお金" },
    { key: "receivables", value_key: :trade_receivables, label: "まだ受け取っていない代金", hint: "売ったけれど入金待ちのお金（売掛金など）" },
    { key: "inventories", value_key: :inventories, label: "在庫", hint: "売る前の商品・製品・材料" },
    { key: "property", value_key: :property_plant_equipment, label: "建物・機械・土地", hint: "工場や店舗、設備（有形固定資産）" },
    { key: "intangibles", value_key: :intangible_assets, label: "のれん・ソフトなど", hint: "買収した会社の上乗せ分やソフトウエアなど、形のない資産" },
    { key: "investments", value_key: :investment_securities, label: "他社の株など", hint: "取引先や子会社の株、長期の投資" }
  ].freeze

  OTHER_ASSETS = { key: "other", label: "その他", hint: "上のどれにも入らない持ち物" }.freeze

  class << self
    def call(edinet_code)
      company = Company.find_by(edinet_code: edinet_code)
      return nil unless company

      row = latest_statement(company.edinet_code)
      financial = StatementInsights.financial_industry?(company.industry)
      base = {
        edinet_code: company.edinet_code,
        company_name: company.company_name,
        industry: company.industry,
        securities_code: company.securities_code.presence,
        is_financial: financial,
        note: financial ? StatementInsights::FINANCIAL_NOTE : nil
      }
      return base.merge(empty_payload) unless row

      income = income_statement(row)
      balance = balance_sheet(row)
      cash_flow = cash_flow(row)
      ratios = StatementInsights.ratios(row, income)
      base.merge(
        fiscal_year: row[:fiscal_year],
        doc_id: row[:doc_id],
        accounting_standard: row[:accounting_standard],
        basis: row[:basis],
        balance_sheet: balance,
        income_statement: income,
        cash_flow: cash_flow,
        ratios: ratios,
        insights: financial ? [] : StatementInsights.build(row, income, ratios, cash_flow[:pattern])
      )
    end

    private

    def empty_payload
      {
        fiscal_year: nil,
        doc_id: nil,
        accounting_standard: nil,
        basis: nil,
        balance_sheet: nil,
        income_statement: nil,
        cash_flow: nil,
        ratios: nil,
        insights: []
      }
    end

    def latest_statement(edinet_code)
      row = select_one(<<~SQL, edinet_code)
        SELECT fs.*, fr.sales AS report_sales
          FROM financial_statements fs
          JOIN financial_reports fr ON fr.doc_id = fs.doc_id
         WHERE fs.edinet_code = ?
         ORDER BY fs.fiscal_year DESC, fr.submitted_date DESC, fs.doc_id DESC
         LIMIT 1
      SQL
      return nil unless row

      AMOUNT_KEYS.each { |key| row[key] = row[key]&.to_i }
      row[:fiscal_year] = row[:fiscal_year].to_i
      row
    end

    def balance_sheet(row)
      total = row[:total_assets]
      parts = ASSET_PARTS.map do |part|
        amount = row[part[:value_key]] || 0
        { key: part[:key], label: part[:label], hint: part[:hint], amount: amount }
      end
      known = parts.sum { |part| part[:amount] }
      parts << OTHER_ASSETS.merge(amount: [ total - known, 0 ].max)

      {
        total_assets: total,
        assets: with_shares(parts, total),
        funding: with_shares(funding_parts(row), total),
        debt_known: !row[:interest_bearing_debt].nil?
      }
    end

    # 右側。負債を「返す必要のあるお金（借入・社債）」と「その他の負債」に分ける。
    # 借入金が取れない会社（IFRS の独自要素）は、負債をまとめて1つにする。
    def funding_parts(row)
      liabilities = row[:total_liabilities] || [ row[:total_assets] - (row[:net_assets] || 0), 0 ].max
      debt = row[:interest_bearing_debt]
      parts = []
      if debt.nil?
        parts << { key: "liabilities", label: "負債", hint: "いずれ払う・返す必要のあるお金（借入金と支払い待ちのお金）", amount: liabilities }
      else
        parts << { key: "debt", label: "借入金・社債", hint: "利息を払って借りていて、返す必要のあるお金", amount: debt }
        parts << { key: "other_liabilities", label: "その他の負債", hint: "仕入先への支払い待ちや、前受けのお金など", amount: [ liabilities - debt, 0 ].max }
      end
      parts << { key: "net_assets", label: "純資産", hint: "株主が出したお金と、これまで貯めた利益。返さなくてよいお金", amount: row[:net_assets] }
      parts
    end

    def with_shares(parts, total)
      parts.map do |part|
        share = total.nil? || total <= 0 || part[:amount].nil? ? nil : part[:amount].to_f / total
        part.merge(share: share)
      end
    end

    # 売上総利益と原価、販管費は、片方が欠けていれば差し引きで埋める。
    def income_statement(row)
      sales = row[:net_sales] || row[:report_sales]
      cost = row[:cost_of_sales]
      gross = row[:gross_profit]
      gross ||= sales - cost if sales && cost
      cost ||= sales - gross if sales && gross
      operating = row[:operating_income]
      sga = row[:sga_expenses]
      sga ||= gross - operating if gross && operating
      {
        net_sales: sales,
        sales_source: sales_source(row),
        cost_of_sales: cost,
        gross_profit: gross,
        sga_expenses: sga,
        operating_income: operating,
        ordinary_income: row[:ordinary_income],
        net_income: row[:net_income]
      }
    end

    def sales_source(row)
      return "statement" unless row[:net_sales].nil?
      return "summary" unless row[:report_sales].nil?

      nil
    end

    def cash_flow(row)
      operating = row[:operating_cf]
      investing = row[:investing_cf]
      financing = row[:financing_cf]
      {
        operating: operating,
        investing: investing,
        financing: financing,
        pattern: StatementInsights.cash_flow_pattern(operating, investing, financing)
      }
    end
  end
end

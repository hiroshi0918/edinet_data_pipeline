# お財布の読み解き。業種の平均とは比べず、一般的な目安の数値で札を出す。
# 閾値は API_CONTRACT.md の「お財布の目安」と揃える。
module StatementInsights
  # 自己資本比率（純資産 ÷ 総資産）
  EQUITY_RATIO_STABLE = 0.5
  EQUITY_RATIO_LEVERAGED = 0.2
  # 現金 ÷ 総資産、または現金が月の売上の何か月分か
  CASH_SHARE_RICH = 0.3
  CASH_MONTHS_RICH = 3.0
  # 持ち物の形（総資産に占める割合）
  PROPERTY_SHARE_HEAVY = 0.4
  INTANGIBLE_SHARE_HEAVY = 0.2
  INVESTMENT_SHARE_HEAVY = 0.25
  INVENTORY_SHARE_HEAVY = 0.2
  # 粗利率（売上総利益 ÷ 売上）
  GROSS_MARGIN_HIGH = 0.5
  GROSS_MARGIN_LOW = 0.15

  # 預金や保険料を預かる業種は、負債の大半が預かり金で、目安が当てはまらない。
  FINANCIAL_INDUSTRIES = [ "銀行業", "保険業", "証券、商品先物取引業", "その他金融業" ].freeze
  FINANCIAL_NOTE = "銀行・保険・証券などは、預金や保険料として預かったお金が負債の大半を占めます。" \
                   "ほかの業種と同じ目安では読めないので、読み解きの札は出していません。".freeze

  # 営業・投資・財務 CF の符号（0 以上を「入り」）の組み合わせ。
  CASH_FLOW_PATTERNS = {
    [ :in, :out, :out ] => {
      key: "steady", tone: "good", label: "本業で稼ぎ、投資と返済に回す",
      text: "本業で稼いだお金で、設備などへの投資と、借入金の返済や配当をまかなっています。"
    },
    [ :in, :out, :in ] => {
      key: "expanding", tone: "neutral", label: "借りてでも投資する",
      text: "本業で稼いだうえに、借入れや増資でもお金を集め、投資に回しています。"
    },
    [ :in, :in, :out ] => {
      key: "restructuring", tone: "neutral", label: "持ち物を売って返済に回す",
      text: "本業で稼いだお金と、持ち物を売ったお金で、借入金の返済や配当をしています。"
    },
    [ :in, :in, :in ] => {
      key: "cash_pile", tone: "neutral", label: "お金を集めている",
      text: "本業・持ち物の売却・借入れのすべてでお金が入り、手元のお金を増やしています。"
    },
    [ :out, :out, :in ] => {
      key: "funding_gap", tone: "caution", label: "借入れや増資で資金をつないでいる",
      text: "本業ではお金が出ていっており、借入れや増資で手元のお金を補っています。"
    },
    [ :out, :in, :in ] => {
      key: "funding_gap", tone: "caution", label: "借入れや増資で資金をつないでいる",
      text: "本業ではお金が出ていっており、持ち物の売却や借入れ・増資で手元のお金を補っています。"
    },
    [ :out, :in, :out ] => {
      key: "shrinking", tone: "caution", label: "持ち物を売って支払いにあてる",
      text: "本業ではお金が出ていっており、持ち物を売ったお金で返済などをしています。"
    },
    [ :out, :out, :out ] => {
      key: "draining", tone: "caution", label: "手元のお金を取り崩している",
      text: "本業・投資・返済のすべてでお金が出ていき、貯めていたお金で払っています。"
    }
  }.freeze

  class << self
    def financial_industry?(industry)
      FINANCIAL_INDUSTRIES.include?(industry)
    end

    def ratios(row, income)
      total = row[:total_assets]
      sales = income[:net_sales]
      cash = row[:cash_and_deposits]
      {
        equity_ratio: share(row[:net_assets], total),
        cash_share: share(cash, total),
        cash_months: cash.nil? || sales.nil? || sales <= 0 ? nil : cash.to_f / (sales / 12.0),
        property_share: share(row[:property_plant_equipment], total),
        intangible_share: share(row[:intangible_assets], total),
        investment_share: share(row[:investment_securities], total),
        inventory_share: share(row[:inventories], total),
        gross_margin: margin(income[:gross_profit], sales),
        operating_margin: margin(income[:operating_income], sales)
      }
    end

    def cash_flow_pattern(operating, investing, financing)
      return nil if [ operating, investing, financing ].any?(&:nil?)

      signs = [ operating, investing, financing ].map { |value| value >= 0 ? :in : :out }
      CASH_FLOW_PATTERNS.fetch(signs)
    end

    # 札の並びは、安全性 → 現金 → 持ち物の形 → 稼ぎ方 → お金の流れ。
    def build(row, income, ratios, pattern)
      [
        safety_insight(row, ratios),
        cash_rich_insight(ratios),
        net_cash_insight(row),
        share_insight(ratios[:property_share], PROPERTY_SHARE_HEAVY, "asset_heavy", "工場・店舗など設備で稼ぐ",
                      "持ち物の%{pct}%%が、建物・機械・土地などの設備です。"),
        share_insight(ratios[:intangible_share], INTANGIBLE_SHARE_HEAVY, "acquisitive", "買収やソフトで大きくなった",
                      "持ち物の%{pct}%%が、のれん（買収した会社の上乗せ分）やソフトウエアなど形のない資産です。"),
        share_insight(ratios[:investment_share], INVESTMENT_SHARE_HEAVY, "investor", "他社の株を多く持つ",
                      "持ち物の%{pct}%%が、他社の株などへの投資です。"),
        share_insight(ratios[:inventory_share], INVENTORY_SHARE_HEAVY, "inventory", "在庫を抱える商売",
                      "持ち物の%{pct}%%が、売る前の商品や材料（在庫）です。"),
        margin_insight(ratios[:gross_margin]),
        loss_insight(income[:net_income]),
        pattern && pattern.merge(key: "cash_flow_#{pattern[:key]}")
      ].compact
    end

    private

    def share(part, total)
      return nil if part.nil? || total.nil? || total <= 0

      part.to_f / total
    end

    def margin(profit, sales)
      return nil if profit.nil? || sales.nil? || sales <= 0

      profit.to_f / sales
    end

    def pct(value)
      (value * 100).round
    end

    def insight(key, tone, label, text)
      { key: key, tone: tone, label: label, text: text }
    end

    def safety_insight(row, ratios)
      net_assets = row[:net_assets]
      equity = ratios[:equity_ratio]
      return nil if net_assets.nil? || equity.nil?

      if net_assets.negative?
        insight("insolvent", "caution", "債務超過",
                "負債が持ち物の合計を上回っています。持ち物をすべて売っても、払う・返すお金に足りない状態です。")
      elsif equity >= EQUITY_RATIO_STABLE
        insight("stable", "good", "借金が少なく安定",
                "持ち物の#{pct(equity)}%を、返さなくてよいお金（株主のお金と貯めた利益）でまかなっています。")
      elsif equity < EQUITY_RATIO_LEVERAGED
        insight("leveraged", "caution", "借金で大きく動かす",
                "持ち物のうち、返さなくてよいお金でまかなえているのは#{pct(equity)}%だけです。残りは借入れや支払い待ちのお金です。")
      end
    end

    def cash_rich_insight(ratios)
      cash_share = ratios[:cash_share]
      months = ratios[:cash_months]
      share_hit = !cash_share.nil? && cash_share >= CASH_SHARE_RICH
      months_hit = !months.nil? && months >= CASH_MONTHS_RICH
      return nil unless share_hit || months_hit

      parts = []
      parts << "持ち物の#{pct(cash_share)}%が現金・預金です" unless cash_share.nil?
      parts << "売上の約#{months.round(1)}か月分にあたります" unless months.nil?
      insight("cash_rich", "neutral", "現金をたっぷり持っている", "#{parts.join('。')}。")
    end

    # 借入金が取れない会社（IFRS の独自要素）は判定しない。
    def net_cash_insight(row)
      debt = row[:interest_bearing_debt]
      cash = row[:cash_and_deposits]
      return nil if debt.nil? || cash.nil? || cash <= debt

      text = if debt.zero?
        "借入金や社債がありません。"
      else
        "現金・預金が、借入金・社債の#{(cash.to_f / debt).round(1)}倍あります。すぐに全部返しても現金が残ります。"
      end
      insight("net_cash", "good", "実質無借金", text)
    end

    def share_insight(value, threshold, key, label, template)
      return nil if value.nil? || value < threshold

      insight(key, "neutral", label, format(template, pct: pct(value)))
    end

    def margin_insight(gross_margin)
      return nil if gross_margin.nil?

      if gross_margin >= GROSS_MARGIN_HIGH
        insight("high_margin", "good", "付加価値の高い商売",
                "売上の#{pct(gross_margin)}%が、原価を引いた粗利として残ります。")
      elsif gross_margin <= GROSS_MARGIN_LOW
        insight("low_margin", "neutral", "薄利多売・卸売型",
                "売上のうち、原価を引いて粗利として残るのは#{pct(gross_margin)}%です。")
      end
    end

    def loss_insight(net_income)
      return nil if net_income.nil? || !net_income.negative?

      insight("net_loss", "caution", "赤字の年", "この年度は、最終的な利益（純利益）が赤字でした。")
    end
  end
end

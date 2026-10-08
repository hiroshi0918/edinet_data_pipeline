# 日経平均の構成銘柄一覧。点は会社シートと同じ総合レベル。
class Nikkei225Query
  def self.call(catalog: Nikkei225Catalog.load)
    constituents = catalog.fetch("constituents")
    codes = constituents.map { |row| row.fetch("edinet_code") }
    companies = Company.where(edinet_code: codes).index_by(&:edinet_code)
    summaries = SheetQuery.summaries_for(companies.keys)

    rows = constituents.map do |row|
      company = companies[row.fetch("edinet_code")]
      summary = summaries[row.fetch("edinet_code")] || {}
      {
        securities_code: row.fetch("securities_code"),
        short_name: row.fetch("short_name"),
        listed_name: row.fetch("listed_name"),
        nikkei_sector: row.fetch("nikkei_sector"),
        edinet_code: company&.edinet_code,
        company_name: company&.company_name || row.fetch("listed_name"),
        industry: company&.industry,
        fiscal_year: summary[:fiscal_year],
        level: summary[:level],
        has_sheet: company.present?
      }
    end

    {
      as_of: catalog.fetch("as_of"),
      source_note: catalog.fetch("source_note"),
      companies: rows.sort_by { |row| [ row[:level].nil? ? 1 : 0, -(row[:level] || 0), row[:securities_code] ] }
    }
  end
end

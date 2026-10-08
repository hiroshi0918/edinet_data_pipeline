# 図鑑のランキング。総合も各軸も、会社シートと同じ点を使う。
class RankingsQuery
  def self.call(industry: nil, axis: nil)
    selected_axis = axis.presence || "level"
    catalog = SheetQuery.axis_catalog
    unless catalog.any? { |item| item[:key] == selected_axis }
      raise InvalidParameter, "Invalid axis: #{selected_axis}"
    end

    companies = Company.order(:edinet_code).to_a
    industries = companies.filter_map(&:industry).uniq.sort
    selected = industry.present? ? companies.select { |company| company.industry == industry } : companies
    summaries = SheetQuery.summaries_for(selected.map(&:edinet_code))
    rows = selected.map do |company|
      summary = summaries[company.edinet_code] || {}
      score = selected_axis == "level" ? summary[:level] : summary.dig(:scores, selected_axis)
      {
        edinet_code: company.edinet_code,
        company_name: company.company_name,
        industry: company.industry,
        fiscal_year: summary[:fiscal_year],
        level: summary[:level],
        score: score
      }
    end

    {
      axis: selected_axis,
      industry: industry.presence,
      industries: industries,
      axes: catalog,
      companies: rows.sort_by { |row| [ row[:score].nil? ? 1 : 0, -(row[:score] || 0), row[:edinet_code] ] }
    }
  end
end

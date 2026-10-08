# 歩みの書き直し。GET /story からは呼ばない。
namespace :story do
  desc "最新有報の歩みを書き直して保存する。引数は EDINET コード"
  task :rewrite, [ :edinet_code ] => :environment do |_task, args|
    code = args[:edinet_code].to_s
    abort "EDINET コードを渡してください: bin/rails 'story:rewrite[E02144]'" if code.empty?

    company = Company.find_by(edinet_code: code)
    abort "会社が見つかりません: #{code}" unless company

    report = FinancialReport.where(edinet_code: code)
      .order(fiscal_year: :desc, submitted_date: :desc, doc_id: :desc)
      .first
    abort "有報がありません: #{code}" unless report

    StoryNarrative.rewrite_document(report.doc_id)
    puts "#{code} #{report.doc_id} を保存しました"
  end
end

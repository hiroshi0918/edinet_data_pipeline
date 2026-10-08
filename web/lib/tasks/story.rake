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

  batch_client = lambda do
    key = StoryRewriter.api_key
    abort "CLAUDE_API_KEY がありません" if key.empty?

    Anthropic::Client.new(api_key: key)
  end

  collect_batch = lambda do |client, batch_id|
    StoryBatch.wait(client, batch_id) do |batch|
      counts = batch.request_counts
      puts "#{batch_id} #{batch.processing_status} 処理中#{counts.processing} 成功#{counts.succeeded} 失敗#{counts.errored + counts.expired + counts.canceled}"
    end
    result = StoryBatch.collect(client, batch_id)
    puts "#{batch_id} #{result[:saved]}件を保存しました"
    puts "#{batch_id} 保存できなかった有報: #{result[:failed].join(' ')}" if result[:failed].any?
  end

  desc "全社の最新有報の歩みを Message Batches でまとめて書き直して保存する"
  task rewrite_all: :environment do
    client = batch_client.call
    doc_ids = StoryBatch.latest_doc_ids
    puts "#{doc_ids.size}社の有報を送ります"

    batch_ids = StoryBatch.submit(client, doc_ids) do |batch, size|
      puts "#{batch.id} を送りました（#{size}件）"
    end
    batch_ids.each { |batch_id| collect_batch.call(client, batch_id) }
  end

  desc "送ったバッチの結果を待って保存する。引数はバッチ ID"
  task :collect, [ :batch_id ] => :environment do |_task, args|
    batch_id = args[:batch_id].to_s
    abort "バッチ ID を渡してください: bin/rails 'story:collect[msgbatch_...]'" if batch_id.empty?

    collect_batch.call(batch_client.call, batch_id)
  end
end

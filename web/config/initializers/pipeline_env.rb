# 親パイプラインの .env から、未設定の CLAUDE_API_KEY だけを取り込む。
# テストはリポジトリの鍵を読まない。
module PipelineEnv
  PATH = Rails.root.join("../.env")
  KEY = "CLAUDE_API_KEY"

  def self.load
    return if Rails.env.test?
    return if ENV[KEY].present?
    return unless PATH.file?

    PATH.each_line do |line|
      stripped = line.strip
      next if stripped.empty? || stripped.start_with?("#") || !stripped.include?("=")

      name, value = stripped.split("=", 2)
      next unless name == KEY

      ENV[KEY] = unquote(value.strip)
      break
    end
  end

  def self.unquote(value)
    quote = value[0]
    return value[1..-2] if (quote == "\"" || quote == "'") && value.end_with?(quote)

    value
  end
end

PipelineEnv.load

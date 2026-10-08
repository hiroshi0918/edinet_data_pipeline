# 日経225の構成銘柄スナップショット。data/nikkei225.json が正本。
class Nikkei225Catalog
  PATH = Rails.root.join("data/nikkei225.json")

  def self.load
    JSON.parse(PATH.read)
  end
end

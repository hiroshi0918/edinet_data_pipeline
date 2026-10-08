# 本番で React の index.html を返す。development では Vite が HTML を出す。
class SpaController < ApplicationController
  def index
    index_path = Rails.root.join("frontend/dist/index.html")
    if index_path.exist?
      send_file index_path, type: "text/html; charset=utf-8", disposition: "inline"
    else
      render plain: "frontend/dist がありません。web/frontend で npm run build してください。",
             status: :not_found
    end
  end
end


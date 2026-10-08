module Api
  module V1
    # 日経225の構成銘柄と、図鑑にある会社の総合点。
    class Nikkei225Controller < BaseController
      def index
        render json: Nikkei225Query.call
      end
    end
  end
end

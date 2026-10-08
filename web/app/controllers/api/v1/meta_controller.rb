module Api
  module V1
    # 収録範囲の KPI とフィルタ用の年度一覧。
    class MetaController < BaseController
      def show
        render json: MetaQuery.call
      end
    end
  end
end

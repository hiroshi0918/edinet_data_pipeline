module Api
  module V1
    class IndustriesController < BaseController
      # 業種別箱ひげ用の企業生値。
      def hc_distribution
        render json: HcDistributionQuery.call(
          metric: params[:metric].presence || "female_manager_ratio",
          year: resolved_year,
          scope: scope_param,
          worker_type: worker_type_param
        )
      end
    end
  end
end

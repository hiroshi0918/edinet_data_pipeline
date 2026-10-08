module Api
  module V1
    class RankingsController < BaseController
      def index
        render json: RankingsQuery.call(industry: params[:industry], axis: params[:axis])
      end

      # GET /rankings/human_capital
      def human_capital
        render json: HumanCapitalRankingQuery.call(
          metric: params[:metric].presence || "female_manager_ratio",
          year: resolved_year,
          scope: scope_param,
          worker_type: worker_type_param
        )
      end

      # GET /rankings/size
      def size
        render json: SizeRankingQuery.call(
          axis: params[:axis].presence || "sales",
          year: resolved_year,
          scope: scope_param,
          worker_type: worker_type_param
        )
      end
    end
  end
end

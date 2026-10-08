module Api
  module V1
    # 企業一覧・1 社プロファイル・スポットライト（1 レスポンスに peer 一式）。
    class CompaniesController < BaseController
      def index
        render json: {
          companies: CompaniesQuery.index(q: params[:q], limit: limit_param)
        }
      end

      def show
        company = CompaniesQuery.show(params[:code])
        return render_not_found("Company not found") unless company

        render json: company
      end

      def sheet
        sheet = SheetQuery.call(params[:code])
        return render_not_found("Company not found") unless sheet

        render json: sheet
      end

      def story
        story = StoryQuery.call(params[:code])
        return render_not_found("Company not found") unless story

        render json: story
      end

      # scope=auto（または auto=1）は SpotlightQuery が評価次元を決める。
      def spotlight
        company = Company.find_by(edinet_code: params[:code])
        return render_not_found("Company not found") unless company

        render json: SpotlightQuery.call(
          company: company,
          year: resolved_year,
          scope: auto_scope_requested? ? "auto" : scope_param,
          worker_type: worker_type_param
        )
      end

      private

      def limit_param
        return nil if params[:limit].blank?

        value = Integer(params[:limit])
        raise InvalidParameter, "Invalid limit: #{params[:limit]}" if value <= 0

        value
      rescue ArgumentError, TypeError
        raise InvalidParameter, "Invalid limit: #{params[:limit]}"
      end
    end
  end
end

module Api
  module V1
    # API 共通。不正パラメータは 400、年未指定は企業数最多年度に落とす。
    class BaseController < ActionController::API
      rescue_from InvalidParameter, with: :render_bad_request

      private

      def render_bad_request(error)
        render json: { error: error.message }, status: :bad_request
      end

      def render_not_found(message = "Not found")
        render json: { error: message }, status: :not_found
      end

      def year_param
        return nil if params[:year].blank?

        Integer(params[:year])
      rescue ArgumentError, TypeError
        raise InvalidParameter, "Invalid year: #{params[:year]}"
      end

      def resolved_year
        year_param || MetaQuery.default_year
      end

      def worker_type_param
        Dimension.validate_worker_type!(params[:worker_type].presence || Dimension::DEFAULT_WORKER_TYPE)
      end

      def scope_param
        Dimension.validate_scope!(params[:scope].presence || Dimension::DEFAULT_SCOPE)
      end

      def auto_scope_requested?
        params[:scope].to_s == "auto" ||
          (params[:scope].blank? && ActiveModel::Type::Boolean.new.cast(params[:auto]))
      end
    end
  end
end

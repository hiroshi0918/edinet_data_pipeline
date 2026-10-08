Rails.application.routes.draw do
  get "up" => "rails/health#show", as: :rails_health_check

  # ダッシュボード JSON。詳細は API_CONTRACT.md。
  namespace :api, defaults: { format: :json } do
    namespace :v1 do
      get "meta", to: "meta#show"
      resources :companies, only: [ :index, :show ], param: :code do
        get :spotlight, on: :member
        get :sheet, on: :member
        get :story, on: :member
      end
      get "industries", to: "industries#index"
      get "industries/hc_distribution", to: "industries#hc_distribution"
      get "rankings", to: "rankings#index"
      get "rankings/human_capital", to: "rankings#human_capital"
      get "rankings/size", to: "rankings#size"
      get "nikkei225", to: "nikkei225#index"
    end
  end

  # 本番では /api 以外の HTML を SPA に渡す。development は Vite :5173 を使う。
  unless Rails.env.development?
    get "*path", to: "spa#index", constraints: ->(req) {
      req.format.html? && !req.path.start_with?("/api", "/up", "/rails")
    }
    root "spa#index"
  end
end

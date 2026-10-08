# This file is copied to spec/ when you run 'rails generate rspec:install'
require "spec_helper"
ENV["RAILS_ENV"] ||= "test"
require_relative "../config/environment"
abort("The Rails environment is running in production mode!") if Rails.env.production?

require "rspec/rails"

Rails.root.glob("spec/support/**/*.rb").sort.each { |f| require f }

db_name = ActiveRecord::Base.connection_db_config.database
if db_name == "edinet_db"
  abort "Refusing to run specs against development database edinet_db"
end

RSpec.configure do |config|
  config.include FactoryBot::Syntax::Methods
  config.include DashboardHelpers

  config.use_transactional_fixtures = true
  config.infer_spec_type_from_file_location!
  config.filter_rails_from_backtrace!

  # ビューは残し、実テーブルだけをテストごとに空にする。
  config.before(:each) do
    ActiveRecord::Base.connection.execute(
      "TRUNCATE TABLE human_capital_metrics, financial_reports, companies RESTART IDENTITY CASCADE"
    )
  end
end

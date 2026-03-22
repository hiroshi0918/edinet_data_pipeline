-- 1. companies テーブル
CREATE TABLE IF NOT EXISTS companies (
    edinet_code VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. financial_reports テーブル
CREATE TABLE IF NOT EXISTS financial_reports (
    doc_id VARCHAR(50) PRIMARY KEY,
    edinet_code VARCHAR(10) REFERENCES companies(edinet_code),
    fiscal_year INTEGER NOT NULL,
    csv_available BOOLEAN NOT NULL DEFAULT TRUE,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    sales BIGINT,
    operating_profit BIGINT,
    net_profit BIGINT,
    employee_count INTEGER,
    submitted_date DATE NOT NULL
);

-- 3. human_capital_metrics テーブル
CREATE TABLE IF NOT EXISTS human_capital_metrics (
    id SERIAL PRIMARY KEY,
    edinet_code VARCHAR(10) REFERENCES companies(edinet_code),
    fiscal_year INTEGER NOT NULL,
    female_manager_ratio NUMERIC(5, 2),        -- Percentage, e.g., 25.50
    male_childcare_leave_ratio NUMERIC(5, 2),  -- Percentage, e.g., 100.00
    gender_wage_gap NUMERIC(5, 2),             -- Percentage, e.g., 75.50
    engagement_score NUMERIC(5, 2),            -- Optional external score
    source_name VARCHAR(100) NOT NULL          -- e.g., 'EDINET', 'OpenWork'
);

"""company_lookup ビューの表組みロジック (_build_history_frame) のユニットテスト.

Streamlit の描画関数は呼ばず、純関数部分だけを検証する。
"""

from __future__ import annotations

import pandas as pd

from edinet_pipeline.dashboard.views.company_lookup import _build_history_frame


def _profile_df() -> pd.DataFrame:
    """query_company_profile の戻り値を模した2年度×2次元のプロファイル."""
    columns = [
        "fiscal_year", "scope", "worker_type", "doc_id", "submitted_date",
        "sales", "operating_profit", "net_profit", "employee_count",
        "female_manager_ratio", "male_childcare_leave_ratio", "gender_wage_gap",
        "average_annual_salary", "average_years_of_service", "average_age",
        "industry", "company_name",
    ]
    rows = [
        # 2024 提出会社×全労働者 (従業員情報あり)
        (2024, "reporting_company", "all", "D001", "2024-06-25",
         12_000_000_000, 1_500_000_000, 900_000_000, 500,
         15.5, 30.0, 75.0, 6_500_000, 12.3, 42.1, "電気機器", "Company A"),
        # 2024 連結子会社×全労働者 (従業員情報は None)
        (2024, "consolidated_subsidiary", "all", "D001", "2024-06-25",
         12_000_000_000, 1_500_000_000, 900_000_000, 500,
         22.0, None, 70.0, None, None, None, "電気機器", "Company A"),
        # 2023 提出会社×全労働者 (HC 欠損)
        (2023, "reporting_company", "all", "D000", "2023-06-25",
         10_000_000_000, 1_200_000_000, 700_000_000, 480,
         None, None, None, 6_300_000, 11.8, 41.5, "電気機器", "Company A"),
    ]
    return pd.DataFrame(rows, columns=columns)


class TestBuildHistoryFrame:
    def test_years_become_columns_in_descending_order(self):
        frame = _build_history_frame(_profile_df(), "reporting_company", "all")
        assert list(frame.columns) == ["2024年度", "2023年度"]
        assert frame.index.name == "指標"

    def test_formats_values_with_units(self):
        frame = _build_history_frame(_profile_df(), "reporting_company", "all")
        assert frame.at["売上高 (億円)", "2024年度"] == "120.0"
        assert frame.at["従業員数 (人)", "2024年度"] == "500"
        assert frame.at["女性管理職比率 (%)", "2024年度"] == "15.5"
        assert frame.at["平均年間給与 (万円)", "2024年度"] == "650"
        assert frame.at["平均勤続年数 (年)", "2023年度"] == "11.8"

    def test_missing_values_render_as_dash(self):
        frame = _build_history_frame(_profile_df(), "reporting_company", "all")
        assert frame.at["女性管理職比率 (%)", "2023年度"] == "—"

    def test_employee_info_stays_on_reporting_company_for_other_dims(self):
        """連結子会社次元でも従業員情報は提出会社単体の値が入ること."""
        frame = _build_history_frame(_profile_df(), "consolidated_subsidiary", "all")
        # HC は連結子会社の値
        assert frame.at["女性管理職比率 (%)", "2024年度"] == "22.0"
        # 従業員情報は提出会社単体の行から補完される
        assert frame.at["平均年間給与 (万円)", "2024年度"] == "650"
        # 連結子会社の行が無い 2023 年度の HC は欠損表示
        assert frame.at["女性管理職比率 (%)", "2023年度"] == "—"

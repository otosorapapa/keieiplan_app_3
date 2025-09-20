"""Input hub for sales, costs, investments, borrowings and tax policy."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

import pandas as pd
import streamlit as st

from formatting import UNIT_FACTORS, format_amount_with_unit, format_ratio
from models import (
    DEFAULT_CAPEX_PLAN,
    DEFAULT_COST_PLAN,
    DEFAULT_LOAN_SCHEDULE,
    DEFAULT_SALES_PLAN,
    DEFAULT_TAX_POLICY,
    MONTH_SEQUENCE,
)
from state import ensure_session_defaults
from theme import inject_theme
from validators import ValidationIssue, validate_bundle

st.set_page_config(
    page_title="経営計画スタジオ｜Inputs",
    page_icon="🧾",
    layout="wide",
)

inject_theme()
ensure_session_defaults()

finance_raw: Dict[str, Dict] = st.session_state.get("finance_raw", {})
if not finance_raw:
    finance_raw = {
        "sales": DEFAULT_SALES_PLAN.model_dump(),
        "costs": DEFAULT_COST_PLAN.model_dump(),
        "capex": DEFAULT_CAPEX_PLAN.model_dump(),
        "loans": DEFAULT_LOAN_SCHEDULE.model_dump(),
        "tax": DEFAULT_TAX_POLICY.model_dump(),
    }
    st.session_state["finance_raw"] = finance_raw

validation_errors: List[ValidationIssue] = st.session_state.get("finance_validation_errors", [])


def _sales_dataframe(data: Dict) -> pd.DataFrame:
    rows: List[Dict[str, float | str]] = []
    for item in data.get("items", []):
        row: Dict[str, float | str] = {
            "チャネル": item.get("channel", ""),
            "商品": item.get("product", ""),
        }
        monthly = item.get("monthly", {})
        amounts = monthly.get("amounts") if isinstance(monthly, dict) else None
        for idx, month in enumerate(MONTH_SEQUENCE, start=0):
            key = f"月{month:02d}"
            if isinstance(amounts, list):
                value = Decimal(str(amounts[idx])) if idx < len(amounts) else Decimal("0")
            elif isinstance(amounts, dict):
                value = Decimal(str(amounts.get(month, 0)))
            else:
                value = Decimal("0")
            row[key] = float(value)
        rows.append(row)
    if not rows:
        rows.append({"チャネル": "オンライン", "商品": "主力製品", **{f"月{m:02d}": 0.0 for m in MONTH_SEQUENCE}})
    df = pd.DataFrame(rows)
    return df


def _capex_dataframe(data: Dict) -> pd.DataFrame:
    items = data.get("items", [])
    if not items:
        return pd.DataFrame(
            [{"投資名": "新工場設備", "金額": 0.0, "開始月": 1, "耐用年数": 5}]
        )
    rows = []
    for item in items:
        rows.append(
            {
                "投資名": item.get("name", ""),
                "金額": float(Decimal(str(item.get("amount", 0)))),
                "開始月": int(item.get("start_month", 1)),
                "耐用年数": int(item.get("useful_life_years", 5)),
            }
        )
    return pd.DataFrame(rows)


def _loan_dataframe(data: Dict) -> pd.DataFrame:
    loans = data.get("loans", [])
    if not loans:
        return pd.DataFrame(
            [
                {
                    "名称": "メインバンク借入",
                    "元本": 0.0,
                    "金利": 0.01,
                    "返済期間(月)": 60,
                    "開始月": 1,
                    "返済タイプ": "equal_principal",
                }
            ]
        )
    rows = []
    for loan in loans:
        rows.append(
            {
                "名称": loan.get("name", ""),
                "元本": float(Decimal(str(loan.get("principal", 0)))),
                "金利": float(Decimal(str(loan.get("interest_rate", 0)))),
                "返済期間(月)": int(loan.get("term_months", 12)),
                "開始月": int(loan.get("start_month", 1)),
                "返済タイプ": loan.get("repayment_type", "equal_principal"),
            }
        )
    return pd.DataFrame(rows)


sales_df = _sales_dataframe(finance_raw.get("sales", {}))
capex_df = _capex_dataframe(finance_raw.get("capex", {}))
loan_df = _loan_dataframe(finance_raw.get("loans", {}))

costs_defaults = finance_raw.get("costs", {})
variable_ratios = costs_defaults.get("variable_ratios", {})
fixed_costs = costs_defaults.get("fixed_costs", {})
noi_defaults = costs_defaults.get("non_operating_income", {})
noe_defaults = costs_defaults.get("non_operating_expenses", {})

settings_state: Dict[str, object] = st.session_state.get("finance_settings", {})
unit = str(settings_state.get("unit", "百万円"))
unit_factor = UNIT_FACTORS.get(unit, Decimal("1"))

st.title("🧾 データ入力ハブ")
st.caption("売上からコスト、投資、借入、税制までを一箇所で整理します。保存すると全ページに反映されます。")

sales_tab, cost_tab, invest_tab, tax_tab = st.tabs(
    ["売上計画", "コスト計画", "投資・借入", "税制・メモ"]
)

with sales_tab:
    st.subheader("売上計画：チャネル×商品×月")
    st.caption("各行はチャネル×商品を表し、12ヶ月の売上高を入力します。単位は円ベースで扱われ、表示単位で丸められます。")
    sales_df = st.data_editor(
        sales_df,
        num_rows="dynamic",
        use_container_width=True,
        key="sales_editor",
    )
    if any(err.field.startswith("sales") for err in validation_errors):
        messages = "<br/>".join(err.message for err in validation_errors if err.field.startswith("sales"))
        st.markdown(f"<div class='field-error'>{messages}</div>", unsafe_allow_html=True)

with cost_tab:
    st.subheader("コスト計画：変動費と固定費")
    var_cols = st.columns(5)
    var_codes = ["COGS_MAT", "COGS_LBR", "COGS_OUT_SRC", "COGS_OUT_CON", "COGS_OTH"]
    var_labels = ["材料費", "外部労務費", "外注費(専属)", "外注費(委託)", "その他原価"]
    variable_inputs: Dict[str, float] = {}
    for col, code, label in zip(var_cols, var_codes, var_labels):
        with col:
            variable_inputs[code] = st.number_input(
                f"{label} 原価率",
                min_value=0.0,
                max_value=1.0,
                step=0.005,
                value=float(variable_ratios.get(code, 0.0)),
                format="%.3f",
            )
    st.caption("変動費は売上高に対する比率で入力します。0〜1の範囲で設定してください。")

    fixed_cols = st.columns(3)
    fixed_codes = ["OPEX_H", "OPEX_K", "OPEX_DEP"]
    fixed_labels = ["人件費", "経費", "減価償却"]
    fixed_inputs: Dict[str, float] = {}
    for col, code, label in zip(fixed_cols, fixed_codes, fixed_labels):
        with col:
            base_value = Decimal(str(fixed_costs.get(code, 0.0)))
            fixed_inputs[code] = st.number_input(
                f"{label} ({unit})",
                min_value=0.0,
                step=1.0,
                value=float(base_value / unit_factor),
                format="%.0f",
            )
    st.caption("固定費は入力した単位で保存されます。")

    st.markdown("#### 営業外収益 / 営業外費用")
    noi_cols = st.columns(3)
    noi_codes = ["NOI_MISC", "NOI_GRANT", "NOI_OTH"]
    noi_labels = ["雑収入", "補助金", "その他"]
    noi_inputs: Dict[str, float] = {}
    for col, code, label in zip(noi_cols, noi_codes, noi_labels):
        with col:
            base_value = Decimal(str(noi_defaults.get(code, 0.0)))
            noi_inputs[code] = st.number_input(
                f"{label} ({unit})",
                min_value=0.0,
                step=1.0,
                value=float(base_value / unit_factor),
            )

    noe_cols = st.columns(2)
    noe_codes = ["NOE_INT", "NOE_OTH"]
    noe_labels = ["支払利息", "その他費用"]
    noe_inputs: Dict[str, float] = {}
    for col, code, label in zip(noe_cols, noe_codes, noe_labels):
        with col:
            base_value = Decimal(str(noe_defaults.get(code, 0.0)))
            noe_inputs[code] = st.number_input(
                f"{label} ({unit})",
                min_value=0.0,
                step=1.0,
                value=float(base_value / unit_factor),
            )

    if any(err.field.startswith("costs") for err in validation_errors):
        messages = "<br/>".join(err.message for err in validation_errors if err.field.startswith("costs"))
        st.markdown(f"<div class='field-error'>{messages}</div>", unsafe_allow_html=True)

with invest_tab:
    st.subheader("投資・借入計画")
    st.markdown("#### 設備投資 (Capex)")
    capex_df = st.data_editor(
        capex_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "金額": st.column_config.NumberColumn("金額 (円)", min_value=0.0, step=1_000_000.0, format="%.0f"),
            "開始月": st.column_config.NumberColumn("開始月", min_value=1, max_value=12, step=1),
            "耐用年数": st.column_config.NumberColumn("耐用年数 (年)", min_value=1, max_value=20, step=1),
        },
        key="capex_editor",
    )

    st.markdown("#### 借入スケジュール")
    loan_df = st.data_editor(
        loan_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "元本": st.column_config.NumberColumn("元本 (円)", min_value=0.0, step=1_000_000.0, format="%.0f"),
            "金利": st.column_config.NumberColumn("金利", min_value=0.0, max_value=0.2, step=0.001, format="%.3f"),
            "返済期間(月)": st.column_config.NumberColumn("返済期間 (月)", min_value=1, max_value=600, step=1),
            "開始月": st.column_config.NumberColumn("開始月", min_value=1, max_value=12, step=1),
            "返済タイプ": st.column_config.SelectboxColumn("返済タイプ", options=["equal_principal", "interest_only"]),
        },
        key="loan_editor",
    )

    if any(err.field.startswith("capex") for err in validation_errors):
        messages = "<br/>".join(err.message for err in validation_errors if err.field.startswith("capex"))
        st.markdown(f"<div class='field-error'>{messages}</div>", unsafe_allow_html=True)
    if any(err.field.startswith("loans") for err in validation_errors):
        messages = "<br/>".join(err.message for err in validation_errors if err.field.startswith("loans"))
        st.markdown(f"<div class='field-error'>{messages}</div>", unsafe_allow_html=True)

with tax_tab:
    st.subheader("税制・備考")
    tax_defaults = finance_raw.get("tax", {})
    corporate_rate = st.number_input(
        "法人税率 (0-55%)",
        min_value=0.0,
        max_value=0.55,
        step=0.01,
        value=float(tax_defaults.get("corporate_tax_rate", 0.3)),
        format="%.2f",
    )
    consumption_rate = st.number_input(
        "消費税率 (0-20%)",
        min_value=0.0,
        max_value=0.20,
        step=0.01,
        value=float(tax_defaults.get("consumption_tax_rate", 0.1)),
        format="%.2f",
    )
    dividend_ratio = st.number_input(
        "配当性向",
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        value=float(tax_defaults.get("dividend_payout_ratio", 0.0)),
        format="%.2f",
    )

    st.caption("税率は自動でバリデーションされます。")

    if any(err.field.startswith("tax") for err in validation_errors):
        messages = "<br/>".join(err.message for err in validation_errors if err.field.startswith("tax"))
        st.markdown(f"<div class='field-error'>{messages}</div>", unsafe_allow_html=True)


save_col, summary_col = st.columns([2, 1])
with save_col:
    if st.button("入力を検証して保存", type="primary"):
        sales_data = {"items": []}
        for _, row in sales_df.fillna(0).iterrows():
            monthly_amounts = [Decimal(str(row[f"月{m:02d}"])) for m in MONTH_SEQUENCE]
            sales_data["items"].append(
                {
                    "channel": str(row.get("チャネル", "")).strip() or "未設定",
                    "product": str(row.get("商品", "")).strip() or "未設定",
                    "monthly": {"amounts": monthly_amounts},
                }
            )

        costs_data = {
            "variable_ratios": {code: Decimal(str(value)) for code, value in variable_inputs.items()},
            "fixed_costs": {code: Decimal(str(value)) * unit_factor for code, value in fixed_inputs.items()},
            "non_operating_income": {code: Decimal(str(value)) * unit_factor for code, value in noi_inputs.items()},
            "non_operating_expenses": {code: Decimal(str(value)) * unit_factor for code, value in noe_inputs.items()},
        }

        capex_data = {
            "items": [
                {
                    "name": ("" if pd.isna(row.get("投資名", "")) else str(row.get("投資名", ""))).strip()
                    or "未設定",
                    "amount": Decimal(str(row.get("金額", 0) if not pd.isna(row.get("金額", 0)) else 0)),
                    "start_month": int(row.get("開始月", 1) if not pd.isna(row.get("開始月", 1)) else 1),
                    "useful_life_years": int(row.get("耐用年数", 5) if not pd.isna(row.get("耐用年数", 5)) else 5),
                }
                for _, row in capex_df.iterrows()
                if Decimal(str(row.get("金額", 0) if not pd.isna(row.get("金額", 0)) else 0)) > 0
            ]
        }

        loan_data = {
            "loans": [
                {
                    "name": ("" if pd.isna(row.get("名称", "")) else str(row.get("名称", ""))).strip()
                    or "借入",
                    "principal": Decimal(
                        str(row.get("元本", 0) if not pd.isna(row.get("元本", 0)) else 0)
                    ),
                    "interest_rate": Decimal(
                        str(row.get("金利", 0) if not pd.isna(row.get("金利", 0)) else 0)
                    ),
                    "term_months": int(
                        row.get("返済期間(月)", 12)
                        if not pd.isna(row.get("返済期間(月)", 12))
                        else 12
                    ),
                    "start_month": int(
                        row.get("開始月", 1) if not pd.isna(row.get("開始月", 1)) else 1
                    ),
                    "repayment_type": (
                        row.get("返済タイプ", "equal_principal")
                        if row.get("返済タイプ", "equal_principal") in {"equal_principal", "interest_only"}
                        else "equal_principal"
                    ),
                }
                for _, row in loan_df.iterrows()
                if Decimal(str(row.get("元本", 0) if not pd.isna(row.get("元本", 0)) else 0)) > 0
            ]
        }

        tax_data = {
            "corporate_tax_rate": Decimal(str(corporate_rate)),
            "consumption_tax_rate": Decimal(str(consumption_rate)),
            "dividend_payout_ratio": Decimal(str(dividend_ratio)),
        }

        bundle_dict = {
            "sales": sales_data,
            "costs": costs_data,
            "capex": capex_data,
            "loans": loan_data,
            "tax": tax_data,
        }

        bundle, issues = validate_bundle(bundle_dict)
        if issues:
            st.session_state["finance_validation_errors"] = issues
            st.toast("入力にエラーがあります。赤枠の項目を修正してください。", icon="❌")
        else:
            st.session_state["finance_validation_errors"] = []
            st.session_state["finance_raw"] = bundle_dict
            st.session_state["finance_models"] = {
                "sales": bundle.sales,
                "costs": bundle.costs,
                "capex": bundle.capex,
                "loans": bundle.loans,
                "tax": bundle.tax,
            }
            st.toast("財務データを保存しました。", icon="✅")

with summary_col:
    total_sales = sum(
        Decimal(str(row[f"月{m:02d}"])) for _, row in sales_df.iterrows() for m in MONTH_SEQUENCE
    )
    avg_ratio = sum(variable_inputs.values()) / len(variable_inputs) if variable_inputs else 0.0
    st.metric("売上合計", format_amount_with_unit(total_sales, unit))
    st.metric("平均原価率", format_ratio(avg_ratio))

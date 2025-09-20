"""Utilities and fixtures for bundled onboarding sample data."""
from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable, List

import pandas as pd
import streamlit as st

from models import (
    MONTH_SEQUENCE,
    CapexItem,
    CapexPlan,
    CostPlan,
    FinanceBundle,
    LoanItem,
    LoanSchedule,
    MonthlySeries,
    SalesItem,
    SalesPlan,
    TaxPolicy,
)

SAMPLE_FISCAL_YEAR = 2025


@dataclass(frozen=True)
class SampleSalesSpec:
    """Definition of a sample sales stream."""

    channel: str
    category: str
    product: str
    unit_price: Decimal
    monthly_quantity: List[int]

    def monthly_revenue(self) -> List[Decimal]:
        return [self.unit_price * Decimal(qty) for qty in self.monthly_quantity]


def _as_decimal(value: int | float | Decimal) -> Decimal:
    return Decimal(str(value))


SAMPLE_SALES_SPECS: List[SampleSalesSpec] = [
    SampleSalesSpec(
        channel="オンライン直販",
        category="SaaS",  # クラウド型の主力プロダクト
        product="成長プラン (月額)",
        unit_price=_as_decimal(120000),
        monthly_quantity=[
            110,
            118,
            125,
            132,
            140,
            148,
            155,
            162,
            170,
            178,
            186,
            195,
        ],
    ),
    SampleSalesSpec(
        channel="オンライン直販",
        category="SaaS",
        product="ライトプラン (月額)",
        unit_price=_as_decimal(45000),
        monthly_quantity=[
            220,
            228,
            240,
            252,
            260,
            268,
            280,
            292,
            300,
            312,
            324,
            336,
        ],
    ),
    SampleSalesSpec(
        channel="フィールドセールス",
        category="エンタープライズ",
        product="エンタープライズ契約",
        unit_price=_as_decimal(900000),
        monthly_quantity=[
            6,
            6,
            7,
            7,
            8,
            8,
            9,
            9,
            10,
            10,
            10,
            11,
        ],
    ),
    SampleSalesSpec(
        channel="パートナー販売",
        category="導入支援",
        product="導入パッケージ",
        unit_price=_as_decimal(320000),
        monthly_quantity=[
            18,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
            25,
            26,
            27,
            28,
        ],
    ),
]


def _build_sales_plan() -> SalesPlan:
    items: List[SalesItem] = []
    for spec in SAMPLE_SALES_SPECS:
        monthly = MonthlySeries(amounts=[Decimal(amount) for amount in spec.monthly_revenue()])
        items.append(
            SalesItem(
                channel=spec.channel,
                product=spec.product,
                monthly=monthly,
            )
        )
    return SalesPlan(items=items)


def _build_cost_plan() -> CostPlan:
    return CostPlan(
        variable_ratios={
            "COGS_MAT": Decimal("0.18"),
            "COGS_LBR": Decimal("0.08"),
            "COGS_OUT_SRC": Decimal("0.05"),
            "COGS_OUT_CON": Decimal("0.02"),
            "COGS_OTH": Decimal("0.01"),
        },
        fixed_costs={
            "OPEX_H": Decimal("130000000"),
            "OPEX_K": Decimal("360000000"),
            "OPEX_DEP": Decimal("24000000"),
        },
        non_operating_income={"NOI_MISC": Decimal("6000000")},
        non_operating_expenses={"NOE_INT": Decimal("12000000")},
    )


def _build_capex_plan() -> CapexPlan:
    return CapexPlan(
        items=[
            CapexItem(
                name="データセンター増強",
                amount=Decimal("85000000"),
                start_month=4,
                useful_life_years=5,
            ),
            CapexItem(
                name="営業支援ツール",
                amount=Decimal("18000000"),
                start_month=1,
                useful_life_years=3,
            ),
        ]
    )


def _build_loan_schedule() -> LoanSchedule:
    return LoanSchedule(
        loans=[
            LoanItem(
                name="成長投資ローン",
                principal=Decimal("125000000"),
                interest_rate=Decimal("0.012"),
                term_months=60,
                start_month=1,
                repayment_type="equal_principal",
            ),
            LoanItem(
                name="設備投資ローン",
                principal=Decimal("60000000"),
                interest_rate=Decimal("0.009"),
                term_months=84,
                start_month=3,
                repayment_type="interest_only",
            ),
        ]
    )


def _build_tax_policy() -> TaxPolicy:
    return TaxPolicy(
        corporate_tax_rate=Decimal("0.30"),
        consumption_tax_rate=Decimal("0.10"),
        dividend_payout_ratio=Decimal("0.12"),
    )


def create_sample_bundle() -> FinanceBundle:
    """Return a finance bundle populated with sample fixtures."""

    return FinanceBundle(
        sales=_build_sales_plan(),
        costs=_build_cost_plan(),
        capex=_build_capex_plan(),
        loans=_build_loan_schedule(),
        tax=_build_tax_policy(),
    )


def sample_finance_raw() -> Dict[str, Dict]:
    """Return the sample bundle serialised to raw dictionaries."""

    bundle = create_sample_bundle()
    return {
        "sales": bundle.sales.model_dump(),
        "costs": bundle.costs.model_dump(),
        "capex": bundle.capex.model_dump(),
        "loans": bundle.loans.model_dump(),
        "tax": bundle.tax.model_dump(),
    }


def _sales_template_dataframe() -> pd.DataFrame:
    rows: List[Dict[str, float | str]] = []
    for spec in SAMPLE_SALES_SPECS:
        row: Dict[str, float | str] = {"チャネル": spec.channel, "商品": spec.product}
        monthly_revenue = spec.monthly_revenue()
        for idx, month in enumerate(MONTH_SEQUENCE):
            row[f"月{month:02d}"] = float(monthly_revenue[idx])
        rows.append(row)
    return pd.DataFrame(rows)


def _sales_tidy_dataframe() -> pd.DataFrame:
    rows: List[Dict[str, float | str | int]] = []
    for spec in SAMPLE_SALES_SPECS:
        monthly_revenue = spec.monthly_revenue()
        for idx, month in enumerate(MONTH_SEQUENCE, start=0):
            rows.append(
                {
                    "チャネル": spec.channel,
                    "カテゴリ": spec.category,
                    "商品": spec.product,
                    "月度": f"{SAMPLE_FISCAL_YEAR}-{month:02d}",
                    "数量": int(spec.monthly_quantity[idx]),
                    "単価": float(spec.unit_price),
                    "売上高": float(monthly_revenue[idx]),
                }
            )
    return pd.DataFrame(rows)


def sample_sales_csv_bytes() -> bytes:
    """CSV representation of the tidy sample sales dataset."""

    df = _sales_tidy_dataframe()
    return df.to_csv(index=False).encode("utf-8-sig")


def sample_sales_excel_bytes() -> bytes:
    """Excel representation of the tidy sample sales dataset."""

    buffer = io.BytesIO()
    df = _sales_tidy_dataframe()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="SampleSales")
    buffer.seek(0)
    return buffer.read()


def _count_unique(values: Iterable[str]) -> int:
    return len({value for value in values})


def apply_sample_data_to_session() -> None:
    """Populate Streamlit session state with the bundled sample dataset."""

    bundle = create_sample_bundle()
    st.session_state["finance_models"] = {
        "sales": bundle.sales,
        "costs": bundle.costs,
        "capex": bundle.capex,
        "loans": bundle.loans,
        "tax": bundle.tax,
    }
    st.session_state["finance_raw"] = sample_finance_raw()
    st.session_state["finance_validation_errors"] = []
    template_df = _sales_template_dataframe()
    st.session_state["sales_template_df"] = template_df
    st.session_state["sales_channel_counter"] = _count_unique(
        (spec.channel for spec in SAMPLE_SALES_SPECS)
    ) + 1
    st.session_state["sales_product_counter"] = _count_unique(
        (spec.product for spec in SAMPLE_SALES_SPECS)
    ) + 1
    st.session_state["sample_data_loaded"] = True


__all__ = [
    "SAMPLE_FISCAL_YEAR",
    "apply_sample_data_to_session",
    "create_sample_bundle",
    "sample_finance_raw",
    "sample_sales_csv_bytes",
    "sample_sales_excel_bytes",
]


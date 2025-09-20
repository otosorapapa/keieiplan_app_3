"""Advanced financial timeline calculations (monthly and annual rollups)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from .pl import PlanConfig, compute_period_amounts
from models import FinanceBundle

getcontext().prec = 28


@dataclass(frozen=True)
class FinancialTimeline:
    """Container for monthly and annual financial statements."""

    monthly: pd.DataFrame
    monthly_pl: pd.DataFrame
    monthly_cf: pd.DataFrame
    monthly_bs: pd.DataFrame
    annual_pl: pd.DataFrame
    annual_cf: pd.DataFrame
    annual_bs: pd.DataFrame
    loan_schedule: pd.DataFrame


def _determine_horizon(bundle: FinanceBundle, horizon_years: int) -> int:
    max_month = 12
    if bundle.capex.items:
        max_month = max(
            max_month,
            max((item.start_month + item.useful_life_years * 12 - 1) for item in bundle.capex.items),
        )
    if bundle.loans.loans:
        max_month = max(
            max_month,
            max((loan.start_month + loan.term_months - 1) for loan in bundle.loans.loans),
        )
    requested = max(max_month, max(12, horizon_years * 12))
    return int(min(requested, 240))


def _depreciation_and_capex_maps(bundle: FinanceBundle, horizon_months: int) -> Tuple[Dict[int, Decimal], Dict[int, Decimal]]:
    depreciation_map: Dict[int, Decimal] = {}
    capex_map: Dict[int, Decimal] = {}
    for item in bundle.capex.items:
        capex_map[item.start_month] = capex_map.get(item.start_month, Decimal("0")) + item.amount
        life_months = item.useful_life_years * 12
        remaining = Decimal(item.amount)
        method = str(item.depreciation_method or "straight_line")
        if method not in {"straight_line", "declining"}:
            method = "straight_line"
        monthly_rate = Decimal("0")
        if method == "declining":
            annual_rate = min(Decimal("1"), Decimal("2") / Decimal(item.useful_life_years))
            monthly_rate_float = 1 - (1 - float(annual_rate)) ** (1 / 12)
            monthly_rate = Decimal(str(monthly_rate_float))
        for offset in range(life_months):
            month = item.start_month + offset
            if month > horizon_months:
                break
            if method == "straight_line":
                depreciation = item.amount / Decimal(life_months)
            else:
                depreciation = remaining * monthly_rate
                if remaining - depreciation < Decimal("1"):
                    depreciation = remaining
            depreciation_map[month] = depreciation_map.get(month, Decimal("0")) + depreciation
            remaining -= depreciation
            if remaining <= Decimal("0"):
                break
    return depreciation_map, capex_map


def _build_loan_schedule(bundle: FinanceBundle, horizon_months: int) -> Dict[int, Dict[str, Decimal]]:
    schedule: Dict[int, Dict[str, Decimal]] = {}
    for loan in bundle.loans.loans:
        outstanding = Decimal(loan.principal)
        monthly_rate = Decimal(loan.interest_rate) / Decimal("12")
        start = int(loan.start_month)
        term = int(loan.term_months)
        grace = min(int(loan.grace_months), term - 1) if term > 0 else 0
        amort_periods = term - grace if loan.repayment_type == "equal_principal" else term
        principal_unit = (
            (Decimal(loan.principal) / Decimal(amort_periods))
            if loan.repayment_type == "equal_principal" and amort_periods > 0
            else Decimal("0")
        )
        for offset in range(term):
            month = start + offset
            if month > horizon_months:
                break
            entry = schedule.setdefault(
                month,
                {"interest": Decimal("0"), "principal": Decimal("0"), "balance_start": Decimal("0"), "balance_end": Decimal("0")},
            )
            balance_start = outstanding
            interest = balance_start * monthly_rate
            if loan.repayment_type == "interest_only":
                principal_payment = Decimal("0")
                if offset == term - 1:
                    principal_payment = outstanding
            else:
                if offset < grace:
                    principal_payment = Decimal("0")
                else:
                    principal_payment = min(principal_unit, outstanding)
            outstanding -= principal_payment
            entry["interest"] += interest
            entry["principal"] += principal_payment
            entry["balance_start"] += balance_start
            entry["balance_end"] += max(Decimal("0"), outstanding)
            if outstanding <= Decimal("0"):
                outstanding = Decimal("0")
                if offset < term - 1:
                    break
    return schedule


def build_financial_timeline(
    bundle: FinanceBundle,
    plan_cfg: PlanConfig,
    *,
    horizon_years: int = 10,
) -> FinancialTimeline:
    """Build monthly statements and annual rollups based on the finance bundle."""

    horizon_months = _determine_horizon(bundle, horizon_years)
    depreciation_map, capex_map = _depreciation_and_capex_maps(bundle, horizon_months)
    loan_schedule = _build_loan_schedule(bundle, horizon_months)

    sales_by_month = bundle.sales.total_by_month()
    wc_days = bundle.costs.working_capital_days
    receivable_days = Decimal(wc_days.get("receivables", Decimal("45")))
    inventory_days = Decimal(wc_days.get("inventory", Decimal("60")))
    payable_days = Decimal(wc_days.get("payables", Decimal("45")))

    monthly_rows: List[Dict[str, Decimal | int | str]] = []
    cash_balance = Decimal("0")
    nwc_prev = Decimal("0")
    net_ppe = Decimal("0")
    period_fraction = Decimal("1") / Decimal("12")

    for month_index in range(1, horizon_months + 1):
        calendar_month = ((month_index - 1) % 12) + 1
        year_index = ((month_index - 1) // 12) + 1
        month_label = f"FY{year_index}-M{calendar_month:02d}"
        sales = Decimal(sales_by_month.get(calendar_month, Decimal("0")))
        period_amounts = compute_period_amounts(
            plan_cfg, sales, period_fraction=period_fraction
        )
        depreciation = depreciation_map.get(month_index, Decimal("0"))
        period_amounts["OPEX_DEP"] = depreciation
        opex_total = period_amounts["OPEX_H"] + period_amounts["OPEX_K"] + depreciation
        period_amounts["OPEX_TTL"] = opex_total
        op = period_amounts["GROSS"] - opex_total
        period_amounts["OP"] = op

        loan_entry = loan_schedule.get(month_index, {})
        interest_payment = loan_entry.get("interest", Decimal("0"))
        principal_payment = loan_entry.get("principal", Decimal("0"))
        debt_balance = loan_entry.get("balance_end", Decimal("0"))
        period_amounts["NOE_INT"] = interest_payment

        non_operating_income = (
            period_amounts.get("NOI_MISC", Decimal("0"))
            + period_amounts.get("NOI_GRANT", Decimal("0"))
            + period_amounts.get("NOI_OTH", Decimal("0"))
        )
        other_expense = period_amounts.get("NOE_OTH", Decimal("0"))
        pretax = op + non_operating_income - other_expense - interest_payment
        taxable = pretax if pretax > 0 else Decimal("0")
        tax = taxable * Decimal(bundle.tax.corporate_tax_rate)
        net_income = pretax - tax
        dividend = bundle.tax.projected_dividend(net_income)
        ord_income = op + non_operating_income - interest_payment - other_expense
        period_amounts["ORD"] = ord_income

        receivables = sales * receivable_days / Decimal("30")
        cogs_total = period_amounts.get("COGS_TTL", Decimal("0"))
        inventory = cogs_total * inventory_days / Decimal("30")
        payables = cogs_total * payable_days / Decimal("30")
        nwc = receivables + inventory - payables
        delta_nwc = nwc - nwc_prev
        nwc_prev = nwc

        operating_cf = op + non_operating_income - other_expense - tax + depreciation - delta_nwc
        capex_out = capex_map.get(month_index, Decimal("0"))
        investing_cf = -capex_out
        financing_cf = -(principal_payment + interest_payment) - dividend
        free_cf = operating_cf + investing_cf + financing_cf
        cash_balance += free_cf
        net_ppe = max(Decimal("0"), net_ppe + capex_out - depreciation)

        assets_total = cash_balance + receivables + inventory + net_ppe
        liabilities_total = payables + debt_balance
        equity = assets_total - liabilities_total

        monthly_rows.append(
            {
                "month_index": month_index,
                "year_index": year_index,
                "calendar_month": calendar_month,
                "month_label": month_label,
                "売上高": sales,
                "売上原価": cogs_total,
                "粗利": period_amounts["GROSS"],
                "販管費": opex_total,
                "営業利益": op,
                "経常利益": ord_income,
                "粗利率": (period_amounts["GROSS"] / sales) if sales > 0 else Decimal("0"),
                "減価償却費": depreciation,
                "法人税": tax,
                "当期純利益": net_income,
                "配当": dividend,
                "営業CF": operating_cf,
                "投資CF": investing_cf,
                "財務CF": financing_cf,
                "フリーCF": free_cf,
                "Δ運転資本": delta_nwc,
                "現金": cash_balance,
                "売掛金": receivables,
                "棚卸資産": inventory,
                "有形固定資産": net_ppe,
                "資産合計": assets_total,
                "買掛金": payables,
                "有利子負債": debt_balance,
                "純資産": equity,
                "負債純資産合計": liabilities_total + equity,
                "利息支払": interest_payment,
                "元本返済": principal_payment,
                "債務償還": principal_payment + interest_payment,
            }
        )

    monthly_df = pd.DataFrame(monthly_rows)
    if not monthly_df.empty:
        numeric_cols = [col for col in monthly_df.columns if col not in {"month_label"} and col not in {"month_index", "year_index", "calendar_month"}]
        for col in numeric_cols:
            monthly_df[col] = monthly_df[col].apply(lambda x: float(x) if isinstance(x, Decimal) else x)
    loan_rows = []
    for month, values in sorted(loan_schedule.items()):
        year_index = ((month - 1) // 12) + 1
        calendar_month = ((month - 1) % 12) + 1
        loan_rows.append(
            {
                "month": month,
                "year_index": year_index,
                "calendar_month": calendar_month,
                "interest": float(values.get("interest", Decimal("0"))),
                "principal": float(values.get("principal", Decimal("0"))),
                "balance_start": float(values.get("balance_start", Decimal("0"))),
                "balance_end": float(values.get("balance_end", Decimal("0"))),
            }
        )
    loan_df = pd.DataFrame(loan_rows)

    monthly_pl = monthly_df[
        [
            "month_index",
            "year_index",
            "calendar_month",
            "month_label",
            "売上高",
            "売上原価",
            "粗利",
            "販管費",
            "営業利益",
            "経常利益",
            "粗利率",
        ]
    ]
    monthly_cf = monthly_df[
        [
            "month_index",
            "year_index",
            "calendar_month",
            "month_label",
            "営業CF",
            "投資CF",
            "財務CF",
            "フリーCF",
            "Δ運転資本",
        ]
    ]
    monthly_bs = monthly_df[
        [
            "month_index",
            "year_index",
            "calendar_month",
            "month_label",
            "現金",
            "売掛金",
            "棚卸資産",
            "有形固定資産",
            "資産合計",
            "買掛金",
            "有利子負債",
            "純資産",
            "負債純資産合計",
        ]
    ]

    def _annual_sum(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
        grouped = df.groupby("year_index", as_index=False)[list(columns)].sum()
        grouped["年度"] = grouped["year_index"].apply(lambda x: f"FY{x}")
        return grouped

    annual_pl = _annual_sum(
        monthly_pl,
        ["売上高", "売上原価", "粗利", "販管費", "営業利益", "経常利益"],
    )
    annual_pl["粗利率"] = annual_pl.apply(
        lambda row: row["粗利"] / row["売上高"] if row["売上高"] else 0.0,
        axis=1,
    )

    annual_cf = _annual_sum(monthly_cf, ["営業CF", "投資CF", "財務CF", "フリーCF", "Δ運転資本"])

    bs_last = (
        monthly_bs.sort_values("month_index")
        .groupby("year_index", as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )
    annual_bs = bs_last[
        [
            "year_index",
            "現金",
            "売掛金",
            "棚卸資産",
            "有形固定資産",
            "資産合計",
            "買掛金",
            "有利子負債",
            "純資産",
            "負債純資産合計",
        ]
    ].copy()
    annual_bs["年度"] = annual_bs["year_index"].apply(lambda x: f"FY{x}")

    return FinancialTimeline(
        monthly=monthly_df,
        monthly_pl=monthly_pl,
        monthly_cf=monthly_cf,
        monthly_bs=monthly_bs,
        annual_pl=annual_pl,
        annual_cf=annual_cf,
        annual_bs=annual_bs,
        loan_schedule=loan_df,
    )


__all__ = ["FinancialTimeline", "build_financial_timeline"]

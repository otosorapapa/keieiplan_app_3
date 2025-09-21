"""Detailed monthly financial statement construction utilities."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Dict, List, Mapping

from models import (
    CapexPlan,
    CostPlan,
    LoanItem,
    LoanSchedule,
    MONTH_SEQUENCE,
    SalesPlan,
    TaxPolicy,
    WorkingCapitalAssumptions,
)

from .plan_constants import COST_CODES, NOI_CODES, NOE_CODES, OPEX_CODES

getcontext().prec = 28


@dataclass(frozen=True)
class LoanSummary:
    """Aggregate information about loan cash flows."""

    monthly: Dict[int, Dict[str, Decimal]]
    yearly: Dict[int, Dict[str, Decimal]]


@dataclass(frozen=True)
class MonthlyStatement:
    """Container for monthly PL/BS/CF outputs."""

    month: int
    pl: Dict[str, Decimal]
    cash_flow: Dict[str, Decimal]
    balance_sheet: Dict[str, Dict[str, Decimal]]
    taxes: Decimal
    net_income: Decimal
    dividends: Decimal
    working_capital: Dict[str, Decimal]
    loan: Dict[str, Decimal]


@dataclass(frozen=True)
class FinancialStatements:
    """Combined monthly and annual statement results."""

    monthly: List[MonthlyStatement]
    annual_pl: Dict[str, Decimal]
    annual_cf: Dict[str, Decimal]
    annual_bs: Dict[str, Dict[str, Decimal]]
    loan_summary: LoanSummary
    fiscal_year_start_month: int = 1
    forecast_years: int = 1


def _reorder_monthly_results(
    statements: List[MonthlyStatement], start_month: int
) -> List[MonthlyStatement]:
    """Rotate monthly statements so the fiscal year starts at *start_month*."""

    if not statements:
        return statements
    if start_month not in range(1, 13):
        return statements
    order = list(range(start_month, 13)) + list(range(1, start_month))
    order_map = {month: index for index, month in enumerate(order)}
    return sorted(statements, key=lambda stmt: order_map.get(stmt.month, stmt.month))


def _loan_schedule_for_item(item: LoanItem) -> List[Dict[str, Decimal]]:
    entries: List[Dict[str, Decimal]] = []
    principal = Decimal(item.principal)
    monthly_rate = Decimal(item.interest_rate) / Decimal("12")
    term_months = int(item.term_months)
    grace_months = min(int(item.grace_period_months or 0), term_months)
    repayment_months = max(0, term_months - grace_months)

    outstanding = principal
    for offset in range(term_months):
        month = int(item.start_month) + offset
        draw = principal if offset == 0 else Decimal("0")
        interest = outstanding * monthly_rate
        principal_payment = Decimal("0")

        in_repayment = offset >= grace_months
        if in_repayment:
            if item.repayment_type == "equal_principal":
                if repayment_months > 0:
                    principal_payment = principal / Decimal(repayment_months)
            elif item.repayment_type == "equal_payment":
                if repayment_months > 0:
                    if monthly_rate == 0:
                        payment = principal / Decimal(repayment_months)
                    else:
                        payment = principal * monthly_rate / (
                            Decimal("1") - (Decimal("1") + monthly_rate) ** (Decimal(-repayment_months))
                        )
                    principal_payment = payment - interest
                    if principal_payment < Decimal("0"):
                        principal_payment = Decimal("0")
            elif item.repayment_type == "interest_only":
                if offset == term_months - 1:
                    principal_payment = outstanding
        else:
            if item.repayment_type == "interest_only" and offset == term_months - 1:
                principal_payment = outstanding

        principal_payment = min(principal_payment, outstanding)
        ending_balance = outstanding - principal_payment

        entries.append(
            {
                "month": month,
                "draw": draw,
                "interest": interest,
                "principal": principal_payment,
                "ending_balance": ending_balance,
            }
        )
        outstanding = ending_balance

    if entries:
        last = entries[-1]
        if abs(last["ending_balance"]) > Decimal("1e-6"):
            adjustment = last["ending_balance"]
            last["principal"] += adjustment
            last["ending_balance"] = Decimal("0")
    return entries


def _aggregate_loan_schedule(schedule: LoanSchedule) -> LoanSummary:
    monthly: Dict[int, Dict[str, Decimal]] = {}
    yearly: Dict[int, Dict[str, Decimal]] = {}

    for loan in schedule.loans:
        for entry in _loan_schedule_for_item(loan):
            month = entry["month"]
            month_bucket = monthly.setdefault(
                month,
                {
                    "draw": Decimal("0"),
                    "principal": Decimal("0"),
                    "interest": Decimal("0"),
                    "ending_balance": Decimal("0"),
                },
            )
            month_bucket["draw"] += entry["draw"]
            month_bucket["principal"] += entry["principal"]
            month_bucket["interest"] += entry["interest"]
            month_bucket["ending_balance"] += entry["ending_balance"]

            year = (month - 1) // 12 + 1
            year_bucket = yearly.setdefault(
                year,
                {"draw": Decimal("0"), "principal": Decimal("0"), "interest": Decimal("0")},
            )
            year_bucket["draw"] += entry["draw"]
            year_bucket["principal"] += entry["principal"]
            year_bucket["interest"] += entry["interest"]

    if monthly:
        running_balance = Decimal("0")
        for month in range(1, max(monthly.keys()) + 1):
            bucket = monthly.setdefault(
                month,
                {
                    "draw": Decimal("0"),
                    "principal": Decimal("0"),
                    "interest": Decimal("0"),
                    "ending_balance": running_balance,
                },
            )
            running_balance = bucket["ending_balance"]

    return LoanSummary(monthly=monthly, yearly=yearly)


def _capex_additions(plan: CapexPlan) -> Dict[int, Decimal]:
    additions: Dict[int, Decimal] = {}
    for item in plan.items:
        additions[item.start_month] = additions.get(item.start_month, Decimal("0")) + Decimal(item.amount)
    return additions


def _capex_depreciation_schedule(plan: CapexPlan) -> Dict[int, Decimal]:
    schedule: Dict[int, Decimal] = {}
    for item in plan.items:
        life_months = max(1, item.useful_life_years * 12)
        if plan.depreciation_method == "declining_balance":
            rate = plan.declining_balance_rate
            if rate is None or rate <= 0 or rate >= 1:
                rate = Decimal("2") / Decimal(item.useful_life_years)
            monthly_rate = rate / Decimal("12")
            book = Decimal(item.amount)
            for offset in range(life_months):
                month = item.start_month + offset
                depreciation = book * monthly_rate
                if depreciation > book:
                    depreciation = book
                if depreciation <= Decimal("0"):
                    break
                schedule[month] = schedule.get(month, Decimal("0")) + depreciation
                book -= depreciation
                if book <= Decimal("0"):
                    break
        else:
            monthly = Decimal(item.amount) / Decimal(life_months)
            for offset in range(life_months):
                month = item.start_month + offset
                schedule[month] = schedule.get(month, Decimal("0")) + monthly
    return schedule


def _line_amount_monthly(
    plan_items: Mapping[str, Mapping[str, object]],
    code: str,
    sales: Decimal,
    gross: Decimal,
    amount_overrides: Mapping[str, Decimal] | None,
) -> Decimal:
    override = None
    if amount_overrides and code in amount_overrides:
        override = Decimal(amount_overrides[code])

    cfg = plan_items.get(code, {})
    method = str(cfg.get("method", "amount"))
    value = Decimal(str(cfg.get("value", Decimal("0"))))
    base = str(cfg.get("rate_base", "sales"))

    if method == "amount" or base == "fixed":
        target = override if override is not None else value
        return target / Decimal("12")

    if override is not None:
        return override

    if base == "gross":
        return gross * value
    return sales * value


def _monthly_sales(sales_plan: SalesPlan) -> Dict[int, Decimal]:
    monthly = {month: Decimal("0") for month in MONTH_SEQUENCE}
    for item in sales_plan.items:
        for month, amount in item.monthly.by_month().items():
            monthly[month] += Decimal(amount)
    return monthly


def build_financial_statements(
    *,
    sales_plan: SalesPlan,
    cost_plan: CostPlan,
    capex_plan: CapexPlan,
    loan_schedule: LoanSchedule,
    tax_policy: TaxPolicy,
    plan_items: Mapping[str, Mapping[str, object]],
    working_capital: WorkingCapitalAssumptions,
    base_sales: Decimal,
    sales_override: Decimal | None = None,
    amount_overrides: Mapping[str, Decimal] | None = None,
    start_month: int = 1,
    forecast_years: int = 1,
) -> FinancialStatements:
    monthly_sales = _monthly_sales(sales_plan)
    scale = Decimal("1")
    if sales_override is not None and base_sales > 0:
        scale = Decimal(sales_override) / Decimal(base_sales)

    for month in monthly_sales:
        monthly_sales[month] *= scale

    capex_additions = _capex_additions(capex_plan)
    capex_depreciation = _capex_depreciation_schedule(capex_plan)
    loan_summary = _aggregate_loan_schedule(loan_schedule)

    monthly_results: List[MonthlyStatement] = []

    prev_cash = Decimal("0")
    prev_receivable = Decimal("0")
    prev_inventory = Decimal("0")
    prev_payable = Decimal("0")
    prev_equity = Decimal("0")
    gross_ppe = Decimal("0")
    accumulated_dep_capex = Decimal("0")

    for month in MONTH_SEQUENCE:
        sales = monthly_sales.get(month, Decimal("0"))
        gross_guess = sales
        for _ in range(6):
            cogs_total = Decimal("0")
            for code in COST_CODES:
                amount = _line_amount_monthly(plan_items, code, sales, gross_guess, amount_overrides)
                if amount < 0:
                    amount = Decimal("0")
                cogs_total += amount
            new_gross = sales - cogs_total
            if abs(new_gross - gross_guess) <= Decimal("0.0001"):
                gross_guess = new_gross
                break
            gross_guess = new_gross

        cogs_breakdown: Dict[str, Decimal] = {}
        cogs_total = Decimal("0")
        for code in COST_CODES:
            amount = _line_amount_monthly(plan_items, code, sales, gross_guess, amount_overrides)
            if amount < 0:
                amount = Decimal("0")
            cogs_breakdown[code] = amount
            cogs_total += amount
        gross = sales - cogs_total

        opex_breakdown: Dict[str, Decimal] = {}
        opex_total = Decimal("0")
        manual_dep = _line_amount_monthly(plan_items, "OPEX_DEP", sales, gross, amount_overrides)
        capex_dep = capex_depreciation.get(month, Decimal("0"))
        for code in OPEX_CODES:
            if code == "OPEX_DEP":
                amount = manual_dep + capex_dep
            else:
                amount = _line_amount_monthly(plan_items, code, sales, gross, amount_overrides)
            if amount < 0:
                amount = Decimal("0")
            opex_breakdown[code] = amount
            opex_total += amount

        op_income = gross - opex_total

        noi_total = Decimal("0")
        for code in NOI_CODES:
            amount = _line_amount_monthly(plan_items, code, sales, gross, amount_overrides)
            if amount < 0:
                amount = Decimal("0")
            noi_total += amount

        manual_interest = _line_amount_monthly(plan_items, "NOE_INT", sales, gross, amount_overrides)
        loan_data = loan_summary.monthly.get(
            month,
            {"draw": Decimal("0"), "principal": Decimal("0"), "interest": Decimal("0"), "ending_balance": Decimal("0")},
        )
        interest_total = manual_interest + loan_data.get("interest", Decimal("0"))

        noe_total = interest_total
        for code in NOE_CODES:
            if code == "NOE_INT":
                continue
            amount = _line_amount_monthly(plan_items, code, sales, gross, amount_overrides)
            if amount < 0:
                amount = Decimal("0")
            noe_total += amount

        ordinary_income = op_income + noi_total - noe_total
        taxes = tax_policy.effective_tax(ordinary_income)
        net_income = ordinary_income - taxes
        dividends = tax_policy.projected_dividend(net_income)

        receivable = sales * working_capital.receivable_days / Decimal("30")
        inventory = cogs_total * working_capital.inventory_days / Decimal("30")
        payable = cogs_total * working_capital.payable_days / Decimal("30")

        delta_wc = (receivable - prev_receivable) + (inventory - prev_inventory) - (payable - prev_payable)
        depreciation_total = opex_breakdown.get("OPEX_DEP", Decimal("0"))

        operating_cf = net_income + depreciation_total - delta_wc
        investing_cf = -capex_additions.get(month, Decimal("0"))
        financing_cf = loan_data.get("draw", Decimal("0")) - loan_data.get("principal", Decimal("0")) - dividends
        net_cf = operating_cf + investing_cf + financing_cf
        cash = prev_cash + net_cf

        gross_ppe += capex_additions.get(month, Decimal("0"))
        accumulated_dep_capex += capex_dep
        net_ppe = max(Decimal("0"), gross_ppe - accumulated_dep_capex)

        assets_total = cash + receivable + inventory + net_ppe
        debt_balance = loan_data.get("ending_balance", Decimal("0"))
        equity = prev_equity + net_income - dividends
        liabilities_total = payable + debt_balance + equity
        difference = assets_total - liabilities_total
        if difference != Decimal("0"):
            equity += difference
            liabilities_total += difference

        pl_row: Dict[str, Decimal] = {
            "REV": sales,
            "COGS_TTL": cogs_total,
            "GROSS": gross,
            "OPEX_H": opex_breakdown.get("OPEX_H", Decimal("0")),
            "OPEX_K": opex_breakdown.get("OPEX_K", Decimal("0")),
            "OPEX_DEP": opex_breakdown.get("OPEX_DEP", Decimal("0")),
            "OPEX_TTL": opex_total,
            "OP": op_income,
            "NOI_MISC": _line_amount_monthly(plan_items, "NOI_MISC", sales, gross, amount_overrides),
            "NOI_GRANT": _line_amount_monthly(plan_items, "NOI_GRANT", sales, gross, amount_overrides),
            "NOI_OTH": _line_amount_monthly(plan_items, "NOI_OTH", sales, gross, amount_overrides),
            "NOE_INT": interest_total,
            "NOE_OTH": _line_amount_monthly(plan_items, "NOE_OTH", sales, gross, amount_overrides),
            "ORD": ordinary_income,
            "TAX": taxes,
            "NET": net_income,
            "DIV": dividends,
        }
        for code in COST_CODES:
            pl_row[code] = cogs_breakdown.get(code, Decimal("0"))

        cash_flow_row = {
            "営業キャッシュフロー": operating_cf,
            "投資キャッシュフロー": investing_cf,
            "財務キャッシュフロー": financing_cf,
            "キャッシュ増減": net_cf,
        }

        balance_sheet_row = {
            "assets": {
                "現金同等物": cash,
                "売掛金": receivable,
                "棚卸資産": inventory,
                "有形固定資産": net_ppe,
            },
            "liabilities": {
                "買掛金": payable,
                "有利子負債": debt_balance,
                "純資産": equity,
            },
            "totals": {
                "assets": assets_total,
                "liabilities": liabilities_total,
            },
        }

        working_capital_row = {
            "accounts_receivable": receivable,
            "inventory": inventory,
            "accounts_payable": payable,
        }

        monthly_results.append(
            MonthlyStatement(
                month=month,
                pl=pl_row,
                cash_flow=cash_flow_row,
                balance_sheet=balance_sheet_row,
                taxes=taxes,
                net_income=net_income,
                dividends=dividends,
                working_capital=working_capital_row,
                loan={
                    "draw": loan_data.get("draw", Decimal("0")),
                    "principal": loan_data.get("principal", Decimal("0")),
                    "interest": interest_total,
                    "ending_balance": debt_balance,
                },
            )
        )

        prev_cash = cash
        prev_receivable = receivable
        prev_inventory = inventory
        prev_payable = payable
        prev_equity = equity

    annual_pl: Dict[str, Decimal] = {}
    for statement in monthly_results:
        for code, value in statement.pl.items():
            annual_pl[code] = annual_pl.get(code, Decimal("0")) + value

    annual_cf = {
        "営業キャッシュフロー": sum((m.cash_flow["営業キャッシュフロー"] for m in monthly_results), start=Decimal("0")),
        "投資キャッシュフロー": sum((m.cash_flow["投資キャッシュフロー"] for m in monthly_results), start=Decimal("0")),
        "財務キャッシュフロー": sum((m.cash_flow["財務キャッシュフロー"] for m in monthly_results), start=Decimal("0")),
        "キャッシュ増減": sum((m.cash_flow["キャッシュ増減"] for m in monthly_results), start=Decimal("0")),
    }

    annual_bs = monthly_results[-1].balance_sheet if monthly_results else {
        "assets": {"現金同等物": Decimal("0"), "売掛金": Decimal("0"), "棚卸資産": Decimal("0"), "有形固定資産": Decimal("0")},
        "liabilities": {"買掛金": Decimal("0"), "有利子負債": Decimal("0"), "純資産": Decimal("0")},
        "totals": {"assets": Decimal("0"), "liabilities": Decimal("0")},
    }

    try:
        start_month_value = int(start_month)
    except Exception:  # pragma: no cover - defensive fallback
        start_month_value = 1
    if start_month_value < 1 or start_month_value > 12:
        start_month_value = 1

    try:
        forecast_years_value = int(forecast_years)
    except Exception:  # pragma: no cover - defensive fallback
        forecast_years_value = 1
    if forecast_years_value <= 0:
        forecast_years_value = 1

    ordered_months = _reorder_monthly_results(monthly_results, start_month_value)

    return FinancialStatements(
        monthly=ordered_months,
        annual_pl=annual_pl,
        annual_cf=annual_cf,
        annual_bs=annual_bs,
        loan_summary=loan_summary,
        fiscal_year_start_month=start_month_value,
        forecast_years=forecast_years_value,
    )


__all__ = [
    "FinancialStatements",
    "LoanSummary",
    "MonthlyStatement",
    "build_financial_statements",
]

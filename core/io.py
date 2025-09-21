"""Utilities for loading and persisting application input data."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Mapping

import pandas as pd

from . import strategy as strategy_utils
from models import (
    CapexPlan,
    CostPlan,
    LoanSchedule,
    SalesPlan,
    TaxPolicy,
    ValidationError,
    WorkingCapitalAssumptions,
)

UploadedFile = Any

MONTH_LABELS = [f"M{month:02d}" for month in range(1, 13)]


def load_uploaded_dataset(file: UploadedFile | None) -> dict[str, Any]:
    """Parse an uploaded dataset file and return metadata only."""

    if file is None:
        return {}

    name = getattr(file, "name", "uploaded_file")
    size = getattr(file, "size", None)
    if size is None:
        try:
            size = len(file.getvalue())
        except Exception:
            size = 0
    return {
        "name": name,
        "size": size,
        "type": getattr(file, "type", "unknown"),
    }


def snapshot_session_state(session_state: Mapping[str, Any]) -> dict[str, Any]:
    """Return a plain dictionary copy of the Streamlit session state."""

    return {key: value for key, value in session_state.items()}


def _dict_to_dataframe(data: Mapping[str, Any], *, value_column: str = "value") -> pd.DataFrame:
    rows = sorted((str(key), data[key]) for key in data)
    frame = pd.DataFrame(rows, columns=["code", value_column])
    if frame.empty:
        frame = pd.DataFrame(columns=["code", value_column])
    return frame


def _sales_to_dataframe(sales: SalesPlan) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in sales.items:
        row: dict[str, Any] = {
            "channel": item.channel,
            "product": item.product,
        }
        monthly = item.monthly.by_month()
        for index, label in enumerate(MONTH_LABELS, start=1):
            row[label] = float(monthly.get(index, Decimal("0")))
        row["annual_total"] = float(item.annual_total)
        rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        columns = ["channel", "product", *MONTH_LABELS, "annual_total"]
        frame = pd.DataFrame(columns=columns)
    return frame


def _capex_to_dataframe(capex: CapexPlan) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in capex.items:
        rows.append(
            {
                "name": item.name,
                "amount": float(item.amount),
                "start_month": int(item.start_month),
                "useful_life_years": int(item.useful_life_years),
                "depreciation_method": capex.depreciation_method,
                "declining_balance_rate": (
                    float(capex.declining_balance_rate)
                    if capex.declining_balance_rate is not None
                    else None
                ),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame(
            columns=[
                "name",
                "amount",
                "start_month",
                "useful_life_years",
                "depreciation_method",
                "declining_balance_rate",
            ]
        )
    return frame


def _loans_to_dataframe(loans: LoanSchedule) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for loan in loans.loans:
        rows.append(
            {
                "name": loan.name,
                "principal": float(loan.principal),
                "interest_rate": float(loan.interest_rate),
                "term_months": int(loan.term_months),
                "start_month": int(loan.start_month),
                "grace_period_months": int(loan.grace_period_months),
                "repayment_type": loan.repayment_type,
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame(
            columns=[
                "name",
                "principal",
                "interest_rate",
                "term_months",
                "start_month",
                "grace_period_months",
                "repayment_type",
            ]
        )
    return frame


def _tax_to_dataframe(tax: TaxPolicy) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "corporate_tax_rate": float(tax.corporate_tax_rate),
                "consumption_tax_rate": float(tax.consumption_tax_rate),
                "dividend_payout_ratio": float(tax.dividend_payout_ratio),
            }
        ]
    )


def _working_capital_to_dataframe(working_capital: WorkingCapitalAssumptions) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "receivable_days": float(working_capital.receivable_days),
                "inventory_days": float(working_capital.inventory_days),
                "payable_days": float(working_capital.payable_days),
            }
        ]
    )


def prepare_finance_export_payload(
    *,
    sales: SalesPlan,
    costs: CostPlan,
    capex: CapexPlan,
    loans: LoanSchedule,
    tax: TaxPolicy,
    working_capital: WorkingCapitalAssumptions,
    settings: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
    strategy: Mapping[str, Any] | None = None,
) -> Dict[str, pd.DataFrame]:
    """Build a mapping of sheet name to DataFrame for export."""

    meta_entries = {"generated_at": datetime.utcnow().isoformat(timespec="seconds")}
    if metadata:
        for key, value in metadata.items():
            meta_entries[str(key)] = value
    metadata_frame = pd.DataFrame(
        [(key, meta_entries[key]) for key in sorted(meta_entries.keys())],
        columns=["key", "value"],
    )

    settings_frame = pd.DataFrame(
        [(str(key), settings[key]) for key in sorted(settings.keys())],
        columns=["key", "value"],
    )
    payload: Dict[str, pd.DataFrame] = {
        "metadata": metadata_frame,
        "settings": settings_frame,
        "sales": _sales_to_dataframe(sales),
        "costs_variable": _dict_to_dataframe(costs.variable_ratios),
        "costs_gross_linked": _dict_to_dataframe(costs.gross_linked_ratios),
        "costs_fixed": _dict_to_dataframe(costs.fixed_costs, value_column="amount"),
        "costs_non_operating_income": _dict_to_dataframe(
            costs.non_operating_income, value_column="amount"
        ),
        "costs_non_operating_expenses": _dict_to_dataframe(
            costs.non_operating_expenses, value_column="amount"
        ),
        "capex": _capex_to_dataframe(capex),
        "loans": _loans_to_dataframe(loans),
        "tax": _tax_to_dataframe(tax),
        "working_capital": _working_capital_to_dataframe(working_capital),
    }
    strategy_state = strategy or {}
    payload["strategy_bsc"] = strategy_utils.bsc_to_dataframe(strategy_state.get("bsc", {}))
    payload["strategy_pest"] = strategy_utils.pest_to_dataframe(strategy_state.get("pest", {}))
    payload["strategy_swot"] = strategy_utils.swot_to_dataframe(strategy_state.get("swot", {}))
    return payload


def export_payload_to_excel(payload: Mapping[str, pd.DataFrame]) -> bytes:
    """Serialize the prepared payload to an Excel workbook."""

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, frame in payload.items():
            safe_name = sheet_name[:31]
            frame.to_excel(writer, sheet_name=safe_name, index=False)
    buffer.seek(0)
    return buffer.getvalue()


def export_payload_to_csv_zip(payload: Mapping[str, pd.DataFrame]) -> bytes:
    """Serialize the prepared payload to a ZIP archive of CSV files."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for sheet_name, frame in payload.items():
            csv_text = frame.to_csv(index=False)
            archive.writestr(f"{sheet_name}.csv", csv_text.encode("utf-8-sig"))
    buffer.seek(0)
    return buffer.getvalue()


def _read_excel_frames(content: bytes) -> Dict[str, pd.DataFrame]:
    frames = pd.read_excel(io.BytesIO(content), sheet_name=None)
    return {key: df for key, df in frames.items()}


def _read_zip_frames(content: bytes) -> Dict[str, pd.DataFrame]:
    frames: Dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".csv"):
                continue
            with archive.open(name) as file:
                data = file.read().decode("utf-8-sig")
            frame = pd.read_csv(io.StringIO(data))
            frames[Path(name).stem] = frame
    return frames


def _frame_to_settings(frame: pd.DataFrame | None) -> Dict[str, Any]:
    if frame is None or frame.empty:
        return {}
    records = frame.to_dict(orient="records")
    return {str(row.get("key")): row.get("value") for row in records if row.get("key")}


def _frame_to_metadata(frame: pd.DataFrame | None) -> Dict[str, Any]:
    if frame is None or frame.empty:
        return {}
    records = frame.to_dict(orient="records")
    return {str(row.get("key")): row.get("value") for row in records if row.get("key")}


def _frame_to_sales(frame: pd.DataFrame | None) -> SalesPlan:
    if frame is None or frame.empty:
        return SalesPlan(items=[])
    clean = frame.where(pd.notna(frame), 0)
    records = clean.to_dict(orient="records")
    items: list[dict[str, Any]] = []
    for row in records:
        monthly = [row.get(label, 0) for label in MONTH_LABELS]
        items.append(
            {
                "channel": row.get("channel", ""),
                "product": row.get("product", ""),
                "monthly": {"amounts": monthly},
            }
        )
    return SalesPlan.from_dict({"items": items})


def _frame_to_cost_plan(frames: Mapping[str, pd.DataFrame]) -> CostPlan:
    def _convert(frame: pd.DataFrame | None) -> Dict[str, Any]:
        if frame is None or frame.empty:
            return {}
        rows = frame.where(pd.notna(frame), 0).to_dict(orient="records")
        return {
            str(row.get("code", "")): row.get("value") or row.get("amount", 0)
            for row in rows
            if str(row.get("code", ""))
        }

    data = {
        "variable_ratios": _convert(frames.get("costs_variable")),
        "gross_linked_ratios": _convert(frames.get("costs_gross_linked")),
        "fixed_costs": _convert(frames.get("costs_fixed")),
        "non_operating_income": _convert(frames.get("costs_non_operating_income")),
        "non_operating_expenses": _convert(frames.get("costs_non_operating_expenses")),
    }
    return CostPlan.from_dict(data)


def _frame_to_capex(frame: pd.DataFrame | None) -> CapexPlan:
    if frame is None or frame.empty:
        return CapexPlan(items=[])
    records = frame.where(pd.notna(frame), None).to_dict(orient="records")
    method = str(records[0].get("depreciation_method", "straight_line")) if records else "straight_line"
    rate = records[0].get("declining_balance_rate") if records else None
    items: list[dict[str, Any]] = []
    for row in records:
        items.append(
            {
                "name": row.get("name", ""),
                "amount": row.get("amount", 0),
                "start_month": row.get("start_month", 1),
                "useful_life_years": row.get("useful_life_years", 1),
            }
        )
    return CapexPlan.from_dict(
        {
            "items": items,
            "depreciation_method": method,
            "declining_balance_rate": rate,
        }
    )


def _frame_to_loans(frame: pd.DataFrame | None) -> LoanSchedule:
    if frame is None or frame.empty:
        return LoanSchedule(loans=[])
    records = frame.where(pd.notna(frame), None).to_dict(orient="records")
    loans = []
    for row in records:
        loans.append(
            {
                "name": row.get("name", ""),
                "principal": row.get("principal", 0),
                "interest_rate": row.get("interest_rate", 0),
                "term_months": row.get("term_months", 0),
                "start_month": row.get("start_month", 1),
                "grace_period_months": row.get("grace_period_months", 0),
                "repayment_type": row.get("repayment_type", "equal_principal"),
            }
        )
    return LoanSchedule.from_dict({"loans": loans})


def _frame_to_tax(frame: pd.DataFrame | None) -> TaxPolicy:
    if frame is None or frame.empty:
        return TaxPolicy()
    row = frame.where(pd.notna(frame), None).iloc[0].to_dict()
    return TaxPolicy.from_dict(row)


def _frame_to_working_capital(frame: pd.DataFrame | None) -> WorkingCapitalAssumptions:
    if frame is None or frame.empty:
        return WorkingCapitalAssumptions()
    row = frame.where(pd.notna(frame), None).iloc[0].to_dict()
    return WorkingCapitalAssumptions.from_dict(row)


def _format_validation(prefix: str, exc: ValidationError) -> str:
    messages = []
    for detail in exc.errors():
        loc = detail.get("loc", ())
        location = " → ".join(str(part) for part in loc) if loc else ""
        msg = detail.get("msg", "無効な値です。")
        if location:
            messages.append(f"{prefix}: {location} — {msg}")
        else:
            messages.append(f"{prefix}: {msg}")
    return "\n".join(messages) if messages else f"{prefix}: {exc}"


def import_finance_payload(file: UploadedFile | None) -> tuple[dict[str, Any], list[str]]:
    """Parse an uploaded export file into finance models and settings."""

    if file is None:
        return {}, ["ファイルが指定されていません。"]

    filename = str(getattr(file, "name", ""))
    suffix = Path(filename).suffix.lower()
    try:
        content = file.getvalue()
    except Exception:  # pragma: no cover - fallback for stream wrappers
        content = file.read()
    try:
        file.seek(0)
    except Exception:  # pragma: no cover - some wrappers do not support seek
        pass

    frames: Dict[str, pd.DataFrame]
    if suffix in {".xlsx", ".xlsm"}:
        frames = _read_excel_frames(content)
    elif suffix in {".zip"}:
        frames = _read_zip_frames(content)
    else:
        return {}, ["対応していないファイル形式です。ExcelまたはZIP(CSV)を指定してください。"]

    warnings: list[str] = []
    result: dict[str, Any] = {
        "settings": _frame_to_settings(frames.get("settings")),
        "metadata": _frame_to_metadata(frames.get("metadata")),
    }

    try:
        sales = _frame_to_sales(frames.get("sales"))
    except ValidationError as exc:
        warnings.append(_format_validation("売上データ", exc))
        sales = SalesPlan(items=[])

    try:
        costs = _frame_to_cost_plan(frames)
    except ValidationError as exc:
        warnings.append(_format_validation("コストデータ", exc))
        costs = CostPlan()

    try:
        capex = _frame_to_capex(frames.get("capex"))
    except ValidationError as exc:
        warnings.append(_format_validation("投資計画", exc))
        capex = CapexPlan(items=[])

    try:
        loans = _frame_to_loans(frames.get("loans"))
    except ValidationError as exc:
        warnings.append(_format_validation("借入計画", exc))
        loans = LoanSchedule(loans=[])

    try:
        tax = _frame_to_tax(frames.get("tax"))
    except ValidationError as exc:
        warnings.append(_format_validation("税制設定", exc))
        tax = TaxPolicy()

    try:
        working_capital = _frame_to_working_capital(frames.get("working_capital"))
    except ValidationError as exc:
        warnings.append(_format_validation("運転資本", exc))
        working_capital = WorkingCapitalAssumptions()

    result["models"] = {
        "sales": sales,
        "costs": costs,
        "capex": capex,
        "loans": loans,
        "tax": tax,
        "working_capital": working_capital,
    }
    result["strategy"] = strategy_utils.frames_to_strategy(frames)

    return result, warnings


__all__ = [
    "MONTH_LABELS",
    "load_uploaded_dataset",
    "snapshot_session_state",
    "prepare_finance_export_payload",
    "export_payload_to_excel",
    "export_payload_to_csv_zip",
    "import_finance_payload",
]

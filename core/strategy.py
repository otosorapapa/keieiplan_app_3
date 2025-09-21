"""Utilities for managing strategy frameworks such as BSC, PEST and SWOT."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import pandas as pd

from formatting import format_amount_with_unit, format_ratio, to_decimal
from models import FinanceBundle

BSC_PERSPECTIVES: List[Tuple[str, str]] = [
    ("financial", "財務"),
    ("customer", "顧客"),
    ("process", "内部プロセス"),
    ("learning", "学習・成長"),
]

PEST_DIMENSIONS: List[Tuple[str, str, str]] = [
    ("political", "政治", "規制・税制、政策動向"),
    ("economic", "経済", "成長率・物価、為替"),
    ("social", "社会", "人口動態・価値観"),
    ("technological", "技術", "自動化・技術変化"),
]

SWOT_CATEGORIES: List[Tuple[str, str]] = [
    ("strengths", "強み"),
    ("weaknesses", "弱み"),
    ("opportunities", "機会"),
    ("threats", "脅威"),
]


def default_bsc_state() -> Dict[str, List[Dict[str, str]]]:
    """Return an empty structure for BSC perspective entries."""

    return {key: [] for key, _ in BSC_PERSPECTIVES}


def default_pest_state() -> Dict[str, List[str]]:
    """Return an empty structure for PEST entries."""

    return {key: [] for key, *_ in PEST_DIMENSIONS}


def default_swot_state() -> Dict[str, List[str]]:
    """Return an empty structure for SWOT entries."""

    return {key: [] for key, _ in SWOT_CATEGORIES}


def _ensure_iterable(value: Any) -> Iterable[Any]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Mapping):
        return value.values()
    if isinstance(value, Iterable):
        return value
    return []


def normalize_bsc_state(data: Mapping[str, Any] | None) -> Dict[str, List[Dict[str, str]]]:
    """Return a sanitized BSC dictionary suitable for storage and rendering."""

    normalized = default_bsc_state()
    if not isinstance(data, Mapping):
        return normalized
    for key in normalized:
        entries = []
        raw_entries = data.get(key)
        for item in _ensure_iterable(raw_entries):
            if isinstance(item, Mapping):
                objective = str(item.get("objective", "")).strip()
                metric = str(item.get("metric", "")).strip()
                target = str(item.get("target", "")).strip()
            elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
                parts = list(item) + ["", "", ""]
                objective = str(parts[0]).strip()
                metric = str(parts[1]).strip()
                target = str(parts[2]).strip()
            else:
                continue
            if not any([objective, metric, target]):
                continue
            entries.append({
                "objective": objective,
                "metric": metric,
                "target": target,
            })
        normalized[key] = entries
    return normalized


def normalize_pest_state(data: Mapping[str, Any] | None) -> Dict[str, List[str]]:
    """Return a sanitized PEST dictionary."""

    normalized = default_pest_state()
    if not isinstance(data, Mapping):
        return normalized
    for key in normalized:
        entries: List[str] = []
        raw_entries = data.get(key)
        for item in _ensure_iterable(raw_entries):
            text = str(item).strip()
            if text:
                entries.append(text)
        normalized[key] = entries
    return normalized


def normalize_swot_state(data: Mapping[str, Any] | None) -> Dict[str, List[str]]:
    """Return a sanitized SWOT dictionary."""

    normalized = default_swot_state()
    if not isinstance(data, Mapping):
        return normalized
    for key in normalized:
        entries: List[str] = []
        raw_entries = data.get(key)
        for item in _ensure_iterable(raw_entries):
            text = str(item).strip()
            if text:
                entries.append(text)
        normalized[key] = entries
    return normalized


def bsc_to_dataframe(state: Mapping[str, Any]) -> pd.DataFrame:
    """Convert BSC entries into a normalized DataFrame for export."""

    normalized = normalize_bsc_state(state)
    rows: List[Dict[str, str]] = []
    for key, _label in BSC_PERSPECTIVES:
        for entry in normalized.get(key, []):
            rows.append(
                {
                    "perspective": key,
                    "objective": entry.get("objective", ""),
                    "metric": entry.get("metric", ""),
                    "target": entry.get("target", ""),
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame(columns=["perspective", "objective", "metric", "target"])
    return frame


def pest_to_dataframe(state: Mapping[str, Any]) -> pd.DataFrame:
    """Convert PEST entries into a DataFrame for export."""

    normalized = normalize_pest_state(state)
    rows: List[Dict[str, str]] = []
    for key, _label, _ in PEST_DIMENSIONS:
        for entry in normalized.get(key, []):
            rows.append({"dimension": key, "factor": entry})
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame(columns=["dimension", "factor"])
    return frame


def swot_to_dataframe(state: Mapping[str, Any]) -> pd.DataFrame:
    """Convert SWOT entries into a DataFrame for export."""

    normalized = normalize_swot_state(state)
    rows: List[Dict[str, str]] = []
    for key, _label in SWOT_CATEGORIES:
        for entry in normalized.get(key, []):
            rows.append({"category": key, "item": entry})
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame(columns=["category", "item"])
    return frame


def dataframe_to_bsc(frame: pd.DataFrame | None) -> Dict[str, List[Dict[str, str]]]:
    """Convert an exported BSC frame back into the session structure."""

    if frame is None or frame.empty:
        return default_bsc_state()
    perspective_col = _resolve_column(frame, {"perspective"})
    objective_col = _resolve_column(frame, {"objective"})
    metric_col = _resolve_column(frame, {"metric"})
    target_col = _resolve_column(frame, {"target"})
    if not all([perspective_col, objective_col, metric_col, target_col]):
        return default_bsc_state()
    grouped: Dict[str, List[Dict[str, str]]] = default_bsc_state()
    records = frame.where(pd.notna(frame), "").to_dict(orient="records")
    for row in records:
        perspective = str(row.get(perspective_col, "")).strip()
        objective = str(row.get(objective_col, "")).strip()
        metric = str(row.get(metric_col, "")).strip()
        target = str(row.get(target_col, "")).strip()
        if perspective not in grouped:
            continue
        if not any([objective, metric, target]):
            continue
        grouped[perspective].append(
            {"objective": objective, "metric": metric, "target": target}
        )
    return grouped


def dataframe_to_pest(frame: pd.DataFrame | None) -> Dict[str, List[str]]:
    """Convert an exported PEST frame back into the session structure."""

    if frame is None or frame.empty:
        return default_pest_state()
    dimension_col = _resolve_column(frame, {"dimension"})
    factor_col = _resolve_column(frame, {"factor"})
    if not all([dimension_col, factor_col]):
        return default_pest_state()
    grouped: Dict[str, List[str]] = default_pest_state()
    records = frame.where(pd.notna(frame), "").to_dict(orient="records")
    for row in records:
        dimension = str(row.get(dimension_col, "")).strip()
        if dimension not in grouped:
            continue
        factor = str(row.get(factor_col, "")).strip()
        if factor:
            grouped[dimension].append(factor)
    return grouped


def dataframe_to_swot(frame: pd.DataFrame | None) -> Dict[str, List[str]]:
    """Convert an exported SWOT frame back into the session structure."""

    if frame is None or frame.empty:
        return default_swot_state()
    category_col = _resolve_column(frame, {"category"})
    item_col = _resolve_column(frame, {"item"})
    if not all([category_col, item_col]):
        return default_swot_state()
    grouped: Dict[str, List[str]] = default_swot_state()
    records = frame.where(pd.notna(frame), "").to_dict(orient="records")
    for row in records:
        category = str(row.get(category_col, "")).strip()
        if category not in grouped:
            continue
        item = str(row.get(item_col, "")).strip()
        if item:
            grouped[category].append(item)
    return grouped


def _resolve_column(frame: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    available = {str(col).lower(): str(col) for col in frame.columns}
    for candidate in candidates:
        key = str(candidate).lower()
        if key in available:
            return available[key]
    return None


def build_bsc_display_frame(state: Mapping[str, Any]) -> pd.DataFrame:
    """Return a DataFrame optimised for on-screen display of BSC entries."""

    frame = bsc_to_dataframe(state)
    if frame.empty:
        return pd.DataFrame(columns=["視点", "目標", "指標", "ターゲット"])
    label_map = {key: label for key, label in BSC_PERSPECTIVES}
    frame = frame.assign(視点=frame["perspective"].map(label_map).fillna(frame["perspective"]))
    frame = frame.rename(columns={"objective": "目標", "metric": "指標", "target": "ターゲット"})
    return frame[["視点", "目標", "指標", "ターゲット"]]


def build_pest_display(state: Mapping[str, Any]) -> Dict[str, List[str]]:
    """Return PEST entries keyed by dimension label for display."""

    normalized = normalize_pest_state(state)
    label_map = {key: label for key, label, _ in PEST_DIMENSIONS}
    return {label_map[key]: normalized.get(key, []) for key in normalized}


def build_swot_display(state: Mapping[str, Any]) -> Dict[str, List[str]]:
    """Return SWOT entries keyed by category label for display."""

    normalized = normalize_swot_state(state)
    label_map = {key: label for key, label in SWOT_CATEGORIES}
    return {label_map[key]: normalized.get(key, []) for key in normalized}


def summarize_financial_context(bundle: FinanceBundle) -> Dict[str, Decimal]:
    """Extract lightweight financial indicators for strategic insights."""

    annual_sales = bundle.sales.annual_total()
    variable_ratio = sum(bundle.costs.variable_ratios.values(), start=Decimal("0"))
    if variable_ratio < Decimal("0"):
        variable_ratio = Decimal("0")
    if variable_ratio > Decimal("1"):
        variable_ratio = Decimal("1")
    gross_margin_ratio = Decimal("1") - variable_ratio
    fixed_cost_total = sum(bundle.costs.fixed_costs.values(), start=Decimal("0"))
    fixed_cost_ratio = Decimal("0")
    if annual_sales and annual_sales != Decimal("0"):
        fixed_cost_ratio = (fixed_cost_total / annual_sales).quantize(Decimal("0.0001"))
    non_operating_income = sum(bundle.costs.non_operating_income.values(), start=Decimal("0"))
    non_operating_expenses = sum(bundle.costs.non_operating_expenses.values(), start=Decimal("0"))
    non_operating_balance = non_operating_income - non_operating_expenses
    return {
        "annual_sales": annual_sales,
        "gross_margin_ratio": gross_margin_ratio,
        "fixed_cost_total": fixed_cost_total,
        "fixed_cost_ratio": fixed_cost_ratio,
        "non_operating_balance": non_operating_balance,
    }


def generate_swot_suggestions(
    swot_state: Mapping[str, Any],
    pest_state: Mapping[str, Any],
    finance_summary: Mapping[str, Any],
    *,
    unit: str,
    currency: str,
    bsc_state: Mapping[str, Any] | None = None,
) -> List[str]:
    """Generate qualitative suggestions referencing SWOT/PEST/finance inputs."""

    normalized_swot = normalize_swot_state(swot_state)
    normalized_pest = normalize_pest_state(pest_state)
    normalized_bsc = normalize_bsc_state(bsc_state or {})

    suggestions: List[str] = []

    annual_sales = to_decimal(finance_summary.get("annual_sales", Decimal("0")))
    if annual_sales > 0:
        suggestions.append(
            "年間売上規模は"
            f"{format_amount_with_unit(annual_sales, unit, currency=currency)}です。"
            " 強みセクションでは市場シェアや価格交渉力の裏付けとして活用しましょう。"
        )

    gross_margin_ratio = to_decimal(finance_summary.get("gross_margin_ratio", Decimal("0")))
    if gross_margin_ratio > Decimal("0"):
        if gross_margin_ratio >= Decimal("0.40"):
            suggestions.append(
                f"粗利率は{format_ratio(gross_margin_ratio)}で推移しています。"
                " 高付加価値サービスやプレミアム価格戦略を強み・機会に紐づけると説得力が高まります。"
            )
        else:
            suggestions.append(
                f"粗利率が{format_ratio(gross_margin_ratio)}に留まっています。"
                " 弱みでは原価改善や値上げ交渉のアクションを検討しましょう。"
            )

    fixed_cost_ratio = to_decimal(finance_summary.get("fixed_cost_ratio", Decimal("0")))
    if fixed_cost_ratio > Decimal("0"):
        if fixed_cost_ratio >= Decimal("0.35"):
            suggestions.append(
                f"固定費比率が{format_ratio(fixed_cost_ratio)}まで上昇しています。"
                " 脅威・弱みでは固定費最適化や業務再設計の必要性を明記するのが有効です。"
            )
        elif fixed_cost_ratio >= Decimal("0.20"):
            suggestions.append(
                f"固定費比率は{format_ratio(fixed_cost_ratio)}です。"
                " BSCの内部プロセス視点と連動し、生産性向上のKPIを設定しましょう。"
            )

    technological = normalized_pest.get("technological", [])
    if technological:
        highlight = technological[0]
        suggestions.append(
            f"技術トレンドとして『{highlight}』が挙がっています。"
            " 機会にはデジタル投資や自動化による競争優位の創出を盛り込みましょう。"
        )

    political = normalized_pest.get("political", [])
    if political:
        suggestions.append(
            "政治・規制の変化が複数登録されています。脅威セクションで規制対応ロードマップを整理するとリスク対策が明確になります。"
        )

    economic = normalized_pest.get("economic", [])
    if economic:
        suggestions.append(
            "経済環境の前提は需要予測や価格設定に直結します。財務視点のKPIと連携し、シナリオ分析とセットで説明すると良いでしょう。"
        )

    learning_entries = normalized_bsc.get("learning", [])
    if learning_entries:
        suggestions.append(
            "学習・成長視点で人材育成テーマが設定されています。強みや機会の実行計画に育成ロードマップを紐づけると整合性が高まります。"
        )

    if not suggestions and any(normalized_swot.values()):
        suggestions.append(
            "SWOT入力が保存されています。PESTや財務指標と突き合わせて、各象限のアクションプランを明文化しましょう。"
        )

    return suggestions


def frames_to_strategy(frames: Mapping[str, pd.DataFrame]) -> Dict[str, Any]:
    """Convert exported frames into the strategy state structure."""

    bsc = dataframe_to_bsc(frames.get("strategy_bsc"))
    pest = dataframe_to_pest(frames.get("strategy_pest"))
    swot = dataframe_to_swot(frames.get("strategy_swot"))
    return {"bsc": bsc, "pest": pest, "swot": swot}


def has_bsc_entries(state: Mapping[str, Any]) -> bool:
    normalized = normalize_bsc_state(state)
    return any(normalized[key] for key in normalized)


def has_pest_entries(state: Mapping[str, Any]) -> bool:
    normalized = normalize_pest_state(state)
    return any(normalized[key] for key in normalized)


def has_swot_entries(state: Mapping[str, Any]) -> bool:
    normalized = normalize_swot_state(state)
    return any(normalized[key] for key in normalized)


__all__ = [
    "BSC_PERSPECTIVES",
    "PEST_DIMENSIONS",
    "SWOT_CATEGORIES",
    "default_bsc_state",
    "default_pest_state",
    "default_swot_state",
    "normalize_bsc_state",
    "normalize_pest_state",
    "normalize_swot_state",
    "bsc_to_dataframe",
    "pest_to_dataframe",
    "swot_to_dataframe",
    "dataframe_to_bsc",
    "dataframe_to_pest",
    "dataframe_to_swot",
    "build_bsc_display_frame",
    "build_pest_display",
    "build_swot_display",
    "summarize_financial_context",
    "generate_swot_suggestions",
    "frames_to_strategy",
    "has_bsc_entries",
    "has_pest_entries",
    "has_swot_entries",
]

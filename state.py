"""Utilities for managing Streamlit session state defaults and resets."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Mapping, Tuple
from uuid import uuid4

import pandas as pd
import streamlit as st

from models import (
    DEFAULT_CAPEX_PLAN,
    DEFAULT_COST_PLAN,
    DEFAULT_LOAN_SCHEDULE,
    DEFAULT_SALES_PLAN,
    DEFAULT_TAX_POLICY,
    DEFAULT_WORKING_CAPITAL,
    FinanceBundle,
)

StateFactory = Callable[[], Any]
TypeHint = type | tuple[type, ...] | None


@dataclass(frozen=True)
class StateSpec:
    """Definition of a session state entry."""

    default_factory: StateFactory
    type_hint: TypeHint
    description: str

    def create_default(self) -> Any:
        """Return a new default value for the state entry."""
        return self.default_factory()

    def is_valid(self, value: Any) -> bool:
        """Check whether *value* matches the declared type hint."""
        if self.type_hint is None:
            return True
        hints = self.type_hint if isinstance(self.type_hint, tuple) else (self.type_hint,)
        return isinstance(value, hints)


STATE_SPECS: Dict[str, StateSpec] = {
    "show_usage_guide": StateSpec(lambda: False, bool, "ヘルプ表示トグル"),
    "sensitivity_zoom_mode": StateSpec(lambda: False, bool, "感応度グラフ拡大モード"),
    "sensitivity_current": StateSpec(dict, dict, "感応度ビュー設定"),
    "kpi_history": StateSpec(dict, dict, "KPIメトリック履歴"),
    "metrics_timeline": StateSpec(list, list, "KPI推移の履歴"),
    "scenario_df": StateSpec(lambda: None, (pd.DataFrame, type(None)), "シナリオ設定データフレーム"),
    "scenario_editor": StateSpec(dict, dict, "シナリオエディタ状態"),
    "scenarios": StateSpec(list, (list, tuple, dict), "シナリオ保存データ"),
    "overrides": StateSpec(dict, dict, "金額上書き値"),
    "sidebar_step": StateSpec(lambda: "①データ入力", str, "サイドバーナビの選択ステップ"),
    "last_updated_ts": StateSpec(lambda: "", str, "最終更新タイムスタンプ"),
    "validation_status": StateSpec(lambda: "—", str, "検証ステータス表示"),
    "what_if_presets": StateSpec(dict, dict, "What-ifプリセット"),
    "what_if_scenarios": StateSpec(dict, dict, "What-ifシナリオ集合"),
    "what_if_default_quantity": StateSpec(lambda: None, (float, int, type(None)), "数量の既定値"),
    "what_if_default_customers": StateSpec(lambda: None, (float, int, type(None)), "顧客数の既定値"),
    "what_if_product_share": StateSpec(lambda: 0.6, (float, int), "製品売上比率の初期値"),
    "what_if_active": StateSpec(lambda: "A", str, "現在アクティブなWhat-ifシナリオ"),
    "sample_data_loaded": StateSpec(lambda: False, bool, "サンプルデータ適用済みフラグ"),
    "finance_raw": StateSpec(dict, dict, "財務入力フォームの生データ"),
    "finance_models": StateSpec(dict, dict, "検証済みの財務モデル"),
    "finance_settings": StateSpec(
        lambda: {
            "unit": "百万円",
            "language": "ja",
            "locale": "ja-JP",
            "currency": "JPY",
            "tax_profile": "jp_sme",
            "fte": 20.0,
            "fiscal_year": 2025,
            "fiscal_year_start_month": 4,
            "forecast_years": 3,
        },
        dict,
        "共通設定（単位・言語・FTEなど）",
    ),
    "state_backups": StateSpec(list, list, "セッションスナップショット"),
    "industry_template_state": StateSpec(dict, dict, "業種テンプレート設定"),
}


INPUT_STATE_KEYS: Tuple[str, ...] = (
    "finance_raw",
    "finance_models",
    "overrides",
    "sample_data_loaded",
    "last_updated_ts",
    "validation_status",
)

ANALYSIS_STATE_KEYS: Tuple[str, ...] = (
    "sensitivity_zoom_mode",
    "sensitivity_current",
    "kpi_history",
    "metrics_timeline",
    "scenario_df",
    "scenario_editor",
    "scenarios",
    "what_if_presets",
    "what_if_scenarios",
    "what_if_default_quantity",
    "what_if_default_customers",
    "what_if_product_share",
    "what_if_active",
)

_BACKUP_EXCLUDE_KEYS: Tuple[str, ...] = ("state_backups",)


def ensure_session_defaults(overrides: Mapping[str, Any] | None = None) -> None:
    """Populate :mod:`st.session_state` with defaults and type-validate entries."""

    overrides = overrides or {}
    for key, spec in STATE_SPECS.items():
        if key in overrides:
            st.session_state[key] = overrides[key]
            continue
        if key not in st.session_state or not spec.is_valid(st.session_state[key]):
            st.session_state[key] = spec.create_default()


def reset_session_keys(keys: Iterable[str] | None = None) -> None:
    """Reset selected state keys to their default values."""

    target_keys = list(keys) if keys is not None else list(STATE_SPECS.keys())
    for key in target_keys:
        if key in STATE_SPECS:
            st.session_state[key] = STATE_SPECS[key].create_default()
        elif key in st.session_state:
            del st.session_state[key]


def reset_app_state(preserve: Iterable[str] | None = None) -> None:
    """Clear the current session state and re-apply defaults."""

    preserved = set(preserve or [])
    for key in list(st.session_state.keys()):
        if key not in preserved:
            del st.session_state[key]
    ensure_session_defaults()


def load_finance_bundle() -> Tuple[FinanceBundle, bool]:
    """Return the validated finance bundle from session or defaults.

    Returns a tuple of ``(bundle, is_custom)`` where *is_custom* indicates
    whether the bundle originates from user-supplied inputs (``True``) or if
    the defaults had to be used (``False``).
    """

    models_state: Dict[str, object] = st.session_state.get("finance_models", {})
    required_keys = {"sales", "costs", "capex", "loans", "tax", "working_capital"}
    if required_keys.issubset(models_state.keys()):
        try:
            bundle = FinanceBundle(
                sales=models_state["sales"],
                costs=models_state["costs"],
                capex=models_state["capex"],
                loans=models_state["loans"],
                tax=models_state["tax"],
                working_capital=models_state["working_capital"],
            )
            return bundle, True
        except Exception:  # pragma: no cover - defensive guard
            pass

    default_bundle = FinanceBundle(
        sales=DEFAULT_SALES_PLAN.model_copy(deep=True),
        costs=DEFAULT_COST_PLAN.model_copy(deep=True),
        capex=DEFAULT_CAPEX_PLAN.model_copy(deep=True),
        loans=DEFAULT_LOAN_SCHEDULE.model_copy(deep=True),
        tax=DEFAULT_TAX_POLICY.model_copy(deep=True),
        working_capital=DEFAULT_WORKING_CAPITAL.model_copy(deep=True),
    )
    return default_bundle, False


def capture_session_snapshot(keys: Iterable[str] | None = None) -> Dict[str, Any]:
    """Return a deep-copied snapshot of selected session state entries."""

    target_keys = list(keys) if keys is not None else [
        key for key in STATE_SPECS.keys() if key not in _BACKUP_EXCLUDE_KEYS
    ]
    snapshot: Dict[str, Any] = {}
    for key in target_keys:
        if key in st.session_state:
            try:
                snapshot[key] = deepcopy(st.session_state[key])
            except Exception:  # pragma: no cover - fallback for uncopyable objects
                snapshot[key] = st.session_state[key]
    return snapshot


def list_state_backups() -> list[Dict[str, Any]]:
    """Return stored session backups as a list of dictionaries."""

    backups = st.session_state.get("state_backups", [])
    if isinstance(backups, list):
        return backups
    return []


def create_state_backup(label: str) -> Dict[str, Any]:
    """Create a new backup snapshot with *label* and store it in the session."""

    ensure_session_defaults()
    entry = {
        "id": str(uuid4()),
        "label": str(label).strip() or "unnamed",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot": capture_session_snapshot(),
    }
    backups = list(list_state_backups())
    backups.insert(0, entry)
    st.session_state["state_backups"] = backups[:10]
    return entry


def restore_state_backup(backup_id: str) -> bool:
    """Restore session state from the backup identified by *backup_id*."""

    for entry in list_state_backups():
        if entry.get("id") == backup_id:
            snapshot = entry.get("snapshot", {})
            reset_app_state(preserve={"state_backups"})
            for key, value in snapshot.items():
                try:
                    st.session_state[key] = deepcopy(value)
                except Exception:  # pragma: no cover - fallback for uncopyable objects
                    st.session_state[key] = value
            return True
    return False


def delete_state_backup(backup_id: str) -> bool:
    """Remove the backup identified by *backup_id* from storage."""

    backups = list(list_state_backups())
    filtered = [entry for entry in backups if entry.get("id") != backup_id]
    if len(filtered) != len(backups):
        st.session_state["state_backups"] = filtered
        return True
    return False


def reset_input_data() -> None:
    """Reset finance-related session entries to their defaults."""

    reset_session_keys(INPUT_STATE_KEYS)


def reset_analysis_parameters() -> None:
    """Reset scenario and analysis related state entries."""

    reset_session_keys(ANALYSIS_STATE_KEYS)


__all__ = [
    "StateSpec",
    "STATE_SPECS",
    "ensure_session_defaults",
    "reset_session_keys",
    "reset_app_state",
    "reset_input_data",
    "reset_analysis_parameters",
    "capture_session_snapshot",
    "list_state_backups",
    "create_state_backup",
    "restore_state_backup",
    "delete_state_backup",
    "load_finance_bundle",
]

import altair as alt
import datetime as dt
import io
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import openpyxl  # noqa: F401
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter


PAGE_TITLE = "経営計画アプリ"
PAGE_ICON = "📊"
LAYOUT = "wide"

STYLE_PATH = Path("assets/style.css")
SAMPLE_PATH = Path("assets/sample_data/plan_inputs.csv")

STR: Dict[str, str] = {
    "subtitle": "入力→検証→分析→可視化→出力をスムーズに。初めてでも迷わない設計。",
    "guide_title": "使い方（概要）",
    "guide_body": """
1. 左サイドバーの「①データ入力」で前提と数値を登録  
2. ②分析・可視化タブでKPIとチャートを確認  
3. ③レポート出力でCSV/XLSX/PNGを保存
""",
    "help_title": "❓ヘルプ",
    "help_body": """
- 必須項目は赤いバッジで表示します。入力例を参考に埋めてください。  
- サンプルデータを読み込むと一連の流れを3クリックで体験できます。  
- 感度分析タブで単価・数量・原価率を動かすとグラフとKPIが即時更新されます。  
- 出力タブからCSV/XLSX/PNGをダウンロードし、会議資料に貼り付けてください。
""",
    "sidebar_intro": "操作の流れ",
    "steps": [
        "Step1: 会社・基本設定",
        "Step2: 数値入力と検証",
        "Step3: 分析・可視化",
        "Step4: レポート出力",
    ],
    "validation_ok": "✅ バリデーションOK",
    "validation_ng": "⚠️ バリデーション未実施",
}


DEFAULTS: Dict[str, Any] = {
    "sales": 1_000_000_000,
    "fte": 20.0,
    "cogs_mat_rate": 0.25,
    "cogs_lbr_rate": 0.06,
    "cogs_out_src_rate": 0.10,
    "cogs_out_con_rate": 0.04,
    "cogs_oth_rate": 0.00,
    "opex_h_rate": 0.17,
    "opex_k_rate": 0.468,
    "opex_dep_rate": 0.006,
    "noi_misc_rate": 0.0001,
    "noi_grant_rate": 0.0,
    "noi_oth_rate": 0.0,
    "noe_int_rate": 0.0074,
    "noe_oth_rate": 0.0,
    "unit": "百万円",
    "fiscal_year": 2025,
}

DEFAULT_PLAN_DATA: Dict[str, Any] = {
    "company_name": "サンプル株式会社",
    "project_name": "FY25 成長戦略プラン",
    "fiscal_year": DEFAULTS["fiscal_year"],
    "unit": DEFAULTS["unit"],
    "unit_price": 500_000.0,
    "quantity": 2_000,
    "base_sales": DEFAULTS["sales"],
    "fte": DEFAULTS["fte"],
    "interest_bearing_debt": 180_000_000.0,
    "ratios": {
        "COGS_MAT": DEFAULTS["cogs_mat_rate"],
        "COGS_LBR": DEFAULTS["cogs_lbr_rate"],
        "COGS_OUT_SRC": DEFAULTS["cogs_out_src_rate"],
        "COGS_OUT_CON": DEFAULTS["cogs_out_con_rate"],
        "COGS_OTH": DEFAULTS["cogs_oth_rate"],
        "OPEX_H": DEFAULTS["opex_h_rate"],
        "OPEX_K": DEFAULTS["opex_k_rate"],
        "OPEX_DEP": DEFAULTS["opex_dep_rate"],
        "NOI_MISC": DEFAULTS["noi_misc_rate"],
        "NOI_GRANT": DEFAULTS["noi_grant_rate"],
        "NOI_OTH": DEFAULTS["noi_oth_rate"],
        "NOE_INT": DEFAULTS["noe_int_rate"],
        "NOE_OTH": DEFAULTS["noe_oth_rate"],
    },
}

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "A": {"label": "シナリオA（ベース）", "sales_multiplier": 1.0, "gp_adjust": 0.0, "opex_adjust": 0.0},
    "B": {"label": "シナリオB（成長+粗利改善）", "sales_multiplier": 1.08, "gp_adjust": 0.01, "opex_adjust": 0.0},
    "C": {"label": "シナリオC（コスト抑制）", "sales_multiplier": 0.97, "gp_adjust": 0.0, "opex_adjust": -0.03},
}


NONOP_DEFAULT = dict(
    noi_misc=0.0,
    noi_grant=0.0,
    noe_int=0.0,
    noe_oth=0.0,
)

ITEMS = [
    ("REV", "売上高", "売上"),
    ("COGS_MAT", "外部仕入｜材料費", "外部仕入"),
    ("COGS_LBR", "外部仕入｜労務費(外部)", "外部仕入"),
    ("COGS_OUT_SRC", "外部仕入｜外注費(専属)", "外部仕入"),
    ("COGS_OUT_CON", "外部仕入｜外注費(委託)", "外部仕入"),
    ("COGS_OTH", "外部仕入｜その他諸経費", "外部仕入"),
    ("COGS_TTL", "外部仕入｜計", "外部仕入"),
    ("GROSS", "粗利(加工高)", "粗利"),
    ("OPEX_H", "内部費用｜人件費", "内部費用"),
    ("OPEX_K", "内部費用｜経費", "内部費用"),
    ("OPEX_DEP", "内部費用｜減価償却費", "内部費用"),
    ("OPEX_TTL", "内部費用｜計", "内部費用"),
    ("OP", "営業利益", "損益"),
    ("NOI_MISC", "営業外収益｜雑収入", "営業外"),
    ("NOI_GRANT", "営業外収益｜補助金/給付金", "営業外"),
    ("NOI_OTH", "営業外収益｜その他", "営業外"),
    ("NOE_INT", "営業外費用｜支払利息", "営業外"),
    ("NOE_OTH", "営業外費用｜雑損", "営業外"),
    ("ORD", "経常利益", "損益"),
    ("BE_SALES", "損益分岐点売上高", "KPI"),
    ("PC_SALES", "一人当たり売上", "KPI"),
    ("PC_GROSS", "一人当たり粗利", "KPI"),
    ("PC_ORD", "一人当たり経常利益", "KPI"),
    ("LDR", "労働分配率", "KPI"),
]

ITEM_LABELS = {code: label for code, label, _ in ITEMS}

PLAIN_LANGUAGE = {
    "REV": "お客様から入る売上全体",
    "COGS_MAT": "主原料や仕入にかかるコスト",
    "COGS_LBR": "外部スタッフや職人さんへの人件費",
    "COGS_OUT_SRC": "専属パートナーへの外注費",
    "COGS_OUT_CON": "必要時だけ依頼するスポット外注費",
    "COGS_OTH": "物流・包材などその他の変動費",
    "COGS_TTL": "外部仕入コストの合計",
    "GROSS": "売上から原価を引いた稼ぐ力",
    "OPEX_H": "自社の人件費（給与・賞与など）",
    "OPEX_K": "オフィス費や販売促進費などの経費",
    "OPEX_DEP": "設備投資を分割計上した費用",
    "OPEX_TTL": "内部費用の合計",
    "OP": "本業だけで稼いだ利益",
    "NOI_MISC": "本業以外の雑収入",
    "NOI_GRANT": "補助金・給付金などの臨時収入",
    "NOI_OTH": "その他の営業外収益",
    "NOE_INT": "借入金などの利息支払",
    "NOE_OTH": "その他の営業外費用",
    "ORD": "金融費用も含めた最終的な利益",
    "BE_SALES": "利益がプラスに転じる売上ライン",
    "PC_SALES": "1人あたりの売上高",
    "PC_GROSS": "1人あたりの粗利",
    "PC_ORD": "1人あたりの経常利益",
    "LDR": "粗利のうち人件費に充てている割合",
}

# --- Utility functions copied from previous business logic ---

def apply_japanese_styles(wb) -> None:
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(28, max(10, max_len + 2))


def format_money_and_percent(ws, money_cols: List[int], percent_cols: List[int]) -> None:
    money_fmt = "\"¥\"#,##0;[Red]-\"¥\"#,##0"
    for c in money_cols:
        col_letter = get_column_letter(c)
        for cell in ws[col_letter][1:]:
            cell.number_format = money_fmt
    for c in percent_cols:
        col_letter = get_column_letter(c)
        for cell in ws[col_letter][1:]:
            cell.number_format = "0%"


def millions(x):
    return x / 1_000_000


def thousands(x):
    return x / 1_000


def format_money(x, unit="百万円"):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    if unit == "百万円":
        return f"{millions(x):,.0f}"
    if unit == "千円":
        return f"{thousands(x):,.0f}"
    return f"{x:,.0f}"


def summarize_plan_metrics(amounts: Dict[str, float]) -> Dict[str, float]:
    sales = float(amounts.get("REV", 0.0))
    gross = float(amounts.get("GROSS", 0.0))
    op = float(amounts.get("OP", 0.0))
    ord_val = float(amounts.get("ORD", 0.0))
    opex = float(amounts.get("OPEX_TTL", 0.0))
    cogs = float(amounts.get("COGS_TTL", sales - gross))

    def safe_ratio(num: float, den: float) -> float:
        return float(num / den) if den not in (0, None) else float("nan")

    metrics = {
        "sales": sales,
        "gross": gross,
        "op": op,
        "ord": ord_val,
        "gross_margin": safe_ratio(gross, sales),
        "op_margin": safe_ratio(op, sales),
        "ord_margin": safe_ratio(ord_val, sales),
        "cogs_ratio": safe_ratio(cogs, sales),
        "opex_ratio": safe_ratio(opex, sales),
        "labor_ratio": safe_ratio(amounts.get("OPEX_H", 0.0), gross),
        "breakeven": float(amounts.get("BE_SALES", float("nan"))),
    }
    return metrics


def format_ratio(value: float) -> str:
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return "—"
    return f"{value * 100:.1f}%"


def generate_ai_recommendations(
    metrics: Dict[str, float],
    numeric_amounts: pd.DataFrame | None,
    numeric_kpis: pd.DataFrame | None,
    unit: str,
) -> List[Dict[str, str]]:
    insights: List[Dict[str, str]] = []
    gm = metrics.get("gross_margin")
    ord_margin = metrics.get("ord_margin")
    labor_ratio = metrics.get("labor_ratio")
    be_sales = metrics.get("breakeven")
    sales = metrics.get("sales", 0.0)

    if gm is not None and math.isfinite(gm):
        if gm < 0.25:
            insights.append(
                {
                    "title": "粗利率が低位です",
                    "body": "粗利率が25%を下回っています。価格改定や高付加価値サービスの投入でマージン改善を検討しましょう。",
                    "tone": "warning",
                }
            )
        elif gm > 0.45:
            insights.append(
                {
                    "title": "粗利率はプレミアム水準",
                    "body": "粗利率が45%超と高水準です。余剰利益を投資や人材育成に再配分する余地があります。",
                    "tone": "positive",
                }
            )

    if ord_margin is not None and math.isfinite(ord_margin):
        if ord_margin < 0:
            insights.append(
                {
                    "title": "経常利益が赤字レンジ",
                    "body": "経常利益がマイナスです。固定費削減と利益率の高い案件へのシフトを緊急で検討してください。",
                    "tone": "alert",
                }
            )
        elif ord_margin < 0.05:
            insights.append(
                {
                    "title": "利益率の底上げが必要",
                    "body": "経常利益率が5%未満です。販売単価の引き上げや高粗利商品の比率向上が改善策になります。",
                    "tone": "warning",
                }
            )
        elif ord_margin > 0.12:
            insights.append(
                {
                    "title": "利益創出力は堅調",
                    "body": "経常利益率が12%超と十分な稼ぐ力があります。積極投資フェーズに移行しても耐性があります。",
                    "tone": "positive",
                }
            )

    if labor_ratio is not None and math.isfinite(labor_ratio):
        if labor_ratio > 0.65:
            insights.append(
                {
                    "title": "人件費の比率が高い",
                    "body": "労働分配率が65%を超えています。生産性向上策やアウトソースの活用でコストを平準化しましょう。",
                    "tone": "warning",
                }
            )
        elif labor_ratio < 0.45:
            insights.append(
                {
                    "title": "人材投資の余地あり",
                    "body": "労働分配率が45%未満です。人材強化やインセンティブ設計に投資し、組織力を底上げするチャンスです。",
                    "tone": "positive",
                }
            )

    if be_sales and sales and math.isfinite(be_sales):
        be_ratio = be_sales / sales if sales else float("nan")
        if math.isfinite(be_ratio) and be_ratio > 0.95:
            insights.append(
                {
                    "title": "損益分岐点が売上に接近",
                    "body": "損益分岐点売上がほぼフル稼働の水準です。固定費の圧縮や粗利率改善で安全余裕を確保しましょう。",
                    "tone": "alert",
                }
            )
        elif math.isfinite(be_ratio) and be_ratio < 0.75:
            insights.append(
                {
                    "title": "損益分岐点に余裕あり",
                    "body": "損益分岐点が売上の75%未満で、収益構造に安全余裕があります。成長投資のアクセルを踏める状態です。",
                    "tone": "positive",
                }
            )

    if numeric_amounts is not None and not numeric_amounts.empty:
        value_cols = [c for c in numeric_amounts.columns if c != "項目"]
        if len(value_cols) >= 2 and "ORD" in numeric_amounts.index:
            base_col = value_cols[0]
            base_ord = float(numeric_amounts.loc["ORD", base_col])
            best_col = None
            best_diff = 0.0
            for col in value_cols[1:]:
                diff = float(numeric_amounts.loc["ORD", col]) - base_ord
                if diff > best_diff:
                    best_diff = diff
                    best_col = col
            if best_col and best_diff > 0:
                insights.append(
                    {
                        "title": f"最有力シナリオ：{best_col}",
                        "body": f"ベース比で経常利益を{format_money(best_diff, unit)} {unit}押し上げます。主要ドライバを戦略課題に落とし込みましょう。",
                        "tone": "positive",
                    }
                )

    if not insights:
        insights.append(
            {
                "title": "データ点検が完了しました",
                "body": "大きな懸念は検出されませんでした。引き続きシナリオ比較と感応度を活用し、計画をチューニングしてください。",
                "tone": "positive",
            }
        )

    return insights[:5]


def detect_anomalies_in_plan(
    numeric_amounts: pd.DataFrame | None,
    numeric_kpis: pd.DataFrame | None,
    unit: str,
    metrics: Dict[str, float],
) -> pd.DataFrame:
    cols = ["カテゴリ", "対象", "値", "判定", "コメント"]
    if numeric_amounts is None or numeric_amounts.empty:
        return pd.DataFrame(columns=cols)

    value_cols = [c for c in numeric_amounts.columns if c != "項目"]
    if not value_cols:
        return pd.DataFrame(columns=cols)

    base_col = value_cols[0]
    anomalies: List[Dict[str, str]] = []

    sales = metrics.get("sales", 0.0)
    base_ord = metrics.get("ord", 0.0)
    base_op = metrics.get("op", 0.0)
    base_gross = metrics.get("gross", 0.0)
    be_sales = metrics.get("breakeven", float("nan"))

    def record(category: str, target: str, value: str, judgement: str, comment: str) -> None:
        anomalies.append({"カテゴリ": category, "対象": target, "値": value, "判定": judgement, "コメント": comment})

    if base_gross <= 0:
        record("損益", "粗利（目標）", f"{format_money(base_gross, unit)} {unit}", "🚨 粗利が不足", "売上より費用が先行しています。可変費率の再点検が必要です。")
    if base_op < 0:
        record("損益", "営業利益（目標）", f"{format_money(base_op, unit)} {unit}", "🚨 赤字リスク", "営業利益がマイナスです。固定費の削減や高粗利案件へのシフトを優先してください。")
    if base_ord < 0:
        record("損益", "経常利益（目標）", f"{format_money(base_ord, unit)} {unit}", "🚨 経常赤字", "営業外損益も含め赤字レンジです。財務・本業双方のてこ入れが求められます。")

    gm = metrics.get("gross_margin")
    if gm is not None and math.isfinite(gm) and gm < 0.2:
        record("利益率", "粗利率", format_ratio(gm), "⚠️ マージン低下", "粗利率が20%を割り込んでいます。価格戦略や原価低減を検討してください。")

    if numeric_kpis is not None and not numeric_kpis.empty and "LDR" in numeric_kpis.index:
        ldr_value = float(numeric_kpis.loc["LDR", base_col])
        if math.isfinite(ldr_value) and ldr_value > 0.7:
            record("人件費", "労働分配率（目標）", format_ratio(ldr_value), "⚠️ 人件費過多", "人件費比率が高すぎます。工数マネジメントや外注活用でバランスを取りましょう。")

    cogs_ratio = metrics.get("cogs_ratio")
    if cogs_ratio is not None and math.isfinite(cogs_ratio) and cogs_ratio > 0.8:
        record("コスト構造", "外部仕入比率", format_ratio(cogs_ratio), "⚠️ コスト高止まり", "仕入費用が売上の80%超です。サプライヤー交渉やポートフォリオ見直しが必要です。")

    if be_sales and sales and math.isfinite(be_sales) and be_sales > sales * 0.95:
        record("安全余裕", "損益分岐点売上", f"{format_money(be_sales, unit)} {unit}", "⚠️ 余裕が僅少", "損益分岐点が現計画売上の95%超です。固定費圧縮で安全マージンを確保しましょう。")

    if numeric_amounts is not None and "ORD" in numeric_amounts.index and len(value_cols) > 1:
        base_ord_value = float(numeric_amounts.loc["ORD", base_col])
        baseline = max(abs(base_ord_value), sales * 0.02, 1_000_000.0)
        for col in value_cols[1:]:
            scn_value = float(numeric_amounts.loc["ORD", col])
            diff = scn_value - base_ord_value
            if diff <= -0.5 * baseline:
                record(
                    "シナリオ",
                    f"{col}｜経常利益",
                    f"{format_money(scn_value, unit)} {unit}",
                    "🚨 大幅悪化",
                    f"ベース比で{format_money(abs(diff), unit)} {unit}の減益です。前提条件の見直しが必要です。",
                )
            elif diff >= 0.5 * baseline:
                record(
                    "シナリオ",
                    f"{col}｜経常利益",
                    f"{format_money(scn_value, unit)} {unit}",
                    "✅ 大幅改善",
                    f"ベース比で{format_money(diff, unit)} {unit}増益です。実現可能性と投資アクションを検証しましょう。",
                )

    if numeric_kpis is not None and not numeric_kpis.empty and "LDR" in numeric_kpis.index and len(value_cols) > 1:
        for col in value_cols[1:]:
            ldr = float(numeric_kpis.loc["LDR", col])
            if math.isfinite(ldr) and ldr > 0.75:
                record(
                    "人件費",
                    f"{col}｜労働分配率",
                    format_ratio(ldr),
                    "⚠️ 人件費過重",
                    "シナリオ適用時に人件費比率が75%を超えます。追加施策での吸収が必要です。",
                )

    if not anomalies:
        return pd.DataFrame(columns=cols)

    return pd.DataFrame(anomalies, columns=cols)


class PlanConfig:
    def __init__(self, base_sales: float, fte: float, unit: str) -> None:
        self.base_sales = base_sales
        self.fte = max(0.0001, fte)
        self.unit = unit
        self.items: Dict[str, Dict[str, float]] = {}

    def set_rate(self, code: str, rate: float, rate_base: str = "sales") -> None:
        self.items[code] = {"method": "rate", "value": float(rate), "rate_base": rate_base}

    def set_amount(self, code: str, amount: float) -> None:
        self.items[code] = {"method": "amount", "value": float(amount), "rate_base": "fixed"}

    def clone(self) -> "PlanConfig":
        c = PlanConfig(self.base_sales, self.fte, self.unit)
        c.items = {k: v.copy() for k, v in self.items.items()}
        return c


def compute(plan: PlanConfig, sales_override: float | None = None, amount_overrides: Dict[str, float] | None = None) -> Dict[str, float]:
    S = float(plan.base_sales if sales_override is None else sales_override)
    amt = {code: 0.0 for code, *_ in ITEMS}
    amt["REV"] = S

    def line_amount(code, gross_guess):
        cfg = plan.items.get(code, None)
        if amount_overrides and code in amount_overrides:
            return float(amount_overrides[code])
        if cfg is None:
            return 0.0
        if cfg["method"] == "amount":
            return float(cfg["value"])
        r = float(cfg["value"])
        base = cfg.get("rate_base", "sales")
        if base == "sales":
            return S * r
        if base == "gross":
            return max(0.0, gross_guess) * r
        if base == "fixed":
            return r
        return S * r

    cogs_codes = ["COGS_MAT", "COGS_LBR", "COGS_OUT_SRC", "COGS_OUT_CON", "COGS_OTH"]
    sales_based_cogs = 0.0
    for code in cogs_codes:
        cfg = plan.items.get(code)
        if cfg and cfg["method"] == "rate" and cfg.get("rate_base", "sales") == "sales":
            sales_based_cogs += S * float(cfg["value"])
        elif cfg and cfg["method"] == "amount":
            sales_based_cogs += float(cfg["value"])

    gross = S - sales_based_cogs
    for _ in range(5):
        cogs = 0.0
        for code in cogs_codes:
            cogs += max(0.0, line_amount(code, gross))
        gross_new = S - cogs
        if abs(gross_new - gross) < 1e-6:
            gross = gross_new
            break
        gross = gross_new

    cogs_total = 0.0
    for code in cogs_codes:
        val = max(0.0, line_amount(code, gross))
        amt[code] = val
        cogs_total += val
    amt["COGS_TTL"] = cogs_total
    amt["GROSS"] = S - cogs_total

    opex_codes = ["OPEX_H", "OPEX_K", "OPEX_DEP"]
    opex_total = 0.0
    for code in opex_codes:
        val = max(0.0, line_amount(code, amt["GROSS"]))
        amt[code] = val
        opex_total += val
    amt["OPEX_TTL"] = opex_total

    amt["OP"] = amt["GROSS"] - amt["OPEX_TTL"]

    noi_codes = ["NOI_MISC", "NOI_GRANT", "NOI_OTH"]
    noe_codes = ["NOE_INT", "NOE_OTH"]
    for code in noi_codes + noe_codes:
        val = max(0.0, line_amount(code, amt["GROSS"]))
        amt[code] = val

    amt["ORD"] = amt["OP"] + (amt["NOI_MISC"] + amt["NOI_GRANT"] + amt["NOI_OTH"]) - (amt["NOE_INT"] + amt["NOE_OTH"])

    var_cost = 0.0
    for code in cogs_codes + opex_codes + noi_codes + noe_codes:
        cfg = plan.items.get(code)
        if cfg and cfg["method"] == "rate" and cfg.get("rate_base", "sales") in ("sales", "gross"):
            if cfg.get("rate_base") == "gross":
                g_ratio = amt["GROSS"] / S if S > 0 else 0.0
                var_cost += S * (cfg["value"] * g_ratio)
            else:
                var_cost += S * cfg["value"]

    fixed_cost = 0.0
    for code in cogs_codes + opex_codes + noi_codes + noe_codes:
        cfg = plan.items.get(code)
        if cfg and cfg["method"] == "amount":
            fixed_cost += cfg["value"]
        elif cfg and cfg.get("rate_base") == "fixed":
            if cfg["method"] == "rate":
                fixed_cost += cfg["value"]
    cm_ratio = 1.0 - (var_cost / S if S > 0 else 0.0)
    if cm_ratio <= 0:
        be_sales = float("inf")
    else:
        be_sales = fixed_cost / cm_ratio
    amt["BE_SALES"] = be_sales

    fte = max(0.0001, plan.fte)
    amt["PC_SALES"] = amt["REV"] / fte
    amt["PC_GROSS"] = amt["GROSS"] / fte
    amt["PC_ORD"] = amt["ORD"] / fte
    amt["LDR"] = (amt["OPEX_H"] / amt["GROSS"]) if amt["GROSS"] > 0 else np.nan

    return amt

# --- Helper utilities specific to the refactored UI ---

def load_local_css() -> None:
    if STYLE_PATH.exists():
        st.markdown(f"<style>{STYLE_PATH.read_text()}</style>", unsafe_allow_html=True)


@st.cache_data
def load_sample_plan(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return DEFAULT_PLAN_DATA
    df = pd.read_csv(path)
    plan = DEFAULT_PLAN_DATA.copy()
    plan["ratios"] = plan["ratios"].copy()
    for _, row in df.iterrows():
        category = row.get("category", "")
        key = row.get("key", "")
        value = row.get("value", "")
        if category == "company":
            if key in {"company_name", "project_name", "unit"}:
                plan[key] = str(value)
            elif key in {"fiscal_year"}:
                plan[key] = int(value)
            elif key in {"interest_bearing_debt"}:
                plan[key] = float(value)
        elif category == "sales":
            if key in {"unit_price", "quantity", "base_sales", "fte"}:
                plan[key] = float(value)
        elif category == "ratios" and key in plan["ratios"]:
            plan["ratios"][key] = float(value)
    plan["base_sales"] = float(plan.get("unit_price", 0.0)) * float(plan.get("quantity", 0.0)) or plan.get("base_sales", DEFAULTS["sales"])
    return plan


def init_session_state() -> None:
    if "plan_data" not in st.session_state:
        st.session_state["plan_data"] = load_sample_plan(SAMPLE_PATH) if SAMPLE_PATH.exists() else DEFAULT_PLAN_DATA.copy()
    else:
        data = st.session_state["plan_data"]
        if "ratios" not in data:
            data["ratios"] = DEFAULT_PLAN_DATA["ratios"].copy()
    if "validation" not in st.session_state:
        st.session_state["validation"] = {"status": "NG", "messages": []}
    if "step" not in st.session_state:
        st.session_state["step"] = 1
    if "last_updated" not in st.session_state:
        st.session_state["last_updated"] = dt.datetime.now()
    if "scenario" not in st.session_state:
        st.session_state["scenario"] = "A"
    if "log" not in st.session_state:
        st.session_state["log"] = []
    if "baseline_metrics" not in st.session_state:
        plan = build_plan_config(DEFAULT_PLAN_DATA)
        base_amounts = compute(plan)
        st.session_state["baseline_metrics"] = summarize_plan_metrics(base_amounts)


def add_log(message: str) -> None:
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state.setdefault("log", []).append(f"[{timestamp}] {message}")


def build_plan_config(plan_data: Dict[str, Any]) -> PlanConfig:
    cfg = PlanConfig(plan_data.get("base_sales", DEFAULTS["sales"]), plan_data.get("fte", DEFAULTS["fte"]), plan_data.get("unit", DEFAULTS["unit"]))
    for code, rate in plan_data.get("ratios", {}).items():
        cfg.set_rate(code, float(rate), "sales")
    return cfg


def compute_plan_outputs(plan_data: Dict[str, Any], *, sales_multiplier: float = 1.0, gp_adjust: float = 0.0, opex_adjust: float = 0.0) -> Tuple[Dict[str, float], Dict[str, float]]:
    cfg = build_plan_config(plan_data)
    cfg.base_sales = cfg.base_sales * sales_multiplier
    if gp_adjust != 0.0:
        ratios = plan_data.get("ratios", {})
        adj = ratios.get("COGS_OTH", 0.0) - gp_adjust
        cfg.set_rate("COGS_OTH", max(0.0, adj), "sales")
    if opex_adjust != 0.0:
        ratios = plan_data.get("ratios", {})
        cfg.set_rate("OPEX_K", max(0.0, ratios.get("OPEX_K", 0.0) * (1 + opex_adjust)), "sales")
    amounts = compute(cfg)
    metrics = summarize_plan_metrics(amounts)
    return amounts, metrics


def plan_to_dataframe(amounts: Dict[str, float], unit: str) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    revenue = amounts.get("REV", 0.0)
    for code, label, group in ITEMS:
        if code not in amounts:
            continue
        value = float(amounts[code])
        ratio = value / revenue if revenue and code not in {"PC_SALES", "PC_GROSS", "PC_ORD", "LDR", "BE_SALES"} else np.nan
        rows.append(
            {
                "カテゴリ": group,
                "項目": label,
                "金額": value,
                "売上比率": ratio,
                "説明": PLAIN_LANGUAGE.get(code, "—"),
            }
        )
    df = pd.DataFrame(rows)
    df = df.sort_values(["カテゴリ", "項目"]).reset_index(drop=True)
    return df


def compute_scenarios(plan_data: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    data_rows = []
    kpi_rows = []
    for key, spec in SCENARIOS.items():
        amounts, metrics = compute_plan_outputs(
            plan_data,
            sales_multiplier=spec.get("sales_multiplier", 1.0),
            gp_adjust=spec.get("gp_adjust", 0.0),
            opex_adjust=spec.get("opex_adjust", 0.0),
        )
        label = spec.get("label", key)
        data_rows.append(
            {
                "シナリオ": label,
                "売上高": amounts.get("REV", 0.0),
                "粗利": amounts.get("GROSS", 0.0),
                "営業利益": amounts.get("OP", 0.0),
                "経常利益": amounts.get("ORD", 0.0),
                "損益分岐点売上": amounts.get("BE_SALES", 0.0),
            }
        )
        kpi_rows.append(
            {
                "シナリオ": label,
                "粗利率": metrics.get("gross_margin", float("nan")),
                "営業利益率": metrics.get("op_margin", float("nan")),
                "経常利益率": metrics.get("ord_margin", float("nan")),
                "労働分配率": metrics.get("labor_ratio", float("nan")),
            }
        )
    summary_df = pd.DataFrame(data_rows)
    kpi_df = pd.DataFrame(kpi_rows)
    return summary_df, kpi_df


def validation_badge() -> str:
    status = st.session_state.get("validation", {}).get("status", "NG")
    if status == "OK":
        return STR["validation_ok"]
    return STR["validation_ng"]


def required_label(label: str) -> str:
    return f"<div class='field-label'><span>{label}</span><span class='badge-required'>必須</span></div>"


def optional_label(label: str) -> str:
    return f"<div class='field-label'><span>{label}</span></div>"


def validate_plan(plan_data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}
    if not plan_data.get("company_name"):
        errors["company_name"] = "会社名を入力してください。"
    if not plan_data.get("project_name"):
        errors["project_name"] = "プロジェクト名を入力してください。"
    if plan_data.get("unit_price", 0.0) <= 0:
        errors["unit_price"] = "売上単価は正の数で入力してください。"
    if plan_data.get("quantity", 0.0) <= 0:
        errors["quantity"] = "販売数量は1以上で入力してください。"
    plan_data["base_sales"] = plan_data.get("unit_price", 0.0) * plan_data.get("quantity", 0.0)
    if plan_data.get("base_sales", 0.0) <= 0:
        errors["unit_price"] = "売上高が0以下です。単価と数量を見直してください。"
    if plan_data.get("fte", 0.0) <= 0:
        errors["fte"] = "人員数は1以上で入力してください。"
    if plan_data.get("interest_bearing_debt", 0.0) < 0:
        errors["interest_bearing_debt"] = "有利子負債は0以上で入力してください。"
    ratios = plan_data.get("ratios", {})
    for code, rate in ratios.items():
        if rate < 0:
            errors[code] = f"{ITEM_LABELS.get(code, code)}は0以上で入力してください。"
    cogs_sum = sum(ratios.get(code, 0.0) for code in ["COGS_MAT", "COGS_LBR", "COGS_OUT_SRC", "COGS_OUT_CON", "COGS_OTH"])
    if cogs_sum >= 1.0:
        errors["COGS_OTH"] = "原価率の合計が100%を超えています。"
    return len(errors) == 0, errors


def render_status_line() -> None:
    last_updated = st.session_state.get("last_updated", dt.datetime.now())
    status_html = f"<div class='status-line'>最終更新：{last_updated.strftime('%Y-%m-%d %H:%M')} ｜ {validation_badge()}</div>"
    st.markdown(status_html, unsafe_allow_html=True)


def render_header() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)
    load_local_css()
    render_status_line()
    left, right = st.columns([0.75, 0.25])
    with left:
        st.title(PAGE_TITLE)
        st.caption(STR["subtitle"])
    with right:
        if st.button("使い方ガイド"):
            with st.expander(STR["guide_title"], expanded=True):
                st.markdown(STR["guide_body"])


def render_help() -> None:
    with st.expander(STR["help_title"], expanded=False):
        st.markdown(STR["help_body"])


def render_sidebar() -> None:
    with st.sidebar:
        st.header("ナビゲーション")
        st.markdown(f"### {STR['sidebar_intro']}")
        for idx, text in enumerate(STR["steps"], start=1):
            active = "active-step" if st.session_state.get("step", 1) == idx else ""
            st.markdown(f"<div class='sidebar-step {active}'>・{text}</div>", unsafe_allow_html=True)
        st.divider()
        if st.button("サンプルデータを読み込む", use_container_width=True):
            st.session_state["plan_data"] = load_sample_plan(SAMPLE_PATH)
            st.session_state["step"] = 2
            st.session_state["validation"] = {"status": "NG", "messages": ["サンプルを読み込みました。"]}
            st.session_state["last_updated"] = dt.datetime.now()
            add_log("サンプルデータを読み込み")
            st.experimental_rerun()
        if st.button("入力をリセット", use_container_width=True):
            st.session_state.clear()
            init_session_state()
            add_log("入力を初期化")
            st.experimental_rerun()


def update_validation(status: bool, messages: List[str]) -> None:
    st.session_state["validation"] = {"status": "OK" if status else "NG", "messages": messages}


def render_step_navigation() -> None:
    step = st.session_state.get("step", 1)
    cols = st.columns([0.2, 0.6, 0.2])
    with cols[0]:
        if step > 1 and st.button("◀ 戻る", use_container_width=True):
            st.session_state["step"] = max(1, step - 1)
            st.experimental_rerun()
    with cols[1]:
        st.markdown(f"<div class='step-indicator'>STEP {step}/4</div>", unsafe_allow_html=True)
    with cols[2]:
        if step < 4 and st.button("次へ ▶", use_container_width=True):
            if step == 2 and st.session_state.get("validation", {}).get("status") != "OK":
                st.warning("検証が完了していません。フォームで「検証して保存」を実行してください。")
            else:
                st.session_state["step"] = min(4, step + 1)
                st.experimental_rerun()


def render_step1(plan_data: Dict[str, Any]) -> None:
    st.markdown("### Step1: 会社・基本設定")
    with st.form("step1_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(required_label("会社名"), unsafe_allow_html=True)
            company_name = st.text_input(
                "company_name",
                value=plan_data.get("company_name", ""),
                placeholder="例：ネクストテック株式会社",
                label_visibility="collapsed",
            )
            st.markdown(required_label("プロジェクト名"), unsafe_allow_html=True)
            project_name = st.text_input(
                "project_name",
                value=plan_data.get("project_name", ""),
                placeholder="例：FY25 中期経営計画",
                label_visibility="collapsed",
            )
            st.markdown(optional_label("有利子負債（円）"), unsafe_allow_html=True)
            interest_bearing_debt = st.number_input(
                "interest_bearing_debt",
                value=float(plan_data.get("interest_bearing_debt", 0.0)),
                min_value=0.0,
                step=1_000_000.0,
                help="例：150000000",
                label_visibility="collapsed",
            )
        with col2:
            st.markdown(optional_label("会計年度"), unsafe_allow_html=True)
            fiscal_year = st.number_input(
                "fiscal_year",
                value=int(plan_data.get("fiscal_year", DEFAULTS["fiscal_year"])),
                step=1,
                format="%d",
                label_visibility="collapsed",
            )
            st.markdown(optional_label("表示単位"), unsafe_allow_html=True)
            unit_options = ["百万円", "千円", "円"]
            unit = st.selectbox(
                "unit",
                options=unit_options,
                index=unit_options.index(plan_data.get("unit", "百万円")) if plan_data.get("unit", "百万円") in unit_options else 0,
                label_visibility="collapsed",
            )
            st.markdown(optional_label("メモ"), unsafe_allow_html=True)
            st.text_area("memo", value="入力値を更新すると右上の最終更新に反映されます。", height=100, label_visibility="collapsed")
        submitted = st.form_submit_button("保存して次へ")
    if submitted:
        plan_data.update(
            {
                "company_name": company_name.strip(),
                "project_name": project_name.strip(),
                "interest_bearing_debt": float(interest_bearing_debt),
                "fiscal_year": int(fiscal_year),
                "unit": unit,
            }
        )
        st.session_state["plan_data"] = plan_data
        st.session_state["step"] = 2
        st.session_state["last_updated"] = dt.datetime.now()
        add_log("基本設定を更新")
        st.experimental_rerun()

def render_rate_inputs(ratios: Dict[str, float], errors: Dict[str, str]) -> None:
    st.markdown("#### 変動費（外部仕入）")
    cols = st.columns(3)
    for idx, code in enumerate(["COGS_MAT", "COGS_LBR", "COGS_OUT_SRC"]):
        with cols[idx]:
            st.markdown(required_label(ITEM_LABELS[code]), unsafe_allow_html=True)
            value = st.number_input(
                f"{code}_input",
                value=float(ratios.get(code, 0.0)),
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                help=PLAIN_LANGUAGE.get(code, ""),
                label_visibility="collapsed",
            )
            ratios[code] = value
            if code in errors:
                st.error(errors[code])
    cols = st.columns(2)
    for idx, code in enumerate(["COGS_OUT_CON", "COGS_OTH"]):
        with cols[idx]:
            st.markdown(required_label(ITEM_LABELS[code]), unsafe_allow_html=True)
            value = st.number_input(
                f"{code}_input",
                value=float(ratios.get(code, 0.0)),
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                help=PLAIN_LANGUAGE.get(code, ""),
                label_visibility="collapsed",
            )
            ratios[code] = value
            if code in errors:
                st.error(errors[code])

    st.markdown("#### 固定費（内部費用）")
    cols = st.columns(3)
    for idx, code in enumerate(["OPEX_H", "OPEX_K", "OPEX_DEP"]):
        with cols[idx]:
            st.markdown(required_label(ITEM_LABELS[code]), unsafe_allow_html=True)
            value = st.number_input(
                f"{code}_input",
                value=float(ratios.get(code, 0.0)),
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                help=PLAIN_LANGUAGE.get(code, ""),
                label_visibility="collapsed",
            )
            ratios[code] = value
            if code in errors:
                st.error(errors[code])

    st.markdown("#### 営業外収支")
    cols = st.columns(3)
    for idx, code in enumerate(["NOI_MISC", "NOI_GRANT", "NOI_OTH"]):
        with cols[idx]:
            st.markdown(optional_label(ITEM_LABELS[code]), unsafe_allow_html=True)
            value = st.number_input(
                f"{code}_input",
                value=float(ratios.get(code, 0.0)),
                min_value=0.0,
                max_value=1.0,
                step=0.001,
                help=PLAIN_LANGUAGE.get(code, ""),
                label_visibility="collapsed",
            )
            ratios[code] = value
    cols = st.columns(2)
    for idx, code in enumerate(["NOE_INT", "NOE_OTH"]):
        with cols[idx]:
            st.markdown(optional_label(ITEM_LABELS[code]), unsafe_allow_html=True)
            value = st.number_input(
                f"{code}_input",
                value=float(ratios.get(code, 0.0)),
                min_value=0.0,
                max_value=1.0,
                step=0.001,
                help=PLAIN_LANGUAGE.get(code, ""),
                label_visibility="collapsed",
            )
            ratios[code] = value


def render_step2(plan_data: Dict[str, Any]) -> None:
    st.markdown("### Step2: 数値入力と検証")
    ratios = plan_data.setdefault("ratios", {}).copy()
    with st.form("step2_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(required_label("売上単価（円、税抜）"), unsafe_allow_html=True)
            unit_price = st.number_input(
                "unit_price",
                min_value=0.0,
                value=float(plan_data.get("unit_price", 0.0)),
                step=1000.0,
                help="例：500000",
                label_visibility="collapsed",
            )
            st.markdown(required_label("販売数量（月間）"), unsafe_allow_html=True)
            quantity = st.number_input(
                "quantity",
                min_value=0.0,
                value=float(plan_data.get("quantity", 0.0)),
                step=10.0,
                help="例：2000",
                label_visibility="collapsed",
            )
        with col2:
            st.markdown(required_label("人員数（FTE）"), unsafe_allow_html=True)
            fte = st.number_input(
                "fte",
                min_value=0.0,
                value=float(plan_data.get("fte", 0.0)),
                step=0.5,
                help="例：20",
                label_visibility="collapsed",
            )
            st.markdown(optional_label("参考メモ"), unsafe_allow_html=True)
            st.text_area("note_step2", value="入力後に下の検証ボタンを押してください。", height=120, label_visibility="collapsed")
        with col3:
            estimated_sales = unit_price * quantity
            st.metric("試算売上高", f"¥{estimated_sales:,.0f}")
            st.metric("FTE当たり売上", f"¥{(estimated_sales / fte) if fte else 0:,.0f}")
            st.caption("※人員数に応じた生産性の目線です。")

        st.divider()
        render_rate_inputs(ratios, {})
        submitted = st.form_submit_button("検証して保存")

    if submitted:
        plan_data.update(
            {
                "unit_price": float(unit_price),
                "quantity": float(quantity),
                "fte": float(fte),
                "ratios": ratios,
            }
        )
        valid, errors = validate_plan(plan_data)
        if not valid:
            update_validation(False, list(errors.values()))
            st.session_state["plan_data"] = plan_data
            st.warning("入力値にエラーがあります。赤枠の項目を修正してください。")
            render_rate_inputs(ratios, errors)
            return
        with st.status("検証中...", expanded=True) as status:
            status.write("数値チェックを実行しています...")
            update_validation(True, ["入力内容の検証が完了しました。"])
            plan_data["base_sales"] = plan_data.get("unit_price", 0.0) * plan_data.get("quantity", 0.0)
            st.session_state["plan_data"] = plan_data
            st.session_state["last_updated"] = dt.datetime.now()
            add_log("数値入力を検証")
            status.update(state="complete", label="検証完了")
        st.session_state["step"] = 3
        st.experimental_rerun()

@st.cache_data
def get_baseline_amounts() -> Dict[str, float]:
    cfg = build_plan_config(DEFAULT_PLAN_DATA)
    return compute(cfg)

def unit_divisor(unit: str) -> float:
    if unit == "百万円":
        return 1_000_000
    if unit == "千円":
        return 1_000
    return 1.0


def format_currency_column(unit: str) -> st.column_config.NumberColumn:
    fmt = "¥{:,}"
    return st.column_config.NumberColumn(
        "金額",
        format=fmt,
        help="金額は表示単位に応じて丸めています。",
    )


def format_ratio_column() -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn("売上比率", format="%.1f%%")


def build_numeric_tables(plan_data: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    amount_rows: Dict[str, Dict[str, Any]] = {}
    kpi_rows: Dict[str, Dict[str, Any]] = {}
    for key, spec in SCENARIOS.items():
        label = spec.get("label", key)
        amounts, metrics = compute_plan_outputs(
            plan_data,
            sales_multiplier=spec.get("sales_multiplier", 1.0),
            gp_adjust=spec.get("gp_adjust", 0.0),
            opex_adjust=spec.get("opex_adjust", 0.0),
        )
        for code in ["REV", "GROSS", "OP", "ORD", "BE_SALES"]:
            row = amount_rows.setdefault(code, {"項目": ITEM_LABELS.get(code, code)})
            row[label] = amounts.get(code, 0.0)
        ldr = metrics.get("labor_ratio", float("nan"))
        kpi_rows.setdefault("LDR", {"項目": ITEM_LABELS.get("LDR", "労働分配率")})[label] = ldr
    amount_df = pd.DataFrame.from_dict(amount_rows, orient="index")
    kpi_df = pd.DataFrame.from_dict(kpi_rows, orient="index")
    return amount_df, kpi_df

def compute_additional_metrics(amounts: Dict[str, float], plan_data: Dict[str, Any]) -> Tuple[float, float]:
    ord_value = float(amounts.get("ORD", 0.0))
    depreciation = float(amounts.get("OPEX_DEP", 0.0))
    interest = float(amounts.get("NOE_INT", 0.0))
    fcf = ord_value + depreciation - interest
    debt = float(plan_data.get("interest_bearing_debt", 0.0))
    if fcf <= 0:
        debt_years = float("inf")
    else:
        debt_years = debt / fcf
    return fcf, debt_years

def render_summary_tab(
    plan_data: Dict[str, Any],
    scenario_summary: pd.DataFrame,
    numeric_amounts: pd.DataFrame,
    numeric_kpis: pd.DataFrame,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    unit = plan_data.get("unit", "百万円")
    scenario_key = st.session_state.get("scenario", "A")
    scenario_key = st.radio(
        "シナリオ選択",
        list(SCENARIOS.keys()),
        index=list(SCENARIOS.keys()).index(scenario_key) if scenario_key in SCENARIOS else 0,
        format_func=lambda x: SCENARIOS[x]["label"],
        horizontal=True,
        key="scenario",
    )
    spec = SCENARIOS[scenario_key]
    amounts, metrics = compute_plan_outputs(
        plan_data,
        sales_multiplier=spec.get("sales_multiplier", 1.0),
        gp_adjust=spec.get("gp_adjust", 0.0),
        opex_adjust=spec.get("opex_adjust", 0.0),
    )
    baseline_amounts = get_baseline_amounts()
    baseline_metrics = summarize_plan_metrics(baseline_amounts)

    fcf, debt_years = compute_additional_metrics(amounts, plan_data)
    base_fcf, base_debt_years = compute_additional_metrics(baseline_amounts, DEFAULT_PLAN_DATA)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric(
        "売上高",
        f"¥{amounts.get('REV', 0.0):,.0f}",
        delta=f"¥{amounts.get('REV', 0.0) - baseline_amounts.get('REV', 0.0):,.0f}",
    )
    m2.metric(
        "粗利率",
        format_ratio(metrics.get("gross_margin")),
        delta=f"{(metrics.get('gross_margin', 0.0) - baseline_metrics.get('gross_margin', 0.0)) * 100:.1f}pt",
    )
    m3.metric(
        "営業利益",
        f"¥{amounts.get('OP', 0.0):,.0f}",
        delta=f"¥{amounts.get('OP', 0.0) - baseline_amounts.get('OP', 0.0):,.0f}",
    )
    m4.metric(
        "FCF（注目）",
        f"¥{fcf:,.0f}",
        delta=f"¥{fcf - base_fcf:,.0f}",
    )
    debt_label = "債務償還年数（注目）"
    if math.isfinite(debt_years):
        debt_value = f"{debt_years:.1f}年"
        debt_delta = base_debt_years - debt_years if math.isfinite(base_debt_years) else float("nan")
        delta_text = f"{debt_delta:+.1f}年" if math.isfinite(debt_delta) else "—"
    else:
        debt_value = "∞"
        delta_text = "—"
    m5.metric(debt_label, debt_value, delta=delta_text)

    divisor = unit_divisor(unit)
    summary_display = scenario_summary.copy()
    for col in ["売上高", "粗利", "営業利益", "経常利益", "損益分岐点売上"]:
        summary_display[col] = summary_display[col] / divisor
    st.dataframe(
        summary_display,
        use_container_width=True,
        column_config={
            "売上高": st.column_config.NumberColumn("売上高", format="{:,}", help="表示単位で丸めています。"),
            "粗利": st.column_config.NumberColumn("粗利", format="{:,}"),
            "営業利益": st.column_config.NumberColumn("営業利益", format="{:,}"),
            "経常利益": st.column_config.NumberColumn("経常利益", format="{:,}"),
            "損益分岐点売上": st.column_config.NumberColumn("損益分岐点売上", format="{:,}"),
        },
        hide_index=True,
    )

    st.markdown("#### AIインサイト")
    insights = generate_ai_recommendations(metrics, numeric_amounts, numeric_kpis, unit)
    for insight in insights:
        tone = insight.get("tone", "positive")
        st.markdown(
            f"<div class='insight-card {tone}'><h4>{insight['title']}</h4><p>{insight['body']}</p></div>",
            unsafe_allow_html=True,
        )

    anomalies = detect_anomalies_in_plan(numeric_amounts, numeric_kpis, unit, metrics)
    if not anomalies.empty:
        st.markdown("#### アラート")
        st.dataframe(
            anomalies,
            use_container_width=True,
            hide_index=True,
            column_config={
                "コメント": st.column_config.TextColumn("コメント", width="large"),
            },
        )
    else:
        st.success("異常値は検出されませんでした。データ整合性は良好です。")

    return amounts, metrics

def render_detail_tab(plan_data: Dict[str, Any], base_amounts: Dict[str, float], scenario_summary: pd.DataFrame) -> None:
    unit = plan_data.get("unit", "百万円")
    df = plan_to_dataframe(base_amounts, unit)
    divisor = unit_divisor(unit)
    display_df = df.copy()
    display_df["金額"] = display_df["金額"] / divisor
    display_df["売上比率"] = display_df["売上比率"].apply(lambda x: x * 100 if pd.notnull(x) else x)
    st.dataframe(
        display_df,
        use_container_width=True,
        column_config={
            "金額": st.column_config.NumberColumn("金額", format="{:,}", help="表示単位で丸めています。"),
            "売上比率": st.column_config.NumberColumn("売上比率", format="%.1f%%"),
            "説明": st.column_config.TextColumn("説明", width="large"),
        },
        hide_index=True,
    )
    st.markdown("#### シナリオ比較")
    display_summary = scenario_summary.copy()
    for col in ["売上高", "粗利", "営業利益", "経常利益", "損益分岐点売上"]:
        display_summary[col] = display_summary[col] / divisor
    st.dataframe(
        display_summary,
        use_container_width=True,
        column_config={
            "売上高": st.column_config.NumberColumn("売上高", format="{:,}"),
            "粗利": st.column_config.NumberColumn("粗利", format="{:,}"),
            "営業利益": st.column_config.NumberColumn("営業利益", format="{:,}"),
            "経常利益": st.column_config.NumberColumn("経常利益", format="{:,}"),
            "損益分岐点売上": st.column_config.NumberColumn("損益分岐点売上", format="{:,}"),
        },
        hide_index=True,
    )

def render_charts_tab(plan_data: Dict[str, Any], base_amounts: Dict[str, float], scenario_summary: pd.DataFrame) -> None:
    unit = plan_data.get("unit", "百万円")
    divisor = unit_divisor(unit)
    summary_data = pd.DataFrame(
        {
            "指標": ["売上高", "粗利", "営業利益", "経常利益"],
            "金額": [base_amounts.get("REV", 0.0), base_amounts.get("GROSS", 0.0), base_amounts.get("OP", 0.0), base_amounts.get("ORD", 0.0)],
        }
    )
    summary_data["金額表示"] = summary_data["金額"] / divisor
    chart_summary = (
        alt.Chart(summary_data)
        .mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8)
        .encode(
            x=alt.X("指標", sort=None),
            y=alt.Y("金額表示", title=f"金額（{unit}換算）"),
            color=alt.Color("指標", legend=None),
            tooltip=[alt.Tooltip("指標"), alt.Tooltip("金額", format=",.0f", title="金額（円）")],
        )
    )
    st.altair_chart(chart_summary, use_container_width=True)

    cost_data = pd.DataFrame(
        {
            "カテゴリ": [ITEM_LABELS[c] for c in ["COGS_MAT", "COGS_LBR", "COGS_OUT_SRC", "COGS_OUT_CON", "COGS_OTH"]],
            "金額": [base_amounts.get(c, 0.0) for c in ["COGS_MAT", "COGS_LBR", "COGS_OUT_SRC", "COGS_OUT_CON", "COGS_OTH"]],
        }
    )
    cost_data["金額表示"] = cost_data["金額"] / divisor
    chart_cost = (
        alt.Chart(cost_data)
        .mark_bar()
        .encode(
            x=alt.X("金額表示", title=f"金額（{unit}換算）"),
            y=alt.Y("カテゴリ", sort="-x"),
            tooltip=[alt.Tooltip("カテゴリ"), alt.Tooltip("金額", format=",.0f", title="金額（円）")],
        )
    )
    st.altair_chart(chart_cost, use_container_width=True)

    scenario_long = scenario_summary.melt("シナリオ", var_name="指標", value_name="金額")
    scenario_long["金額表示"] = scenario_long["金額"] / divisor
    chart_scenario = (
        alt.Chart(scenario_long)
        .mark_line(point=True)
        .encode(
            x=alt.X("シナリオ", sort=list(scenario_summary["シナリオ"])),
            y=alt.Y("金額表示", title=f"金額（{unit}換算）"),
            color=alt.Color("指標", title="指標"),
            tooltip=["シナリオ", "指標", alt.Tooltip("金額", format=",.0f", title="金額（円）")],
        )
    )
    st.altair_chart(chart_scenario, use_container_width=True)

def render_sensitivity_tab(plan_data: Dict[str, Any], base_amounts: Dict[str, float]) -> None:
    unit = plan_data.get("unit", "百万円")
    col1, col2, col3 = st.columns(3)
    price_adj = col1.slider("単価調整（±%）", -20.0, 20.0, 0.0, step=1.0)
    qty_adj = col2.slider("数量調整（±%）", -20.0, 20.0, 0.0, step=1.0)
    cogs_adj = col3.slider("原価率調整（±pt）", -10.0, 10.0, 0.0, step=0.5)

    adjusted_plan = plan_data.copy()
    adjusted_plan["unit_price"] = plan_data.get("unit_price", 0.0) * (1 + price_adj / 100)
    adjusted_plan["quantity"] = plan_data.get("quantity", 0.0) * (1 + qty_adj / 100)
    adjusted_plan["base_sales"] = adjusted_plan["unit_price"] * adjusted_plan["quantity"]
    ratios = plan_data.get("ratios", {}).copy()
    ratios["COGS_OTH"] = max(0.0, ratios.get("COGS_OTH", 0.0) - cogs_adj / 100)
    adjusted_plan["ratios"] = ratios

    amounts, metrics = compute_plan_outputs(adjusted_plan)
    fcf, debt_years = compute_additional_metrics(amounts, adjusted_plan)

    base_metrics = summarize_plan_metrics(base_amounts)
    base_fcf, base_debt_years = compute_additional_metrics(base_amounts, plan_data)

    m1, m2, m3 = st.columns(3)
    m1.metric("調整後 売上高", f"¥{amounts.get('REV', 0.0):,.0f}", delta=f"¥{amounts.get('REV', 0.0) - base_amounts.get('REV', 0.0):,.0f}")
    m2.metric("調整後 粗利率", format_ratio(metrics.get("gross_margin")), delta=f"{(metrics.get('gross_margin', 0.0) - base_metrics.get('gross_margin', 0.0)) * 100:.1f}pt")
    if math.isfinite(debt_years):
        delta_years = base_debt_years - debt_years if math.isfinite(base_debt_years) else float("nan")
        delta_text = f"{delta_years:+.1f}年" if math.isfinite(delta_years) else "—"
        debt_value = f"{debt_years:.1f}年"
    else:
        debt_value = "∞"
        delta_text = "—"
    m3.metric("調整後 債務償還年数", debt_value, delta=delta_text)

    chart_data = pd.DataFrame(
        {
            "指標": ["売上高", "粗利", "営業利益", "経常利益", "FCF"],
            "ベース": [
                base_amounts.get("REV", 0.0),
                base_amounts.get("GROSS", 0.0),
                base_amounts.get("OP", 0.0),
                base_amounts.get("ORD", 0.0),
                base_fcf,
            ],
            "調整後": [
                amounts.get("REV", 0.0),
                amounts.get("GROSS", 0.0),
                amounts.get("OP", 0.0),
                amounts.get("ORD", 0.0),
                fcf,
            ],
        }
    )
    chart_long = chart_data.melt("指標", var_name="シナリオ", value_name="金額")
    chart_long["金額表示"] = chart_long["金額"] / unit_divisor(unit)
    chart = (
        alt.Chart(chart_long)
        .mark_bar()
        .encode(
            x=alt.X("指標", sort=None),
            y=alt.Y("金額表示", title=f"金額（{unit}換算）"),
            color="シナリオ",
            tooltip=["指標", "シナリオ", alt.Tooltip("金額", format=",.0f", title="金額（円）")],
        )
    )
    st.altair_chart(chart, use_container_width=True)

def render_log_tab() -> None:
    st.markdown("### 操作ログ")
    logs = st.session_state.get("log", [])
    if logs:
        st.code("\n".join(logs))
        if st.button("ログをクリア", use_container_width=True):
            st.session_state["log"] = []
            st.experimental_rerun()
    else:
        st.info("まだログはありません。入力や検証を実行すると表示されます。")

def create_summary_png(amounts: Dict[str, float]) -> bytes:
    labels = ["売上高", "粗利", "営業利益", "経常利益"]
    values = [amounts.get("REV", 0.0), amounts.get("GROSS", 0.0), amounts.get("OP", 0.0), amounts.get("ORD", 0.0)]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(labels, values, color=["#2B6CB0", "#4A90E2", "#2B6CB0", "#2B6CB0"])
    ax.set_ylabel("金額（円）")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"¥{x:,.0f}"))
    ax.set_title("主要KPIサマリー", fontsize=12)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val, f"¥{val:,.0f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()

def create_excel_bytes(
    plan_df: pd.DataFrame,
    scenario_summary: pd.DataFrame,
    scenario_kpis: pd.DataFrame,
    numeric_amounts: pd.DataFrame,
    numeric_kpis: pd.DataFrame,
    plan_data: Dict[str, Any],
) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        plan_df.to_excel(writer, sheet_name="金額", index=False)
        scenario_summary.to_excel(writer, sheet_name="シナリオ", index=False)
        scenario_kpis.to_excel(writer, sheet_name="KPI", index=False)
        numeric_amounts.to_excel(writer, sheet_name="シナリオ数値")
        numeric_kpis.to_excel(writer, sheet_name="シナリオ比率")
        wb = writer.book
        if "金額" in wb.sheetnames:
            ws = wb["金額"]
            format_money_and_percent(ws, [3], [4])
        if "シナリオ" in wb.sheetnames:
            ws = wb["シナリオ"]
            format_money_and_percent(ws, list(range(2, ws.max_column + 1)), [])
        if "KPI" in wb.sheetnames:
            ws = wb["KPI"]
            for col in range(2, ws.max_column + 1):
                for row in range(2, ws.max_row + 1):
                    ws.cell(row=row, column=col).number_format = "0.0%"
        if "シナリオ数値" in wb.sheetnames:
            ws = wb["シナリオ数値"]
            format_money_and_percent(ws, list(range(2, ws.max_column + 1)), [])
        if "シナリオ比率" in wb.sheetnames:
            ws = wb["シナリオ比率"]
            for col in range(2, ws.max_column + 1):
                for row in range(2, ws.max_row + 1):
                    ws.cell(row=row, column=col).number_format = "0.0%"
        meta_ws = wb.create_sheet("メタ情報")
        meta_data = [
            ("作成日時", dt.datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("プロジェクト", plan_data.get("project_name", "—")),
            ("会社名", plan_data.get("company_name", "—")),
            ("会計年度", plan_data.get("fiscal_year", "—")),
            ("表示単位", plan_data.get("unit", "—")),
            ("FTE", plan_data.get("fte", "—")),
        ]
        for idx, (key, value) in enumerate(meta_data, start=1):
            meta_ws.cell(row=idx, column=1, value=key)
            meta_ws.cell(row=idx, column=2, value=value)
        apply_japanese_styles(wb)
    return output.getvalue()

def render_export_section(
    plan_data: Dict[str, Any],
    base_amounts: Dict[str, float],
    scenario_summary: pd.DataFrame,
    scenario_kpis: pd.DataFrame,
    numeric_amounts: pd.DataFrame,
    numeric_kpis: pd.DataFrame,
) -> None:
    st.markdown("### Step4: レポート出力")
    unit = plan_data.get("unit", "百万円")
    plan_df = plan_to_dataframe(base_amounts, unit)
    csv_df = plan_df.copy()
    divisor = unit_divisor(unit)
    csv_df["金額"] = csv_df["金額"] / divisor
    csv_df["売上比率"] = csv_df["売上比率"].apply(lambda x: x * 100 if pd.notnull(x) else x)
    csv_bytes = csv_df.to_csv(index=False).encode("utf-8-sig")

    excel_bytes = create_excel_bytes(plan_df, scenario_summary, scenario_kpis, numeric_amounts, numeric_kpis, plan_data)
    png_bytes = create_summary_png(base_amounts)

    project_name = plan_data.get("project_name", "plan").replace(" ", "")
    file_prefix = f"{dt.datetime.now():%Y%m%d}_{project_name}"
    st.download_button("CSVをダウンロード", data=csv_bytes, file_name=f"{file_prefix}_summary.csv", mime="text/csv")
    st.download_button(
        "Excelをダウンロード",
        data=excel_bytes,
        file_name=f"{file_prefix}_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.download_button("PNGをダウンロード", data=png_bytes, file_name=f"{file_prefix}_chart.png", mime="image/png")
    st.caption("CSVは表示単位で丸め、Excel/PNGは円単位の正確値で出力しています。")

def render_analysis_tabs(plan_data: Dict[str, Any]) -> Tuple[Dict[str, float], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base_amounts, _ = compute_plan_outputs(plan_data)
    scenario_summary, scenario_kpis = compute_scenarios(plan_data)
    numeric_amounts, numeric_kpis = build_numeric_tables(plan_data)
    tabs = st.tabs(["サマリー", "詳細KPI", "チャート", "感度分析", "ログ"])
    with tabs[0]:
        render_summary_tab(plan_data, scenario_summary, numeric_amounts, numeric_kpis)
    with tabs[1]:
        render_detail_tab(plan_data, base_amounts, scenario_summary)
    with tabs[2]:
        render_charts_tab(plan_data, base_amounts, scenario_summary)
    with tabs[3]:
        render_sensitivity_tab(plan_data, base_amounts)
    with tabs[4]:
        render_log_tab()
    return base_amounts, scenario_summary, scenario_kpis, numeric_amounts, numeric_kpis

def main() -> None:
    init_session_state()
    plan_data = st.session_state.get("plan_data", DEFAULT_PLAN_DATA.copy())
    render_header()
    render_sidebar()
    render_help()
    render_step_navigation()

    step = st.session_state.get("step", 1)
    if step == 1:
        render_step1(plan_data)
        return
    if step == 2:
        render_step2(plan_data)
        return

    base_amounts, scenario_summary, scenario_kpis, numeric_amounts, numeric_kpis = render_analysis_tabs(plan_data)
    if step >= 4:
        render_export_section(plan_data, base_amounts, scenario_summary, scenario_kpis, numeric_amounts, numeric_kpis)


if __name__ == "__main__":
    mpl.rcParams["axes.unicode_minus"] = False
    main()

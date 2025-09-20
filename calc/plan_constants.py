"""Shared constants for plan calculations and reporting."""
from __future__ import annotations

from typing import Dict, List, Tuple

# Code, display label, category tuples used throughout the financial model.
ITEMS: List[Tuple[str, str, str]] = [
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


ITEM_LABELS: Dict[str, str] = {code: label for code, label, _ in ITEMS}


COST_CODES: List[str] = [
    "COGS_MAT",
    "COGS_LBR",
    "COGS_OUT_SRC",
    "COGS_OUT_CON",
    "COGS_OTH",
]

OPEX_CODES: List[str] = ["OPEX_H", "OPEX_K", "OPEX_DEP"]

NOI_CODES: List[str] = ["NOI_MISC", "NOI_GRANT", "NOI_OTH"]

NOE_CODES: List[str] = ["NOE_INT", "NOE_OTH"]


__all__ = [
    "ITEMS",
    "ITEM_LABELS",
    "COST_CODES",
    "OPEX_CODES",
    "NOI_CODES",
    "NOE_CODES",
]

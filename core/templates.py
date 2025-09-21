"""Industry template definitions and helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Mapping, Sequence

from models import CostPlan


def _as_decimal(value: float | int | str | Decimal) -> Decimal:
    return Decimal(str(value))


def _normalise_breakdown(breakdown: Mapping[str, float | Decimal]) -> Dict[str, Decimal]:
    total = sum(Decimal(str(v)) for v in breakdown.values())
    if total <= 0:
        raise ValueError("Breakdown weights must sum to a positive number.")
    return {key: Decimal(str(value)) / total for key, value in breakdown.items()}


@dataclass(frozen=True)
class IndustryTemplate:
    """Describes default ratios for a representative industry."""

    id: str
    name: str
    description: str
    gross_margin_ratio: Decimal
    fixed_cost_ratio: Decimal
    variable_cost_shares: Dict[str, Decimal]
    fixed_cost_shares: Dict[str, Decimal]
    notes: str
    source: str
    last_updated: date

    def variable_ratios(self, gross_margin: Decimal | None = None) -> Dict[str, Decimal]:
        """Return variable cost ratios keyed by cost code."""

        margin = gross_margin if gross_margin is not None else self.gross_margin_ratio
        margin = max(Decimal("0"), min(Decimal("0.99"), margin))
        cogs_ratio = Decimal("1") - margin
        ratios: Dict[str, Decimal] = {}
        for code, weight in self.variable_cost_shares.items():
            ratios[code] = (cogs_ratio * weight).quantize(Decimal("0.0001"))
        return ratios

    def fixed_cost_amounts(
        self,
        annual_sales: Decimal,
        *,
        fixed_cost_ratio: Decimal | None = None,
    ) -> Dict[str, Decimal]:
        """Allocate fixed costs using *annual_sales* as the base."""

        ratio = fixed_cost_ratio if fixed_cost_ratio is not None else self.fixed_cost_ratio
        ratio = max(Decimal("0"), min(Decimal("0.99"), ratio))
        total = (annual_sales * ratio).quantize(Decimal("1"))
        allocations: Dict[str, Decimal] = {}
        remaining = total
        shares = list(self.fixed_cost_shares.items())
        for index, (code, weight) in enumerate(shares):
            if index == len(shares) - 1:
                allocations[code] = remaining
            else:
                amount = (total * weight).quantize(Decimal("1"))
                allocations[code] = amount
                remaining -= amount
        return allocations

    def build_cost_plan(
        self,
        *,
        annual_sales: Decimal,
        gross_margin: Decimal | None = None,
        fixed_cost_ratio: Decimal | None = None,
        base_plan: CostPlan | None = None,
    ) -> CostPlan:
        """Generate a :class:`CostPlan` with ratios derived from the template."""

        base = base_plan or CostPlan()
        variable = self.variable_ratios(gross_margin)
        fixed = self.fixed_cost_amounts(annual_sales, fixed_cost_ratio=fixed_cost_ratio)
        return CostPlan(
            variable_ratios=variable,
            fixed_costs=fixed,
            gross_linked_ratios=base.gross_linked_ratios,
            non_operating_income=base.non_operating_income,
            non_operating_expenses=base.non_operating_expenses,
        )


def _template(
    *,
    id: str,
    name: str,
    description: str,
    gross_margin_ratio: float,
    fixed_cost_ratio: float,
    variable_cost_shares: Mapping[str, float],
    fixed_cost_shares: Mapping[str, float],
    notes: str,
    source: str,
    last_updated: date,
) -> IndustryTemplate:
    return IndustryTemplate(
        id=id,
        name=name,
        description=description,
        gross_margin_ratio=_as_decimal(gross_margin_ratio),
        fixed_cost_ratio=_as_decimal(fixed_cost_ratio),
        variable_cost_shares=_normalise_breakdown(variable_cost_shares),
        fixed_cost_shares=_normalise_breakdown(fixed_cost_shares),
        notes=notes,
        source=source,
        last_updated=last_updated,
    )


INDUSTRY_TEMPLATES: Sequence[IndustryTemplate] = (
    _template(
        id="food_service",
        name="飲食業",
        description="原価と人件費が売上に強く連動する想定のフルサービス型飲食店。",
        gross_margin_ratio=0.55,
        fixed_cost_ratio=0.32,
        variable_cost_shares={
            "COGS_MAT": 0.68,
            "COGS_LBR": 0.22,
            "COGS_OUT_SRC": 0.10,
        },
        fixed_cost_shares={
            "OPEX_H": 0.35,
            "OPEX_K": 0.45,
            "OPEX_DEP": 0.20,
        },
        notes="推定: 飲食業の平均粗利率55%・固定費率32% (中小企業庁 業種別指標 2023)。",
        source="中小企業庁 業種別財務指標 2023",
        last_updated=date(2024, 6, 1),
    ),
    _template(
        id="retail",
        name="小売業",
        description="在庫回転を重視する郊外型小売チェーンの平均モデル。",
        gross_margin_ratio=0.32,
        fixed_cost_ratio=0.28,
        variable_cost_shares={
            "COGS_MAT": 0.82,
            "COGS_LBR": 0.06,
            "COGS_OUT_SRC": 0.12,
        },
        fixed_cost_shares={
            "OPEX_H": 0.40,
            "OPEX_K": 0.40,
            "OPEX_DEP": 0.20,
        },
        notes="推定: 小売業の平均粗利率32% (総務省『商業動態統計』2024年1月速報)。",
        source="総務省 商業動態統計 2024",
        last_updated=date(2024, 5, 1),
    ),
    _template(
        id="saas",
        name="SaaS・ITサービス",
        description="サブスクリプション型SaaSの標準モデル。サーバー費用は変動費で計上。",
        gross_margin_ratio=0.78,
        fixed_cost_ratio=0.45,
        variable_cost_shares={
            "COGS_MAT": 0.25,
            "COGS_LBR": 0.45,
            "COGS_OUT_SRC": 0.30,
        },
        fixed_cost_shares={
            "OPEX_H": 0.25,
            "OPEX_K": 0.55,
            "OPEX_DEP": 0.20,
        },
        notes="推定: 上場SaaSベンチマーク (SaaS定点観測レポート2024) を元に粗利率78%。",
        source="SaaS定点観測レポート 2024",
        last_updated=date(2024, 4, 1),
    ),
)


def list_industry_templates() -> List[IndustryTemplate]:
    """Return all configured industry templates."""

    return list(INDUSTRY_TEMPLATES)


def get_industry_template(template_id: str) -> IndustryTemplate | None:
    """Return the template matching *template_id* if it exists."""

    for template in INDUSTRY_TEMPLATES:
        if template.id == template_id:
            return template
    return None


__all__ = [
    "IndustryTemplate",
    "INDUSTRY_TEMPLATES",
    "list_industry_templates",
    "get_industry_template",
]


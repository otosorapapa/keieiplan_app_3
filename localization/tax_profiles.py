"""Tax and statutory parameter presets tied to locales."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable


@dataclass(frozen=True)
class TaxProfile:
    """Preset parameters for a country's tax and statutory model."""

    code: str
    country: str
    corporate_tax_rate: Decimal
    consumption_tax_rate: Decimal
    social_insurance_rate: Decimal
    depreciation_key: str


TAX_PROFILES: Dict[str, TaxProfile] = {
    "jp_sme": TaxProfile(
        code="jp_sme",
        country="JP",
        corporate_tax_rate=Decimal("0.232"),
        consumption_tax_rate=Decimal("0.10"),
        social_insurance_rate=Decimal("0.15"),
        depreciation_key="tax_profiles.jp_sme.depreciation",
    ),
    "us_standard": TaxProfile(
        code="us_standard",
        country="US",
        corporate_tax_rate=Decimal("0.26"),
        consumption_tax_rate=Decimal("0.07"),
        social_insurance_rate=Decimal("0.141"),
        depreciation_key="tax_profiles.us_standard.depreciation",
    ),
    "cn_standard": TaxProfile(
        code="cn_standard",
        country="CN",
        corporate_tax_rate=Decimal("0.25"),
        consumption_tax_rate=Decimal("0.13"),
        social_insurance_rate=Decimal("0.16"),
        depreciation_key="tax_profiles.cn_standard.depreciation",
    ),
    "kr_standard": TaxProfile(
        code="kr_standard",
        country="KR",
        corporate_tax_rate=Decimal("0.25"),
        consumption_tax_rate=Decimal("0.10"),
        social_insurance_rate=Decimal("0.13"),
        depreciation_key="tax_profiles.kr_standard.depreciation",
    ),
}


def get_tax_profile(code: str) -> TaxProfile:
    """Return the configured tax profile raising ``KeyError`` if missing."""

    if code not in TAX_PROFILES:
        raise KeyError(f"Unknown tax profile: {code}")
    return TAX_PROFILES[code]


def available_tax_profiles() -> Iterable[TaxProfile]:
    """Iterate through all tax profiles in declaration order."""

    return TAX_PROFILES.values()


__all__ = [
    "TaxProfile",
    "TAX_PROFILES",
    "available_tax_profiles",
    "get_tax_profile",
]

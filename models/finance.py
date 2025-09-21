"""Dataclass-based models representing the core financial planning inputs."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Literal, Mapping, Sequence, Tuple

MonthIndex = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
MONTH_SEQUENCE: Sequence[MonthIndex] = tuple(range(1, 13))


def _twelve_zeroes() -> List[Decimal]:
    return [Decimal("0") for _ in MONTH_SEQUENCE]


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("数値を入力してください。") from exc


def _convert_for_dump(value: Any, *, json_mode: bool) -> Any:
    if isinstance(value, Decimal):
        return float(value) if json_mode else Decimal(value)
    if isinstance(value, list):
        return [_convert_for_dump(item, json_mode=json_mode) for item in value]
    if isinstance(value, dict):
        return {key: _convert_for_dump(val, json_mode=json_mode) for key, val in value.items()}
    return value


class ValidationError(Exception):
    """Simplified validation error compatible with the original interface."""

    def __init__(self, errors: List[Dict[str, Any]]) -> None:
        super().__init__("Validation failed")
        self._errors = errors

    def errors(self) -> List[Dict[str, Any]]:
        return self._errors


class ModelMixin:
    """Provide ``model_dump``/``model_copy`` helpers mimicking Pydantic models."""

    def model_dump(self, mode: str | None = None) -> Dict[str, Any]:
        data = asdict(self)
        return _convert_for_dump(data, json_mode=(mode == "json"))

    def model_copy(self, deep: bool = False):  # type: ignore[override]
        if not deep:
            return replace(self)
        return self.__class__.from_dict(self.model_dump())  # type: ignore[misc]


@dataclass
class MonthlySeries(ModelMixin):
    """A 12-month series of Decimal amounts."""

    amounts: List[Decimal] = field(default_factory=_twelve_zeroes)

    def __post_init__(self) -> None:
        try:
            values = list(self.amounts)
        except TypeError as exc:
            raise ValueError("月次データはリスト形式で入力してください。") from exc
        converted: List[Decimal] = []
        for value in values:
            try:
                converted.append(_as_decimal(value))
            except ValueError as exc:
                raise ValueError("月次データは数値で入力してください。") from exc
        if len(converted) != 12:
            raise ValueError("月次データは必ず12ヶ月分を入力してください。")
        self.amounts = converted

    @classmethod
    def from_dict(cls, data: Any) -> "MonthlySeries":
        if isinstance(data, MonthlySeries):
            return data
        if isinstance(data, Mapping):
            if "amounts" not in data:
                raise ValidationError([
                    {"loc": ("amounts",), "msg": "12ヶ月分の金額を指定してください。"}
                ])
            raw = data.get("amounts")
        else:
            raw = data
        try:
            return cls(amounts=list(raw))  # type: ignore[arg-type]
        except TypeError as exc:  # pragma: no cover - defensive
            raise ValidationError([
                {"loc": ("amounts",), "msg": "月次データはリスト形式で入力してください。"}
            ]) from exc
        except ValueError as exc:
            raise ValidationError([
                {"loc": ("amounts",), "msg": str(exc)}
            ]) from exc

    def total(self) -> Decimal:
        return sum(self.amounts, start=Decimal("0"))

    def by_month(self) -> Dict[MonthIndex, Decimal]:
        return {month: self.amounts[index] for index, month in enumerate(MONTH_SEQUENCE)}


@dataclass
class SalesItem(ModelMixin):
    """Monthly sales for a specific product sold through a channel."""

    channel: str
    product: str
    monthly: MonthlySeries = field(default_factory=MonthlySeries)

    def __post_init__(self) -> None:
        self.channel = str(self.channel)
        self.product = str(self.product)
        if not isinstance(self.monthly, MonthlySeries):
            self.monthly = MonthlySeries.from_dict(self.monthly)

    @property
    def annual_total(self) -> Decimal:
        return self.monthly.total()

    @classmethod
    def from_dict(cls, data: Any) -> "SalesItem":
        if isinstance(data, SalesItem):
            return data
        if not isinstance(data, Mapping):
            raise ValidationError([
                {"loc": tuple(), "msg": "売上項目は辞書形式で指定してください。"}
            ])
        monthly_raw = data.get("monthly", {})
        try:
            monthly = (
                monthly_raw
                if isinstance(monthly_raw, MonthlySeries)
                else MonthlySeries.from_dict(monthly_raw)
            )
        except ValidationError as exc:
            errors = []
            for detail in exc.errors():
                loc = ("monthly",) + tuple(detail.get("loc", ()))
                errors.append({"loc": loc, "msg": detail.get("msg", "不正な値です。")})
            raise ValidationError(errors) from exc
        return cls(
            channel=str(data.get("channel", "")),
            product=str(data.get("product", "")),
            monthly=monthly,
        )


@dataclass
class SalesPlan(ModelMixin):
    """Sales broken down by channel, product and month."""

    items: List[SalesItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        converted: List[SalesItem] = []
        for item in self.items:
            if isinstance(item, SalesItem):
                converted.append(item)
            else:
                converted.append(SalesItem.from_dict(item))
        self.items = converted

    def total_by_month(self) -> Dict[MonthIndex, Decimal]:
        totals = {month: Decimal("0") for month in MONTH_SEQUENCE}
        for item in self.items:
            for month, value in item.monthly.by_month().items():
                totals[month] += value
        return totals

    def annual_total(self) -> Decimal:
        return sum((item.annual_total for item in self.items), start=Decimal("0"))

    def channels(self) -> List[str]:
        return sorted({item.channel for item in self.items})

    def products(self) -> List[str]:
        return sorted({item.product for item in self.items})

    @classmethod
    def from_dict(cls, data: Any) -> "SalesPlan":
        if isinstance(data, SalesPlan):
            return data
        if not isinstance(data, Mapping):
            raise ValidationError([
                {"loc": tuple(), "msg": "売上計画は辞書形式で指定してください。"}
            ])
        raw_items = data.get("items", [])
        if raw_items is None:
            raw_items = []
        if not isinstance(raw_items, Iterable) or isinstance(raw_items, (str, bytes)):
            raise ValidationError([
                {"loc": ("items",), "msg": "items はリスト形式で指定してください。"}
            ])
        items: List[SalesItem] = []
        errors: List[Dict[str, Any]] = []
        for index, raw_item in enumerate(raw_items):
            try:
                items.append(SalesItem.from_dict(raw_item))
            except ValidationError as exc:
                for detail in exc.errors():
                    loc = ("items", index) + tuple(detail.get("loc", ()))
                    errors.append({"loc": loc, "msg": detail.get("msg", "不正な値です。")})
        if errors:
            raise ValidationError(errors)
        return cls(items=items)


def _parse_ratio_dict(raw: Any, field_name: str) -> Tuple[Dict[str, Decimal], List[Dict[str, Any]]]:
    result: Dict[str, Decimal] = {}
    errors: List[Dict[str, Any]] = []
    if raw is None:
        return result, errors
    if not isinstance(raw, Mapping):
        errors.append({"loc": (field_name,), "msg": "辞書形式で入力してください。"})
        return result, errors
    for key, value in raw.items():
        key_str = str(key)
        try:
            dec = _as_decimal(value)
        except ValueError:
            errors.append({"loc": (field_name, key_str), "msg": "数値を入力してください。"})
            continue
        if dec < Decimal("0") or dec > Decimal("1"):
            errors.append({
                "loc": (field_name, key_str),
                "msg": f"{field_name} の '{key_str}' は0〜1の範囲に収めてください。",
            })
            continue
        result[key_str] = dec
    return result, errors


def _parse_amount_dict(raw: Any, field_name: str) -> Tuple[Dict[str, Decimal], List[Dict[str, Any]]]:
    result: Dict[str, Decimal] = {}
    errors: List[Dict[str, Any]] = []
    if raw is None:
        return result, errors
    if not isinstance(raw, Mapping):
        errors.append({"loc": (field_name,), "msg": "辞書形式で入力してください。"})
        return result, errors
    for key, value in raw.items():
        key_str = str(key)
        try:
            dec = _as_decimal(value)
        except ValueError:
            errors.append({"loc": (field_name, key_str), "msg": "数値を入力してください。"})
            continue
        if dec < Decimal("0"):
            errors.append({
                "loc": (field_name, key_str),
                "msg": f"{field_name} の '{key_str}' は0以上の金額を入力してください。",
            })
            continue
        result[key_str] = dec
    return result, errors


@dataclass
class CostPlan(ModelMixin):
    """Cost configuration split into variable ratios and fixed amounts."""

    variable_ratios: Dict[str, Decimal] = field(default_factory=dict)
    fixed_costs: Dict[str, Decimal] = field(default_factory=dict)
    gross_linked_ratios: Dict[str, Decimal] = field(default_factory=dict)
    non_operating_income: Dict[str, Decimal] = field(default_factory=dict)
    non_operating_expenses: Dict[str, Decimal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.variable_ratios = {str(k): _as_decimal(v) for k, v in self.variable_ratios.items()}
        self.fixed_costs = {str(k): _as_decimal(v) for k, v in self.fixed_costs.items()}
        self.gross_linked_ratios = {str(k): _as_decimal(v) for k, v in self.gross_linked_ratios.items()}
        self.non_operating_income = {str(k): _as_decimal(v) for k, v in self.non_operating_income.items()}
        self.non_operating_expenses = {str(k): _as_decimal(v) for k, v in self.non_operating_expenses.items()}
        self._validate_ranges()

    def _validate_ranges(self) -> None:
        for label, ratios in (
            ("variable_ratios", self.variable_ratios),
            ("gross_linked_ratios", self.gross_linked_ratios),
        ):
            for code, ratio in ratios.items():
                if ratio < Decimal("0") or ratio > Decimal("1"):
                    raise ValueError(f"{label} の '{code}' は0〜1の範囲に収めてください。")
        for label, amounts in (
            ("fixed_costs", self.fixed_costs),
            ("non_operating_income", self.non_operating_income),
            ("non_operating_expenses", self.non_operating_expenses),
        ):
            for code, amount in amounts.items():
                if amount < Decimal("0"):
                    raise ValueError(f"{label} の '{code}' は0以上の金額を入力してください。")

    @classmethod
    def from_dict(cls, data: Any) -> "CostPlan":
        if isinstance(data, CostPlan):
            return data
        if not isinstance(data, Mapping):
            raise ValidationError([
                {"loc": tuple(), "msg": "コスト計画は辞書形式で指定してください。"}
            ])
        variable, errors = _parse_ratio_dict(data.get("variable_ratios"), "variable_ratios")
        gross, gross_errors = _parse_ratio_dict(data.get("gross_linked_ratios"), "gross_linked_ratios")
        fixed, fixed_errors = _parse_amount_dict(data.get("fixed_costs"), "fixed_costs")
        noi, noi_errors = _parse_amount_dict(data.get("non_operating_income"), "non_operating_income")
        noe, noe_errors = _parse_amount_dict(data.get("non_operating_expenses"), "non_operating_expenses")
        errors.extend(gross_errors)
        errors.extend(fixed_errors)
        errors.extend(noi_errors)
        errors.extend(noe_errors)
        if errors:
            raise ValidationError(errors)
        return cls(
            variable_ratios=variable,
            gross_linked_ratios=gross,
            fixed_costs=fixed,
            non_operating_income=noi,
            non_operating_expenses=noe,
        )


@dataclass
class CapexItem(ModelMixin):
    """Single capital expenditure entry."""

    name: str
    amount: Decimal
    start_month: MonthIndex
    useful_life_years: int

    def __post_init__(self) -> None:
        self.name = str(self.name)
        self.amount = _as_decimal(self.amount)
        self.start_month = int(self.start_month)
        self.useful_life_years = int(self.useful_life_years)
        if self.amount <= 0:
            raise ValueError("投資金額は正の値を入力してください。")
        if self.start_month < 1 or self.start_month > 12:
            raise ValueError("開始月は1〜12で設定してください。")
        if self.useful_life_years < 1 or self.useful_life_years > 20:
            raise ValueError("耐用年数は1〜20年の範囲で設定してください。")

    def annual_depreciation(self) -> Decimal:
        life_months = Decimal(self.useful_life_years * 12)
        return self.amount / (life_months / Decimal("12"))

    @classmethod
    def from_dict(cls, data: Any) -> "CapexItem":
        if isinstance(data, CapexItem):
            return data
        if not isinstance(data, Mapping):
            raise ValidationError([
                {"loc": tuple(), "msg": "投資項目は辞書形式で指定してください。"}
            ])
        errors: List[Dict[str, Any]] = []
        name = str(data.get("name", ""))
        if name.strip() == "":
            errors.append({"loc": ("name",), "msg": "投資名を入力してください。"})
        amount_value: Decimal | None = None
        try:
            amount_value = _as_decimal(data.get("amount", 0))
        except ValueError:
            errors.append({"loc": ("amount",), "msg": "金額は数値で入力してください。"})
        else:
            if amount_value <= 0:
                errors.append({"loc": ("amount",), "msg": "投資金額は正の値を入力してください。"})
        start_month_value: int | None = None
        try:
            start_month_value = int(data.get("start_month", 1))
        except Exception:
            errors.append({"loc": ("start_month",), "msg": "開始月は1〜12の整数で入力してください。"})
        else:
            if start_month_value < 1 or start_month_value > 12:
                errors.append({"loc": ("start_month",), "msg": "開始月は1〜12で設定してください。"})
        life_value: int | None = None
        try:
            life_value = int(data.get("useful_life_years", 1))
        except Exception:
            errors.append({"loc": ("useful_life_years",), "msg": "耐用年数は整数で入力してください。"})
        else:
            if life_value < 1 or life_value > 20:
                errors.append({"loc": ("useful_life_years",), "msg": "耐用年数は1〜20年の範囲で設定してください。"})
        if errors:
            raise ValidationError(errors)
        assert amount_value is not None and start_month_value is not None and life_value is not None
        return cls(
            name=name,
            amount=amount_value,
            start_month=start_month_value,
            useful_life_years=life_value,
        )


@dataclass
class CapexPlan(ModelMixin):
    items: List[CapexItem] = field(default_factory=list)
    depreciation_method: Literal["straight_line", "declining_balance"] = "straight_line"
    declining_balance_rate: Decimal | None = None

    def __post_init__(self) -> None:
        self.items = [item if isinstance(item, CapexItem) else CapexItem.from_dict(item) for item in self.items]
        method = str(self.depreciation_method)
        if method not in {"straight_line", "declining_balance"}:
            raise ValueError("減価償却法は 'straight_line' または 'declining_balance' を指定してください。")
        self.depreciation_method = method
        if self.depreciation_method == "declining_balance" and self.declining_balance_rate not in (None, "", 0):
            rate = _as_decimal(self.declining_balance_rate)
            if not Decimal("0") < rate < Decimal("1"):
                raise ValueError("定率法の償却率は0より大きく1未満で設定してください。")
            self.declining_balance_rate = rate
        else:
            self.declining_balance_rate = None

    def annual_depreciation(self) -> Decimal:
        if self.depreciation_method == "declining_balance" and self.declining_balance_rate is not None:
            rate = self.declining_balance_rate
            return sum((item.amount * rate for item in self.items), start=Decimal("0"))
        return sum((item.annual_depreciation() for item in self.items), start=Decimal("0"))

    def total_investment(self) -> Decimal:
        return sum((item.amount for item in self.items), start=Decimal("0"))

    @classmethod
    def from_dict(cls, data: Any) -> "CapexPlan":
        if isinstance(data, CapexPlan):
            return data
        if not isinstance(data, Mapping):
            raise ValidationError([
                {"loc": tuple(), "msg": "投資計画は辞書形式で指定してください。"}
            ])
        raw_items = data.get("items", [])
        if raw_items is None:
            raw_items = []
        if not isinstance(raw_items, Iterable) or isinstance(raw_items, (str, bytes)):
            raise ValidationError([
                {"loc": ("items",), "msg": "items はリスト形式で指定してください。"}
            ])
        items: List[CapexItem] = []
        errors: List[Dict[str, Any]] = []
        for index, raw_item in enumerate(raw_items):
            try:
                items.append(CapexItem.from_dict(raw_item))
            except ValidationError as exc:
                for detail in exc.errors():
                    loc = ("items", index) + tuple(detail.get("loc", ()))
                    errors.append({"loc": loc, "msg": detail.get("msg", "不正な値です。")})
        method = str(data.get("depreciation_method", "straight_line"))
        if method not in {"straight_line", "declining_balance"}:
            errors.append({
                "loc": ("depreciation_method",),
                "msg": "減価償却法は 'straight_line' または 'declining_balance' を指定してください。",
            })
        rate_raw = data.get("declining_balance_rate")
        rate_value: Decimal | None = None
        if rate_raw not in (None, "", 0):
            try:
                rate_value = _as_decimal(rate_raw)
            except ValueError:
                errors.append({"loc": ("declining_balance_rate",), "msg": "定率法の償却率は数値で入力してください。"})
            else:
                if not Decimal("0") < rate_value < Decimal("1"):
                    errors.append({
                        "loc": ("declining_balance_rate",),
                        "msg": "定率法の償却率は0より大きく1未満で設定してください。",
                    })
        if errors:
            raise ValidationError(errors)
        if method != "declining_balance":
            rate_value = None
        return cls(items=items, depreciation_method=method, declining_balance_rate=rate_value)


@dataclass
class LoanItem(ModelMixin):
    """Definition of a single borrowing schedule."""

    name: str
    principal: Decimal
    interest_rate: Decimal
    term_months: int
    start_month: MonthIndex
    grace_period_months: int = 0
    repayment_type: Literal["equal_principal", "equal_payment", "interest_only"] = "equal_principal"

    def __post_init__(self) -> None:
        self.name = str(self.name)
        self.principal = _as_decimal(self.principal)
        self.interest_rate = _as_decimal(self.interest_rate)
        self.term_months = int(self.term_months)
        self.start_month = int(self.start_month)
        self.grace_period_months = int(self.grace_period_months)
        if self.interest_rate < Decimal("0") or self.interest_rate > Decimal("0.2"):
            raise ValueError("金利は0%〜20%の範囲で入力してください。")
        if self.principal <= 0:
            raise ValueError("借入元本は正の値を入力してください。")
        if self.term_months < 1 or self.term_months > 600:
            raise ValueError("返済期間は1〜600ヶ月の範囲で入力してください。")
        if self.start_month < 1 or self.start_month > 12:
            raise ValueError("開始月は1〜12で設定してください。")
        if self.grace_period_months < 0 or self.grace_period_months > self.term_months:
            raise ValueError("据置期間は返済期間以内で設定してください。")
        if self.repayment_type not in {"equal_principal", "equal_payment", "interest_only"}:
            self.repayment_type = "equal_principal"

    def annual_interest(self) -> Decimal:
        return self.principal * self.interest_rate

    @classmethod
    def from_dict(cls, data: Any) -> "LoanItem":
        if isinstance(data, LoanItem):
            return data
        if not isinstance(data, Mapping):
            raise ValidationError([
                {"loc": tuple(), "msg": "借入項目は辞書形式で指定してください。"}
            ])
        errors: List[Dict[str, Any]] = []
        name = str(data.get("name", ""))
        if name.strip() == "":
            errors.append({"loc": ("name",), "msg": "名称を入力してください。"})
        principal_value: Decimal | None = None
        try:
            principal_value = _as_decimal(data.get("principal", 0))
        except ValueError:
            errors.append({"loc": ("principal",), "msg": "元本は数値で入力してください。"})
        else:
            if principal_value <= 0:
                errors.append({"loc": ("principal",), "msg": "借入元本は正の値を入力してください。"})
        interest_value: Decimal | None = None
        try:
            interest_value = _as_decimal(data.get("interest_rate", 0))
        except ValueError:
            errors.append({"loc": ("interest_rate",), "msg": "金利は数値で入力してください。"})
        else:
            if interest_value < Decimal("0") or interest_value > Decimal("0.2"):
                errors.append({"loc": ("interest_rate",), "msg": "金利は0%〜20%の範囲で入力してください。"})
        term_value: int | None = None
        try:
            term_value = int(data.get("term_months", 1))
        except Exception:
            errors.append({"loc": ("term_months",), "msg": "返済期間は整数で入力してください。"})
        else:
            if term_value < 1 or term_value > 600:
                errors.append({"loc": ("term_months",), "msg": "返済期間は1〜600ヶ月の範囲で入力してください。"})
        start_month_value: int | None = None
        try:
            start_month_value = int(data.get("start_month", 1))
        except Exception:
            errors.append({"loc": ("start_month",), "msg": "開始月は1〜12の整数で入力してください。"})
        else:
            if start_month_value < 1 or start_month_value > 12:
                errors.append({"loc": ("start_month",), "msg": "開始月は1〜12で設定してください。"})
        grace_value: int | None = None
        try:
            grace_value = int(data.get("grace_period_months", 0))
        except Exception:
            errors.append({"loc": ("grace_period_months",), "msg": "据置期間は整数で入力してください。"})
        else:
            if grace_value < 0:
                errors.append({"loc": ("grace_period_months",), "msg": "据置期間は0以上で入力してください。"})
        repayment_type = str(data.get("repayment_type", "equal_principal"))
        if repayment_type not in {"equal_principal", "equal_payment", "interest_only"}:
            errors.append({"loc": ("repayment_type",), "msg": "返済タイプが不正です。"})
        if (
            grace_value is not None
            and term_value is not None
            and grace_value > term_value
        ):
            errors.append({"loc": ("grace_period_months",), "msg": "据置期間は返済期間以内で設定してください。"})
        if errors:
            raise ValidationError(errors)
        assert (
            principal_value is not None
            and interest_value is not None
            and term_value is not None
            and start_month_value is not None
            and grace_value is not None
        )
        return cls(
            name=name,
            principal=principal_value,
            interest_rate=interest_value,
            term_months=term_value,
            start_month=start_month_value,
            grace_period_months=grace_value,
            repayment_type=repayment_type,
        )


@dataclass
class LoanSchedule(ModelMixin):
    loans: List[LoanItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.loans = [loan if isinstance(loan, LoanItem) else LoanItem.from_dict(loan) for loan in self.loans]

    def annual_interest(self) -> Decimal:
        return sum((loan.annual_interest() for loan in self.loans), start=Decimal("0"))

    def outstanding_principal(self) -> Decimal:
        return sum((loan.principal for loan in self.loans), start=Decimal("0"))

    @classmethod
    def from_dict(cls, data: Any) -> "LoanSchedule":
        if isinstance(data, LoanSchedule):
            return data
        if not isinstance(data, Mapping):
            raise ValidationError([
                {"loc": tuple(), "msg": "借入スケジュールは辞書形式で指定してください。"}
            ])
        raw_loans = data.get("loans", [])
        if raw_loans is None:
            raw_loans = []
        if not isinstance(raw_loans, Iterable) or isinstance(raw_loans, (str, bytes)):
            raise ValidationError([
                {"loc": ("loans",), "msg": "loans はリスト形式で指定してください。"}
            ])
        loans: List[LoanItem] = []
        errors: List[Dict[str, Any]] = []
        for index, raw_loan in enumerate(raw_loans):
            try:
                loans.append(LoanItem.from_dict(raw_loan))
            except ValidationError as exc:
                for detail in exc.errors():
                    loc = ("loans", index) + tuple(detail.get("loc", ()))
                    errors.append({"loc": loc, "msg": detail.get("msg", "不正な値です。")})
        if errors:
            raise ValidationError(errors)
        return cls(loans=loans)


@dataclass
class WorkingCapitalAssumptions(ModelMixin):
    """Operational working capital assumptions expressed in turnover days."""

    receivable_days: Decimal = Decimal("45")
    inventory_days: Decimal = Decimal("30")
    payable_days: Decimal = Decimal("35")

    def __post_init__(self) -> None:
        self.receivable_days = _as_decimal(self.receivable_days)
        self.inventory_days = _as_decimal(self.inventory_days)
        self.payable_days = _as_decimal(self.payable_days)
        self._validate()

    def _validate(self) -> None:
        for field_name, value in (
            ("receivable_days", self.receivable_days),
            ("inventory_days", self.inventory_days),
            ("payable_days", self.payable_days),
        ):
            if value < Decimal("0"):
                raise ValueError(f"{field_name} は0以上で入力してください。")
            if value > Decimal("365"):
                raise ValueError(f"{field_name} は365日以内で設定してください。")

    @classmethod
    def from_dict(cls, data: Any) -> "WorkingCapitalAssumptions":
        if isinstance(data, WorkingCapitalAssumptions):
            return data
        if not isinstance(data, Mapping):
            raise ValidationError([
                {"loc": tuple(), "msg": "運転資本設定は辞書形式で指定してください。"}
            ])
        defaults = {
            "receivable_days": Decimal("45"),
            "inventory_days": Decimal("30"),
            "payable_days": Decimal("35"),
        }
        errors: List[Dict[str, Any]] = []
        values: Dict[str, Decimal] = {}
        for key, default in defaults.items():
            raw_value = data.get(key, default)
            try:
                dec_value = _as_decimal(raw_value)
            except ValueError:
                errors.append({"loc": (key,), "msg": "数値を入力してください。"})
                continue
            if dec_value < Decimal("0"):
                errors.append({"loc": (key,), "msg": f"{key} は0以上で入力してください。"})
            elif dec_value > Decimal("365"):
                errors.append({"loc": (key,), "msg": f"{key} は365日以内で設定してください。"})
            else:
                values[key] = dec_value
        if errors:
            raise ValidationError(errors)
        return cls(**values)


@dataclass
class TaxPolicy(ModelMixin):
    corporate_tax_rate: Decimal = Decimal("0.30")
    consumption_tax_rate: Decimal = Decimal("0.10")
    dividend_payout_ratio: Decimal = Decimal("0.0")

    def __post_init__(self) -> None:
        self.corporate_tax_rate = _as_decimal(self.corporate_tax_rate)
        self.consumption_tax_rate = _as_decimal(self.consumption_tax_rate)
        self.dividend_payout_ratio = _as_decimal(self.dividend_payout_ratio)
        self._validate()

    def _validate(self) -> None:
        if not Decimal("0") <= self.corporate_tax_rate <= Decimal("0.55"):
            raise ValueError("法人税率は0%〜55%の範囲で設定してください。")
        if not Decimal("0") <= self.consumption_tax_rate <= Decimal("0.20"):
            raise ValueError("消費税率は0%〜20%の範囲で設定してください。")
        if not Decimal("0") <= self.dividend_payout_ratio <= Decimal("1"):
            raise ValueError("配当性向は0%〜100%の範囲で設定してください。")

    @classmethod
    def from_dict(cls, data: Any) -> "TaxPolicy":
        if isinstance(data, TaxPolicy):
            return data
        if not isinstance(data, Mapping):
            raise ValidationError([
                {"loc": tuple(), "msg": "税制設定は辞書形式で指定してください。"}
            ])
        defaults = {
            "corporate_tax_rate": Decimal("0.30"),
            "consumption_tax_rate": Decimal("0.10"),
            "dividend_payout_ratio": Decimal("0.0"),
        }
        bounds = {
            "corporate_tax_rate": (Decimal("0"), Decimal("0.55")),
            "consumption_tax_rate": (Decimal("0"), Decimal("0.20")),
            "dividend_payout_ratio": (Decimal("0"), Decimal("1")),
        }
        errors: List[Dict[str, Any]] = []
        values: Dict[str, Decimal] = {}
        for key, default in defaults.items():
            raw_value = data.get(key, default)
            try:
                dec_value = _as_decimal(raw_value)
            except ValueError:
                errors.append({"loc": (key,), "msg": "数値を入力してください。"})
                continue
            lower, upper = bounds[key]
            if dec_value < lower or dec_value > upper:
                errors.append({
                    "loc": (key,),
                    "msg": f"{key} は{lower}〜{upper}の範囲で設定してください。",
                })
            else:
                values[key] = dec_value
        if errors:
            raise ValidationError(errors)
        return cls(**values)

    def effective_tax(self, ordinary_income: Decimal) -> Decimal:
        if ordinary_income <= 0:
            return Decimal("0")
        return ordinary_income * self.corporate_tax_rate

    def projected_dividend(self, net_income: Decimal) -> Decimal:
        if net_income <= 0:
            return Decimal("0")
        return net_income * self.dividend_payout_ratio


@dataclass(frozen=True)
class FinanceBundle(ModelMixin):
    """Convenience container to pass around typed plan inputs."""

    sales: SalesPlan
    costs: CostPlan
    capex: CapexPlan
    loans: LoanSchedule
    tax: TaxPolicy
    working_capital: WorkingCapitalAssumptions

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FinanceBundle":
        errors: List[Dict[str, Any]] = []
        try:
            sales = SalesPlan.from_dict(data.get("sales", {}))
        except ValidationError as exc:
            for detail in exc.errors():
                errors.append({"loc": ("sales",) + tuple(detail.get("loc", ())), "msg": detail.get("msg", "不正な値です。")})
            sales = None
        try:
            costs = CostPlan.from_dict(data.get("costs", {}))
        except ValidationError as exc:
            for detail in exc.errors():
                errors.append({"loc": ("costs",) + tuple(detail.get("loc", ())), "msg": detail.get("msg", "不正な値です。")})
            costs = None
        try:
            capex = CapexPlan.from_dict(data.get("capex", {}))
        except ValidationError as exc:
            for detail in exc.errors():
                errors.append({"loc": ("capex",) + tuple(detail.get("loc", ())), "msg": detail.get("msg", "不正な値です。")})
            capex = None
        try:
            loans = LoanSchedule.from_dict(data.get("loans", {}))
        except ValidationError as exc:
            for detail in exc.errors():
                errors.append({"loc": ("loans",) + tuple(detail.get("loc", ())), "msg": detail.get("msg", "不正な値です。")})
            loans = None
        try:
            tax = TaxPolicy.from_dict(data.get("tax", {}))
        except ValidationError as exc:
            for detail in exc.errors():
                errors.append({"loc": ("tax",) + tuple(detail.get("loc", ())), "msg": detail.get("msg", "不正な値です。")})
            tax = None
        try:
            working_capital = WorkingCapitalAssumptions.from_dict(data.get("working_capital", {}))
        except ValidationError as exc:
            for detail in exc.errors():
                errors.append({"loc": ("working_capital",) + tuple(detail.get("loc", ())), "msg": detail.get("msg", "不正な値です。")})
            working_capital = None
        if errors or not all([sales, costs, capex, loans, tax, working_capital]):
            raise ValidationError(errors or [{"loc": tuple(), "msg": "無効な財務データが含まれています。"}])
        return cls(
            sales=sales,
            costs=costs,
            capex=capex,
            loans=loans,
            tax=tax,
            working_capital=working_capital,
        )


DEFAULT_SALES_PLAN = SalesPlan(
    items=[
        SalesItem(
            channel="オンライン",
            product="主力製品",
            monthly=MonthlySeries(amounts=[Decimal("80000000")] * 12),
        ),
    ]
)

DEFAULT_COST_PLAN = CostPlan(
    variable_ratios={
        "COGS_MAT": Decimal("0.25"),
        "COGS_LBR": Decimal("0.06"),
        "COGS_OUT_SRC": Decimal("0.10"),
        "COGS_OUT_CON": Decimal("0.04"),
        "COGS_OTH": Decimal("0.00"),
    },
    fixed_costs={
        "OPEX_H": Decimal("170000000"),
        "OPEX_K": Decimal("468000000"),
        "OPEX_DEP": Decimal("6000000"),
    },
    non_operating_income={
        "NOI_MISC": Decimal("100000"),
    },
    non_operating_expenses={
        "NOE_INT": Decimal("7400000"),
    },
)

DEFAULT_CAPEX_PLAN = CapexPlan(items=[])
DEFAULT_LOAN_SCHEDULE = LoanSchedule(loans=[])
DEFAULT_TAX_POLICY = TaxPolicy()
DEFAULT_WORKING_CAPITAL = WorkingCapitalAssumptions()

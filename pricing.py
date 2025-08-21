from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, List

import math


@dataclass
class InputRow:
    asin: str
    start_date: date
    min_acceptable_price: float
    ref_discount_percent: float  # e.g. 20 means 20% off -> factor 0.8
    past30_discount_percent: float  # e.g. 10 means 10% off -> factor 0.9


@dataclass
class OutputRow:
    asin: str
    start_date: date
    ref_price_floor: Optional[float]
    ref_window_start: Optional[date]
    ref_window_end: Optional[date]
    past30_price_floor: Optional[float]
    past_window_start: Optional[date]
    past_window_end: Optional[date]
    feasible: bool
    reason: Optional[str] = None


def _round_money(x: float) -> float:
    """Round to 2 decimals, half-up.

    Python's round is bankers' rounding; for currency, prefer half-up.
    """
    return math.floor(x * 100 + 0.5) / 100.0


def _ensure_positive(value: float, name: str) -> None:
    if value is None or not isinstance(value, (int, float)):
        raise ValueError(f"{name} 必须是数字")
    if value <= 0:
        raise ValueError(f"{name} 必须大于 0")


def _percent_to_factor(pct: float, name: str) -> float:
    if pct is None:
        raise ValueError(f"{name} 未提供")
    try:
        pct = float(pct)
    except Exception as e:
        raise ValueError(f"{name} 必须是数字") from e
    if pct < 0 or pct > 99.9999:  # 100% 折扣将导致价格为 0，不可行
        raise ValueError(f"{name} 应在 0-99.99 之间")
    return 1.0 - pct / 100.0


def parse_date(s: str) -> date:
    """Parse a date string.

    Accepts YYYY/MM/DD and MM/DD/YYYY. Also accepts ISO YYYY-MM-DD.
    """
    if isinstance(s, date):
        return s
    s = str(s).strip().replace(".", "/").replace("-", "/")
    for fmt in ("%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Try ISO fallback YYYY-MM-DD
    try:
        return datetime.fromisoformat(s.replace("/", "-")).date()
    except Exception:
        pass
    raise ValueError("日期格式应为 YYYY/MM/DD 或 MM/DD/YYYY")


def compute_needed_floors(
    min_acceptable_price: float,
    ref_discount_percent: float,
    past30_discount_percent: float,
    start_date: date,
) -> Tuple[Optional[float], Optional[float], date, date, date, date, bool, Optional[str]]:
    """
    Given seller's minimum acceptable promo price and discount requirements, compute:
    - Minimum reference price floor (R_needed)
    - Minimum past-30-day lowest price floor (L_needed)
    - 90-day window [S-90, S-1]
    - 30-day window [S-30, S-1]
    - Feasibility flag (always True if discounts < 100%)
    - Reason if infeasible
    """
    _ensure_positive(min_acceptable_price, "最低可接受活动价")
    if not isinstance(start_date, date):
        start_date = parse_date(start_date)

    ref_factor = _percent_to_factor(ref_discount_percent, "参考价折扣(%)")
    past_factor = _percent_to_factor(past30_discount_percent, "过去30天最低价折扣(%)")

    # If factor is 0, then R_needed/L_needed -> infinite; mark infeasible
    infeasible_reasons: List[str] = []

    R_needed: Optional[float]
    L_needed: Optional[float]

    if ref_factor <= 0:
        R_needed = None
        infeasible_reasons.append("参考价折扣为100%，无法满足最低活动价")
    else:
        R_needed = _round_money(min_acceptable_price / ref_factor)

    if past_factor <= 0:
        L_needed = None
        infeasible_reasons.append("过去30天最低价折扣为100%，无法满足最低活动价")
    else:
        L_needed = _round_money(min_acceptable_price / past_factor)

    ref_window_end = start_date - timedelta(days=1)
    ref_window_start = start_date - timedelta(days=90)
    past_window_end = start_date - timedelta(days=1)
    past_window_start = start_date - timedelta(days=30)

    feasible = len(infeasible_reasons) == 0
    reason = "; ".join(infeasible_reasons) if infeasible_reasons else None

    return (
        R_needed,
        L_needed,
        ref_window_start,
        ref_window_end,
        past_window_start,
        past_window_end,
        feasible,
        reason,
    )


def calculate_for_row(row: InputRow) -> OutputRow:
    (
        R_needed,
        L_needed,
        ref_window_start,
        ref_window_end,
        past_window_start,
        past_window_end,
        feasible,
        reason,
    ) = compute_needed_floors(
        row.min_acceptable_price,
        row.ref_discount_percent,
        row.past30_discount_percent,
        row.start_date,
    )

    return OutputRow(
        asin=row.asin,
        start_date=row.start_date,
        ref_price_floor=R_needed,
        ref_window_start=ref_window_start,
        ref_window_end=ref_window_end,
        past30_price_floor=L_needed,
        past_window_start=past_window_start,
        past_window_end=past_window_end,
        feasible=feasible,
        reason=reason,
    )


def build_suggestions(result: OutputRow) -> List[str]:
    tips: List[str] = []
    def fmt_date(d: Optional[date]) -> str:
        return d.strftime("%Y/%m/%d") if isinstance(d, date) else ""

    if result.ref_price_floor is not None and result.ref_window_start and result.ref_window_end:
        tips.append(
            f"参考价不得低于 ${result.ref_price_floor:.2f}，"
            f"{fmt_date(result.ref_window_start)}-{fmt_date(result.ref_window_end)} 期间不要将价格/促销价下调到该值以下，"
            f"且避免超过 70% 的时间以该价格促销。"
        )
    if result.past30_price_floor is not None and result.past_window_start and result.past_window_end:
        tips.append(
            f"{fmt_date(result.past_window_start)}-{fmt_date(result.past_window_end)} 期间，"
            f"产品实际成交价不得低于 ${result.past30_price_floor:.2f}。"
        )
    if not result.feasible and result.reason:
        tips.append(f"注意：{result.reason}")
    return tips


def generate_template_rows() -> List[InputRow]:
    today = date.today()
    return [
        InputRow(
            asin="B00EXAMPLE",
            start_date=today.replace(day=1) + timedelta(days=30),
            min_acceptable_price=19.99,
            ref_discount_percent=20.0,
            past30_discount_percent=10.0,
        )
    ]


# Optional: Pandas helpers (import lazily to avoid hard dependency if used as library)

def to_dataframe(rows: List[OutputRow]):
    import pandas as pd

    def fmt(d: Optional[date]) -> Optional[str]:
        return d.strftime("%Y/%m/%d") if isinstance(d, date) else None

    data = [
        {
            "ASIN": r.asin,
            "活动开始日期": fmt(r.start_date),
            "参考价最低不得低于": r.ref_price_floor,
            "参考价窗口开始": fmt(r.ref_window_start),
            "参考价窗口结束": fmt(r.ref_window_end),
            "过去30天最低价最低不得低于": r.past30_price_floor,
            "过去30天窗口开始": fmt(r.past_window_start),
            "过去30天窗口结束": fmt(r.past_window_end),
            "可行": r.feasible,
            "备注": r.reason or "",
        }
        for r in rows
    ]
    return pd.DataFrame(data)


def template_dataframe():
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "ASIN": "B00EXAMPLE",
                "活动开始日期(MM/DD/YYYY)": (date.today() + timedelta(days=14)).strftime("%m/%d/%Y"),
                "最低可接受活动价($)": 19.99,
                "参考价折扣要求(%)": 20,
                "过去30天最低价折扣(%)": 0,
            }
        ]
    )


def from_input_dataframe(df) -> List[InputRow]:
    date_col_candidates = [
        "活动开始日期(MM/DD/YYYY)",
        "活动开始日期(YYYY/MM/DD)",
    ]
    date_col = next((c for c in date_col_candidates if c in df.columns), None)
    if not date_col:
        raise ValueError("缺少列: 活动开始日期(MM/DD/YYYY) 或 活动开始日期(YYYY/MM/DD)")

    required_cols = [
        "ASIN",
        date_col,
        "最低可接受活动价($)",
        "参考价折扣要求(%)",
        "过去30天最低价折扣(%)",
    ]
    for c in required_cols:
        if c not in df.columns:
            raise ValueError(f"缺少列: {c}")

    rows: List[InputRow] = []
    for _, r in df.iterrows():
        rows.append(
            InputRow(
                asin=str(r["ASIN"]).strip(),
                start_date=parse_date(r[date_col]),
                min_acceptable_price=float(r["最低可接受活动价($)"]),
                ref_discount_percent=float(r["参考价折扣要求(%)"]),
                past30_discount_percent=float(r["过去30天最低价折扣(%)"]),
            )
        )
    return rows


def batch_calculate(rows: List[InputRow]) -> List[OutputRow]:
    return [calculate_for_row(r) for r in rows]
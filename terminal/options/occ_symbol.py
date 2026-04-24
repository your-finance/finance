"""Helpers for constructing OCC-standard option symbols."""

import re
from datetime import datetime
from typing import Dict


_OCC_RE = re.compile(r"^(?P<sym>[A-Z]{1,6})(?P<date>\d{6})(?P<cp>[CP])(?P<strike>\d{8})$")
_HUMAN_RE = re.compile(
    r"^(?P<sym>[A-Z]{1,6})\s+(?P<date>\d{4}-\d{2}-\d{2}|\d{6})\s+(?P<strike>\d+(?:\.\d+)?)(?P<cp>[CP])$"
)


def parse_option_contract(text: str) -> Dict[str, object]:
    """Parse an option contract from a user-friendly string.

    Accepted formats:
        - "QQQ 2026-09-18 410P"     (ISO date)
        - "QQQ 260918 410P"         (compact YYMMDD)
        - "QQQ260918P00410000"      (OCC symbol)

    Returns: {symbol, expiration ("YYYY-MM-DD"), strike (float), side ("CALL"|"PUT")}

    Raises ValueError with a readable message on bad input — trade.md uses the
    message verbatim to ask Boss for clarification.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("option contract is empty")

    raw = " ".join(text.strip().upper().split())  # collapse whitespace

    m = _OCC_RE.match(raw)
    if m:
        sym = m.group("sym")
        date_part = m.group("date")
        side = "CALL" if m.group("cp") == "C" else "PUT"
        strike = int(m.group("strike")) / 1000.0
        expiration = _parse_compact_date(date_part)
        return {"symbol": sym, "expiration": expiration, "strike": float(strike), "side": side}

    m = _HUMAN_RE.match(raw)
    if m:
        sym = m.group("sym")
        date_part = m.group("date")
        side = "CALL" if m.group("cp") == "C" else "PUT"
        strike = float(m.group("strike"))
        if strike <= 0:
            raise ValueError(f"strike must be positive: {raw!r}")
        if "-" in date_part:
            # validate ISO
            datetime.strptime(date_part, "%Y-%m-%d")
            expiration = date_part
        else:
            expiration = _parse_compact_date(date_part)
        return {"symbol": sym, "expiration": expiration, "strike": strike, "side": side}

    raise ValueError(
        f"could not parse option contract {text!r}. "
        f"Expected formats: 'QQQ 2026-09-18 410P', 'QQQ 260918 410P', or OCC 'QQQ260918P00410000'."
    )


def _parse_compact_date(yymmdd: str) -> str:
    """Convert YYMMDD -> YYYY-MM-DD. Two-digit year always treated as 20YY."""
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        raise ValueError(f"compact date must be YYMMDD digits, got {yymmdd!r}")
    dt = datetime.strptime(yymmdd, "%y%m%d")
    # %y maps 00-68 -> 2000-2068, 69-99 -> 1969-1999. Force 20YY.
    if dt.year < 2000:
        dt = dt.replace(year=dt.year + 100)
    return dt.strftime("%Y-%m-%d")


def build_occ_symbol(symbol: str, expiration: str, strike: float, side: str) -> str:
    """Build an OCC option symbol.

    Format: SYMBOL + YYMMDD + C/P + STRIKE*1000 padded to 8 digits
    Example: AAPL 2026-03-21 Call @ 200.0 -> AAPL260321C00200000
    """
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must be non-empty")

    side_upper = side.upper()
    if side_upper not in ("CALL", "PUT"):
        raise ValueError(f"side must be CALL or PUT, got {side}")

    exp_dt = datetime.strptime(expiration, "%Y-%m-%d")
    date_part = exp_dt.strftime("%y%m%d")
    cp = "C" if side_upper == "CALL" else "P"
    strike_int = int(round(strike * 1000))
    strike_part = f"{strike_int:08d}"
    return f"{normalized_symbol}{date_part}{cp}{strike_part}"

import pytest

from terminal.options.occ_symbol import build_occ_symbol, parse_option_contract


def test_standard_call():
    assert build_occ_symbol("AAPL", "2026-03-21", 200.0, "CALL") == "AAPL260321C00200000"


def test_standard_put():
    assert build_occ_symbol("AAPL", "2026-03-21", 200.0, "PUT") == "AAPL260321P00200000"


def test_lowercase_side():
    assert build_occ_symbol("AAPL", "2026-03-21", 200.0, "call") == "AAPL260321C00200000"


def test_fractional_strike():
    assert build_occ_symbol("NVDA", "2026-06-20", 152.5, "CALL") == "NVDA260620C00152500"


def test_small_strike():
    assert build_occ_symbol("SOFI", "2026-12-19", 7.5, "CALL") == "SOFI261219C00007500"


def test_long_ticker():
    assert build_occ_symbol("GOOGL", "2026-03-21", 180.0, "CALL") == "GOOGL260321C00180000"


def test_invalid_side():
    with pytest.raises(ValueError, match="side must be"):
        build_occ_symbol("AAPL", "2026-03-21", 200.0, "X")


def test_invalid_date():
    with pytest.raises(ValueError):
        build_occ_symbol("AAPL", "not-a-date", 200.0, "CALL")


def test_empty_symbol():
    with pytest.raises(ValueError, match="non-empty"):
        build_occ_symbol("   ", "2026-03-21", 200.0, "CALL")


# ----- parse_option_contract -----

class TestParseOptionContract:
    def test_parse_standard_contract(self):
        result = parse_option_contract("QQQ 2026-09-18 410P")
        assert result == {
            "symbol": "QQQ",
            "expiration": "2026-09-18",
            "strike": 410.0,
            "side": "PUT",
        }

    def test_parse_standard_contract_call(self):
        result = parse_option_contract("AAPL 2026-03-21 200C")
        assert result == {
            "symbol": "AAPL",
            "expiration": "2026-03-21",
            "strike": 200.0,
            "side": "CALL",
        }

    def test_parse_compact_date_contract(self):
        result = parse_option_contract("QQQ 260918 410P")
        assert result["expiration"] == "2026-09-18"
        assert result["side"] == "PUT"
        assert result["strike"] == 410.0
        assert result["symbol"] == "QQQ"

    def test_parse_occ_symbol(self):
        result = parse_option_contract("QQQ260918P00410000")
        assert result == {
            "symbol": "QQQ",
            "expiration": "2026-09-18",
            "strike": 410.0,
            "side": "PUT",
        }

    def test_parse_occ_symbol_call(self):
        result = parse_option_contract("AAPL260321C00200000")
        assert result["side"] == "CALL"
        assert result["strike"] == 200.0

    def test_parse_occ_fractional_strike(self):
        result = parse_option_contract("NVDA260620C00152500")
        assert result["strike"] == 152.5

    def test_parse_long_ticker_occ(self):
        result = parse_option_contract("GOOGL260321C00180000")
        assert result["symbol"] == "GOOGL"
        assert result["strike"] == 180.0

    def test_parse_fractional_strike_standard(self):
        result = parse_option_contract("NVDA 2026-06-20 152.5C")
        assert result["strike"] == 152.5

    def test_parse_lowercase_side(self):
        result = parse_option_contract("QQQ 2026-09-18 410p")
        assert result["side"] == "PUT"

    def test_parse_extra_whitespace(self):
        result = parse_option_contract("  QQQ   2026-09-18   410P  ")
        assert result["symbol"] == "QQQ"

    def test_invalid_contract_raises(self):
        with pytest.raises(ValueError):
            parse_option_contract("QQQ 410 maybe")

    def test_invalid_side_letter_raises(self):
        with pytest.raises(ValueError):
            parse_option_contract("QQQ 2026-09-18 410X")

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            parse_option_contract("")

    def test_negative_strike_raises(self):
        with pytest.raises(ValueError):
            parse_option_contract("QQQ 2026-09-18 -410P")

    def test_round_trip_with_build(self):
        """parse -> build -> parse should be idempotent."""
        original = parse_option_contract("QQQ260918P00410000")
        rebuilt = build_occ_symbol(
            original["symbol"], original["expiration"],
            original["strike"], original["side"],
        )
        assert rebuilt == "QQQ260918P00410000"
        assert parse_option_contract(rebuilt) == original

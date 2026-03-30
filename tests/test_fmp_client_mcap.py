"""FMP historical market cap 方法测试（mock HTTP）"""
import pytest
from unittest.mock import patch
from src.data.fmp_client import FMPClient


@pytest.fixture
def client():
    return FMPClient(api_key="test_key")


def test_get_historical_market_cap_success(client):
    mock_data = [
        {"symbol": "AAPL", "date": "2024-01-02", "marketCap": 3000000000000},
        {"symbol": "AAPL", "date": "2024-01-03", "marketCap": 3050000000000},
    ]
    with patch.object(client, '_request', return_value=mock_data):
        result = client.get_historical_market_cap("AAPL", "2024-01-01", "2024-01-10")
    assert len(result) == 2
    assert result[0]["market_cap"] == 3000000000000
    assert result[0]["date"] == "2024-01-02"
    assert result[0]["symbol"] == "AAPL"


def test_get_historical_market_cap_empty(client):
    with patch.object(client, '_request', return_value=[]):
        result = client.get_historical_market_cap("ZZZZ", "2024-01-01", "2024-01-10")
    assert result == []


def test_get_historical_market_cap_none_response(client):
    with patch.object(client, '_request', return_value=None):
        result = client.get_historical_market_cap("AAPL", "2024-01-01", "2024-01-10")
    assert result == []


def test_get_historical_market_cap_calls_stable_endpoint(client):
    """确认调用的是 stable 端点路径，symbol 作为 query param"""
    with patch.object(client, '_request', return_value=[]) as mock_req:
        client.get_historical_market_cap("AAPL", "2024-01-01", "2024-12-31")
    mock_req.assert_called_once_with(
        "historical-market-capitalization",
        {"symbol": "AAPL", "from": "2024-01-01", "to": "2024-12-31"},
    )

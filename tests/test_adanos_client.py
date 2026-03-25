"""Tests for Adanos social sentiment API client."""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.data.adanos_client import AdanosClient, _SOURCE_CONFIG


# --- Fixtures ---

SAMPLE_REDDIT_RESPONSE = {
    "ticker": "NVDA",
    "company_name": "NVIDIA Corp",
    "found": True,
    "buzz_score": 76.7,
    "mentions": 750,
    "sentiment_score": 0.034,
    "positive_count": 506,
    "negative_count": 408,
    "neutral_count": 615,
    "total_upvotes": 5249,
    "unique_posts": 418,
    "subreddit_count": 29,
    "trend": "rising",
    "bullish_pct": 33,
    "bearish_pct": 27,
    "period_days": 7,
    "top_subreddits": [
        {"subreddit": "wallstreetbets", "count": 133},
        {"subreddit": "stocks", "count": 44},
    ],
    "daily_trend": [
        {"date": "2026-03-08", "mentions": 113, "sentiment_score": 0.032, "buzz_score": 78.0},
        {"date": "2026-03-07", "mentions": 87, "sentiment_score": 0.047, "buzz_score": 74.6},
        {"date": "2026-03-06", "mentions": 135, "sentiment_score": 0.069, "buzz_score": 80.3},
    ],
    "top_mentions": [
        {"text_snippet": "NVDA is great", "sentiment_score": 0.5, "upvotes": 10,
         "subreddit": "stocks", "created_utc": "2026-03-08T12:00:00"},
    ],
}

SAMPLE_X_RESPONSE = {
    "ticker": "NVDA",
    "company_name": "NVIDIA Corp",
    "found": True,
    "buzz_score": 84.2,
    "mentions": 2503,
    "sentiment_score": 0.177,
    "positive_count": 1324,
    "negative_count": 412,
    "neutral_count": 767,
    "total_upvotes": 56775,
    "unique_tweets": 2503,
    "trend": "rising",
    "bullish_pct": 53,
    "bearish_pct": 16,
    "period_days": 7,
    "is_validated": True,
    "daily_trend": [
        {"date": "2026-03-08", "mentions": 296, "sentiment_score": 0.152, "buzz_score": 86.5},
        {"date": "2026-03-07", "mentions": 286, "sentiment_score": 0.196, "buzz_score": 86.0},
    ],
    "top_tweets": [
        {"text_snippet": "NVDA rally!", "sentiment_score": 0.4, "likes": 1000,
         "author": "trader1", "created_at": "2026-03-08T14:00:00Z"},
    ],
}

SAMPLE_REDDIT_TRENDING = [
    {
        "ticker": "GOOGL",
        "company_name": "Alphabet Inc - Class A",
        "buzz_score": 78.7,
        "trend": "rising",
        "mentions": 1108,
        "unique_posts": 786,
        "subreddit_count": 35,
        "sentiment_score": 0.007,
        "bullish_pct": 34,
        "bearish_pct": 33,
        "total_upvotes": 3219,
        "trend_history": [78.1, 80.1, 78.4, 79.2, 75.0, 80.1, 78.7],
    },
    {
        "ticker": "AAPL",
        "company_name": "Apple Inc",
        "buzz_score": 74.1,
        "trend": "stable",
        "mentions": 640,
        "unique_posts": 500,
        "subreddit_count": 20,
        "sentiment_score": 0.03,
        "bullish_pct": 41,
        "bearish_pct": 18,
        "total_upvotes": 2100,
        "trend_history": [72.0, 72.4, 73.8, 73.5, 74.4, 74.0, 74.1],
    },
]

SAMPLE_X_TRENDING = [
    {
        "ticker": "TSLA",
        "company_name": "Tesla Inc",
        "buzz_score": 89.3,
        "trend": "rising",
        "mentions": 2932,
        "sentiment_score": 0.218,
        "bullish_pct": 57,
        "bearish_pct": 19,
        "total_upvotes": 264703,
        "unique_tweets": 2932,
        "is_validated": True,
        "trend_history": [87.17, 88.0, 89.24, 90.42, 88.14, 90.0, 89.3],
    },
]

SAMPLE_REDDIT_SECTORS = [
    {
        "buzz_score": 89.74727788563018,
        "trend": "stable",
        "mentions": 12046,
        "unique_tickers": 536,
        "subreddit_count": 50,
        "sentiment_score": 0.083,
        "bullish_pct": 70,
        "bearish_pct": 45,
        "total_upvotes": 38017,
        "top_tickers": ["SPY", "VOO", "VT", "VTI", "VXUS"],
        "sector": "Financials",
    },
]

SAMPLE_X_SECTORS = [
    {
        "buzz_score": 91.4,
        "trend": "stable",
        "mentions": 22435,
        "unique_tickers": 227,
        "unique_authors": 11217,
        "sentiment_score": 0.318,
        "bullish_pct": 67,
        "bearish_pct": 11,
        "total_upvotes": 389894,
        "top_tickers": ["NVDA", "MSTR", "AAPL", "MSFT", "MU"],
        "sector": "Information Technology",
    },
]

SAMPLE_REDDIT_MARKET = {
    "buzz_score": 47.7,
    "trend": "stable",
    "mentions": 54836,
    "unique_posts": 21190,
    "subreddit_count": 52,
    "total_upvotes": 122458,
    "active_tickers": 2764,
    "sentiment_score": 0.043,
    "positive_count": 20091,
    "negative_count": 14603,
    "neutral_count": 20142,
    "bullish_pct": 37,
    "bearish_pct": 27,
    "trend_history": [49.8, 50.1, 50.0, 49.7, 49.7, 49.2, 47.7],
    "drivers": [
        {"ticker": "GOOGL", "mentions": 1113, "buzz_score": 78.7, "sentiment_score": 0.007},
        {"ticker": "TSLA", "mentions": 649, "buzz_score": 76.7, "sentiment_score": -0.066},
    ],
}

SAMPLE_X_MARKET = {
    "buzz_score": 60.0,
    "trend": "rising",
    "mentions": 44488,
    "unique_tweets": 44209,
    "unique_authors": 18688,
    "total_upvotes": 941035,
    "active_tickers": 1124,
    "sentiment_score": 0.299,
    "positive_count": 28809,
    "negative_count": 5872,
    "neutral_count": 9807,
    "bullish_pct": 65,
    "bearish_pct": 13,
    "trend_history": [61.0, 61.0, 61.4, 61.1, 61.5, 61.4, 60.0],
    "drivers": [
        {"ticker": "TSLA", "mentions": 2921, "buzz_score": 89.3, "sentiment_score": 0.219},
        {"ticker": "NVDA", "mentions": 2165, "buzz_score": 86.4, "sentiment_score": 0.243},
    ],
}

FIXED_UTC_NOW = datetime(2026, 3, 25, 22, 55, tzinfo=timezone.utc)


@pytest.fixture
def client():
    return AdanosClient(api_key="test_key")


# --- Tests ---

class TestAdanosClient:

    def test_init(self, client):
        assert client.api_key == "test_key"
        assert client.base_url == "https://api.adanos.org"

    def test_invalid_source_raises(self, client):
        with pytest.raises(ValueError, match="Invalid source"):
            client.get_stock_sentiment("NVDA", source="tiktok")

    @patch("src.data.adanos_client.requests.get")
    def test_get_stock_sentiment_reddit(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_REDDIT_RESPONSE
        mock_get.return_value = mock_resp

        result = client.get_stock_sentiment("NVDA", source="reddit", days=7)

        assert result is not None
        assert result["ticker"] == "NVDA"
        assert result["buzz_score"] == 76.7
        assert result["mentions"] == 750
        assert result["bullish_pct"] == 33
        assert len(result["daily_trend"]) == 3

        # Verify endpoint
        call_url = mock_get.call_args[0][0]
        assert "/reddit/stocks/v1/stock/NVDA" in call_url

    @patch("src.data.adanos_client.requests.get")
    def test_get_stock_sentiment_x(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_X_RESPONSE
        mock_get.return_value = mock_resp

        result = client.get_stock_sentiment("NVDA", source="x", days=7)

        assert result is not None
        assert result["buzz_score"] == 84.2
        assert result["unique_tweets"] == 2503

        call_url = mock_get.call_args[0][0]
        assert "/x/stocks/v1/stock/NVDA" in call_url

    @patch("src.data.adanos_client.requests.get")
    def test_not_found_returns_none(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ticker": "ZZZZ", "found": False}
        mock_get.return_value = mock_resp

        result = client.get_stock_sentiment("ZZZZ", source="reddit")
        assert result is None

    @patch("src.data.adanos_client.requests.get")
    def test_auth_error_returns_none(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_get.return_value = mock_resp

        result = client.get_stock_sentiment("NVDA", source="reddit")
        assert result is None

    def test_no_api_key_returns_none(self):
        client = AdanosClient(api_key="")
        result = client.get_stock_sentiment("NVDA", source="reddit")
        assert result is None


class TestGetSentimentRows:

    @patch("src.data.adanos_client.requests.get")
    def test_reddit_rows_expanded(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_REDDIT_RESPONSE
        mock_get.return_value = mock_resp

        rows = client.get_sentiment_rows("NVDA", source="reddit", days=7)

        assert len(rows) == 3  # 3 days in daily_trend
        assert rows[0]["date"] == "2026-03-08"
        assert rows[0]["source"] == "reddit"
        assert rows[0]["buzz_score"] == 78.0  # day-level buzz
        assert rows[0]["total_mentions"] == 113
        assert rows[0]["sentiment_score"] == 0.032
        assert rows[0]["bullish_pct"] == 33  # aggregate, only on latest day
        assert rows[0]["subreddit_count"] == 29
        # Non-latest days should have None for aggregate fields
        assert rows[1]["bullish_pct"] is None
        assert rows[1]["subreddit_count"] is None
        assert rows[2]["positive_count"] is None
        assert rows[0]["created_at"] is not None

        # top_mentions JSON only on first (latest) day
        assert rows[0]["top_mentions"] is not None
        parsed = json.loads(rows[0]["top_mentions"])
        assert isinstance(parsed, list)
        assert rows[1]["top_mentions"] is None
        assert rows[2]["top_mentions"] is None

        # top_subreddits JSON only on first day
        assert rows[0]["top_subreddits"] is not None
        assert rows[1]["top_subreddits"] is None

    @patch("src.data.adanos_client.requests.get")
    def test_x_rows_field_mapping(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_X_RESPONSE
        mock_get.return_value = mock_resp

        rows = client.get_sentiment_rows("NVDA", source="x", days=7)

        assert len(rows) == 2
        assert rows[0]["source"] == "x"
        # unique_tweets → unique_posts
        assert rows[0]["unique_posts"] == 2503
        # is_validated mapped
        assert rows[0]["is_validated"] == 1
        # subreddit_count should be None for X
        assert rows[0]["subreddit_count"] is None
        # top_subreddits should be None for X
        assert rows[0]["top_subreddits"] is None

    @patch("src.data.adanos_client.requests.get")
    def test_reversed_daily_trend_order(self, mock_get, client):
        """Aggregate fields must land on max-date row regardless of API ordering."""
        reversed_response = dict(SAMPLE_REDDIT_RESPONSE)
        reversed_response["daily_trend"] = list(reversed(
            SAMPLE_REDDIT_RESPONSE["daily_trend"]
        ))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = reversed_response
        mock_get.return_value = mock_resp

        rows = client.get_sentiment_rows("NVDA", source="reddit", days=7)
        assert len(rows) == 3
        # Find the row with max date — it should have aggregate fields
        latest_row = [r for r in rows if r["date"] == "2026-03-08"][0]
        oldest_row = [r for r in rows if r["date"] == "2026-03-06"][0]
        assert latest_row["bullish_pct"] == 33
        assert latest_row["top_mentions"] is not None
        assert latest_row["subreddit_count"] == 29
        # Older rows should NOT have aggregate fields
        assert oldest_row["bullish_pct"] is None
        assert oldest_row["top_mentions"] is None
        assert oldest_row["subreddit_count"] is None

    @patch("src.data.adanos_client.requests.get")
    def test_api_failure_returns_empty(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        rows = client.get_sentiment_rows("NVDA", source="reddit")
        assert rows == []

    @patch("src.data.adanos_client.requests.get")
    def test_empty_daily_trend_returns_empty(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ticker": "NVDA", "found": True,
            "buzz_score": 50, "daily_trend": [],
        }
        mock_get.return_value = mock_resp

        rows = client.get_sentiment_rows("NVDA", source="reddit")
        assert rows == []


class TestGetTrending:

    @patch("src.data.adanos_client.requests.get")
    def test_trending_returns_list(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_REDDIT_TRENDING
        mock_get.return_value = mock_resp

        result = client.get_trending(source="reddit", days=7, limit=5)
        assert len(result) == 2
        assert result[0]["ticker"] == "GOOGL"

    @patch("src.data.adanos_client.requests.get")
    def test_trending_failure_returns_none(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        result = client.get_trending(source="x")
        assert result is None

    @patch("src.data.adanos_client.requests.get")
    def test_get_trending_rows_reddit(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_REDDIT_TRENDING
        mock_get.return_value = mock_resp

        with patch("src.data.adanos_client._utc_now", return_value=FIXED_UTC_NOW):
            rows = client.get_trending_rows(source="reddit", days=7, limit=5)

        assert rows is not None
        assert len(rows) == 2
        assert rows[0]["date"] == "2026-03-25"
        assert rows[0]["rank"] == 1
        assert rows[0]["ticker"] == "GOOGL"
        assert rows[0]["unique_posts"] == 786
        assert rows[0]["subreddit_count"] == 35
        assert rows[0]["is_validated"] is None
        assert json.loads(rows[0]["trend_history"]) == SAMPLE_REDDIT_TRENDING[0]["trend_history"]
        assert rows[0]["period_days"] == 7
        assert rows[0]["created_at"] == "2026-03-25T22:55:00Z"

    @patch("src.data.adanos_client.requests.get")
    def test_get_trending_rows_x_maps_unique_tweets(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_X_TRENDING
        mock_get.return_value = mock_resp

        with patch("src.data.adanos_client._utc_now", return_value=FIXED_UTC_NOW):
            rows = client.get_trending_rows(source="x", days=7, limit=5)

        assert rows is not None
        assert len(rows) == 1
        assert rows[0]["unique_posts"] == 2932
        assert rows[0]["is_validated"] == 1
        assert rows[0]["subreddit_count"] is None
        assert json.loads(rows[0]["trend_history"]) == SAMPLE_X_TRENDING[0]["trend_history"]


class TestGetMarketSentiment:

    @patch("src.data.adanos_client.requests.get")
    def test_market_sentiment_returns_dict(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_REDDIT_MARKET
        mock_get.return_value = mock_resp

        result = client.get_market_sentiment(source="reddit", days=7)
        assert result is not None
        assert result["active_tickers"] == 2764
        assert result["mentions"] == 54836

    @patch("src.data.adanos_client.requests.get")
    def test_market_sentiment_failure_returns_none(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        result = client.get_market_sentiment(source="x")
        assert result is None

    @patch("src.data.adanos_client.requests.get")
    def test_market_sentiment_row_reddit(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_REDDIT_MARKET
        mock_get.return_value = mock_resp

        with patch("src.data.adanos_client._utc_now", return_value=FIXED_UTC_NOW):
            row = client.get_market_sentiment_row(source="reddit", days=7)

        assert row is not None
        assert row["date"] == "2026-03-25"
        assert row["unique_posts"] == 21190
        assert row["subreddit_count"] == 52
        assert row["unique_authors"] is None
        assert row["active_tickers"] == 2764
        assert json.loads(row["trend_history"]) == SAMPLE_REDDIT_MARKET["trend_history"]
        assert json.loads(row["drivers"]) == SAMPLE_REDDIT_MARKET["drivers"]
        assert json.loads(row["raw_json"])["buzz_score"] == 47.7
        assert row["created_at"] == "2026-03-25T22:55:00Z"

    @patch("src.data.adanos_client.requests.get")
    def test_market_sentiment_row_x_maps_unique_tweets(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_X_MARKET
        mock_get.return_value = mock_resp

        with patch("src.data.adanos_client._utc_now", return_value=FIXED_UTC_NOW):
            row = client.get_market_sentiment_row(source="x", days=7)

        assert row is not None
        assert row["unique_posts"] == 44209
        assert row["unique_authors"] == 18688
        assert row["subreddit_count"] is None
        assert row["active_tickers"] == 1124
        assert json.loads(row["drivers"]) == SAMPLE_X_MARKET["drivers"]


class TestGetTrendingSectors:

    @patch("src.data.adanos_client.requests.get")
    def test_trending_sectors_returns_list(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_REDDIT_SECTORS
        mock_get.return_value = mock_resp

        result = client.get_trending_sectors(source="reddit", days=7, limit=5)
        assert result is not None
        assert len(result) == 1
        assert result[0]["sector"] == "Financials"

    @patch("src.data.adanos_client.requests.get")
    def test_trending_sectors_failure_returns_none(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        result = client.get_trending_sectors(source="x")
        assert result is None

    @patch("src.data.adanos_client.requests.get")
    def test_get_trending_sectors_rows_x(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_X_SECTORS
        mock_get.return_value = mock_resp

        with patch("src.data.adanos_client._utc_now", return_value=FIXED_UTC_NOW):
            rows = client.get_trending_sectors_rows(source="x", days=7, limit=5)

        assert rows is not None
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-03-25"
        assert rows[0]["sector"] == "Information Technology"
        assert rows[0]["unique_authors"] == 11217
        assert rows[0]["subreddit_count"] is None
        assert json.loads(rows[0]["top_tickers"]) == SAMPLE_X_SECTORS[0]["top_tickers"]
        assert rows[0]["created_at"] == "2026-03-25T22:55:00Z"

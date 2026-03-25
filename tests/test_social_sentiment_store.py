"""Tests for social_sentiment table in MarketStore."""
import pytest
from pathlib import Path
from src.data.market_store import MarketStore


@pytest.fixture
def store(tmp_path):
    """Create a temporary MarketStore."""
    db_path = tmp_path / "test_market.db"
    return MarketStore(db_path=db_path)


def _make_rows(source="reddit", days=3, base_mentions=100):
    """Generate sample social sentiment rows."""
    rows = []
    for i in range(days):
        rows.append({
            "date": "2026-03-{:02d}".format(10 - i),
            "source": source,
            "buzz_score": 70.0 + i,
            "total_mentions": base_mentions + i * 10,
            "sentiment_score": 0.05 * (i + 1),
            "positive_count": 50 + i,
            "negative_count": 30 + i,
            "neutral_count": 20 + i,
            "bullish_pct": 35 + i,
            "bearish_pct": 25 - i,
            "trend": "rising" if i == 0 else "stable",
            "total_upvotes": 1000 + i * 100,
            "unique_posts": 80 + i,
            "subreddit_count": 10 if source == "reddit" else None,
            "is_validated": None if source == "reddit" else 1,
            "top_mentions": '["test snippet"]' if i == 0 else None,
            "top_subreddits": '[{"subreddit": "wsb"}]' if i == 0 and source == "reddit" else None,
            "period_days": 7,
            "created_at": "2026-03-10T07:00:00",
        })
    return rows


def _make_trending_rows(source="reddit", count=3, date="2026-03-25"):
    rows = []
    for rank in range(1, count + 1):
        rows.append({
            "date": date,
            "source": source,
            "rank": rank,
            "ticker": "T{:02d}".format(rank),
            "company_name": "Company {}".format(rank),
            "buzz_score": 90.0 - rank,
            "trend": "rising" if rank == 1 else "stable",
            "mentions": 1000 - rank * 10,
            "sentiment_score": 0.1 * rank,
            "bullish_pct": 40 + rank,
            "bearish_pct": 20 - rank,
            "total_upvotes": 10000 + rank,
            "trend_history": "[70.0, 80.0, 90.0]",
            "unique_posts": 500 + rank,
            "subreddit_count": 10 if source == "reddit" else None,
            "is_validated": None if source == "reddit" else 1,
            "period_days": 7,
            "created_at": "2026-03-25T22:55:00Z",
        })
    return rows


def _make_sector_rows(source="reddit", date="2026-03-25"):
    return [
        {
            "date": date,
            "source": source,
            "sector": "Information Technology",
            "buzz_score": 91.4,
            "trend": "stable",
            "mentions": 22435,
            "unique_tickers": 227,
            "sentiment_score": 0.318,
            "bullish_pct": 67,
            "bearish_pct": 11,
            "total_upvotes": 389894,
            "top_tickers": '["NVDA","MSTR","AAPL"]',
            "subreddit_count": 50 if source == "reddit" else None,
            "unique_authors": None if source == "reddit" else 11217,
            "period_days": 7,
            "created_at": "2026-03-25T22:55:00Z",
        },
        {
            "date": date,
            "source": source,
            "sector": "Financials",
            "buzz_score": 85.0,
            "trend": "rising",
            "mentions": 12046,
            "unique_tickers": 536,
            "sentiment_score": 0.083,
            "bullish_pct": 70,
            "bearish_pct": 45,
            "total_upvotes": 38017,
            "top_tickers": '["SPY","VOO"]',
            "subreddit_count": 50 if source == "reddit" else None,
            "unique_authors": None if source == "reddit" else 9000,
            "period_days": 7,
            "created_at": "2026-03-25T22:55:00Z",
        },
    ]


def _make_market_sentiment_rows(source="reddit", date="2026-03-25", buzz_score=47.7):
    return [{
        "date": date,
        "source": source,
        "buzz_score": buzz_score,
        "trend": "stable" if source == "reddit" else "rising",
        "mentions": 54836 if source == "reddit" else 44488,
        "unique_posts": 21190 if source == "reddit" else 44209,
        "unique_authors": None if source == "reddit" else 18688,
        "subreddit_count": 52 if source == "reddit" else None,
        "total_upvotes": 122458 if source == "reddit" else 941035,
        "active_tickers": 2764 if source == "reddit" else 1124,
        "sentiment_score": 0.043 if source == "reddit" else 0.299,
        "positive_count": 20091 if source == "reddit" else 28809,
        "negative_count": 14603 if source == "reddit" else 5872,
        "neutral_count": 20142 if source == "reddit" else 9807,
        "bullish_pct": 37 if source == "reddit" else 65,
        "bearish_pct": 27 if source == "reddit" else 13,
        "trend_history": "[49.8, 50.1, 50.0, 49.7, 49.7, 49.2, 47.7]",
        "drivers": '[{"ticker":"GOOGL"}]',
        "raw_json": '{"buzz_score": 47.7}',
        "period_days": 7,
        "created_at": "2026-03-25T22:55:00Z",
    }]


class TestUpsertSocialSentiment:

    def test_basic_upsert(self, store):
        rows = _make_rows(source="reddit", days=3)
        count = store.upsert_social_sentiment("NVDA", rows)
        assert count == 3

    def test_upsert_both_sources(self, store):
        reddit_rows = _make_rows(source="reddit", days=2)
        x_rows = _make_rows(source="x", days=2)
        store.upsert_social_sentiment("NVDA", reddit_rows)
        store.upsert_social_sentiment("NVDA", x_rows)

        all_rows = store.get_social_sentiment("NVDA", limit=10)
        assert len(all_rows) == 4  # 2 reddit + 2 x

    def test_upsert_replaces_on_conflict(self, store):
        rows = _make_rows(source="reddit", days=1)
        store.upsert_social_sentiment("NVDA", rows)

        # Update with different buzz
        rows[0]["buzz_score"] = 99.9
        store.upsert_social_sentiment("NVDA", rows)

        result = store.get_social_sentiment("NVDA", source="reddit", limit=1)
        assert len(result) == 1
        assert result[0]["buzz_score"] == 99.9

    def test_upsert_empty_rows(self, store):
        count = store.upsert_social_sentiment("NVDA", [])
        assert count == 0

    def test_upsert_skips_missing_date(self, store):
        rows = [{"source": "reddit", "buzz_score": 50, "created_at": "now"}]
        count = store.upsert_social_sentiment("NVDA", rows)
        assert count == 0

    def test_upsert_skips_missing_source(self, store):
        rows = [{"date": "2026-03-10", "buzz_score": 50, "created_at": "now"}]
        count = store.upsert_social_sentiment("NVDA", rows)
        assert count == 0

    def test_symbol_uppercased(self, store):
        rows = _make_rows(source="reddit", days=1)
        store.upsert_social_sentiment("nvda", rows)
        result = store.get_social_sentiment("NVDA")
        assert len(result) == 1
        assert result[0]["symbol"] == "NVDA"


class TestGetSocialSentiment:

    def test_get_with_source_filter(self, store):
        store.upsert_social_sentiment("NVDA", _make_rows("reddit", 3))
        store.upsert_social_sentiment("NVDA", _make_rows("x", 3))

        reddit_only = store.get_social_sentiment("NVDA", source="reddit")
        assert all(r["source"] == "reddit" for r in reddit_only)

        x_only = store.get_social_sentiment("NVDA", source="x")
        assert all(r["source"] == "x" for r in x_only)

    def test_get_ordered_newest_first(self, store):
        store.upsert_social_sentiment("NVDA", _make_rows("reddit", 3))
        rows = store.get_social_sentiment("NVDA", source="reddit")
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates, reverse=True)

    def test_get_with_limit(self, store):
        store.upsert_social_sentiment("NVDA", _make_rows("reddit", 5))
        rows = store.get_social_sentiment("NVDA", source="reddit", limit=2)
        assert len(rows) == 2

    def test_get_nonexistent_symbol(self, store):
        rows = store.get_social_sentiment("ZZZZ")
        assert rows == []


class TestGetLatestSocialSentiment:

    def test_latest_returns_one(self, store):
        store.upsert_social_sentiment("NVDA", _make_rows("reddit", 3))
        latest = store.get_latest_social_sentiment("NVDA", source="reddit")
        assert latest is not None
        assert latest["date"] == "2026-03-10"

    def test_latest_no_data(self, store):
        assert store.get_latest_social_sentiment("ZZZZ") is None


class TestGetSocialSentimentBulk:

    def test_bulk_returns_dict(self, store):
        store.upsert_social_sentiment("NVDA", _make_rows("reddit", 2))
        store.upsert_social_sentiment("AAPL", _make_rows("reddit", 2))

        result = store.get_social_sentiment_bulk(["NVDA", "AAPL", "ZZZZ"])
        assert "NVDA" in result
        assert "AAPL" in result
        assert "ZZZZ" not in result

    def test_bulk_with_source_filter(self, store):
        store.upsert_social_sentiment("NVDA", _make_rows("reddit", 2))
        store.upsert_social_sentiment("NVDA", _make_rows("x", 2))

        result = store.get_social_sentiment_bulk(["NVDA"], source="reddit")
        assert all(r["source"] == "reddit" for r in result["NVDA"])


class TestSchemaIntegrity:

    def test_social_sentiment_in_stats(self, store):
        stats = store.get_stats()
        assert "social_sentiment" in stats
        assert "market_sentiment" in stats
        assert stats["social_sentiment"] == 0

    def test_social_sentiment_in_valid_tables(self):
        from src.data.market_store import _VALID_TABLES
        assert "social_sentiment" in _VALID_TABLES
        assert "market_sentiment" in _VALID_TABLES
        assert "social_trending" in _VALID_TABLES
        assert "social_trending_sectors" in _VALID_TABLES

    def test_all_fields_stored(self, store):
        rows = _make_rows("reddit", 1)
        store.upsert_social_sentiment("NVDA", rows)
        result = store.get_social_sentiment("NVDA")[0]

        assert result["buzz_score"] == 70.0
        assert result["total_mentions"] == 100
        assert result["sentiment_score"] == 0.05
        assert result["positive_count"] == 50
        assert result["negative_count"] == 30
        assert result["neutral_count"] == 20
        assert result["bullish_pct"] == 35
        assert result["bearish_pct"] == 25
        assert result["trend"] == "rising"
        assert result["total_upvotes"] == 1000
        assert result["unique_posts"] == 80
        assert result["subreddit_count"] == 10
        assert result["top_mentions"] == '["test snippet"]'
        assert result["top_subreddits"] == '[{"subreddit": "wsb"}]'
        assert result["period_days"] == 7
        assert result["created_at"] == "2026-03-10T07:00:00"


class TestSocialTrendingStore:

    def test_upsert_social_trending_replaces_day_source_snapshot(self, store):
        date = "2026-03-25"
        store.upsert_social_trending(date, "reddit", _make_trending_rows("reddit", count=3))
        store.upsert_social_trending(date, "reddit", _make_trending_rows("reddit", count=2))

        rows = store.get_social_trending(date, "reddit")
        assert len(rows) == 2
        assert [r["rank"] for r in rows] == [1, 2]

    def test_upsert_social_trending_empty_rows_clears_existing(self, store):
        date = "2026-03-25"
        store.upsert_social_trending(date, "x", _make_trending_rows("x", count=2))
        cleared = store.upsert_social_trending(date, "x", [])

        assert cleared == 0
        assert store.get_social_trending(date, "x") == []

    def test_get_social_trending_orders_by_rank(self, store):
        date = "2026-03-25"
        rows = _make_trending_rows("reddit", count=3)
        rows[0]["rank"] = 3
        rows[1]["rank"] = 1
        rows[2]["rank"] = 2
        store.upsert_social_trending(date, "reddit", rows)

        result = store.get_social_trending(date, "reddit")
        assert [r["rank"] for r in result] == [1, 2, 3]


class TestSocialTrendingSectorsStore:

    def test_upsert_social_trending_sectors_replaces_day_source_snapshot(self, store):
        date = "2026-03-25"
        store.upsert_social_trending_sectors(date, "reddit", _make_sector_rows("reddit"))
        store.upsert_social_trending_sectors(date, "reddit", _make_sector_rows("reddit")[:1])

        rows = store.get_social_trending_sectors(date, "reddit")
        assert len(rows) == 1
        assert rows[0]["sector"] == "Information Technology"

    def test_get_social_trending_sectors_orders_by_buzz_score(self, store):
        date = "2026-03-25"
        store.upsert_social_trending_sectors(date, "x", _make_sector_rows("x"))

        rows = store.get_social_trending_sectors(date, "x")
        assert len(rows) == 2
        assert rows[0]["buzz_score"] >= rows[1]["buzz_score"]

    def test_sector_fields_round_trip(self, store):
        date = "2026-03-25"
        store.upsert_social_trending_sectors(date, "x", _make_sector_rows("x")[:1])

        row = store.get_social_trending_sectors(date, "x")[0]
        assert row["unique_authors"] == 11217
        assert row["top_tickers"] == '["NVDA","MSTR","AAPL"]'
        assert row["period_days"] == 7


class TestMarketSentimentStore:

    def test_upsert_market_sentiment_replaces_on_conflict(self, store):
        store.upsert_market_sentiment(_make_market_sentiment_rows("reddit", buzz_score=47.7))
        store.upsert_market_sentiment(_make_market_sentiment_rows("reddit", buzz_score=51.2))

        rows = store.get_market_sentiment(source="reddit", limit=5)
        assert len(rows) == 1
        assert rows[0]["buzz_score"] == 51.2

    def test_get_market_sentiment_with_source_filter(self, store):
        store.upsert_market_sentiment(_make_market_sentiment_rows("reddit"))
        store.upsert_market_sentiment(_make_market_sentiment_rows("x"))

        reddit_rows = store.get_market_sentiment(source="reddit", limit=5)
        assert len(reddit_rows) == 1
        assert reddit_rows[0]["source"] == "reddit"

    def test_latest_market_sentiment(self, store):
        store.upsert_market_sentiment(_make_market_sentiment_rows("reddit", date="2026-03-24", buzz_score=40.0))
        store.upsert_market_sentiment(_make_market_sentiment_rows("reddit", date="2026-03-25", buzz_score=47.7))

        latest = store.get_latest_market_sentiment(source="reddit")
        assert latest is not None
        assert latest["date"] == "2026-03-25"
        assert latest["active_tickers"] == 2764

    def test_market_sentiment_fields_round_trip(self, store):
        store.upsert_market_sentiment(_make_market_sentiment_rows("x"))

        row = store.get_latest_market_sentiment(source="x")
        assert row is not None
        assert row["unique_posts"] == 44209
        assert row["unique_authors"] == 18688
        assert row["raw_json"] == '{"buzz_score": 47.7}'
        assert row["period_days"] == 7

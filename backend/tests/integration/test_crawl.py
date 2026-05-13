import json
from unittest.mock import MagicMock, patch

import pytest


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _crawl(client, url="https://example.com", max_items=5):
    return client.post("/api/crawl", json={"url": url, "max_items": max_items})


class TestCrawlAuth:
    def test_missing_api_key_returns_401(self, unauth_client):
        response = unauth_client.post("/api/crawl", json={"url": "https://example.com"})
        assert response.status_code == 401


class TestCrawlValidation:
    def test_missing_url_returns_422(self, client):
        response = client.post("/api/crawl", json={})
        assert response.status_code == 422

    def test_max_items_above_50_returns_422(self, client):
        response = _crawl(client, max_items=51)
        assert response.status_code == 422

    def test_max_items_below_1_returns_422(self, client):
        response = _crawl(client, max_items=0)
        assert response.status_code == 422


class TestCrawlNoApiKey:
    def test_missing_firecrawl_key_returns_error_event(self, client):
        with patch("routers.crawl.settings") as mock_settings:
            mock_settings.FIRECRAWL_API_KEY = ""
            response = _crawl(client)
        events = _parse_sse(response.text)
        assert any(e["type"] == "error" for e in events)


class TestCrawlSuccess:
    @pytest.fixture
    def mock_crawl_deps(self, mock_predict):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "success": True,
            "data": {"markdown": "## 게시글\n사기 같은 제품입니다.\n환불 요청합니다.", "html": ""},
        }

        with (
            patch("routers.crawl.http.post", return_value=mock_resp),
            patch("routers.crawl.extract_texts", return_value=(["사기 같은 제품입니다.", "환불 요청합니다."], "trafilatura")),
            patch("routers.crawl.settings") as mock_settings,
        ):
            mock_settings.FIRECRAWL_API_KEY = "fc-test"
            mock_settings.LLM_PROVIDER_EXTRACT = "ollama"
            yield

    def test_returns_200(self, client, mock_crawl_deps):
        response = _crawl(client)
        assert response.status_code == 200

    def test_response_is_event_stream(self, client, mock_crawl_deps):
        response = _crawl(client)
        assert "text/event-stream" in response.headers["content-type"]

    def test_scraped_event_emitted(self, client, mock_crawl_deps):
        response = _crawl(client)
        events = _parse_sse(response.text)
        assert any(e["type"] == "scraped" for e in events)

    def test_extracted_event_emitted(self, client, mock_crawl_deps):
        response = _crawl(client)
        events = _parse_sse(response.text)
        extracted = [e for e in events if e["type"] == "extracted"]
        assert len(extracted) == 1
        assert extracted[0]["count"] == 2

    def test_done_event_emitted(self, client, mock_crawl_deps):
        response = _crawl(client)
        events = _parse_sse(response.text)
        done = [e for e in events if e["type"] == "done"]
        assert len(done) == 1
        assert done[0]["saved"] == 2

    def test_item_events_contain_risk_fields(self, client, mock_crawl_deps):
        response = _crawl(client)
        events = _parse_sse(response.text)
        items = [e for e in events if e["type"] == "item"]
        assert len(items) == 2
        for item in items:
            assert "risk_level" in item
            assert "risk_score" in item
            assert "content_id" in item
            assert "triggered_rules" in item


class TestCrawlScrapingFailure:
    def test_scraping_failure_emits_error_event(self, client):
        with (
            patch("routers.crawl.http.post", side_effect=Exception("연결 실패")),
            patch("routers.crawl.settings") as mock_settings,
        ):
            mock_settings.FIRECRAWL_API_KEY = "fc-test"
            response = _crawl(client)

        events = _parse_sse(response.text)
        assert any(e["type"] == "error" for e in events)

import io
from unittest.mock import patch

import pytest

from services.prediction_service import prediction_service
from tests.conftest import MOCK_FINAL_RESULT, MOCK_PREDICTIONS


def _csv(rows: str) -> bytes:
    return rows.encode("utf-8")


def _upload(client, content: bytes, filename: str):
    return client.post(
        "/api/upload",
        files={"file": (filename, io.BytesIO(content), "text/plain")},
    )


class TestUploadAuth:
    def test_missing_api_key_returns_401(self, unauth_client):
        response = unauth_client.post(
            "/api/upload",
            files={"file": ("test.csv", io.BytesIO(b"content_id,text\nA,hello"), "text/csv")},
        )
        assert response.status_code == 401


class TestUploadFormat:
    def test_unsupported_format_returns_400(self, client):
        response = _upload(client, b"data", "file.pdf")
        assert response.status_code == 400

    def test_missing_columns_returns_400(self, client):
        response = _upload(client, _csv("id,body\nA,hello"), "file.csv")
        assert response.status_code == 400
        assert "content_id" in response.json()["detail"]

    def test_max_rows_exceeded_returns_400(self, client, mock_predict):
        header = "content_id,text\n"
        rows = "".join(f"ID{i},text{i}\n" for i in range(1001))
        response = _upload(client, _csv(header + rows), "file.csv")
        assert response.status_code == 400
        assert "1000" in response.json()["detail"]


class TestUploadCSV:
    def test_valid_csv_returns_200(self, client, mock_predict):
        data = _csv("content_id,text\nU001,첫 번째\nU002,두 번째")
        response = _upload(client, data, "file.csv")
        assert response.status_code == 200

    def test_saved_count_is_correct(self, client, mock_predict):
        data = _csv("content_id,text\nU001,첫 번째\nU002,두 번째")
        result = _upload(client, data, "file.csv").json()
        assert result["saved"] == 2
        assert result["total"] == 2
        assert result["skipped"] == 0

    def test_duplicate_is_skipped(self, client, mock_predict):
        data = _csv("content_id,text\nU001,첫 번째\nU002,두 번째")
        _upload(client, data, "file.csv")
        result = _upload(client, data, "file.csv").json()
        assert result["skipped"] == 2
        assert result["saved"] == 0

    def test_empty_row_reported_as_error(self, client, mock_predict):
        data = _csv("content_id,text\n,\nU001,정상")
        result = _upload(client, data, "file.csv").json()
        assert len(result["errors"]) == 1
        assert result["saved"] == 1


class TestUploadJSON:
    def test_valid_json_upload(self, client, mock_predict):
        data = '[{"content_id": "J001", "text": "JSON 텍스트"}]'.encode("utf-8")
        response = _upload(client, data, "file.json")
        assert response.status_code == 200
        assert response.json()["saved"] == 1

    def test_invalid_json_returns_400(self, client):
        response = _upload(client, b"not json", "file.json")
        assert response.status_code == 400

    def test_non_array_json_returns_400(self, client):
        response = _upload(client, '{"content_id": "J001", "text": "텍스트"}'.encode("utf-8"), "file.json")
        assert response.status_code == 400


class TestUploadTXT:
    def test_valid_txt_upload(self, client, mock_predict):
        data = "첫 번째 줄\n두 번째 줄\n세 번째 줄".encode("utf-8")
        response = _upload(client, data, "file.txt")
        assert response.status_code == 200
        assert response.json()["saved"] == 3

    def test_empty_lines_skipped(self, client, mock_predict):
        data = "줄 하나\n\n\n줄 둘".encode("utf-8")
        result = _upload(client, data, "file.txt").json()
        assert result["saved"] == 2

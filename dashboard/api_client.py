import requests

BASE_URL = "http://localhost:8000"


def get_contents(status: str = None) -> list:
    params = {"status": status} if status else {}
    res = requests.get(f"{BASE_URL}/api/contents", params=params)
    res.raise_for_status()
    return res.json()


def get_content(content_id: str) -> dict:
    res = requests.get(f"{BASE_URL}/api/contents/{content_id}")
    res.raise_for_status()
    return res.json()


def analyze_content(content_id: str, text: str) -> dict:
    res = requests.post(
        f"{BASE_URL}/api/analyze",
        json={"content_id": content_id, "text": text},
    )
    res.raise_for_status()
    return res.json()


def submit_review(content_id: str, action: str, comment: str = "") -> dict:
    res = requests.post(
        f"{BASE_URL}/api/reviews/{content_id}",
        json={"action": action, "comment": comment or None},
    )
    res.raise_for_status()
    return res.json()
